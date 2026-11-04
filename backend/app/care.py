"""Care Connect: from an approved referral to a confirmed appointment and attendance.

The directory holds only what a provider publishes about itself. Availability is never shown or guessed:
he sends a request with his preferred times, a coordinator agrees a slot with the clinic, and he gets a
discreet calendar entry. Each step, and every reason for a delay or a missed visit, is recorded.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import db, security
from .main import ROOT, BARRIERS, current_clinician, current_user, own_assessment, _median

router = APIRouter()

LEVEL_KINDS = {"emergency": "emergency", "urgent_specialist": "urology", "andrology": "urology", "fertility_services": "urology",
               "same_day_primary": "primary", "primary_care": "primary"}
OPEN = ("requested", "confirmed")
MISSED_REASONS = BARRIERS + ("forgot", "clinic_cancelled", "felt_better")
DECLINE_REASONS = ("not_accepting", "wrong_service", "no_slots", "insurance", "other")
HANDOVER_DAYS = 14
TIMES = ("morning", "afternoon", "evening")
DAYS = ("weekday", "weekend")


def seed():
    """Loads the starting directory once. Coordinators add and confirm clinics afterwards."""
    data = json.loads((ROOT / "knowledge" / "providers.json").read_text())["providers"]
    with db.tx() as c:
        have = {r["id"] for r in c.execute("SELECT id FROM providers").fetchall()}
        for p in data:
            if p["id"] not in have:
                c.execute("""INSERT INTO providers (id, name_en, name_ar, area, area_ar, sector, kinds, website, active, added_at, added_by)
                             VALUES (?,?,?,?,?,?,?,?,1,?,?)""",
                          (p["id"], p["name_en"], p["name_ar"], p["area"], p["area_ar"], p["sector"], ",".join(p["kinds"]), p["website"], time.time(), "directory"))


def _provider(r, lang="en"):
    return {"id": r["id"], "name": r["name_ar"] if lang == "ar" else r["name_en"], "name_en": r["name_en"], "name_ar": r["name_ar"],
            "area": r["area_ar"] if lang == "ar" else r["area"], "sector": r["sector"], "kinds": r["kinds"].split(","),
            "website": r["website"], "confirmed_at": r["confirmed_at"], "confirm_note": r["confirm_note"] if r["confirmed_at"] else None}


def providers_for(level, lang="en"):
    kind = LEVEL_KINDS.get(level)
    if not kind:
        return []
    with db.tx() as c:
        rows = c.execute("SELECT * FROM providers WHERE active=1 ORDER BY confirmed_at IS NULL, name_en").fetchall()
    return [_provider(r, lang) for r in rows if kind in r["kinds"].split(",")]


def _referral(c, aid):
    return c.execute("SELECT * FROM referrals WHERE assessment_id=?", (aid,)).fetchone()


def _level(ref):
    return ref["final_level"] or ref["level"]


def _appt(c, aid):
    return c.execute("SELECT * FROM appointments WHERE assessment_id=? ORDER BY created_at DESC LIMIT 1", (aid,)).fetchone()


def _appt_view(a, lang="en", clinician=False):
    if not a:
        return None
    with db.tx() as c:
        p = c.execute("SELECT * FROM providers WHERE id=?", (a["provider_id"],)).fetchone()
    prefs = security.unseal(a["prefs"]) or {}
    out = {"id": a["id"], "status": a["status"], "provider": _provider(p, lang) if p else None, "created_at": a["created_at"],
           "updated_at": a["updated_at"], "slot_at": a["slot_at"], "place_note": security.unseal(a["place_note"]),
           "reason": a["reason"], "share_code": a["share_code"],
           "times": prefs.get("times", []), "days": prefs.get("days", []), "contact": prefs.get("contact", "messages")}
    if clinician:
        out.update({"assessment_id": a["assessment_id"], "phone": prefs.get("phone"), "note": prefs.get("note")})
    return out


def _tell(c, aid, en, ar):
    """Leaves a message in his Riaya inbox, in his language. No SMS or email is sent."""
    row = c.execute("SELECT lang FROM users WHERE id=(SELECT user_id FROM assessments WHERE id=?)", (aid,)).fetchone()
    text = ar if row and row["lang"] == "ar" else en
    c.execute("INSERT INTO messages (id, assessment_id, sender, body, ts) VALUES (?,?,?,?,?)",
              (str(uuid.uuid4()), aid, "clinician", security.seal(text), time.time()))


# ------------------------------------------------------------------ public directory
@router.get("/api/providers")
def list_providers(level: Optional[str] = None, lang: str = "en"):
    if level:
        return {"providers": providers_for(level, lang)}
    with db.tx() as c:
        rows = c.execute("SELECT * FROM providers WHERE active=1 ORDER BY confirmed_at IS NULL, name_en").fetchall()
    return {"providers": [_provider(r, lang) for r in rows]}


# ------------------------------------------------------------------ patient side
@router.get("/api/assessments/{aid}/care")
def care_state(aid: str, lang: str = "en", user=Depends(current_user)):
    own_assessment(aid, user)
    with db.tx() as c:
        ref, a = _referral(c, aid), _appt(c, aid)
    if not ref:
        return {"stage": "no_referral"}
    level = _level(ref)
    if level == "emergency":
        stage = "emergency"
    elif ref["status"] == "pending_review":
        stage = "awaiting_review"
    elif level not in LEVEL_KINDS:
        stage = "not_needed"
    elif a and a["status"] in OPEN + ("attended",):
        stage = a["status"]
    else:
        stage = "choose"
    return {"stage": stage, "level": level, "appointment": _appt_view(a, lang),
            "providers": providers_for(level, lang) if stage == "choose" else [],
            "missed_reasons": list(MISSED_REASONS)}


class RequestIn(BaseModel):
    provider_id: str = Field(min_length=1, max_length=40)
    times: List[str] = Field(default_factory=list, max_length=3)
    days: List[str] = Field(default_factory=list, max_length=2)
    contact: str = Field("messages", pattern="^(messages|phone)$")
    phone: Optional[str] = Field(None, max_length=20)
    share_summary: bool = True
    note: Optional[str] = Field(None, max_length=500)


@router.post("/api/assessments/{aid}/appointment")
def request_appointment(aid: str, body: RequestIn, user=Depends(current_user)):
    own_assessment(aid, user)
    phone = "".join(ch for ch in (body.phone or "") if ch.isdigit() or ch == "+")
    if body.contact == "phone" and not (8 <= len(phone.lstrip("+")) <= 15):
        raise HTTPException(400, "Enter a phone number with 8 to 15 digits, or choose to be contacted in Riaya messages.")
    with db.tx() as c:
        ref = _referral(c, aid)
        if not ref or ref["status"] in ("pending_review", "rejected"):
            raise HTTPException(409, "A doctor needs to approve your referral before you choose a clinic.")
        level = _level(ref)
        if level == "emergency":
            raise HTTPException(409, "This needs emergency care now. Go to an emergency department or call 998.")
        p = c.execute("SELECT * FROM providers WHERE id=? AND active=1", (body.provider_id,)).fetchone()
        if not p or LEVEL_KINDS.get(level) not in p["kinds"].split(","):
            raise HTTPException(400, "Choose one of the clinics shown for your referral.")
        a = _appt(c, aid)
        if a and a["status"] in OPEN:
            raise HTTPException(409, "You already have an open request. Cancel it first to choose another clinic.")
        now, code = time.time(), None
        if body.share_summary:
            code = security.share_code()
            c.execute("INSERT INTO shares VALUES (?,?,?,?,0,NULL)", (code, aid, now, now + HANDOVER_DAYS * 86400))
        prefs = {"times": [x for x in body.times if x in TIMES], "days": [x for x in body.days if x in DAYS],
                 "contact": body.contact, "phone": phone if body.contact == "phone" else None, "note": (body.note or "").strip() or None}
        appt_id = str(uuid.uuid4())
        c.execute("""INSERT INTO appointments (id, assessment_id, provider_id, status, prefs, created_at, updated_at, share_code)
                     VALUES (?,?,?,?,?,?,?,?)""", (appt_id, aid, p["id"], "requested", security.seal(prefs), now, now, code))
    db.event(aid, "appointment_requested", p["id"])
    return care_state(aid, user=user)


@router.delete("/api/assessments/{aid}/appointment")
def cancel_appointment(aid: str, user=Depends(current_user)):
    own_assessment(aid, user)
    with db.tx() as c:
        a = _appt(c, aid)
        if not a or a["status"] not in OPEN:
            raise HTTPException(404, "No open request to cancel")
        c.execute("UPDATE appointments SET status='cancelled', updated_at=? WHERE id=?", (time.time(), a["id"]))
        if a["share_code"]:
            c.execute("UPDATE shares SET revoked=1 WHERE code=?", (a["share_code"],))
        if a["status"] == "confirmed":
            c.execute("UPDATE referrals SET status='approved' WHERE assessment_id=? AND status='booked'", (aid,))
    db.event(aid, "appointment_cancelled")
    return {"ok": True}


class OutcomeIn(BaseModel):
    outcome: str = Field(pattern="^(attended|missed)$")
    reason: Optional[str] = None


def _record_outcome(c, a, outcome, reason, self_reported):
    now = time.time()
    if outcome == "attended":
        c.execute("UPDATE appointments SET status='attended', updated_at=? WHERE id=?", (now, a["id"]))
        c.execute("UPDATE referrals SET status='attended', attended_at=COALESCE(attended_at, ?), self_reported=? WHERE assessment_id=?",
                  (now, int(self_reported), a["assessment_id"]))
    else:
        reason = reason if reason in MISSED_REASONS else "other"
        c.execute("UPDATE appointments SET status='missed', reason=?, updated_at=? WHERE id=?", (reason, now, a["id"]))
        # the referral stays open so he can choose again
        c.execute("UPDATE referrals SET status='approved', barrier=? WHERE assessment_id=?", (reason, a["assessment_id"]))


@router.post("/api/assessments/{aid}/appointment/outcome")
def appointment_outcome(aid: str, body: OutcomeIn, user=Depends(current_user)):
    own_assessment(aid, user)
    with db.tx() as c:
        a = _appt(c, aid)
        if not a or a["status"] != "confirmed":
            raise HTTPException(409, "There is no confirmed appointment to update")
        _record_outcome(c, a, body.outcome, body.reason, True)
    db.event(aid, f"appointment_{body.outcome}", body.reason)
    return {"ok": True}


def _ics_time(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@router.get("/api/assessments/{aid}/appointment.ics")
def appointment_ics(aid: str, user=Depends(current_user)):
    """A calendar entry that says only 'Appointment' and the place, so nothing private shows on a lock screen."""
    own_assessment(aid, user)
    with db.tx() as c:
        a = _appt(c, aid)
        p = c.execute("SELECT * FROM providers WHERE id=?", (a["provider_id"],)).fetchone() if a else None
    if not a or a["status"] != "confirmed" or not a["slot_at"]:
        raise HTTPException(404, "No confirmed appointment")
    place = (p["name_en"] if p else "") + (f" ({security.unseal(a['place_note'])})" if a["place_note"] else "")
    esc = lambda s: s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", " ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Riaya//Care Connect//EN", "BEGIN:VEVENT",
             f"UID:{a['id']}@riaya", f"DTSTAMP:{_ics_time(time.time())}", f"DTSTART:{_ics_time(a['slot_at'])}",
             f"DTEND:{_ics_time(a['slot_at'] + 3600)}", "SUMMARY:Appointment", f"LOCATION:{esc(place)}",
             "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Appointment tomorrow", "TRIGGER:-P1D", "END:VALARM",
             "END:VEVENT", "END:VCALENDAR"]
    return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=appointment.ics"})


# ------------------------------------------------------------------ coordinator side
@router.get("/api/clinician/appointments")
def appointment_queue(clin=Depends(current_clinician)):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM appointments WHERE status IN ('requested','confirmed') ORDER BY created_at").fetchall()
        levels = {r["assessment_id"]: _level(r) for r in c.execute(
            "SELECT * FROM referrals WHERE assessment_id IN (SELECT assessment_id FROM appointments WHERE status IN ('requested','confirmed'))").fetchall()}
    out = []
    for r in rows:
        v = _appt_view(r, clinician=True)
        v["level"] = levels.get(r["assessment_id"])
        out.append(v)
    return {"appointments": out, "decline_reasons": list(DECLINE_REASONS), "missed_reasons": list(MISSED_REASONS)}


class DecisionIn(BaseModel):
    action: str = Field(pattern="^(confirm|decline|attended|missed)$")
    slot_at: Optional[float] = None
    place_note: Optional[str] = Field(None, max_length=200)
    reason: Optional[str] = None


@router.post("/api/clinician/appointments/{appt_id}")
def decide_appointment(appt_id: str, body: DecisionIn, clin=Depends(current_clinician)):
    now = time.time()
    with db.tx() as c:
        a = c.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
        if not a:
            raise HTTPException(404, "No such request")
        p = c.execute("SELECT * FROM providers WHERE id=?", (a["provider_id"],)).fetchone()
        aid, name_en, name_ar = a["assessment_id"], p["name_en"] if p else "", p["name_ar"] if p else ""
        if body.action == "confirm":
            if a["status"] not in OPEN:
                raise HTTPException(409, "This request is no longer open")
            if not body.slot_at or body.slot_at < now:
                raise HTTPException(400, "Choose a date and time in the future")
            c.execute("UPDATE appointments SET status='confirmed', slot_at=?, place_note=?, decided_by=?, confirmed_at=?, updated_at=? WHERE id=?",
                      (body.slot_at, security.seal((body.place_note or "").strip() or None), clin, now, now, appt_id))
            c.execute("UPDATE referrals SET status='booked', booked_at=COALESCE(booked_at, ?) WHERE assessment_id=?", (now, aid))
            _tell(c, aid, f"Your appointment at {name_en} is confirmed. Open My journey to see the time and add it to your calendar.",
                  f"تم تأكيد موعدك في {name_ar}. افتح «مساري» لمعرفة الوقت وإضافته إلى التقويم.")
        elif body.action == "decline":
            if a["status"] != "requested":
                raise HTTPException(409, "Only a new request can be declined")
            if body.reason not in DECLINE_REASONS:
                raise HTTPException(400, "Choose a reason so he understands why")
            c.execute("UPDATE appointments SET status='declined', reason=?, decided_by=?, updated_at=? WHERE id=?", (body.reason, clin, now, appt_id))
            if a["share_code"]:
                c.execute("UPDATE shares SET revoked=1 WHERE code=?", (a["share_code"],))
            _tell(c, aid, f"{name_en} could not take your request. Open My journey to choose another clinic. Your referral is still valid.",
                  f"لم يتمكن {name_ar} من قبول طلبك. افتح «مساري» لاختيار عيادة أخرى. إحالتك ما زالت سارية.")
        else:
            if a["status"] != "confirmed":
                raise HTTPException(409, "Only a confirmed appointment can be marked")
            _record_outcome(c, a, body.action, body.reason, False)
    db.audit(clin, f"appointment_{body.action}", aid)
    db.event(aid, f"appointment_{body.action}", body.reason)
    return {"ok": True}


class ProviderIn(BaseModel):
    name_en: str = Field(min_length=3, max_length=120)
    name_ar: str = Field(min_length=2, max_length=120)
    area: str = Field(min_length=2, max_length=120)
    area_ar: str = Field(min_length=2, max_length=120)
    sector: str = Field(pattern="^(public|private)$")
    kinds: List[str] = Field(min_length=1, max_length=3)
    website: str = Field(pattern=r"^https://[^\s]+$", max_length=200)


@router.get("/api/clinician/providers")
def all_providers(clin=Depends(current_clinician)):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM providers ORDER BY active DESC, name_en").fetchall()
    return {"providers": [dict(_provider(r), active=bool(r["active"]), confirmed_by=r["confirmed_by"]) for r in rows]}


@router.post("/api/clinician/providers")
def add_provider(body: ProviderIn, clin=Depends(current_clinician)):
    kinds = [k for k in body.kinds if k in ("urology", "primary", "emergency")]
    if not kinds:
        raise HTTPException(400, "Choose at least one service: urology, primary or emergency")
    pid = "p" + uuid.uuid4().hex[:8]
    with db.tx() as c:
        c.execute("""INSERT INTO providers (id, name_en, name_ar, area, area_ar, sector, kinds, website, active, added_at, added_by)
                     VALUES (?,?,?,?,?,?,?,?,1,?,?)""",
                  (pid, body.name_en.strip(), body.name_ar.strip(), body.area.strip(), body.area_ar.strip(), body.sector, ",".join(kinds), body.website, time.time(), clin))
    db.audit(clin, "provider_added", pid)
    return {"id": pid}


class ConfirmIn(BaseModel):
    note: str = Field(min_length=10, max_length=300)


@router.post("/api/clinician/providers/{pid}/confirm")
def confirm_provider(pid: str, body: ConfirmIn, clin=Depends(current_clinician)):
    """Records who checked the clinic, when and how. Patients see the date and the note."""
    with db.tx() as c:
        if not c.execute("UPDATE providers SET confirmed_at=?, confirmed_by=?, confirm_note=? WHERE id=?",
                         (time.time(), clin, body.note.strip(), pid)).rowcount:
            raise HTTPException(404, "No such clinic")
    db.audit(clin, "provider_confirmed", pid)
    return {"ok": True}


@router.post("/api/clinician/providers/{pid}/active")
def set_provider_active(pid: str, active: bool, clin=Depends(current_clinician)):
    with db.tx() as c:
        if not c.execute("UPDATE providers SET active=? WHERE id=?", (int(active), pid)).rowcount:
            raise HTTPException(404, "No such clinic")
    db.audit(clin, "provider_active" if active else "provider_hidden", pid)
    return {"ok": True}


def metrics(include_simulated=False):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM appointments").fetchall()
    req = len(rows)
    confirmed = [r for r in rows if r["confirmed_at"]]
    attended = sum(r["status"] == "attended" for r in rows)
    missed = sum(r["status"] == "missed" for r in rows)
    reasons = {}
    for r in rows:
        if r["status"] in ("missed", "declined") and r["reason"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    return {"requests": req, "confirmed": len(confirmed), "attended": attended, "missed": missed,
            "declined_by_clinic": sum(r["status"] == "declined" for r in rows), "cancelled": sum(r["status"] == "cancelled" for r in rows),
            "booking_rate": round(len(confirmed) / req, 3) if req else None,
            "attendance_rate": round(attended / (attended + missed), 3) if attended + missed else None,
            "median_hours_to_confirm": _median([(r["confirmed_at"] - r["created_at"]) / 3600 for r in confirmed]),
            "reasons": reasons}
