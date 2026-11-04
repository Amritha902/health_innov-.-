"""Care navigation: the structured package that goes from triage to the receiving clinic.

A FHIR R4 'document' Bundle whose Composition is the referral letter. Its sections are written so
the receiving clinician does not have to re-take the history or repeat tests that are already valid:
  reason for referral · screening summary · results already available (with source and date) ·
  investigations requested · genomic flag · patient preferences and consent scope · reviewing clinician
"""
import uuid
from datetime import datetime, timezone

from . import ifhas
from .knowledge import graph

RECEIVER = {
    "andrology": "Andrology / Urology clinic",
    "urgent_specialist": "Urology (urgent)",
    "fertility_services": "Fertility centre (couple assessment)",
    "primary_care": "Family medicine / IFHAS screening provider",
    "same_day_primary": "Primary care (same day)",
    "emergency": "Emergency department",
    "self_care": "No referral",
}
LANG = {"ar": "Arabic", "en": "English", "ur": "Urdu", "hi": "Hindi", "ml": "Malayalam", "other": "Other"}


def _section(title, lines):
    html = "<div xmlns=\"http://www.w3.org/1999/xhtml\"><ul>" + "".join(f"<li>{_e(x)}</li>" for x in lines) + "</ul></div>"
    return {"title": title, "text": {"status": "generated", "div": html}, "lines": lines}


def _e(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(answers, result, referral, reviewer=None):
    g = graph()
    t = result["triage"]
    final = (referral or {}).get("final_level") or t["level"]
    ins = result["instruments"]
    sem, labs = result.get("semen") or {}, result.get("labs") or {}
    now = datetime.now(timezone.utc).isoformat()

    reason = [r["reason"] for r in t["reasons"]] or ["Self-referral for a men's reproductive-health check"]
    summary = [f"Age {answers.get('age')}", f"BMI {ins.get('bmi')}" if ins.get("bmi") else None,
               f"STOP-Bang {ins.get('stop_bang')}/8", f"AUDIT-C {ins['audit_c']}/12" if "audit_c" in ins else None,
               f"PSS-4 {ins['pss4']}/16" if "pss4" in ins else None, f"PHQ-2 {ins['phq2']}/6" if "phq2" in ins else None,
               f"ADAM {'positive' if ins.get('adam_positive') else 'negative'}" if "adam_positive" in ins else None]
    summary = [x for x in summary if x]
    top = list(result.get("attribution", {}).items())[:5]
    summary += [f"Main modifiable signal: {g.nodes[k]['label']} (contribution {v:.2f})" for k, v in top if g.nodes[k].get("modifiable")]
    if answers.get("months_trying"):
        summary.append(f"Trying to conceive for {answers['months_trying']} months" + (f"; wife's age {answers['partner_age']}" if answers.get("partner_age") else ""))

    available = []
    if sem:
        vals = sem.get("values") or {}
        src = "laboratory" if sem.get("source") == "lab" else f"home device ({sem.get('kit')}) — screening only, needs lab confirmation"
        available.append(f"Semen ({src}): " + (", ".join(f"{k} {v}" for k, v in vals.items() if k not in ("source", "kit")) or "see findings"))
        available += [f"  finding: {f[1]}" for f in sem.get("findings", [])]
    for name, value, date in labs.get("already_done", []):
        available.append(f"{name}: {value}" + (f" ({date})" if date else "") + " — valid, do not repeat unless clinically indicated")
    w = result.get("wearable") or {}
    if w:
        bits = [f"{k.replace('_', ' ')} {w[k]}" for k in ("sleep_avg_h", "steps_avg", "social_jetlag_h", "spo2_low_nights", "night_glucose_high_pct", "glucose_cv") if w.get(k) is not None]
        available.append(f"Device summary ({', '.join(w.get('sources', []))}): " + "; ".join(bits))
    if not available:
        available = ["No prior results."]

    requested = t["tests"] or ["Clinical assessment"]
    genomic = t.get("genomic") or {"flag": False}
    gen_lines = (genomic["reasons"] + [f"Suggested: {x}" for x in genomic["tests"]] + ["Offer genetic counselling before and after testing."]) if genomic.get("flag") else ["No genetic flag."]

    prefs = [f"Preferred language: {LANG.get(answers.get('pref_language'), 'not stated')}",
             f"Doctor preference: {'male doctor' if answers.get('pref_clinician') == 'male' else 'none stated'}",
             "Contact: " + ("through the Riaya app only — no phone calls or SMS" if answers.get("pref_contact") == "app_only" else "patient will contact the clinic"),
             "Consent: shared by the patient for this referral only. Do not forward to family, employer or insurer without his consent.",
             "Screening summary, not a diagnosis."]
    signoff = [f"Reviewed and approved by {reviewer or (referral or {}).get('reviewer') or 'pending review'} on {now[:10]}",
               f"Suggested level {t['level']} → final level {final}"]

    sections = [_section("Reason for referral", reason), _section("Screening summary", summary),
                _section("Results already available", available), _section("Investigations requested", requested),
                _section("Genomic flag", gen_lines), _section("Patient preferences and consent", prefs),
                _section("Clinical review", signoff)]

    comp_id = str(uuid.uuid4())
    composition = {"resourceType": "Composition", "id": comp_id, "status": "final" if (referral or {}).get("reviewed_at") else "preliminary",
                   "type": {"coding": [{"system": "http://loinc.org", "code": "57133-1", "display": "Referral note"}]},
                   "date": now, "title": f"Referral to {RECEIVER.get(final, final)}",
                   "author": [{"display": reviewer or "Riaya triage service"}],
                   "section": [{k: v for k, v in s.items() if k != "lines"} for s in sections]}
    base = ifhas.bundle(answers, result)
    for e in base["entry"]:
        if e["resource"]["resourceType"] == "ServiceRequest":
            sr = e["resource"]
            sr["status"] = "active" if (referral or {}).get("reviewed_at") else "draft"
            sr["code"]["coding"][0]["code"] = final
            sr["performerType"] = {"text": RECEIVER.get(final, final)}
            sr["priority"] = "urgent" if t.get("rapid_review") else sr["priority"]
    bundle = {"resourceType": "Bundle", "id": str(uuid.uuid4()), "type": "document", "timestamp": now,
              "entry": [{"fullUrl": f"urn:uuid:{comp_id}", "resource": composition}] + base["entry"]}
    letter = {"to": RECEIVER.get(final, final), "date": now[:10], "sections": [{"title": s["title"], "lines": s["lines"]} for s in sections]}
    return {"bundle": bundle, "letter": letter}
