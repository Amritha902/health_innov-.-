"""Explained findings, missing-data awareness, contradiction checks and what-if scenarios.

Every finding is a card with five parts, so nothing is a black box:
  observation  - what we saw, and where it came from
  relevance    - the pathway in the evidence graph that links it to reproductive health
  evidence     - grade of the weakest link on that pathway, and the sources
  recommendation - one concrete step
  limitation   - what this observation can and cannot tell
"""
from . import features, obs_ar
from .knowledge import graph
from .plan import ACTIONS

LIMITS = {
    "watch": ("Consumer wearables estimate this. They do not diagnose a condition.", "الأجهزة القابلة للارتداء تقدّر هذا ولا تشخّص حالة."),
    "cgm": ("Glucose-sensor patterns are for screening, not a diabetes diagnosis.", "أنماط جهاز السكر للفحص الأولي وليست تشخيصاً للسكري."),
    "lab": ("One result. Values vary from test to test, so a repeat confirms it.", "نتيجة واحدة. القيم تتفاوت، والفحص المتكرر يؤكدها."),
    "home_test": ("Home tests check count and movement only, and need lab confirmation.", "الفحوصات المنزلية تقيس العدد والحركة فقط وتحتاج تأكيداً مخبرياً."),
    "questionnaire": ("Based on your own answers.", "مبني على إجاباتك."),
    "STOP-Bang": ("A screening questionnaire. Many people who score high do not have sleep apnoea.", "استبيان فحص أولي. كثير ممن يحصلون على درجة عالية لا يعانون انقطاع النفس."),
    "AUDIT-C": ("A screening questionnaire for drinking patterns.", "استبيان فحص أولي لأنماط الشرب."),
    "PSS-4": ("A short stress questionnaire; it reflects the last month only.", "استبيان قصير للضغط يعكس الشهر الماضي فقط."),
    "PHQ-2": ("A two-question mood screen, not a diagnosis of depression.", "فحص من سؤالين للمزاج وليس تشخيصاً للاكتئاب."),
    "ADAM": ("Very sensitive but not specific; a blood test is needed.", "حساس جداً لكنه غير محدد؛ يلزم فحص دم."),
}
WEAK = ("The research behind this link is limited (grade {g}). Treat it as a possibility, not a fact.",
        "الأبحاث وراء هذا الرابط محدودة (درجة {g}). تعامل معه كاحتمال وليس حقيقة.")
CLINICAL_STEP = {
    "varicocele": ("A men's health specialist can check whether treatment would help.", "يمكن لمختص صحة الرجل تقييم ما إذا كان العلاج مفيداً."),
    "cryptorchidism": ("Mention this history at any men's health visit.", "اذكر هذا التاريخ في أي زيارة لصحة الرجل."),
    "mumps": ("Mention this history at any men's health visit.", "اذكر هذا التاريخ في أي زيارة لصحة الرجل."),
    "chemo": ("A specialist can advise on testing and options.", "يمكن للمختص تقديم المشورة حول الفحوصات والخيارات."),
    "genetic": ("Genetic counselling can explain options privately.", "يمكن للاستشارة الوراثية شرح الخيارات بسرية."),
    "consanguinity": ("Genetic counselling is available if results suggest it.", "الاستشارة الوراثية متاحة إذا دعت النتائج."),
    "paternal_age": ("Nothing to change; it is useful context for your doctor.", "لا شيء لتغييره؛ معلومة مفيدة لطبيبك."),
    "recent_fever": ("Sperm production recovers over about 3 months; recheck after that.", "يتعافى إنتاج الحيوانات المنوية خلال نحو ٣ أشهر؛ أعد الفحص بعدها."),
    "low_count": ("A lab semen analysis confirms or rules this out.", "تحليل السائل المنوي في المختبر يؤكد ذلك أو ينفيه."),
    "low_motility": ("A lab semen analysis confirms or rules this out.", "تحليل السائل المنوي في المختبر يؤكد ذلك أو ينفيه."),
    "azoospermia": ("A men's health specialist will explain the next tests.", "سيشرح مختص صحة الرجل الفحوصات التالية."),
}


def _lang(pair, lang):
    return pair[1] if lang == "ar" else pair[0]


def cards(result, lang="en", min_value=0.3):
    g = graph()
    out = []
    attribution = result.get("attribution", {})
    for node, value in sorted(result["inputs"].items(), key=lambda kv: -attribution.get(kv[0], 0)):
        n = g.nodes[node]
        if value < min_value or n.get("protective"):
            continue
        prov = result["provenance"].get(node, [])
        paths = g.paths(node)
        path = paths[0] if paths else None
        label = n.get("label_ar" if lang == "ar" else "label", n["label"])
        if path:
            names = [("القدرة على الإنجاب" if lang == "ar" else "fertility potential") if x == "subfertility"
                     else g.nodes[x].get("label_ar" if lang == "ar" else "label", g.nodes[x]["label"]) for x in path["nodes"]]
            relevance = " → ".join(names)
            grade, refs = path["grade"], path["refs"]
        else:
            relevance, grade, refs = "", None, []
        rec = ACTIONS.get(node) or CLINICAL_STEP.get(node)
        sources = list(dict.fromkeys(p["source"] for p in prov))
        limits = [_lang(LIMITS[s], lang) for s in sources if s in LIMITS]
        if grade in ("C", "D"):
            limits.append(_lang(WEAK, lang).format(g=grade))
        out.append({
            "node": node, "label": label, "value": value, "contribution": attribution.get(node, 0),
            "observation": "؛ ".join(obs_ar.translate(p["reason"]) for p in prov) if lang == "ar" else "; ".join(p["reason"] for p in prov),
            "sources": sources,
            "relevance": relevance, "grade": grade,
            "evidence": [{"key": r, "text": g.refs[r]} for r in refs],
            "recommendation": _lang(rec, lang) if rec else None,
            "limitations": limits,
            "modifiable": bool(n.get("modifiable")),
        })
    return out


DOMAINS = [
    ("body", "Weight and waist", "الوزن والخصر"),
    ("sleep", "Sleep", "النوم"),
    ("activity", "Activity", "النشاط"),
    ("substances", "Smoking, shisha, alcohol, steroids", "التدخين والشيشة والكحول والمنشطات"),
    ("breathing", "Breathing during sleep", "التنفس أثناء النوم"),
    ("mood", "Mood and stress", "المزاج والضغط"),
    ("metabolic", "Blood sugar", "سكر الدم"),
    ("hormones", "Hormones", "الهرمونات"),
    ("semen", "Semen analysis", "تحليل السائل المنوي"),
]


def data_coverage(answers, wearable, semen, labs, lang="en"):
    """For each domain: measured (device or lab), reported (his answers), not answered, or not measured.
    Unknown is never shown as normal."""
    w, a, lv = wearable or {}, answers or {}, (labs or {}).get("values", {})
    has = lambda *ks: any(a.get(k) not in (None, "", "skip", []) for k in ks)
    status = {
        "body": "reported" if has("height_cm", "weight_kg") else "not_answered",
        "sleep": "measured" if w.get("sleep_avg_h") else "reported" if has("sleep_h") else "not_answered",
        "activity": "measured" if w.get("steps_avg") else "reported" if has("sitting_h", "exercise_days") else "not_answered",
        "substances": "reported" if has("smoking", "waterpipe", "audit1", "aas") else "not_answered",
        "breathing": "measured" if w.get("spo2_low_nights") is not None else "reported" if has("snore", "tired") else "not_answered",
        "mood": "reported" if has("phq1", "phq2", "pss1") else "not_answered",
        "metabolic": "measured" if (w.get("glucose_readings") or lv.get("hba1c") is not None) else "reported" if has("diabetes") else "not_answered",
        "hormones": "measured" if any(lv.get(k) is not None for k in ("testosterone", "fsh", "lh")) else "not_measured",
        "semen": "measured" if semen and semen.get("source") == "lab" else "screened" if semen else "not_measured",
    }
    words = {"measured": ("Measured", "مُقاس"), "screened": ("Home screen only", "فحص منزلي فقط"), "reported": ("From your answers", "من إجاباتك"),
             "not_answered": ("Not answered", "لم تتم الإجابة"), "not_measured": ("Not measured yet", "لم يُقس بعد")}
    return [{"domain": d, "label": en if lang != "ar" else ar, "status": status[d], "status_text": _lang(words[status[d]], lang)} for d, en, ar in DOMAINS]


def contradictions(answers, wearable, semen, labs, lang="en"):
    """Disagreements between what he reported and what devices or labs show. One fixed rule applies to scoring: a measured value
    (device or lab) is used over a self-report. Every disagreement is still shown to him and the clinician for discussion; none is hidden."""
    a, w, lv = answers or {}, wearable or {}, (labs or {}).get("values", {})
    out = []

    def add(key, en, ar, severity="info"):
        out.append({"key": key, "text": ar if lang == "ar" else en, "severity": severity})

    try:
        if w.get("sleep_avg_h") and a.get("sleep_h") not in (None, "", "skip") and abs(float(a["sleep_h"]) - w["sleep_avg_h"]) >= 1.5:
            add("sleep", f"Reported sleep ({a['sleep_h']} h) differs from the watch ({w['sleep_avg_h']} h). The score uses the measured value; worth checking which reflects a typical week.",
                f"النوم المُبلّغ ({a['sleep_h']} س) يختلف عن الساعة ({w['sleep_avg_h']} س). يعتمد التقييم على القيمة المقاسة؛ يستحق التأكد أيهما يعكس أسبوعاً معتاداً.")
    except (TypeError, ValueError):
        pass
    a1c = lv.get("hba1c")
    if a1c is not None and a1c >= 6.5 and a.get("diabetes") in ("no", None):
        add("diabetes", f"HbA1c {a1c}% is in the diabetes range, but no diabetes was reported. Worth confirming with a doctor.",
            f"السكر التراكمي {a1c}٪ في نطاق السكري، لكن لم يُذكر السكري. يستحق التأكيد مع طبيب.", "review")
    t, lh = lv.get("testosterone"), lv.get("lh")
    if t is not None and lv.get("testosterone_unit") == "ng/dL":
        t = t / 28.84
    if t is not None and t < 8 and lh is not None and lh < 1.5 and a.get("aas") in ("never", None):
        add("hormones", "Low testosterone with very low LH is the pattern seen with outside testosterone or steroid use, which was not reported. A clinician should ask, without judgement.",
            "انخفاض التستوستيرون مع انخفاض شديد في LH هو النمط المرتبط باستخدام تستوستيرون أو منشطات خارجية، ولم يُذكر ذلك. ينبغي أن يسأل الطبيب دون أحكام.", "review")
    try:
        if w.get("steps_avg") and w["steps_avg"] < 4000 and a.get("sitting_h") not in (None, "", "skip") and float(a["sitting_h"]) <= 4:
            add("activity", f"Few hours of sitting were reported, but the watch shows {int(w['steps_avg'])} steps a day.",
                f"أُبلغ عن ساعات جلوس قليلة، لكن الساعة تُظهر {int(w['steps_avg'])} خطوة يومياً.")
    except (TypeError, ValueError):
        pass
    if w.get("alcohol_drinks_per_week") and a.get("audit1") in (0, "0"):
        add("alcohol", "No drinking was reported, but drinks are logged in the Health app.", "لم يُذكر الشرب، لكن توجد مشروبات مسجلة في تطبيق الصحة.")
    if semen and semen.get("source") == "home_test" and semen.get("normal") and (labs or {}).get("findings"):
        add("tests", "The home test looked normal, but blood tests show abnormal hormones. Home tests can miss problems.",
            "بدا الفحص المنزلي طبيعياً، لكن تحاليل الدم تُظهر هرمونات غير طبيعية. قد تفوت الفحوصات المنزلية بعض المشكلات.", "review")
    return out


def what_if(answers, wearable, semen, labs, improve, lang="en"):
    """Educational scenario: how much of today's signal comes from the factors he chooses to change.
    It is not a prediction of his fertility."""
    g = graph()
    inputs, _, _ = features.build_inputs(answers, wearable, semen, labs)
    # test results (semen outcomes) are facts, not levers: the scenario looks only at habits and health factors
    inputs = {k: v for k, v in inputs.items() if g.nodes[k]["type"] in ("exposure", "condition")}
    allowed = [n for n in improve if n in inputs and g.nodes[n].get("modifiable")]
    before = g.propagate(inputs)["subfertility"]
    changed = {k: v for k, v in inputs.items() if k not in allowed}
    after = g.propagate(changed)["subfertility"]
    from .triage import tier_of
    note = ("Signals from habits and health factors only. An educational scenario based on published links, not a prediction of your fertility."
            if lang != "ar" else "المؤشرات الناتجة عن العادات والعوامل الصحية فقط. سيناريو تثقيفي مبني على روابط منشورة، وليس توقعاً لقدرتك على الإنجاب.")
    return {"improved": allowed, "before": round(before, 3), "after": round(after, 3),
            "before_tier": tier_of(before), "after_tier": tier_of(after),
            "reduction_pct": round(100 * (before - after) / before, 1) if before else 0, "note": note,
            "options": [{"node": k, "label": g.nodes[k].get("label_ar" if lang == "ar" else "label")} for k in inputs if g.nodes[k].get("modifiable") and inputs[k] >= 0.3]}
