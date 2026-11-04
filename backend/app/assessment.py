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


def user_view(result, lang="en"):
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
        "plan": [{"label": p["label"], "action": p["action_" + lang], "why": p["why"]} for p in result["plan"]],
        "more": [{"label": p["label"], "action": p["action_" + lang]} for p in result["plan_more"]],
        "strengths": result["strengths"],
        "tests": t["tests"],
        "parallel": t["parallel"],
        "semen_notes": (result.get("semen") or {}).get("notes", []),
    }
