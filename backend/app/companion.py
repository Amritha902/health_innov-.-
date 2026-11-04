"""12-week companion. Sperm take about 74 days to develop, so a change in habits shows in results after
roughly three months. He picks up to three goals from his own summary; a doctor reviews the plan when he has
agreed to doctor review; each week he records how it went; trends show what changed. Reminders are an optional
calendar entry that says only 'Weekly check-in'."""
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import db, security
from .main import current_clinician, current_user, own_assessment, graph, _clinician_can_see
from .plan import ACTIONS
from .care import _tell

router = APIRouter()
WEEKS = 12
MAX_GOALS = 3
# goals that have a number worth tracking: (key, en, ar, min, max, better)
MEASURES = {
    "sleep_loss": ("sleep_h", "Average sleep (hours a night)", "متوسط النوم (ساعات في الليلة)", 3, 12, "higher"),
    "smoking": ("cigs_per_day", "Cigarettes a day", "عدد السجائر يومياً", 0, 80, "lower"),
    "waterpipe": ("sessions", "Shisha sessions this week", "جلسات الشيشة هذا الأسبوع", 0, 30, "lower"),
    "obesity": ("weight_kg", "Weight (kg)", "الوزن (كغ)", 40, 250, "lower"),
    "sedentary": ("active_days", "Days with 30+ minutes of walking", "أيام مشي ٣٠ دقيقة أو أكثر", 0, 7, "higher"),
    "alcohol": ("drinks", "Drinks this week", "عدد المشروبات هذا الأسبوع", 0, 60, "lower"),
    "screen_night": ("nights", "Nights the phone was away an hour before sleep", "ليالٍ أبعدت فيها الهاتف قبل النوم بساعة", 0, 7, "higher"),
    "tight_underwear": ("days", "Days in loose cotton underwear", "أيام بملابس داخلية قطنية فضفاضة", 0, 7, "higher"),
    "caffeine_late": ("days", "Days with no caffeine after 2 pm", "أيام بلا كافيين بعد الثانية ظهراً", 0, 7, "higher"),
}
ADHERENCE = ["Not this week", "A few days", "Most days", "Every day"]
# goal names in his words, not the clinical factor name
GOALS = {
    "smoking": ("Smoke less, then stop", "قلّل التدخين ثم توقف"), "waterpipe": ("Cut down on shisha", "قلّل الشيشة"),
    "alcohol": ("Keep alcohol low or none", "قلّل الكحول أو امتنع عنه"), "sleep_loss": ("Sleep 7 hours or more", "نَم ٧ ساعات أو أكثر"),
    "obesity": ("Lose 5–10% of body weight", "اخسر ٥–١٠٪ من وزنك"), "sedentary": ("Move more, sit less", "تحرّك أكثر واجلس أقل"),
    "tight_underwear": ("Wear loose cotton underwear", "البس ملابس داخلية قطنية فضفاضة"), "screen_night": ("Phone away an hour before bed", "أبعد الهاتف قبل النوم بساعة"),
    "caffeine_late": ("No caffeine after 2 pm", "لا كافيين بعد الثانية ظهراً"), "psych_stress": ("Ten minutes a day to reset", "عشر دقائق يومياً لتستعيد توازنك"),
    "hot_bath": ("Pause sauna and jacuzzi", "أوقف الساونا والجاكوزي"), "laptop_lap": ("Laptop off your lap", "أبعد الحاسوب عن حضنك"),
    "phone_pocket": ("Phone out of your trouser pocket", "أخرج الهاتف من جيب البنطال"), "western_diet": ("More fish, nuts and vegetables", "مزيد من السمك والمكسرات والخضروات"),
    "late_eating": ("Last meal 2–3 hours before sleep", "آخر وجبة قبل النوم بساعتين إلى ثلاث"), "synthetic_textile": ("Cotton or linen underwear", "ملابس داخلية من القطن أو الكتان"),
    "glycaemic_spikes": ("No sweet drinks after 9 pm", "لا مشروبات محلّاة بعد التاسعة مساءً"), "circadian": ("Keep the same wake-up time", "ثبّت وقت الاستيقاظ"),
}


def _now():
    return time.time()


def _current_week(p):
    if not p["start_at"]:
        return 0
    return min(WEEKS + 1, int((_now() - p["start_at"]) // (7 * 86400)) + 1)


def _items(nodes, lang):
    g = graph()
    out = []
    for n in nodes:
        en, ar = ACTIONS[n]
        m = MEASURES.get(n)
        factor = g.nodes[n].get("label_ar" if lang == "ar" else "label", g.nodes[n]["label"])
        out.append({"node": n, "label": GOALS[n][1 if lang == "ar" else 0] if n in GOALS else factor, "factor": factor,
                    "action": ar if lang == "ar" else en,
                    "measure": {"key": m[0], "label": m[2] if lang == "ar" else m[1], "min": m[3], "max": m[4], "better": m[5]} if m else None})
    return out


def _candidates(row):
    res = security.unseal(row["result"]) or {}
    # only everyday habits; medical items (sleep apnoea, varicocele, medicines) belong with the doctor, not a weekly check-in
    return [x["node"] for x in (res.get("plan", []) + res.get("plan_more", [])) if x["node"] in GOALS]


def _latest(c, user):
    return c.execute("SELECT * FROM plans WHERE user_id=? AND status NOT IN ('stopped') ORDER BY created_at DESC LIMIT 1", (user,)).fetchone()


def plan_view(p, lang="en"):
    if not p:
        return None
    with db.tx() as c:
        rows = c.execute("SELECT * FROM checkins WHERE plan_id=? ORDER BY week", (p["id"],)).fetchall()
    nodes = security.unseal(p["items"])
    checks = {r["week"]: security.unseal(r["data"]) for r in rows}
    week = _current_week(p)
    items = _items(nodes, lang)
    for it in items:
        it["weeks"] = [{"week": w, "adherence": checks.get(w, {}).get("items", {}).get(it["node"], {}).get("adherence"),
                        "value": checks.get(w, {}).get("items", {}).get(it["node"], {}).get("value")} for w in range(1, WEEKS + 1)]
        done = [x["adherence"] for x in it["weeks"] if x["adherence"] is not None]
        recent = done[-4:]
        vals = [x["value"] for x in it["weeks"] if x["value"] is not None]
        it["summary"] = {"weeks_logged": len(done), "recent_adherence": round(sum(recent) / len(recent) / 3, 2) if recent else None,
                         "first": vals[0] if vals else None, "latest": vals[-1] if vals else None}
    status = p["status"]
    if status in ("active", "self_guided") and week > WEEKS:
        status = "completed"
    return {"id": p["id"], "status": status, "assessment_id": p["assessment_id"], "created_at": p["created_at"], "start_at": p["start_at"],
            "week": min(week, WEEKS), "weeks": WEEKS, "items": items, "reminders": bool(p["reminders"]),
            "doctor_note": security.unseal(p["review_note"]), "reviewed_at": p["reviewed_at"],
            "due": status in ("active", "self_guided") and 1 <= week <= WEEKS and week not in checks,
            "energy": [checks.get(w, {}).get("energy") for w in range(1, WEEKS + 1)],
            "adherence_labels": ADHERENCE}


# ------------------------------------------------------------------ patient
@router.get("/api/assessments/{aid}/plan-options")
def plan_options(aid: str, lang: str = "en", user=Depends(current_user)):
    row = own_assessment(aid, user)
    return {"options": _items(_candidates(row), "ar" if lang == "ar" else "en"), "max": MAX_GOALS,
            "doctor_review": bool(row["review_consent"])}


class PlanIn(BaseModel):
    nodes: List[str] = Field(min_length=1, max_length=MAX_GOALS)


@router.post("/api/assessments/{aid}/plan")
def start_plan(aid: str, body: PlanIn, lang: str = "en", user=Depends(current_user)):
    row = own_assessment(aid, user)
    allowed = _candidates(row)
    nodes = list(dict.fromkeys(body.nodes))
    if any(n not in allowed for n in nodes):
        raise HTTPException(400, "Choose goals from your own summary")
    now = _now()
    review = bool(row["review_consent"])
    with db.tx() as c:
        if _latest(c, user) and _latest(c, user)["status"] in ("proposed", "active", "self_guided") and _current_week(_latest(c, user)) <= WEEKS:
            raise HTTPException(409, "You already have a plan running. Stop it first to start a new one.")
        pid = str(uuid.uuid4())
        c.execute("INSERT INTO plans (id, user_id, assessment_id, status, created_at, start_at, items, reminders) VALUES (?,?,?,?,?,?,?,0)",
                  (pid, user, aid, "proposed" if review else "self_guided", now, None if review else now, security.seal(nodes)))
        p = c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
    db.event(aid, "plan_started", ",".join(nodes))
    return plan_view(p, lang)


@router.get("/api/me/plan")
def my_plan(lang: str = "en", user=Depends(current_user)):
    with db.tx() as c:
        p = _latest(c, user)
    return {"plan": plan_view(p, "ar" if lang == "ar" else "en")}


class CheckinIn(BaseModel):
    week: Optional[int] = Field(None, ge=1, le=WEEKS)
    items: Dict[str, Dict[str, Optional[float]]]
    energy: Optional[int] = Field(None, ge=1, le=5)


@router.post("/api/me/plan/checkin")
def checkin(body: CheckinIn, lang: str = "en", user=Depends(current_user)):
    with db.tx() as c:
        p = _latest(c, user)
    if not p or p["status"] not in ("active", "self_guided"):
        raise HTTPException(409, "Your plan starts once a doctor has reviewed it.")
    cur = _current_week(p)
    week = body.week or cur
    if cur > WEEKS and week == cur:
        raise HTTPException(409, "Your 12 weeks are complete. A follow-up check will show what changed.")
    if not (cur - 1 <= week <= cur):
        raise HTTPException(400, "You can record this week or catch up on last week.")
    nodes = security.unseal(p["items"])
    items = {}
    for n, v in body.items.items():
        if n not in nodes:
            raise HTTPException(400, "That goal is not in your plan")
        a = v.get("adherence")
        if a is None or a not in (0, 1, 2, 3):
            raise HTTPException(400, "Choose how the week went for each goal")
        entry = {"adherence": int(a)}
        m = MEASURES.get(n)
        if v.get("value") is not None:
            if not m or not m[3] <= v["value"] <= m[4]:
                raise HTTPException(400, f"{m[1] if m else n}: enter a number between {m[3]} and {m[4]}" if m else "This goal has no number to record")
            entry["value"] = v["value"]
        items[n] = entry
    data = security.seal({"items": items, "energy": body.energy})
    with db.tx() as c:
        if c.execute("UPDATE checkins SET data=?, ts=? WHERE plan_id=? AND week=?", (data, _now(), p["id"], week)).rowcount == 0:
            c.execute("INSERT INTO checkins (plan_id, week, ts, data) VALUES (?,?,?,?)", (p["id"], week, _now(), data))
    db.event(p["assessment_id"], "plan_checkin", str(week))
    return plan_view(p, "ar" if lang == "ar" else "en")


class ReminderIn(BaseModel):
    enabled: bool


@router.post("/api/me/plan/reminders")
def set_reminders(body: ReminderIn, user=Depends(current_user)):
    with db.tx() as c:
        p = _latest(c, user)
        if not p:
            raise HTTPException(404, "No plan")
        c.execute("UPDATE plans SET reminders=? WHERE id=?", (int(body.enabled), p["id"]))
    return {"ok": True}


@router.get("/api/me/plan/reminders.ics")
def reminders_ics(user=Depends(current_user)):
    """A weekly entry that says only 'Weekly check-in', at 8 pm Gulf time, for the rest of the 12 weeks."""
    with db.tx() as c:
        p = _latest(c, user)
    if not p or not p["start_at"]:
        raise HTTPException(404, "Your plan has not started yet")
    gst = timezone(timedelta(hours=4))
    start = datetime.fromtimestamp(p["start_at"], gst) + timedelta(days=7)
    start = start.replace(hour=20, minute=0, second=0, microsecond=0)
    left = max(1, WEEKS - _current_week(p) + 1)
    while start.timestamp() < _now():
        start += timedelta(days=7)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Riaya//Companion//EN",
             "BEGIN:VTIMEZONE", "TZID:Asia/Dubai", "BEGIN:STANDARD", "DTSTART:19700101T000000", "TZOFFSETFROM:+0400", "TZOFFSETTO:+0400",
             "TZNAME:GST", "END:STANDARD", "END:VTIMEZONE",
             "BEGIN:VEVENT", f"UID:{p['id']}-weekly@riaya", f"DTSTAMP:{stamp}", f"DTSTART;TZID=Asia/Dubai:{start.strftime('%Y%m%dT%H%M%S')}",
             "DURATION:PT10M", f"RRULE:FREQ=WEEKLY;COUNT={left}", "SUMMARY:Weekly check-in",
             "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Weekly check-in", "TRIGGER:PT0M", "END:VALARM", "END:VEVENT", "END:VCALENDAR"]
    return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar", headers={"Content-Disposition": "attachment; filename=weekly-check-in.ics"})


@router.delete("/api/me/plan")
def stop_plan(user=Depends(current_user)):
    with db.tx() as c:
        p = _latest(c, user)
        if not p:
            raise HTTPException(404, "No plan")
        c.execute("UPDATE plans SET status='stopped' WHERE id=?", (p["id"],))
    db.event(p["assessment_id"], "plan_stopped")
    return {"ok": True}


# ------------------------------------------------------------------ doctor review
@router.get("/api/clinician/plans")
def plan_queue(clin=Depends(current_clinician)):
    with db.tx() as c:
        rows = c.execute("""SELECT p.* FROM plans p JOIN assessments a ON a.id=p.assessment_id
                            WHERE p.status IN ('proposed','active') AND a.review_consent=1 ORDER BY p.created_at""").fetchall()
    return {"plans": [plan_view(r) for r in rows]}


class PlanReviewIn(BaseModel):
    action: str = Field(pattern="^(approve|change)$")
    remove: List[str] = Field(default_factory=list)
    note: Optional[str] = Field(None, max_length=500)


@router.post("/api/clinician/plans/{pid}")
def review_plan(pid: str, body: PlanReviewIn, clin=Depends(current_clinician)):
    with db.tx() as c:
        p = c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
        if not p or not _clinician_can_see(c, p["assessment_id"]):
            raise HTTPException(404, "Not found or not shared")
        if p["status"] != "proposed":
            raise HTTPException(409, "This plan has already been reviewed")
        nodes = security.unseal(p["items"])
        if body.action == "change":
            if not (body.note or "").strip():
                raise HTTPException(400, "Explain the change so he understands it")
            nodes = [n for n in nodes if n not in body.remove]
            if not nodes:
                raise HTTPException(400, "Keep at least one goal, or approve as proposed")
        now = _now()
        c.execute("UPDATE plans SET status='active', start_at=?, reviewed_by=?, reviewed_at=?, review_note=?, items=? WHERE id=?",
                  (now, clin, now, security.seal((body.note or "").strip() or None), security.seal(nodes), pid))
        _tell(c, p["assessment_id"], "Your 12-week plan has been reviewed by a doctor and starts today. Open My journey to see it.",
              "راجع طبيب خطتك لمدة ١٢ أسبوعاً وتبدأ اليوم. افتح «مساري» لرؤيتها.")
    db.audit(clin, f"plan_{body.action}", p["assessment_id"])
    return {"ok": True}
