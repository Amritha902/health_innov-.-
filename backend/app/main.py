import os
from contextlib import asynccontextmanager
import statistics
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import assessment, db, fabric, ifhas, questionnaire, security, semen, wearables
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
    user = os.environ.get("RIAYA_CLINICIAN_USER", "clinician")
    pw = os.environ.get("RIAYA_CLINICIAN_PASSWORD", "demo-clinician")
    with db.tx() as c:
        if not c.execute("SELECT 1 FROM clinicians WHERE username=?", (user,)).fetchone():
            salt, h = security.hash_password(pw)
            c.execute("INSERT INTO clinicians VALUES (?,?,?,?)", (user, salt, h, "Duty clinician"))


@asynccontextmanager
async def lifespan(_app):
    startup()
    yield


app = FastAPI(title="Riaya API", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)


@app.middleware("http")
async def headers(request, call_next):
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
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
    with db.tx() as c:
        row = c.execute("SELECT username FROM sessions WHERE token_hash=? AND expires_at>?",
                        (security.token_hash(authorization[7:]), time.time())).fetchone()
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
        c.execute("INSERT INTO users VALUES (?,?,?,?)", (uid, security.token_hash(token), time.time(), body.lang))
    return {"token": token}


class ConsentIn(BaseModel):
    core: bool
    clinician_review: bool = False
    wearables: bool = False
    research: bool = False


@app.post("/api/consent")
def set_consent(body: ConsentIn, user=Depends(current_user)):
    if not body.core:
        raise HTTPException(400, "Core consent is needed to produce a summary")
    with db.tx() as c:
        for p, v in body.model_dump().items():
            c.execute("INSERT INTO consents VALUES (?,?,?,?,?)", (user, p, int(v), CONSENT_VERSION, time.time()))
    return consents(user)


@app.get("/api/consent")
def get_consent(user=Depends(current_user)):
    return consents(user)


# ------------------------------------------------------------------ assessment
@app.post("/api/assessments")
def start(user=Depends(current_user)):
    if not consents(user)["core"]:
        raise HTTPException(403, "Consent required")
    aid = str(uuid.uuid4())
    with db.tx() as c:
        c.execute("INSERT INTO assessments (id, user_id, started_at) VALUES (?,?,?)", (aid, user, time.time()))
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
    result = assessment.run(answers, security.unseal(row["wearable"]), security.unseal(row["semen"]))
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
            c.execute("INSERT INTO referrals (id, assessment_id, level, status, created_at) VALUES (?,?,?,?,?)",
                      (str(uuid.uuid4()), aid, t["level"], status, now))
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
        ref = c.execute("SELECT status, final_level, reviewed_at FROM referrals WHERE assessment_id=?", (aid,)).fetchone()
    view["referral"] = dict(ref) if ref else None
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


@app.get("/api/me/export")
def export_me(user=Depends(current_user)):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM assessments WHERE user_id=?", (user,)).fetchall()
        shares = c.execute("SELECT code, created_at, expires_at, revoked, used_by FROM shares WHERE assessment_id IN "
                           "(SELECT id FROM assessments WHERE user_id=?)", (user,)).fetchall()
    return {"consents": consents(user), "shares": [dict(s) for s in shares],
            "assessments": [{"id": r["id"], "started_at": r["started_at"], "completed_at": r["completed_at"],
                             "answers": security.unseal(r["answers"]), "device_summary": security.unseal(r["wearable"]),
                             "test_result": security.unseal(r["semen"]), "result": security.unseal(r["result"])} for r in rows]}


@app.delete("/api/me")
def delete_me(user=Depends(current_user)):
    """Erases everything about this person. Aggregate counters in `events` lose the link (assessment id removed)."""
    with db.tx() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM assessments WHERE user_id=?", (user,)).fetchall()]
        for aid in ids:
            c.execute("DELETE FROM referrals WHERE assessment_id=?", (aid,))
            c.execute("DELETE FROM shares WHERE assessment_id=?", (aid,))
            c.execute("DELETE FROM feedback WHERE assessment_id=?", (aid,))
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


@app.post("/api/clinician/login")
def login(body: LoginIn):
    with db.tx() as c:
        row = c.execute("SELECT * FROM clinicians WHERE username=?", (body.username,)).fetchone()
        if not row or not security.check_password(body.password, row["salt"], row["pw_hash"]):
            db.audit(body.username, "login_failed")
            raise HTTPException(401, "Invalid credentials")
        token = security.new_token()
        c.execute("INSERT INTO sessions VALUES (?,?,?)", (security.token_hash(token), body.username, time.time() + 8 * 3600))
    db.audit(body.username, "login")
    return {"token": token, "name": row["display_name"]}


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
                            ORDER BY CASE a.level WHEN 'emergency' THEN 0 WHEN 'urgent_specialist' THEN 1
                                     WHEN 'same_day_primary' THEN 2 WHEN 'andrology' THEN 3 ELSE 4 END, a.completed_at""").fetchall()
        recent = c.execute("""SELECT a.*, r.status, r.final_level, r.reviewed_at, r.reviewer FROM assessments a
                              JOIN referrals r ON r.assessment_id=a.id WHERE a.review_consent=1 AND r.status!='pending_review'
                              ORDER BY r.reviewed_at DESC LIMIT 30""").fetchall()
    db.audit(clin, "view_queue")
    pick = lambda r: {"id": r["id"], "tier": r["tier"], "level": r["level"], "cohort": r["cohort"],
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
    db.audit(clin, "view_case", aid)
    result = security.unseal(row["result"])
    answers = security.unseal(row["answers"]) or {}
    if result and "models" not in result:
        from . import ml, synth
        result["models"] = {"uci_logistic": ml.predict(answers),
                            "simulated_gbm": synth.explain(answers, result["instruments"], result.get("wearable"))}
    g = graph()
    return {"id": aid, "answers": security.unseal(row["answers"]), "result": result,
            "referral": {k: ref[k] for k in ref.keys() if k != "note"} if ref else None,
            "paths": {n: g.paths(n)[:3] for n in list((result or {}).get("attribution", {}))[:5]},
            "references": {r: g.refs[r] for r in {r for e in g.edges for r in e["refs"]}},
            "simulated": bool(row["simulated"])}


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
    decision: str = Field(pattern="^(approve|modify)$")
    final_level: Optional[str] = None
    note: Optional[str] = Field(None, max_length=2000)


@app.post("/api/clinician/cases/{aid}/review")
def review(aid: str, body: ReviewIn, clin=Depends(current_clinician)):
    from .triage import LEVELS
    with db.tx() as c:
        ref = c.execute("SELECT * FROM referrals WHERE assessment_id=?", (aid,)).fetchone()
        if not ref:
            raise HTTPException(404, "No referral")
        final = ref["level"] if body.decision == "approve" else body.final_level
        if final not in LEVELS:
            raise HTTPException(400, "Invalid level")
        c.execute("UPDATE referrals SET status='approved', reviewed_at=?, reviewer=?, final_level=?, note=? WHERE id=?",
                  (time.time(), clin, final, security.seal(body.note), ref["id"]))
    db.audit(clin, f"review_{body.decision}", aid)
    db.event(aid, "reviewed", final)
    return {"status": "approved", "final_level": final}


class StatusIn(BaseModel):
    status: str = Field(pattern="^(booked|attended|declined)$")


@app.post("/api/clinician/cases/{aid}/status")
def referral_status(aid: str, body: StatusIn, clin=Depends(current_clinician)):
    col = {"booked": "booked_at", "attended": "attended_at"}.get(body.status)
    with db.tx() as c:
        sets = "status=?" + (f", {col}=?" if col else "")
        args = [body.status] + ([time.time()] if col else []) + [aid]
        if not c.execute(f"UPDATE referrals SET {sets} WHERE assessment_id=?", args).rowcount:
            raise HTTPException(404, "No referral")
    db.audit(clin, f"referral_{body.status}", aid)
    db.event(aid, f"referral_{body.status}")
    return {"ok": True}


@app.get("/api/clinician/metrics")
def metrics(include_simulated: bool = True, clin=Depends(current_clinician)):
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


@app.get("/api/clinician/audit")
def audit_log(clin=Depends(current_clinician)):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM audit ORDER BY ts DESC LIMIT 200").fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ static web app
app.mount("/knowledge", StaticFiles(directory=ROOT / "knowledge"), name="knowledge")
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
