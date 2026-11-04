from . import features, ml, plan, synth, triage
from .knowledge import graph

DISCLAIMER = {
    "en": "This is a screening summary, not a diagnosis. It shows signals worth acting on and where to go next.",
    "ar": "هذا ملخص فحص أولي وليس تشخيصاً. يوضح المؤشرات التي تستحق الاهتمام والخطوة التالية المناسبة.",
}


def run(answers, wearable=None, semen=None, with_models=True):
    g = graph()
    inputs, provenance, ins = features.build_inputs(answers, wearable, semen)
    scores = g.score(inputs)
    attribution = g.shapley(inputs)
    decision = triage.decide(answers, ins, scores, semen, g, wearable)
    top, more = plan.build(attribution, g, inputs)
    protective = [{"node": k, "label": g.nodes[k]["label"]} for k in inputs if g.nodes[k].get("protective")]
    result = {
        "disclaimer": DISCLAIMER,
        "triage": decision,
        "scores": scores,
        "inputs": inputs,
        "provenance": provenance,
        "instruments": ins,
        "attribution": attribution,
        "plan": top,
        "plan_more": more,
        "strengths": protective,
        "non_modifiable": [{"node": k, "label": g.nodes[k]["label"]} for k in attribution
                           if g.nodes[k].get("modifiable") is False],
        "semen": semen,
        "wearable": wearable,
    }
    if with_models:
        result["models"] = {"uci_logistic": ml.predict(answers), "simulated_gbm": synth.explain(answers, ins, wearable)}
    return result


TESTS_AR = {
    "Repeat semen analysis": "إعادة تحليل السائل المنوي",
    "FSH, LH, total testosterone (morning)": "هرمونات FSH وLH والتستوستيرون الكلي (صباحاً)",
    "Scrotal examination ± ultrasound": "فحص سريري ± تصوير بالموجات فوق الصوتية",
    "Karyotype and Y-chromosome microdeletion testing (if indicated)": "فحص الكروموسومات والحذف الدقيق في الكروموسوم Y (عند الحاجة)",
    "Repeat semen analysis after 2–7 days abstinence": "إعادة تحليل السائل المنوي بعد امتناع ٢–٧ أيام",
    "Semen analysis (should happen at the first visit, alongside your wife's assessment)": "تحليل السائل المنوي (في الزيارة الأولى، بالتزامن مع فحص زوجتك)",
    "FSH, LH, total testosterone": "هرمونات FSH وLH والتستوستيرون الكلي",
    "Semen analysis": "تحليل السائل المنوي",
    "Urine / swab test for common infections": "فحص بول / مسحة للالتهابات الشائعة",
    "Total testosterone (7–11 am)": "التستوستيرون الكلي (٧–١١ صباحاً)",
    "HbA1c": "السكر التراكمي HbA1c",
    "Lipid profile": "الدهون في الدم",
    "Baseline semen analysis": "تحليل أساسي للسائل المنوي",
}
NOTES_AR = {
    "One result": "نتيجة واحدة لا تكفي. تتفاوت النتائج كثيراً؛ وتُؤكَّد أي نتيجة غير طبيعية بفحص متكرر بعد نحو ٣ أشهر.",
    "Home devices": "الأجهزة المنزلية تقيس العدد والحركة فقط (لا الشكل ولا الحجم ولا الحمض النووي). أكّد أي نتيجة منخفضة في المختبر.",
    "Home tests": "الفحوصات المنزلية تقيس جزءاً فقط من التحليل. النتيجة الطبيعية لا تنفي كل شيء، والنتيجة المنخفضة تحتاج تأكيداً في المختبر.",
    "Abstinence": "الامتناع لأقل من يومين أو أكثر من ٧ أيام قد يغيّر النتائج؛ وقد تلزم إعادة الفحص.",
}


def _tr_note(n, lang):
    if lang != "ar":
        return n
    return next((v for k, v in NOTES_AR.items() if n.startswith(k)), n)


USER_TERMS = {"subfertility": {"en": "Fertility potential", "ar": "القدرة على الإنجاب"}}


def _path(p, lang, g):
    """User-facing wording: the end point reads 'fertility potential', never a diagnosis label."""
    if not p:
        return p
    key = "label_ar" if lang == "ar" else "label"
    return dict(p, labels=[USER_TERMS.get(n, {}).get(lang) or g.nodes[n].get(key, g.nodes[n]["label"]) for n in p["nodes"]])


def user_view(result, lang="en"):
    g = graph()
    lab = lambda n: g.nodes[n].get("label_ar" if lang == "ar" else "label", g.nodes[n]["label"])
    """What the man sees: no scores, no 'risk', no diagnosis language."""
    t = result["triage"]
    signal_words = {"low": {"en": "A few signals", "ar": "مؤشرات قليلة"},
                    "moderate": {"en": "Some signals worth acting on", "ar": "بعض المؤشرات التي تستحق الاهتمام"},
                    "high": {"en": "Several signals — a check-up is a smart move", "ar": "عدة مؤشرات — الفحص خطوة ذكية"}}
    return {
        "disclaimer": result["disclaimer"][lang],
        "summary": signal_words[t["tier"]][lang],
        "next_step": t["message"][lang],
        "level": t["level"],
        "immediate": t["immediate"],
        "under_review": t["requires_review"],
        "plan": [{"label": lab(p["node"]), "action": p["action_" + lang], "why": _path(p["why"], lang, g)} for p in result["plan"]],
        "more": [{"label": lab(p["node"]), "action": p["action_" + lang]} for p in result["plan_more"]],
        "strengths": [{"node": s["node"], "label": lab(s["node"])} for s in result["strengths"]],
        "tests": [TESTS_AR.get(x, x) if lang == "ar" else x for x in t["tests"]],
        "parallel": t["parallel"],
        "semen_notes": [_tr_note(n, lang) for n in (result.get("semen") or {}).get("notes", [])],
    }
