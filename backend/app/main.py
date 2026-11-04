import os
from contextlib import asynccontextmanager
import statistics
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import assessment, db, fabric, handover, ifhas, labs, obs_ar, questionnaire, security, semen, wearables
from .knowledge import graph

ROOT = Path(__file__).resolve().parents[2]
CONSENT_VERSION = "1.0"
PURPOSES = {"core": True, "clinician_review": False, "wearables": False, "research": False}
SHARE_HOURS = 72
MAX_UPLOAD = 300 * 1024 * 1024

def startup():
    db.init()
    problems = graph().validate()
    if problems:
        raise RuntimeError("Knowledge graph invalid: " + "; ".join(problems[:5]))
    # Never create a publicly guessable clinician account in a deployed environment.
    # Demo credentials are available only when explicitly enabled for local demonstrations.
    demo_mode = os.environ.get("RIAYA_ENABLE_DEMO_CLINICIAN", "").lower() == "true"
    user = os.environ.get("RIAYA_CLINICIAN_USER") or ("clinician" if demo_mode else None)
    pw = os.environ.get("RIAYA_CLINICIAN_PASSWORD") or ("demo-clinician" if demo_mode else None)
    if user and pw:
        problem = None if demo_mode and not os.environ.get("RIAYA_CLINICIAN_PASSWORD") else security.password_problem(pw, user)
        if problem:
            # refuse to provision a weak account rather than run with it
            print(f"[riaya] clinician account NOT created: {problem}", flush=True)
            return
        with db.tx() as c:
            if not c.execute("SELECT 1 FROM clinicians WHERE username=?", (user,)).fetchone():
                salt, h = security.hash_password(pw)
                c.execute("INSERT INTO clinicians VALUES (?,?,?,?)", (user, salt, h, "Duty clinician"))


@asynccontextmanager
async def lifespan(_app):
    startup()
    yield


app = FastAPI(title="Riaya API", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)


FIELD_NAMES = {"new": "New password", "current": "Current password", "username": "Username", "password": "Password", "body": "Message",
               "text": "Text", "session": "Session", "status": "Status", "decision": "Decision", "trust": "Trust rating", "clarity": "Clarity rating",
               "comfort": "Comfort rating", "improve": "Changes"}


def _readable(err):
    loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query")]
    field = FIELD_NAMES.get(loc[-1], loc[-1].replace("_", " ").capitalize()) if loc else "Input"
    t, ctx = err.get("type", ""), err.get("ctx", {}) or {}
    if t == "string_too_short":
        return f"{field} must be at least {ctx.get('min_length')} characters."
    if t == "string_too_long":
        return f"{field} must be at most {ctx.get('max_length')} characters."
    if t in ("greater_than_equal", "greater_than"):
        return f"{field} must be at least {ctx.get('ge', ctx.get('gt'))}."
    if t in ("less_than_equal", "less_than"):
        return f"{field} must be at most {ctx.get('le', ctx.get('lt'))}."
    if t == "missing":
        return f"{field} is required."
    if t == "string_pattern_mismatch":
        return f"{field} has a value that is not allowed."
    if t in ("float_parsing", "int_parsing", "float_type", "int_type"):
        return f"{field} must be a number."
    return f"{field}: {err.get('msg', 'invalid value')}."


from fastapi.exceptions import RequestValidationError  # noqa: E402


@app.exception_handler(RequestValidationError)
async def validation_errors(request, exc):
    """Plain-language errors instead of raw validation output."""
    msgs = list(dict.fromkeys(_readable(e) for e in exc.errors()))
    return JSONResponse({"detail": " ".join(msgs), "errors": msgs}, status_code=422)


@app.middleware("http")
async def headers(request, call_next):
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


# ------------------------------------------------------------------ auth helpers
def current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    with db.tx() as c:
        row = c.execute("SELECT id FROM users WHERE token_hash=?", (security.token_hash(authorization[7:]),)).fetchone()
    if not row:
        raise HTTPException(401, "Unknown token")
    return row["id"]


def current_clinician(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    now = time.time()
    with db.tx() as c:
        row = c.execute("SELECT username, last_seen FROM sessions WHERE token_hash=? AND expires_at>?",
                        (security.token_hash(authorization[7:]), now)).fetchone()
        if row and row["last_seen"] and now - row["last_seen"] > IDLE_TIMEOUT:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (security.token_hash(authorization[7:]),))
            row = None
        elif row:
            c.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (now, security.token_hash(authorization[7:])))
    if not row:
        raise HTTPException(401, "Session expired")
    return row["username"]


def consents(user_id):
    with db.tx() as c:
        rows = c.execute("SELECT purpose, granted FROM consents WHERE user_id=? ORDER BY ts", (user_id,)).fetchall()
    state = {p: False for p in PURPOSES}
    for r in rows:
        state[r["purpose"]] = bool(r["granted"])
    return state


def own_assessment(aid, user_id):
    with db.tx() as c:
        row = c.execute("SELECT * FROM assessments WHERE id=? AND user_id=?", (aid, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "Not found")
    return row


# ------------------------------------------------------------------ public reference data
@app.get("/api/graph")
def get_graph():
    return graph().data


@app.get("/api/questionnaire")
def get_questionnaire():
    return questionnaire.schema(graph())


@app.get("/api/model-card")
def model_card():
    from . import ml, synth
    meta = synth.load()["meta"]
    return {"evidence_engine": {"nodes": len(graph().nodes), "edges": len(graph().edges),
                                "references": len(graph().refs)},
            "simulated_gbm": meta, "uci_logistic": {"model": "Logistic regression", "data": "UCI Fertility (n=100)",
                                                    "coefficients": dict(zip(ml.model()["features"], ml.model()["coef"]))}}


class FabricIn(BaseModel):
    text: str = Field(max_length=500)
    garment: str = "underwear"
    fit: str = "regular"


@app.post("/api/fabric")
def fabric_check(body: FabricIn):
    return fabric.assess(body.text, body.garment, body.fit)


# ------------------------------------------------------------------ anonymous session + consent
class SessionIn(BaseModel):
    lang: str = "ar"


@app.post("/api/session")
def new_session(body: SessionIn):
    """No name, phone, email or Emirates ID. The token lives only on the man's device."""
    token, uid = security.new_token(), str(uuid.uuid4())
    with db.tx() as c:
        c.execute("INSERT INTO users (id, token_hash, created_at, lang) VALUES (?,?,?,?)", (uid, security.token_hash(token), time.time(), body.lang))
    return {"token": token}


class ConsentIn(BaseModel):
    core: bool
    clinician_review: bool = False
    wearables: bool = False
    research: bool = False


@app.post("/api/consent")
def set_consent(body: ConsentIn, user=Depends(current_user)):
    if not body.core:
        raise HTTPException(400, "Core consent is needed to produce a summary. To stop completely, delete your data instead.")
    before = consents(user)
    with db.tx() as c:
        for p, v in body.model_dump().items():
            c.execute("INSERT INTO consents VALUES (?,?,?,?,?)", (user, p, int(v), CONSENT_VERSION, time.time()))
        if before["clinician_review"] and not body.clinician_review:
            # withdrawal: doctors lose access to every check, and pending reviews leave the queue
            c.execute("UPDATE assessments SET review_consent=0 WHERE user_id=?", (user,))
            c.execute("""UPDATE referrals SET status='suggested' WHERE status='pending_review'
                         AND assessment_id IN (SELECT id FROM assessments WHERE user_id=?)""", (user,))
            c.execute("UPDATE shares SET revoked=1 WHERE assessment_id IN (SELECT id FROM assessments WHERE user_id=?)", (user,))
    if before["clinician_review"] and not body.clinician_review:
        db.audit("user", "withdrew_clinician_review")
    return consents(user)


@app.get("/api/consent")
def get_consent(user=Depends(current_user)):
    return consents(user)


# ------------------------------------------------------------------ assessment
CHANNELS = ("web", "chat", "watch", "whatsapp")


@app.post("/api/assessments")
def start(channel: str = "web", user=Depends(current_user)):
    if not consents(user)["core"]:
        raise HTTPException(403, "Consent required")
    aid = str(uuid.uuid4())
    with db.tx() as c:
        c.execute("INSERT INTO assessments (id, user_id, started_at, channel) VALUES (?,?,?,?)",
                  (aid, user, time.time(), channel if channel in CHANNELS else "web"))
    db.event(aid, "started")
    return {"id": aid}


class AnswersIn(BaseModel):
    answers: dict


@app.put("/api/assessments/{aid}/answers")
def save_answers(aid: str, body: AnswersIn, user=Depends(current_user)):
    own_assessment(aid, user)
    allowed = {q["id"] for q in questionnaire.QUESTIONS}
    clean = {k: v for k, v in body.answers.items() if k in allowed}  # data minimisation: drop anything unexpected
    with db.tx() as c:
        c.execute("UPDATE assessments SET answers=? WHERE id=?", (security.seal(clean), aid))
    db.event(aid, "answers_saved", str(len(clean)))
    return {"saved": len(clean)}


@app.post("/api/assessments/{aid}/wearables")
async def upload_wearables(aid: str, file: UploadFile = File(...), user=Depends(current_user)):
    row = own_assessment(aid, user)
    if not consents(user)["wearables"]:
        raise HTTPException(403, "Device-data consent not given")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "File too large")
    try:
        summary = wearables.detect_and_parse(file.filename or "", raw)
    except (ValueError, StopIteration, KeyError) as e:
        raise HTTPException(422, str(e) or "Could not read file")
    finally:
        del raw  # raw export is never stored
    merged = wearables.merge(security.unseal(row["wearable"]), summary)
    with db.tx() as c:
        c.execute("UPDATE assessments SET wearable=? WHERE id=?", (security.seal(merged), aid))
    db.event(aid, "wearable_import", summary.get("source"))
    return merged


class ManualDevice(BaseModel):
    sleep_avg_h: Optional[float] = Field(None, ge=0, le=16)
    steps_avg: Optional[float] = Field(None, ge=0, le=60000)
    screen_daily_h: Optional[float] = Field(None, ge=0, le=24)
    spo2_low_nights: Optional[int] = Field(None, ge=0, le=31)
    social_jetlag_h: Optional[float] = Field(None, ge=0, le=12)


@app.post("/api/assessments/{aid}/device-manual")
def manual_device(aid: str, body: ManualDevice, user=Depends(current_user)):
    row = own_assessment(aid, user)
    merged = wearables.merge(security.unseal(row["wearable"]), {**body.model_dump(exclude_none=True), "source": "manual"})
    with db.tx() as c:
        c.execute("UPDATE assessments SET wearable=? WHERE id=?", (security.seal(merged), aid))
    return merged


class SemenIn(BaseModel):
    source: str = Field(pattern="^(lab|home_quant|home_simple)$")
    kit: Optional[str] = None
    result: Optional[str] = None
    volume_ml: Optional[float] = Field(None, ge=0, le=20)
    concentration_m_per_ml: Optional[float] = Field(None, ge=0, le=500)
    total_count_m: Optional[float] = Field(None, ge=0, le=3000)
    total_motility_pct: Optional[float] = Field(None, ge=0, le=100)
    progressive_motility_pct: Optional[float] = Field(None, ge=0, le=100)
    normal_forms_pct: Optional[float] = Field(None, ge=0, le=100)
    vitality_pct: Optional[float] = Field(None, ge=0, le=100)
    ph: Optional[float] = Field(None, ge=5, le=10)
    abstinence_days: Optional[float] = Field(None, ge=0, le=60)
    motile_conc_m_per_ml: Optional[float] = Field(None, ge=0, le=500)
    prog_motile_conc_m_per_ml: Optional[float] = Field(None, ge=0, le=500)


@app.post("/api/assessments/{aid}/semen")
def add_semen(aid: str, body: SemenIn, user=Depends(current_user)):
    own_assessment(aid, user)
    d = body.model_dump(exclude_none=True)
    if body.source == "lab":
        out = semen.interpret_lab(d)
    elif body.source == "home_quant":
        out = semen.interpret_home_quantitative(d, body.kit or "yo")
    else:
        out = semen.interpret_home(body.kit or "other", body.result)
    with db.tx() as c:
        c.execute("UPDATE assessments SET semen=? WHERE id=?", (security.seal(out), aid))
    db.event(aid, "semen_added", body.source)
    return {"findings": out["findings"], "notes": out["notes"], "normal": out["normal"]}


def _cohort(answers):
    age = answers.get("age")
    try:
        band = f"{int(float(age)) // 10 * 10}s"
    except (TypeError, ValueError):
        band = "unknown"
    return f"{band}|{answers.get('background') or 'unknown'}"


@app.post("/api/assessments/{aid}/submit")
def submit(aid: str, lang: str = "en", user=Depends(current_user)):
    row = own_assessment(aid, user)
    answers = security.unseal(row["answers"]) or {}
    if not answers.get("age"):
        raise HTTPException(400, "Please answer at least the 'About you' section")
    result = assessment.run(answers, security.unseal(row["wearable"]), security.unseal(row["semen"]), labs=security.unseal(row["labs"]))
    t = result["triage"]
    review_ok = consents(user)["clinician_review"]
    now = time.time()
    with db.tx() as c:
        c.execute("""UPDATE assessments SET result=?, completed_at=?, tier=?, level=?, requires_review=?, review_consent=?, cohort=?
                     WHERE id=?""", (security.seal(result), now, t["tier"], t["level"], int(t["requires_review"]),
                                     int(review_ok), _cohort(answers), aid))
        c.execute("DELETE FROM referrals WHERE assessment_id=? AND status='pending_review'", (aid,))
        if t["level"] != "self_care":
            status = "pending_review" if t["requires_review"] and review_ok else "suggested"
            due = now + t["sla_hours"] * 3600 if t.get("rapid_review") and t.get("sla_hours") else None
            c.execute("INSERT INTO referrals (id, assessment_id, level, status, created_at, rapid, due_at) VALUES (?,?,?,?,?,?,?)",
                      (str(uuid.uuid4()), aid, t["level"], status, now, int(bool(t.get("rapid_review"))), due))
    db.event(aid, "completed", t["level"])
    view = assessment.user_view(result, lang if lang in ("en", "ar") else "en")
    view["clinician_review"] = "queued" if t["requires_review"] and review_ok else ("available" if t["requires_review"] else "not_needed")
    return view


@app.get("/api/assessments/{aid}/result")
def get_result(aid: str, lang: str = "en", user=Depends(current_user)):
    row = own_assessment(aid, user)
    result = security.unseal(row["result"])
    if not result:
        raise HTTPException(404, "Not completed")
    view = assessment.user_view(result, lang)
    with db.tx() as c:
        ref = c.execute("SELECT status, final_level, reviewed_at, rapid, due_at, video_url FROM referrals WHERE assessment_id=?", (aid,)).fetchone()
    view["referral"] = dict(ref) if ref else None
    view["review_consent"] = bool(row["review_consent"])
    t = result["triage"]
    view["clinician_review"] = ("queued" if row["review_consent"] else "available") if t["requires_review"] else "not_needed"
    return view


@app.get("/api/assessments/{aid}/ifhas")
def ifhas_export(aid: str, user=Depends(current_user)):
    row = own_assessment(aid, user)
    result = security.unseal(row["result"])
    if not result:
        raise HTTPException(404, "Not completed")
    db.event(aid, "ifhas_export")
    return JSONResponse(ifhas.bundle(security.unseal(row["answers"]), result),
                        headers={"Content-Disposition": "attachment; filename=prescreen-summary.fhir.json"})


@app.post("/api/assessments/{aid}/share")
def create_share(aid: str, user=Depends(current_user)):
    own_assessment(aid, user)
    code = security.share_code()
    now = time.time()
    with db.tx() as c:
        c.execute("INSERT INTO shares VALUES (?,?,?,?,0,NULL)", (code, aid, now, now + SHARE_HOURS * 3600))
    db.event(aid, "share_created")
    return {"code": code, "expires_in_hours": SHARE_HOURS}


@app.delete("/api/shares/{code}")
def revoke_share(code: str, user=Depends(current_user)):
    with db.tx() as c:
        n = c.execute("""UPDATE shares SET revoked=1 WHERE code=? AND assessment_id IN
                         (SELECT id FROM assessments WHERE user_id=?)""", (code, user)).rowcount
    if not n:
        raise HTTPException(404, "Not found")
    return {"revoked": True}


class FeedbackIn(BaseModel):
    trust: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    comfort: int = Field(ge=1, le=5)


@app.post("/api/assessments/{aid}/feedback")
def feedback(aid: str, body: FeedbackIn, user=Depends(current_user)):
    own_assessment(aid, user)
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO feedback VALUES (?,?,?,?,?)", (aid, body.trust, body.clarity, body.comfort, time.time()))
    return {"ok": True}


@app.post("/api/me/recovery")
def make_recovery(user=Depends(current_user)):
    """A code he can write down to restore his checks on a new phone. Shown once; only a hash is stored. A new code replaces the old one."""
    code = security.recovery_code()
    with db.tx() as c:
        c.execute("UPDATE users SET recovery_hash=? WHERE id=?", (security.token_hash(security.normalise_code(code)), user))
    db.audit("user", "recovery_code_created")
    return {"code": code}


class RecoverIn(BaseModel):
    code: str = Field(min_length=10, max_length=40)


@app.post("/api/recover")
def recover(body: RecoverIn, request: Request):
    """Restores access on a new device. The old device's link stops working, in case the phone was lost."""
    now, ip = time.time(), (request.client.host if request.client else "?")
    norm = security.normalise_code(body.code)
    outcome, token = None, None
    with db.tx() as c:
        fails = c.execute("SELECT COUNT(*) FROM login_attempts WHERE username='recovery' AND ip=? AND ts>?", (ip, now - LOCK_WINDOW)).fetchone()[0]
        if fails >= MAX_FAILS:
            outcome = "locked"
        else:
            row = c.execute("SELECT id FROM users WHERE recovery_hash=?", (security.token_hash(norm),)).fetchone() if len(norm) == 20 else None
            if row:
                token = security.new_token()
                c.execute("UPDATE users SET token_hash=?, recovery_hash=NULL WHERE id=?", (security.token_hash(token), row["id"]))
                outcome = "ok"
            else:
                c.execute("INSERT INTO login_attempts VALUES (?,?,?)", ("recovery", ip, now))
                outcome = "bad"
    if outcome == "locked":
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    if outcome == "bad":
        raise HTTPException(404, "That code was not recognised. Check it and try again.")
    db.audit("user", "recovered_on_new_device")
    with db.tx() as c:
        last = c.execute("SELECT id FROM assessments WHERE user_id=(SELECT id FROM users WHERE token_hash=?) ORDER BY started_at DESC LIMIT 1",
                         (security.token_hash(token),)).fetchone()
    return {"token": token, "aid": last["id"] if last else None, "note": "Your code has been used. Create a new one in Privacy & sharing."}


@app.get("/api/me/export")
def export_me(user=Depends(current_user)):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM assessments WHERE user_id=?", (user,)).fetchall()
        shares = c.execute("SELECT code, created_at, expires_at, revoked, used_by FROM shares WHERE assessment_id IN "
                           "(SELECT id FROM assessments WHERE user_id=?)", (user,)).fetchall()
    return {"consents": consents(user), "shares": [dict(s) for s in shares],
            "assessments": [{"id": r["id"], "started_at": r["started_at"], "completed_at": r["completed_at"],
                             "answers": security.unseal(r["answers"]), "device_summary": security.unseal(r["wearable"]),
                             "test_result": security.unseal(r["semen"]), "blood_tests": security.unseal(r["labs"]),
                             "result": security.unseal(r["result"]), "messages": _msgs_for(r["id"])} for r in rows]}


def _msgs_for(aid):
    with db.tx() as c:
        return _messages(c, aid)


@app.delete("/api/me")
def delete_me(user=Depends(current_user)):
    """Erases everything about this person. Aggregate counters in `events` lose the link (assessment id removed)."""
    with db.tx() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM assessments WHERE user_id=?", (user,)).fetchall()]
        for aid in ids:
            c.execute("DELETE FROM referrals WHERE assessment_id=?", (aid,))
            c.execute("DELETE FROM shares WHERE assessment_id=?", (aid,))
            c.execute("DELETE FROM feedback WHERE assessment_id=?", (aid,))
            c.execute("DELETE FROM messages WHERE assessment_id=?", (aid,))
            c.execute("DELETE FROM partner_links WHERE assessment_id=?", (aid,))
            c.execute("UPDATE events SET assessment_id=NULL WHERE assessment_id=?", (aid,))
        c.execute("DELETE FROM assessments WHERE user_id=?", (user,))
        c.execute("DELETE FROM consents WHERE user_id=?", (user,))
        c.execute("DELETE FROM users WHERE id=?", (user,))
    db.audit("user", "erased_all_data")
    return {"deleted": True, "assessments": len(ids)}


# ------------------------------------------------------------------ clinician side
class LoginIn(BaseModel):
    username: str
    password: str


SESSION_HOURS = 8
IDLE_TIMEOUT = 30 * 60           # sign out after 30 minutes without activity
MAX_FAILS, LOCK_WINDOW = 5, 15 * 60
_DUMMY = security.hash_password("timing-equaliser")


@app.post("/api/clinician/login")
def login(body: LoginIn, request: Request):
    now = time.time()
    ip = request.client.host if request.client else "?"
    user = body.username.strip()[:80]
    outcome, row, token = None, None, None
    with db.tx() as c:
        c.execute("DELETE FROM sessions WHERE expires_at<?", (now,))
        c.execute("DELETE FROM login_attempts WHERE ts<?", (now - LOCK_WINDOW,))
        fails = c.execute("SELECT COUNT(*) FROM login_attempts WHERE (username=? OR ip=?) AND ts>?", (user, ip, now - LOCK_WINDOW)).fetchone()[0]
        if fails >= MAX_FAILS:
            outcome = "locked"
        else:
            row = c.execute("SELECT * FROM clinicians WHERE username=?", (user,)).fetchone()
            # same work whether or not the user exists, so usernames cannot be discovered by timing
            salt, expected = (row["salt"], row["pw_hash"]) if row else _DUMMY
            if security.check_password(body.password, salt, expected) and row is not None:
                c.execute("DELETE FROM login_attempts WHERE username=?", (user,))
                token = security.new_token()
                c.execute("INSERT INTO sessions (token_hash, username, expires_at, last_seen) VALUES (?,?,?,?)",
                          (security.token_hash(token), user, now + SESSION_HOURS * 3600, now))
                outcome = "ok"
            else:
                c.execute("INSERT INTO login_attempts VALUES (?,?,?)", (user, ip, now))
                outcome = "failed"
    # the transaction is committed before any error is raised, so failed attempts always count
    if outcome == "locked":
        db.audit(user, "login_locked")
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    if outcome == "failed":
        db.audit(user, "login_failed")
        raise HTTPException(401, "Invalid username or password")
    db.audit(user, "login")
    return {"token": token, "name": row["display_name"], "expires_in": SESSION_HOURS * 3600, "idle_timeout": IDLE_TIMEOUT}


@app.post("/api/clinician/logout")
def logout(authorization: str = Header(None), clin=Depends(current_clinician)):
    with db.tx() as c:
        c.execute("DELETE FROM sessions WHERE token_hash=?", (security.token_hash(authorization[7:]),))
    db.audit(clin, "logout")
    return {"ok": True}


class PasswordIn(BaseModel):
    current: str
    new: str = Field(min_length=12, max_length=200)


@app.post("/api/clinician/password")
def change_password(body: PasswordIn, authorization: str = Header(None), clin=Depends(current_clinician)):
    problem = security.password_problem(body.new, clin)
    with db.tx() as c:
        row = c.execute("SELECT * FROM clinicians WHERE username=?", (clin,)).fetchone()
        wrong = not security.check_password(body.current, row["salt"], row["pw_hash"])
        if not wrong and not problem:
            salt, h = security.hash_password(body.new)
            c.execute("UPDATE clinicians SET salt=?, pw_hash=? WHERE username=?", (salt, h, clin))
            # every other session for this clinician ends
            c.execute("DELETE FROM sessions WHERE username=? AND token_hash!=?", (clin, security.token_hash(authorization[7:])))
    if wrong:
        db.audit(clin, "password_change_failed")
        raise HTTPException(403, "Current password is wrong")
    if problem:
        raise HTTPException(400, problem)
    db.audit(clin, "password_changed")
    return {"ok": True}


def _case_summary(row, ref):
    return {"id": row["id"], "completed_at": row["completed_at"], "tier": row["tier"], "level": row["level"],
            "cohort": row["cohort"], "simulated": bool(row["simulated"]),
            "referral": dict(ref) if ref else None}


@app.get("/api/clinician/queue")
def queue(clin=Depends(current_clinician)):
    """Only cases where the man consented to clinician review (or shared a code) are visible."""
    with db.tx() as c:
        rows = c.execute("""SELECT a.*, r.id rid, r.status, r.level rlevel, r.created_at rcreated, r.final_level
                            FROM assessments a JOIN referrals r ON r.assessment_id=a.id
                            WHERE a.review_consent=1 AND r.status='pending_review'
                            ORDER BY r.rapid DESC, COALESCE(r.due_at, 9e18), CASE a.level WHEN 'emergency' THEN 0 WHEN 'urgent_specialist' THEN 1
                                     WHEN 'same_day_primary' THEN 2 WHEN 'andrology' THEN 3 ELSE 4 END, a.completed_at""").fetchall()
        recent = c.execute("""SELECT a.*, r.status, r.final_level, r.reviewed_at, r.reviewer FROM assessments a
                              JOIN referrals r ON r.assessment_id=a.id WHERE a.review_consent=1 AND r.status!='pending_review'
                              ORDER BY r.reviewed_at DESC LIMIT 30""").fetchall()
    db.audit(clin, "view_queue")
    with db.tx() as c:
        extra = {r["assessment_id"]: dict(r) for r in c.execute("SELECT assessment_id, rapid, due_at FROM referrals").fetchall()}
        unread = {r[0]: r[1] for r in c.execute("SELECT assessment_id, COUNT(*) FROM messages WHERE sender='user' AND read_at IS NULL GROUP BY assessment_id")}
    pick = lambda r: {"rapid": bool(extra.get(r["id"], {}).get("rapid")), "due_at": extra.get(r["id"], {}).get("due_at"),
                      "unread": unread.get(r["id"], 0), "id": r["id"], "tier": r["tier"], "level": r["level"], "cohort": r["cohort"],
                      "completed_at": r["completed_at"], "simulated": bool(r["simulated"]),
                      "status": r["status"], "final_level": r["final_level"]}
    return {"pending": [pick(r) for r in rows], "recent": [pick(r) for r in recent]}


def _clinician_can_see(c, aid):
    row = c.execute("SELECT * FROM assessments WHERE id=?", (aid,)).fetchone()
    if not row:
        return None
    if row["review_consent"]:
        return row
    shared = c.execute("SELECT 1 FROM shares WHERE assessment_id=? AND revoked=0 AND expires_at>? AND used_by IS NOT NULL",
                       (aid, time.time())).fetchone()
    return row if shared else None


@app.get("/api/clinician/cases/{aid}")
def case(aid: str, clin=Depends(current_clinician)):
    with db.tx() as c:
        row = _clinician_can_see(c, aid)
        if not row:
            raise HTTPException(404, "Not found or not shared")
        ref = c.execute("SELECT * FROM referrals WHERE assessment_id=?", (aid,)).fetchone()
    with db.tx() as c:
        msgs = _messages(c, aid)
    db.audit(clin, "view_case", aid)
    result = security.unseal(row["result"])
    answers = security.unseal(row["answers"]) or {}
    if result and "models" not in result:
        from . import ml, synth
        result["models"] = {"uci_logistic": ml.predict(answers),
                            "simulated_gbm": synth.explain(answers, result["instruments"], result.get("wearable"))}
    g = graph()
    return {"id": aid, "answers": security.unseal(row["answers"]), "result": result,
            "referral": {k: ref[k] for k in ref.keys() if k not in ("note", "override_reason")} if ref else None,
            "review_note": security.unseal(ref["note"]) if ref and ref["note"] else None,
            "paths": {n: g.paths(n)[:3] for n in list((result or {}).get("attribution", {}))[:5]},
            "references": {r: g.refs[r] for r in {r for e in g.edges for r in e["refs"]}},
            "simulated": bool(row["simulated"]), "messages": msgs}


@app.post("/api/clinician/share/{code}")
def open_share(code: str, clin=Depends(current_clinician)):
    with db.tx() as c:
        s = c.execute("SELECT * FROM shares WHERE code=? AND revoked=0 AND expires_at>?", (code.upper(), time.time())).fetchone()
        if not s:
            raise HTTPException(404, "Code invalid, expired or revoked")
        c.execute("UPDATE shares SET used_by=? WHERE code=?", (clin, code.upper()))
    db.audit(clin, "open_share", s["assessment_id"])
    return {"assessment_id": s["assessment_id"]}


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(approve|modify|reject)$")
    final_level: Optional[str] = None
    note: Optional[str] = Field(None, max_length=2000)


@app.post("/api/clinician/cases/{aid}/review")
def review(aid: str, body: ReviewIn, clin=Depends(current_clinician)):
    from .triage import LEVELS
    with db.tx() as c:
        ref = c.execute("SELECT * FROM referrals WHERE assessment_id=?", (aid,)).fetchone()
        if not ref:
            raise HTTPException(404, "No referral")
        final = ref["level"] if body.decision == "approve" else "self_care" if body.decision == "reject" else body.final_level
        if final not in LEVELS:
            raise HTTPException(400, "Invalid level")
        if body.decision != "approve" and not (body.note or "").strip():
            raise HTTPException(400, "A reason is required when you change or reject the suggested pathway")
        c.execute("UPDATE referrals SET status=?, reviewed_at=?, reviewer=?, final_level=?, note=?, override_reason=? WHERE id=?",
                  ("rejected" if body.decision == "reject" else "approved", time.time(), clin, final, security.seal(body.note),
                   security.seal(body.note).decode() if body.decision != "approve" else None, ref["id"]))
    db.audit(clin, f"review_{body.decision}", aid)
    db.event(aid, "reviewed", final)
    return {"status": "approved", "final_level": final}


BARRIERS = ("cost", "time", "embarrassment", "distance", "waiting_list", "partner", "not_needed", "other")


class StatusIn(BaseModel):
    status: str = Field(pattern="^(booked|attended|tests_done|followed_up|declined)$")
    barrier: Optional[str] = None


@app.post("/api/clinician/cases/{aid}/status")
def referral_status(aid: str, body: StatusIn, clin=Depends(current_clinician)):
    col = {"booked": "booked_at", "attended": "attended_at", "tests_done": "tests_done_at", "followed_up": "followup_at"}.get(body.status)
    with db.tx() as c:
        sets = "status=?" + (f", {col}=?" if col else "") + (", barrier=?" if body.status == "declined" else "")
        args = [body.status] + ([time.time()] if col else []) + ([body.barrier if body.barrier in BARRIERS else "other"] if body.status == "declined" else []) + [aid]
        if not c.execute(f"UPDATE referrals SET {sets} WHERE assessment_id=?", args).rowcount:
            raise HTTPException(404, "No referral")
    db.audit(clin, f"referral_{body.status}", aid)
    db.event(aid, f"referral_{body.status}")
    return {"ok": True}


@app.get("/api/clinician/metrics")
def metrics(include_simulated: bool = False, clin=Depends(current_clinician)):
    sim = "" if include_simulated else " AND simulated=0"
    with db.tx() as c:
        a = c.execute(f"SELECT * FROM assessments WHERE 1=1{sim}").fetchall()
        r = c.execute(f"SELECT * FROM referrals WHERE 1=1{sim}").fetchall()
        fb = c.execute("SELECT AVG(trust) t, AVG(clarity) cl, AVG(comfort) co, COUNT(*) n FROM feedback").fetchone()
    done = [x for x in a if x["completed_at"]]
    minutes = [(x["completed_at"] - x["started_at"]) / 60 for x in done]
    review_h = [(x["reviewed_at"] - x["created_at"]) / 3600 for x in r if x["reviewed_at"]]
    to_eval_d = [(x["attended_at"] - x["created_at"]) / 86400 for x in r if x["attended_at"]]
    approved = [x for x in r if x["status"] in ("approved", "booked", "attended", "declined")]
    by = lambda key: _group([x for x in done], key)
    return {
        "started": len(a), "completed": len(done), "completion_rate": round(len(done) / len(a), 3) if a else None,
        "median_minutes_to_complete": _median(minutes),
        "referrals": len(r), "pending_review": sum(x["status"] == "pending_review" for x in r),
        "median_hours_to_review": _median(review_h),
        "median_days_to_evaluation": _median(to_eval_d),
        "referral_completion_rate": round(sum(x["status"] == "attended" for x in approved) / len(approved), 3) if approved else None,
        "clinician_changed_level": sum(1 for x in r if x["final_level"] and x["final_level"] != x["level"]),
        "levels": _count(x["level"] for x in done),
        "by_age": by(lambda x: (x["cohort"] or "unknown|").split("|")[0]),
        "by_background": by(lambda x: (x["cohort"] or "|unknown").split("|")[1]),
        "user_feedback": dict(fb) if fb and fb["n"] else None,
    }


def _median(v):
    return round(statistics.median(v), 2) if v else None


def _count(it):
    out = {}
    for k in it:
        out[k] = out.get(k, 0) + 1
    return out


def _group(rows, key):
    groups = {}
    for x in rows:
        groups.setdefault(key(x), []).append(x)
    return {k: {"n": len(v), "tiers": _count(y["tier"] for y in v),
                "referred_pct": round(100 * sum(y["level"] != "self_care" for y in v) / len(v), 1)} for k, v in sorted(groups.items())}


@app.get("/api/insights")
def programme_insights(include_simulated: bool = False, clin=Depends(current_clinician)):
    """Aggregated, k-anonymised programme dashboard for the health authority."""
    from . import insights
    db.audit(clin, "view_insights")
    return insights.build(include_simulated)


@app.get("/api/clinician/audit")
def audit_log(clin=Depends(current_clinician)):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM audit ORDER BY ts DESC LIMIT 200").fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ passive first look (device data only, no questions)
PASSIVE_TEXT = {
    "sleep_loss": ("Your sleep averages under 6 hours. Short sleep is linked to lower testosterone and sperm count.",
                   "متوسط نومك أقل من ٦ ساعات. قلة النوم مرتبطة بانخفاض التستوستيرون وعدد الحيوانات المنوية."),
    "circadian": ("Your weekend sleep shifts by 2+ hours. This 'social jet lag' is linked to poorer semen quality.",
                  "يتغير نومك في عطلة الأسبوع بساعتين أو أكثر. هذا «الإرهاق الاجتماعي» مرتبط بجودة أقل للسائل المنوي."),
    "osa": ("Your oxygen dipped below 90% on several nights. That can be a sign of sleep apnoea, which is common, treatable and affects hormones.",
            "انخفض الأكسجين لديك عن ٩٠٪ في عدة ليالٍ. قد يكون ذلك علامة على انقطاع النفس أثناء النوم، وهو شائع وقابل للعلاج ويؤثر في الهرمونات."),
    "sedentary": ("You average fewer than 5,000 steps a day.", "متوسط خطواتك أقل من ٥٠٠٠ خطوة يومياً."),
    "caffeine_late": ("Caffeine is logged late in the day on most days.", "تُسجَّل الكافيين في وقت متأخر من اليوم معظم الأيام."),
    "glycaemic_spikes": ("Your glucose often rises above 140 mg/dL at night.", "يرتفع السكر لديك كثيراً فوق ١٤٠ ملغ/دسل ليلاً."),
    "screen_time_high": ("Your daily screen time is high.", "وقت الشاشة اليومي لديك مرتفع."),
}


@app.post("/api/assessments/{aid}/passive")
def passive(aid: str, lang: str = "en", user=Depends(current_user)):
    """What the devices alone suggest, before any question is asked."""
    from . import features
    row = own_assessment(aid, user)
    w = security.unseal(row["wearable"])
    if not w:
        raise HTTPException(400, "Add device data first")
    inputs, why, _ = features.build_inputs({}, w)
    device = {n: v for n, v in inputs.items() if any(p["source"] in ("watch", "cgm", "phone") for p in why.get(n, []))}
    g = graph()
    attr = g.shapley(device)
    i = 1 if lang == "ar" else 0
    findings = []
    for node in attr:
        path = g.paths(node)
        findings.append({"node": node, "text": PASSIVE_TEXT.get(node, (g.nodes[node]["label"],) * 2)[i],
                         "label": g.nodes[node].get("label_ar" if i else "label"),
                         "evidence": path[0]["grade"] if path else None,
                         "sources": [obs_ar.translate(p["reason"]) if i else p["reason"] for p in why[node]]})
    db.event(aid, "passive_preview", str(len(findings)))
    return {"summary": {k: w.get(k) for k in ("sleep_avg_h", "steps_avg", "social_jetlag_h", "spo2_low_nights", "night_glucose_high_pct", "late_caffeine_days_per_week", "resting_hr_avg", "hrv_sdnn_avg") if w.get(k) is not None},
            "findings": findings}


# ------------------------------------------------------------------ closed loop + journey
class ProgressIn(BaseModel):
    status: str = Field(pattern="^(booked|attended|tests_done|declined)$")
    barrier: Optional[str] = None


@app.post("/api/assessments/{aid}/progress")
def report_progress(aid: str, body: ProgressIn, user=Depends(current_user)):
    """The man closes the loop himself when the clinic is not connected yet."""
    own_assessment(aid, user)
    col = {"booked": "booked_at", "attended": "attended_at", "tests_done": "tests_done_at"}.get(body.status)
    with db.tx() as c:
        ref = c.execute("SELECT * FROM referrals WHERE assessment_id=?", (aid,)).fetchone()
        if not ref:
            raise HTTPException(404, "No referral for this check")
        if body.status == "declined":
            c.execute("UPDATE referrals SET status='declined', barrier=?, self_reported=1 WHERE id=?",
                      (body.barrier if body.barrier in BARRIERS else "other", ref["id"]))
        else:
            c.execute(f"UPDATE referrals SET status=?, {col}=COALESCE({col}, ?), self_reported=1 WHERE id=?", (body.status, time.time(), ref["id"]))
    db.event(aid, f"self_{body.status}", body.barrier)
    return {"ok": True}


def _changes(prev, cur, g, lang):
    key = "label_ar" if lang == "ar" else "label"
    a, b = prev.get("inputs", {}), cur.get("inputs", {})
    improved = [g.nodes[n][key] for n in a if g.nodes[n].get("modifiable") and a[n] - b.get(n, 0) >= 0.2]
    new = [g.nodes[n][key] for n in b if b[n] >= 0.3 and a.get(n, 0) < 0.3]
    return {"improved": improved, "new": new,
            "index_before": prev["triage"]["index"], "index_after": cur["triage"]["index"],
            "tier_before": prev["triage"]["tier"], "tier_after": cur["triage"]["tier"]}


@app.get("/api/me/journey")
def journey(lang: str = "en", user=Depends(current_user)):
    from . import recommend
    lang = lang if lang in ("en", "ar") else "en"
    g = graph()
    with db.tx() as c:
        rows = c.execute("SELECT * FROM assessments WHERE user_id=? AND completed_at IS NOT NULL ORDER BY completed_at", (user,)).fetchall()
        refs = {r["assessment_id"]: dict(r) for r in c.execute(
            "SELECT * FROM referrals WHERE assessment_id IN (SELECT id FROM assessments WHERE user_id=?)", (user,)).fetchall()}
    checks, prev = [], None
    for r in rows:
        res = security.unseal(r["result"])
        answers, w, sem, lb = security.unseal(r["answers"]), security.unseal(r["wearable"]), security.unseal(r["semen"]), security.unseal(r["labs"])
        ref = refs.get(r["id"])
        steps = [{"step": "completed", "at": r["completed_at"]}]
        if ref:
            steps += [{"step": k, "at": ref[col]} for k, col in (("referred", "created_at"), ("reviewed", "reviewed_at"), ("booked", "booked_at"),
                      ("attended", "attended_at"), ("tests_done", "tests_done_at"), ("followed_up", "followup_at")) if ref.get(col)]
            if ref["status"] == "declined":
                steps.append({"step": "declined", "at": None, "barrier": ref.get("barrier")})
        have = [{"name": n, "value": v, "date": d} for n, v, d in (lb or {}).get("already_done", [])]
        if sem:
            have.insert(0, {"name": "Semen analysis" if sem.get("source") == "lab" else "Home sperm test", "value": "normal" if sem.get("normal") else "below reference", "date": None})
        view = assessment.user_view(res, lang)
        checks.append({"id": r["id"], "completed_at": r["completed_at"], "tier": r["tier"], "level": r["level"], "next_step": view["next_step"],
                       "summary": view["summary"], "discuss": [c_["label"] for c_ in recommend.cards(res, lang)[:3]],
                       "coverage": recommend.data_coverage(answers, w, sem, lb, lang), "tests_have": have,
                       "referral_status": ref["status"] if ref else None, "steps": steps,
                       "changes": _changes(prev, res, g, lang) if prev else None})
        prev = res
    due = (rows[-1]["completed_at"] + 90 * 86400) if rows else None
    return {"checks": checks[::-1], "recheck_due": due, "barriers": list(BARRIERS)}


# ------------------------------------------------------------------ lab report interpreter
@app.post("/api/assessments/{aid}/lab-report")
async def read_lab_report(aid: str, file: Optional[UploadFile] = File(None), text: Optional[str] = Form(None), user=Depends(current_user)):
    """Extracts values for him to confirm. Nothing is saved and the file is discarded."""
    from . import labreport
    own_assessment(aid, user)
    if file is not None:
        raw = await file.read()
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(413, "File too large")
        if raw[:5] == b"%PDF-":
            try:
                text = labreport.pdf_text(raw)
            except Exception:
                raise HTTPException(422, "Could not read this PDF")
        else:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(415, "Send a PDF or text. Photos are read on the phone first.")
        del raw
    if not text or len(text) > 60000:
        raise HTTPException(400, "No report text")
    out = labreport.extract(text)
    db.event(aid, "lab_report_read", str(len(out["values"])))
    return out


# ------------------------------------------------------------------ explained findings and what-if
def _explain(row, lang):
    from . import recommend
    result = security.unseal(row["result"])
    if not result:
        raise HTTPException(404, "Not completed")
    answers, w, sem, lb = security.unseal(row["answers"]), security.unseal(row["wearable"]), security.unseal(row["semen"]), security.unseal(row["labs"])
    return {"cards": recommend.cards(result, lang), "coverage": recommend.data_coverage(answers, w, sem, lb, lang),
            "contradictions": recommend.contradictions(answers, w, sem, lb, lang),
            "baseline": (w or {}).get("personal_baseline")}


@app.get("/api/assessments/{aid}/explain")
def explain(aid: str, lang: str = "en", user=Depends(current_user)):
    return _explain(own_assessment(aid, user), lang if lang in ("en", "ar") else "en")


class WhatIfIn(BaseModel):
    improve: list[str] = Field(default_factory=list, max_length=20)


@app.post("/api/assessments/{aid}/whatif")
def whatif(aid: str, body: WhatIfIn, lang: str = "en", user=Depends(current_user)):
    from . import recommend
    row = own_assessment(aid, user)
    return recommend.what_if(security.unseal(row["answers"]) or {}, security.unseal(row["wearable"]), security.unseal(row["semen"]),
                             security.unseal(row["labs"]), body.improve, lang)


@app.get("/api/clinician/cases/{aid}/explain")
def clin_explain(aid: str, clin=Depends(current_clinician)):
    with db.tx() as c:
        row = _clinician_can_see(c, aid)
    if not row:
        raise HTTPException(404, "Not found")
    db.audit(clin, "view_explanation", aid)
    return _explain(row, "en")


# ------------------------------------------------------------------ blood results
class LabsIn(BaseModel):
    testosterone: Optional[float] = Field(None, ge=0, le=2000)
    testosterone_unit: str = Field("nmol/L", pattern="^(nmol/L|ng/dL)$")
    fsh: Optional[float] = Field(None, ge=0, le=200)
    lh: Optional[float] = Field(None, ge=0, le=200)
    hba1c: Optional[float] = Field(None, ge=3, le=20)
    vitamin_d: Optional[float] = Field(None, ge=0, le=400)
    vitamin_d_unit: str = Field("ng/mL", pattern="^(ng/mL|nmol/L)$")
    date: Optional[str] = Field(None, max_length=10)


@app.post("/api/assessments/{aid}/labs")
def add_labs(aid: str, body: LabsIn, user=Depends(current_user)):
    own_assessment(aid, user)
    out = labs.interpret(body.model_dump(exclude_none=True))
    with db.tx() as c:
        c.execute("UPDATE assessments SET labs=? WHERE id=?", (security.seal(out), aid))
    db.event(aid, "labs_added")
    return {"findings": [f[:3] for f in out["findings"]]}


# ------------------------------------------------------------------ rapid review: request, messages, video
@app.post("/api/assessments/{aid}/request-review")
def request_review(aid: str, user=Depends(current_user)):
    """Explicit, case-level consent for a clinician to see this assessment (when global review consent was not given)."""
    row = own_assessment(aid, user)
    if not row["completed_at"]:
        raise HTTPException(400, "Not completed")
    with db.tx() as c:
        c.execute("INSERT INTO consents VALUES (?,?,?,?,?)", (user, f"clinician_review:{aid}", 1, CONSENT_VERSION, time.time()))
        c.execute("UPDATE assessments SET review_consent=1 WHERE id=?", (aid,))
        c.execute("UPDATE referrals SET status='pending_review' WHERE assessment_id=? AND status='suggested'", (aid,))
        if not c.execute("SELECT 1 FROM referrals WHERE assessment_id=?", (aid,)).fetchone():
            c.execute("INSERT INTO referrals (id, assessment_id, level, status, created_at) VALUES (?,?,?,?,?)",
                      (str(uuid.uuid4()), aid, row["level"], "pending_review", time.time()))
    db.event(aid, "review_requested")
    return {"queued": True}


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _messages(c, aid):
    return [{"id": r["id"], "sender": r["sender"], "body": security.unseal(r["body"]), "ts": r["ts"],
             "voice": bool(r["audio"]), "seconds": r["seconds"]}
            for r in c.execute("SELECT id, sender, body, ts, seconds, audio IS NOT NULL AS audio FROM messages WHERE assessment_id=? ORDER BY ts", (aid,)).fetchall()]


MAX_NOTE = 3 * 1024 * 1024
AUDIO_TYPES = ("audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-m4a", "audio/aac")


async def _store_note(c, aid, sender, file, seconds):
    raw = await file.read()
    mime = (file.content_type or "").split(";")[0]
    if len(raw) > MAX_NOTE:
        raise HTTPException(413, "Voice note too long")
    if mime not in AUDIO_TYPES:
        raise HTTPException(415, "Unsupported audio type")
    c.execute("INSERT INTO messages (id, assessment_id, sender, body, ts, audio, mime, seconds) VALUES (?,?,?,?,?,?,?,?)",
              (str(uuid.uuid4()), aid, sender, security.seal(""), time.time(), security.fernet().encrypt(raw), mime, seconds))


def _note(c, aid, mid):
    from fastapi.responses import Response
    r = c.execute("SELECT audio, mime FROM messages WHERE id=? AND assessment_id=?", (mid, aid)).fetchone()
    if not r or not r["audio"]:
        raise HTTPException(404, "Not found")
    return Response(security.fernet().decrypt(r["audio"]), media_type=r["mime"], headers={"Cache-Control": "no-store"})


@app.post("/api/assessments/{aid}/voice-notes")
async def user_note(aid: str, file: UploadFile = File(...), seconds: float = Form(0), user=Depends(current_user)):
    row = own_assessment(aid, user)
    if not row["review_consent"]:
        raise HTTPException(403, "Request a clinician review first")
    with db.tx() as c:
        await _store_note(c, aid, "user", file, seconds)
    db.event(aid, "voice_note_user")
    return {"ok": True}


@app.get("/api/assessments/{aid}/voice-notes/{mid}")
def user_note_get(aid: str, mid: str, user=Depends(current_user)):
    own_assessment(aid, user)
    with db.tx() as c:
        return _note(c, aid, mid)


@app.post("/api/clinician/cases/{aid}/voice-notes")
async def clin_note(aid: str, file: UploadFile = File(...), seconds: float = Form(0), clin=Depends(current_clinician)):
    with db.tx() as c:
        if not _clinician_can_see(c, aid):
            raise HTTPException(404, "Not found")
        await _store_note(c, aid, "clinician", file, seconds)
    db.audit(clin, "voice_note_sent", aid)
    return {"ok": True}


@app.get("/api/clinician/cases/{aid}/voice-notes/{mid}")
def clin_note_get(aid: str, mid: str, clin=Depends(current_clinician)):
    with db.tx() as c:
        if not _clinician_can_see(c, aid):
            raise HTTPException(404, "Not found")
        db_ = _note(c, aid, mid)
    db.audit(clin, "voice_note_played", aid)
    return db_


@app.get("/api/assessments/{aid}/messages")
def user_messages(aid: str, user=Depends(current_user)):
    own_assessment(aid, user)
    with db.tx() as c:
        c.execute("UPDATE messages SET read_at=? WHERE assessment_id=? AND sender='clinician' AND read_at IS NULL", (time.time(), aid))
        return _messages(c, aid)


@app.post("/api/assessments/{aid}/messages")
def user_send(aid: str, body: MessageIn, user=Depends(current_user)):
    row = own_assessment(aid, user)
    if not row["review_consent"]:
        raise HTTPException(403, "Request a clinician review first")
    with db.tx() as c:
        c.execute("INSERT INTO messages (id, assessment_id, sender, body, ts) VALUES (?,?,?,?,?)", (str(uuid.uuid4()), aid, "user", security.seal(body.body), time.time()))
    return {"ok": True}


@app.get("/api/clinician/cases/{aid}/messages")
def clin_messages(aid: str, clin=Depends(current_clinician)):
    with db.tx() as c:
        if not _clinician_can_see(c, aid):
            raise HTTPException(404, "Not found")
        c.execute("UPDATE messages SET read_at=? WHERE assessment_id=? AND sender='user' AND read_at IS NULL", (time.time(), aid))
        return _messages(c, aid)


@app.post("/api/clinician/cases/{aid}/messages")
def clin_send(aid: str, body: MessageIn, clin=Depends(current_clinician)):
    with db.tx() as c:
        if not _clinician_can_see(c, aid):
            raise HTTPException(404, "Not found")
        c.execute("INSERT INTO messages (id, assessment_id, sender, body, ts) VALUES (?,?,?,?,?)", (str(uuid.uuid4()), aid, "clinician", security.seal(body.body), time.time()))
    db.audit(clin, "message_sent", aid)
    return {"ok": True}


VIDEO_BASE = os.environ.get("RIAYA_VIDEO_BASE", "https://meet.jit.si")


@app.post("/api/clinician/cases/{aid}/video")
def start_video(aid: str, clin=Depends(current_clinician)):
    """Creates an unguessable video room. For production, point RIAYA_VIDEO_BASE at a self-hosted Jitsi inside the UAE."""
    url = f"{VIDEO_BASE}/riaya-{security.new_token()[:24]}"
    with db.tx() as c:
        if not _clinician_can_see(c, aid):
            raise HTTPException(404, "Not found")
        c.execute("UPDATE referrals SET video_url=? WHERE assessment_id=?", (url, aid))
        c.execute("INSERT INTO messages (id, assessment_id, sender, body, ts) VALUES (?,?,?,?,?)", (str(uuid.uuid4()), aid, "clinician",
                  security.seal("استشارتك المرئية الخاصة جاهزة. افتح الرابط من صفحة نتيجتك متى كنت مستعداً. / "
                                "A private video consultation is ready. Open the link on your result page when you are ready."), time.time()))
    db.audit(clin, "video_created", aid)
    return {"url": url}


# ------------------------------------------------------------------ care navigation handover
@app.get("/api/clinician/cases/{aid}/handover")
def get_handover(aid: str, clin=Depends(current_clinician)):
    with db.tx() as c:
        row = _clinician_can_see(c, aid)
        if not row:
            raise HTTPException(404, "Not found")
        ref = c.execute("SELECT * FROM referrals WHERE assessment_id=?", (aid,)).fetchone()
        if ref:
            c.execute("UPDATE referrals SET handover_at=? WHERE id=?", (time.time(), ref["id"]))
    out = handover.build(security.unseal(row["answers"]) or {}, security.unseal(row["result"]),
                         {k: ref[k] for k in ref.keys() if k != "note"} if ref else None, clin)
    db.audit(clin, "handover_generated", aid)
    return out


# ------------------------------------------------------------------ partner mode (status only)
PARTNER_DAYS = 30
PARTNER_TEXT = {
    "none": {"en": "He has completed his men's health check. No follow-up visit is needed right now.",
             "ar": "أكمل فحص صحة الرجل. لا حاجة لزيارة متابعة في الوقت الحالي."},
    "routine": {"en": "He has completed his men's health check. A routine follow-up visit is recommended.",
                "ar": "أكمل فحص صحة الرجل. يُنصح بزيارة متابعة روتينية."},
    "specialist": {"en": "He has completed his men's health check. A specialist visit is recommended — he is taking the next step.",
                   "ar": "أكمل فحص صحة الرجل. يُنصح بزيارة مختص — وهو يتخذ الخطوة التالية."},
    "together": {"en": "He has completed his men's health check. A joint visit to a fertility clinic is recommended, so you can both be seen at the same time.",
                 "ar": "أكمل فحص صحة الرجل. يُنصح بزيارة مشتركة لعيادة الخصوبة، ليتم فحصكما معاً في الوقت نفسه."},
}


def _partner_status(level):
    if level == "fertility_services":
        return "together"
    if level in ("andrology", "urgent_specialist", "emergency", "same_day_primary"):
        return "specialist"
    return "routine" if level == "primary_care" else "none"


@app.post("/api/assessments/{aid}/partner-link")
def partner_link(aid: str, user=Depends(current_user)):
    row = own_assessment(aid, user)
    if not row["completed_at"]:
        raise HTTPException(400, "Not completed")
    token = security.new_token()
    with db.tx() as c:
        c.execute("DELETE FROM partner_links WHERE assessment_id=?", (aid,))
        c.execute("INSERT INTO partner_links VALUES (?,?,?,?,0,0)", (security.token_hash(token), aid, time.time(), time.time() + PARTNER_DAYS * 86400))
    db.event(aid, "partner_link_created")
    return {"token": token, "path": f"/partner.html#{token}", "expires_in_days": PARTNER_DAYS}


@app.delete("/api/assessments/{aid}/partner-link")
def partner_revoke(aid: str, user=Depends(current_user)):
    own_assessment(aid, user)
    with db.tx() as c:
        c.execute("UPDATE partner_links SET revoked=1 WHERE assessment_id=?", (aid,))
    return {"revoked": True}


@app.get("/api/partner/{token}")
def partner_view(token: str):
    """Shows only completion and the broad kind of next step. No answers, scores, results or reasons."""
    with db.tx() as c:
        link = c.execute("SELECT * FROM partner_links WHERE token_hash=? AND revoked=0 AND expires_at>?",
                         (security.token_hash(token), time.time())).fetchone()
        if not link:
            raise HTTPException(404, "This link has expired or was withdrawn")
        a = c.execute("SELECT completed_at, level FROM assessments WHERE id=?", (link["assessment_id"],)).fetchone()
        ref = c.execute("SELECT final_level FROM referrals WHERE assessment_id=?", (link["assessment_id"],)).fetchone()
        c.execute("UPDATE partner_links SET views=views+1 WHERE token_hash=?", (link["token_hash"],))
    level = (ref and ref["final_level"]) or a["level"]
    status = _partner_status(level)
    return {"completed_on": time.strftime("%Y-%m-%d", time.gmtime(a["completed_at"])), "status": status, "message": PARTNER_TEXT[status]}


# ------------------------------------------------------------------ conversational channels (WhatsApp + demo)
from fastapi import Request  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from xml.sax.saxutils import escape as xml_escape  # noqa: E402
from . import conversation  # noqa: E402

PUBLIC_URL = os.environ.get("RIAYA_PUBLIC_URL", "").rstrip("/")


def _load_session(key):
    with db.tx() as c:
        r = c.execute("SELECT state FROM chat_sessions WHERE key_hash=?", (key,)).fetchone()
    return security.unseal(r["state"]) if r else None


def _save_session(key, st):
    with db.tx() as c:
        c.execute("DELETE FROM chat_sessions WHERE key_hash=?", (key,))
        c.execute("INSERT INTO chat_sessions VALUES (?,?,?)", (key, security.seal(st), time.time()))


def _drop_session(key):
    with db.tx() as c:
        c.execute("DELETE FROM chat_sessions WHERE key_hash=?", (key,))


def _new_identity(st):
    token, uid = security.new_token(), str(uuid.uuid4())
    with db.tx() as c:
        c.execute("INSERT INTO users (id, token_hash, created_at, lang) VALUES (?,?,?,?)", (uid, security.token_hash(token), time.time(), st["lang"] or "ar"))
        c.execute("INSERT INTO consents VALUES (?,?,?,?,?)", (uid, "core", 1, CONSENT_VERSION, time.time()))
        aid = str(uuid.uuid4())
        c.execute("INSERT INTO assessments (id, user_id, started_at, channel) VALUES (?,?,?,?)", (aid, uid, time.time(), "whatsapp"))
    db.event(aid, "started", st.get("channel"))
    st.update(uid=uid, token=token, aid=aid)


def _summary_text(view, st, base):
    lang = st["lang"]
    lines = [f"*{view['next_step']}*", view["summary"]]
    if view["plan"]:
        lines.append("")
        lines.append("Your top opportunities:" if lang == "en" else "أهم فرصك:")
        lines += [f"{i + 1}. {p['action']}" for i, p in enumerate(view["plan"])]
    if view.get("clinician_review") == "queued":
        lines += ["", "A licensed doctor will review this before any referral is final." if lang == "en" else "سيراجع طبيب مرخّص ملخصك قبل اعتماد أي إحالة."]
    lines += ["", view["disclaimer"]]
    link = f"{base}/index.html#t={st['token']}&a={st['aid']}" if base else None
    if link:
        lines += ["", ("Full private summary, IFHAS hand-off and doctor messages: " if lang == "en" else "الملخص الكامل وتسليم «إفحص» ورسائل الطبيب: ") + link]
    lines += ["", "Reply *delete* to erase everything." if lang == "en" else "أرسل *حذف* لمسح كل شيء."]
    return "\n".join(lines)


def converse(key, text, channel, base, has_media=False):
    st = _load_session(key) or dict(conversation.new_state(), channel=channel)
    replies, event = conversation.handle(st, text, has_media)
    if event in ("delete", "restart"):
        if st.get("uid"):
            delete_me(user=st["uid"])
        _drop_session(key)
        if event == "delete":
            return ["Everything has been erased. Send any message to start again." if st.get("lang") != "ar" else "تم مسح كل شيء. أرسل أي رسالة للبدء من جديد."]
        st = dict(conversation.new_state(), channel=channel, lang=st.get("lang"))
        replies, event = conversation.handle(st, "1" if st["lang"] == "ar" else "2" if st["lang"] == "en" else text)
    if event == "start" and not st.get("uid"):
        _new_identity(st)
    if st.get("uid") and event in ("answers", "finish"):
        with db.tx() as c:
            c.execute("INSERT INTO consents VALUES (?,?,?,?,?)", (st["uid"], "clinician_review", int(st["review"]), CONSENT_VERSION, time.time()))
            c.execute("UPDATE assessments SET answers=? WHERE id=?", (security.seal(st["answers"]), st["aid"]))
    if event == "finish":
        view = submit(st["aid"], st["lang"], user=st["uid"])
        replies = [_summary_text(view, st, base)]
    _save_session(key, st)
    return replies


def _twilio_valid(request, form):
    tok = os.environ.get("TWILIO_AUTH_TOKEN")
    if not tok:
        return True  # sandbox / local demo
    import base64
    import hashlib
    import hmac
    url = (PUBLIC_URL + request.url.path) if PUBLIC_URL else str(request.url)
    data = url + "".join(k + form[k] for k in sorted(form))
    sig = base64.b64encode(hmac.new(tok.encode(), data.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(sig, request.headers.get("X-Twilio-Signature", ""))


@app.post("/api/whatsapp/twilio")
async def whatsapp(request: Request):
    """Twilio WhatsApp webhook (sandbox or production sender). The phone number is never stored: only a salted hash keys the session."""
    form = {k: str(v) for k, v in (await request.form()).items()}
    if not _twilio_valid(request, form):
        raise HTTPException(403, "Bad signature")
    salt = os.environ.get("RIAYA_PHONE_SALT", "riaya")
    key = "wa:" + security.token_hash(salt + form.get("From", ""))
    base = PUBLIC_URL or str(request.base_url).rstrip("/")
    replies = converse(key, form.get("Body", ""), "whatsapp", base, has_media=int(form.get("NumMedia", "0") or 0) > 0)
    xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response>" + "".join(f"<Message>{xml_escape(r)}</Message>" for r in replies) + "</Response>"
    return Response(xml, media_type="application/xml")


@app.get("/api/config")
def public_config():
    """Non-secret settings the web app needs (e.g. the WhatsApp number to show as a QR code)."""
    return {"whatsapp_number": os.environ.get("RIAYA_WHATSAPP_NUMBER", ""), "whatsapp_join": os.environ.get("RIAYA_WHATSAPP_JOIN", "")}


class DemoIn(BaseModel):
    session: str = Field(min_length=16, max_length=64)
    text: str = Field("", max_length=500)


@app.post("/api/conversation/demo")
def conversation_demo(body: DemoIn, request: Request):
    """Same engine as WhatsApp, for the in-app WhatsApp-style demo."""
    base = PUBLIC_URL or str(request.base_url).rstrip("/")
    return {"replies": converse("demo:" + security.token_hash(body.session), body.text, "demo", base)}


# ------------------------------------------------------------------ static web app
app.mount("/knowledge", StaticFiles(directory=ROOT / "knowledge"), name="knowledge")
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
