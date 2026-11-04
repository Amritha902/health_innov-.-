"""Lab Intelligence: keeps every confirmed result, judges each one against the range its own lab printed,
checks how the sample was collected, lines results up over time, and lets a doctor reconcile what was read.

Nothing here diagnoses. A single result outside the range is described as a reason to repeat or discuss,
following WHO 2021 (semen), AUA 2018 and the Endocrine Society 2018 (testosterone), and ADA (HbA1c)."""
import time
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import db, security
from .labreport import FIELDS
from .main import current_clinician, current_user, _clinician_can_see

router = APIRouter()

# Used only when the report printed no range. Semen limits are the WHO 2021 5th centiles.
DEFAULT_REF = {
    "volume_ml": (1.4, None), "concentration_m_per_ml": (16, None), "total_count_m": (39, None),
    "progressive_motility_pct": (30, None), "total_motility_pct": (42, None), "normal_forms_pct": (4, None),
    "vitality_pct": (54, None), "ph": (7.2, None), "testosterone": (10.4, None), "fsh": (1.5, 12.4), "lh": (1.7, 8.6),
    "hba1c": (None, 5.7), "vitamin_d": (20, None),
}
HIGHER_BETTER = {"volume_ml", "concentration_m_per_ml", "total_count_m", "progressive_motility_pct", "total_motility_pct",
                 "normal_forms_pct", "vitality_pct", "testosterone", "vitamin_d"}
LOWER_BETTER = {"hba1c"}
SEMEN = {f for f, v in FIELDS.items() if v[4] == "semen" and f != "abstinence_days"}
NAMES = {
    "volume_ml": ("Semen volume", "حجم السائل المنوي"), "concentration_m_per_ml": ("Sperm concentration", "تركيز الحيوانات المنوية"),
    "total_count_m": ("Total sperm count", "العدد الكلي للحيوانات المنوية"), "progressive_motility_pct": ("Progressive motility", "الحركة التقدمية"),
    "total_motility_pct": ("Total motility", "الحركة الكلية"), "normal_forms_pct": ("Normal forms", "الأشكال الطبيعية"),
    "vitality_pct": ("Vitality", "الحيوية"), "ph": ("pH", "درجة الحموضة"), "testosterone": ("Total testosterone", "التستوستيرون الكلي"),
    "fsh": ("FSH", "الهرمون المنبه للجريب FSH"), "lh": ("LH", "الهرمون الملوتن LH"), "hba1c": ("HbA1c", "السكر التراكمي HbA1c"),
    "vitamin_d": ("Vitamin D", "فيتامين د"),
}
TEXT = {
    "abstinence": ("Abstinence was {d:g} days. WHO 2021 asks for 2–7 days, so this result may not represent you.",
                   "كانت فترة الامتناع {d:g} أيام. توصي منظمة الصحة العالمية (٢٠٢١) بـ ٢–٧ أيام، لذا قد لا تمثّل هذه النتيجة حالتك."),
    "fever": ("A fever in the 3 months before the test can lower sperm results for a while. A repeat after recovery gives a truer picture.",
              "الحمّى خلال الأشهر الثلاثة السابقة قد تخفض نتائج الحيوانات المنوية مؤقتاً. إعادة الفحص بعد التعافي تعطي صورة أدق."),
    "late": ("Taken at {t}. Testosterone is highest in the early morning, so guidelines use a sample taken before 10 am.",
             "أُخذت العينة الساعة {t}. يكون التستوستيرون في أعلى مستوياته صباحاً، لذا تعتمد الإرشادات عينة قبل العاشرة صباحاً."),
    "nonfasting": ("Not fasting. Guidelines prefer a fasting morning sample for testosterone.",
                   "العينة لم تكن صائمة. تفضّل الإرشادات عينة صباحية صائمة للتستوستيرون."),
    "repeat_semen": ("One semen result outside the range is not a diagnosis. Guidelines advise a second test, ideally 2–3 months later.",
                     "نتيجة واحدة خارج المعدل ليست تشخيصاً. تنصح الإرشادات بفحص ثانٍ، ويفضّل بعد ٢–٣ أشهر."),
    "repeat_t": ("A low testosterone result is confirmed with a second early-morning test before any diagnosis.",
                 "يُؤكَّد انخفاض التستوستيرون بفحص صباحي ثانٍ قبل أي تشخيص."),
    "mixed_labs": ("These results come from different labs. Each one is judged against its own lab's range.",
                   "هذه النتائج من مختبرات مختلفة. تُقارن كل نتيجة بمعدل مختبرها."),
}


def _t(key, lang, **kw):
    en, ar = TEXT[key]
    return (ar if lang == "ar" else en).format(**kw)


def status(field, value, ref):
    low, high = (ref.get("low"), ref.get("high")) if ref else DEFAULT_REF.get(field, (None, None))
    if field == "hba1c" and value is not None:
        return "high" if value >= 6.5 else "borderline" if value >= 5.7 else "normal"
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def context_notes(field, ctx, lang):
    out = []
    if field in SEMEN:
        d = ctx.get("abstinence_days")
        if d is not None and not 2 <= d <= 7:
            out.append(_t("abstinence", lang, d=d))
        if ctx.get("fever_recent"):
            out.append(_t("fever", lang))
    if field == "testosterone":
        tm = ctx.get("time")
        if tm and tm >= "10:00":
            out.append(_t("late", lang, t=tm))
        if ctx.get("fasting") is False:
            out.append(_t("nonfasting", lang))
    return out


# ------------------------------------------------------------------ storage
class LabValue(BaseModel):
    field: str
    value: float
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    ref_text: Optional[str] = Field(None, max_length=40)
    extracted_value: Optional[float] = None
    score: Optional[float] = None
    line: Optional[str] = Field(None, max_length=240)
    lab_flag: Optional[str] = Field(None, max_length=10)


class LabSaveIn(BaseModel):
    assessment_id: Optional[str] = None
    collected_on: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    lab_name: Optional[str] = Field(None, max_length=80)
    source: str = Field("report", pattern="^(report|manual)$")
    abstinence_days: Optional[float] = Field(None, ge=0, le=60)
    time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    fasting: Optional[bool] = None
    fever_recent: Optional[bool] = None
    values: List[LabValue] = Field(min_length=1, max_length=20)


def _row_view(r, lang="en", clinician=False):
    d = security.unseal(r["data"])
    rev = d.get("review") or {}
    value = rev.get("value", d["value"]) if r["review_status"] == "corrected" else d["value"]
    ref = d.get("ref")
    unit = FIELDS[d["field"]][3]
    out = {"id": r["id"], "field": d["field"], "name": NAMES.get(d["field"], (d["field"], d["field"]))[1 if lang == "ar" else 0],
           "value": value, "unit": unit, "date": r["collected_on"], "ref": ref,
           "ref_used": "lab" if ref and (ref.get("low") is not None or ref.get("high") is not None) else "typical",
           "status": status(d["field"], value, ref), "lab_flag": d.get("lab_flag"), "source": d.get("source"),
           "lab_name": d.get("lab_name"), "context": d.get("context", {}), "notes": context_notes(d["field"], d.get("context", {}), lang),
           "review_status": r["review_status"], "review_note": rev.get("note"), "edited_by_user": d.get("edited_by_user", False),
           "assessment_id": r["assessment_id"]}
    if clinician:
        out.update({"line": d.get("line"), "score": d.get("score"), "extracted_value": d.get("extracted_value"), "original_value": d["value"]})
    return out


@router.post("/api/me/labs")
def save_labs(body: LabSaveIn, user=Depends(current_user)):
    """He saves values he has checked against his report. A doctor can later accept, correct or set aside each one."""
    if body.assessment_id:
        with db.tx() as c:
            if not c.execute("SELECT 1 FROM assessments WHERE id=? AND user_id=?", (body.assessment_id, user)).fetchone():
                raise HTTPException(404, "Not found")
    ctx = {k: v for k, v in {"abstinence_days": body.abstinence_days, "time": body.time, "fasting": body.fasting,
                             "fever_recent": body.fever_recent}.items() if v is not None}
    saved, now = [], time.time()
    with db.tx() as c:
        for v in body.values:
            if v.field not in FIELDS or v.field == "abstinence_days":
                raise HTTPException(400, f"Unknown test: {v.field}")
            lo, hi = FIELDS[v.field][2]
            if not lo <= v.value <= hi:
                raise HTTPException(400, f"{NAMES[v.field][0]}: {v.value:g} is outside what a lab can report ({lo}–{hi} {FIELDS[v.field][3]}). Check the number and unit.")
            if v.ref_low is not None and v.ref_high is not None and v.ref_low >= v.ref_high:
                raise HTTPException(400, f"{NAMES[v.field][0]}: the range's lower limit must be below its upper limit.")
            ref = {"low": v.ref_low, "high": v.ref_high, "text": v.ref_text} if v.ref_low is not None or v.ref_high is not None else None
            data = {"field": v.field, "value": v.value, "ref": ref, "context": ctx, "source": body.source, "lab_name": body.lab_name,
                    "line": v.line, "score": v.score, "lab_flag": v.lab_flag, "extracted_value": v.extracted_value,
                    "edited_by_user": v.extracted_value is not None and abs(v.extracted_value - v.value) > 1e-9}
            rid = str(uuid.uuid4())
            c.execute("INSERT INTO lab_results (id, user_id, assessment_id, collected_on, created_at, review_status, data) VALUES (?,?,?,?,?,?,?)",
                      (rid, user, body.assessment_id, body.collected_on or time.strftime("%Y-%m-%d"), now, "pending", security.seal(data)))
            saved.append(rid)
    if body.assessment_id:
        db.event(body.assessment_id, "labs_saved", str(len(saved)))
    return {"saved": saved}


def timeline(user, lang="en", clinician=False):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM lab_results WHERE user_id=? ORDER BY collected_on, created_at", (user,)).fetchall()
    series = {}
    for r in rows:
        v = _row_view(r, lang, clinician)
        series.setdefault(v["field"], []).append(v)
    out = []
    for field in [f for f in FIELDS if f in series]:
        pts = series[field]
        used = [p for p in pts if p["review_status"] != "rejected"]
        latest = used[-1] if used else None
        prev = used[-2] if len(used) > 1 else None
        change = None
        if latest and prev:
            diff = latest["value"] - prev["value"]
            direction = "better" if (diff > 0 and field in HIGHER_BETTER) or (diff < 0 and field in LOWER_BETTER) else \
                        "worse" if (diff < 0 and field in HIGHER_BETTER) or (diff > 0 and field in LOWER_BETTER) else "changed"
            change = {"diff": round(diff, 2), "pct": round(100 * diff / prev["value"], 1) if prev["value"] else None,
                      "direction": direction if abs(diff) > 1e-9 else "same", "since": prev["date"]}
        advice = []
        if latest and latest["status"] != "normal":
            out_of_range = [p for p in used if p["status"] != "normal"]
            if field in SEMEN and len(out_of_range) == 1:
                advice.append(_t("repeat_semen", lang))
            if field == "testosterone" and latest["status"] == "low" and len(out_of_range) == 1:
                advice.append(_t("repeat_t", lang))
        if len({(p["lab_name"] or "", (p["ref"] or {}).get("text") or "") for p in used}) > 1:
            advice.append(_t("mixed_labs", lang))
        out.append({"field": field, "name": pts[0]["name"], "unit": pts[0]["unit"], "points": pts, "latest": latest,
                    "change": change, "advice": advice, "higher_is_better": field in HIGHER_BETTER, "lower_is_better": field in LOWER_BETTER})
    pending = sum(1 for r in rows if r["review_status"] == "pending")
    return {"series": out, "pending_review": pending,
            "note": "معلومات فحص أولي وليست تشخيصاً. تختلف المعدلات بين المختبرات، وتُقارن كل نتيجة بالمعدل المطبوع على تقريرها." if lang == "ar" else
                    "Screening information, not a diagnosis. Ranges differ between labs; each result is compared with the range printed on its own report."}


@router.get("/api/me/labs")
def my_labs(lang: str = "en", user=Depends(current_user)):
    return timeline(user, "ar" if lang == "ar" else "en")


@router.delete("/api/me/labs/{rid}")
def delete_lab(rid: str, user=Depends(current_user)):
    with db.tx() as c:
        if not c.execute("DELETE FROM lab_results WHERE id=? AND user_id=?", (rid, user)).rowcount:
            raise HTTPException(404, "Not found")
    return {"ok": True}


# ------------------------------------------------------------------ doctor reconciliation
def _visible_user(c, aid):
    row = _clinician_can_see(c, aid)
    return row["user_id"] if row else None


@router.get("/api/clinician/cases/{aid}/labs")
def case_labs(aid: str, clin=Depends(current_clinician)):
    with db.tx() as c:
        uid = _visible_user(c, aid)
    if not uid:
        raise HTTPException(404, "Not found or not shared")
    db.audit(clin, "view_labs", aid)
    return timeline(uid, clinician=True)


@router.get("/api/clinician/labs/pending")
def pending_labs(clin=Depends(current_clinician)):
    with db.tx() as c:
        rows = c.execute("""SELECT l.* FROM lab_results l JOIN assessments a ON a.id=l.assessment_id
                            WHERE l.review_status='pending' AND a.review_consent=1 ORDER BY l.created_at""").fetchall()
    return {"results": [_row_view(r, clinician=True) for r in rows]}


class ReconcileIn(BaseModel):
    action: str = Field(pattern="^(accept|correct|reject)$")
    value: Optional[float] = None
    note: Optional[str] = Field(None, max_length=300)


@router.post("/api/clinician/labs/{rid}")
def reconcile(rid: str, body: ReconcileIn, clin=Depends(current_clinician)):
    with db.tx() as c:
        r = c.execute("SELECT * FROM lab_results WHERE id=?", (rid,)).fetchone()
        if not r or not r["assessment_id"] or not _visible_user(c, r["assessment_id"]):
            raise HTTPException(404, "Not found or not shared")
        d = security.unseal(r["data"])
        if body.action != "accept" and not (body.note or "").strip():
            raise HTTPException(400, "Add a short reason so he understands the change")
        if body.action == "correct":
            lo, hi = FIELDS[d["field"]][2]
            if body.value is None or not lo <= body.value <= hi:
                raise HTTPException(400, f"Enter the value as printed on the report ({lo}–{hi} {FIELDS[d['field']][3]})")
        d["review"] = {"by": clin, "at": time.time(), "note": (body.note or "").strip() or None,
                       **({"value": body.value} if body.action == "correct" else {})}
        c.execute("UPDATE lab_results SET review_status=?, data=? WHERE id=?",
                  ({"accept": "accepted", "correct": "corrected", "reject": "rejected"}[body.action], security.seal(d), rid))
    db.audit(clin, f"lab_{body.action}", r["assessment_id"])
    return {"ok": True}
