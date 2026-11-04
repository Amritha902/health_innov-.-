"""Hand-off to the IFHAS reproductive-health screening visit (and any EMR) as a FHIR R4 Bundle.

The man decides whether to hand this over (as a file, a QR code at the clinic, or a one-time share code).
No identifiers are included: the clinic links it to his record at the visit.
Field mapping to the official IFHAS reproductive-health questionnaire is to be confirmed with ADPHC;
LOINC codes are used only where the code is standard, otherwise a local code system is used.
"""
import uuid
from datetime import datetime, timezone

LOCAL = "https://riaya.health/fhir/CodeSystem/screening"
LOINC = "http://loinc.org"


def _obs(code, system, display, value, unit=None):
    o = {"resourceType": "Observation", "id": str(uuid.uuid4()), "status": "final",
         "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "survey"}]}],
         "code": {"coding": [{"system": system, "code": code, "display": display}]}}
    if isinstance(value, (int, float)):
        o["valueQuantity"] = {"value": value, **({"unit": unit} if unit else {})}
    else:
        o["valueString"] = str(value)
    return o


def bundle(answers, result, created_at=None):
    ins, t = result["instruments"], result["triage"]
    when = created_at or datetime.now(timezone.utc).isoformat()
    obs = []
    if ins.get("bmi"):
        obs.append(_obs("39156-5", LOINC, "Body mass index", ins["bmi"], "kg/m2"))
    for k, code, disp, unit in (("height_cm", "8302-2", "Body height", "cm"), ("weight_kg", "29463-7", "Body weight", "kg"),
                                ("waist_cm", "8280-0", "Waist circumference", "cm")):
        if answers.get(k) not in (None, ""):
            obs.append(_obs(code, LOINC, disp, float(answers[k]), unit))
    if "phq2" in ins:
        obs.append(_obs("55758-7", LOINC, "PHQ-2 total score", ins["phq2"]))
    if "audit_c" in ins:
        obs.append(_obs("75626-2", LOINC, "AUDIT-C total score", ins["audit_c"]))
    for key, disp in (("stop_bang", "STOP-Bang score"), ("pss4", "PSS-4 score")):
        if key in ins:
            obs.append(_obs(key, LOCAL, disp, ins[key]))
    if "adam_positive" in ins:
        obs.append(_obs("adam", LOCAL, "ADAM screen", "positive" if ins["adam_positive"] else "negative"))
    sem = result.get("semen") or {}
    for code, text, sev in sem.get("findings", []):
        obs.append(_obs(f"semen-{code}", LOCAL, f"Semen screen ({sem.get('source')})", text))
    for node, reasons in result["provenance"].items():
        obs.append(_obs(f"signal-{node}", LOCAL, "Screening signal", "; ".join(r["reason"] for r in reasons)))

    qr = {"resourceType": "QuestionnaireResponse", "id": str(uuid.uuid4()), "status": "completed",
          "questionnaire": "https://riaya.health/fhir/Questionnaire/male-reproductive-prescreen|1.0",
          "authored": when,
          "item": [{"linkId": k, "answer": [{"valueString": ", ".join(map(str, v)) if isinstance(v, list) else str(v)}]}
                   for k, v in answers.items() if v not in (None, "", "skip", [])]}
    sr = {"resourceType": "ServiceRequest", "id": str(uuid.uuid4()), "status": "draft" if t["requires_review"] else "active",
          "intent": "proposal", "priority": "stat" if t["immediate"] else "routine",
          "code": {"coding": [{"system": LOCAL, "code": t["level"]}], "text": t["message"]["en"]},
          "reasonCode": [{"text": r["reason"]} for r in t["reasons"]],
          "note": [{"text": "Suggested tests: " + "; ".join(t["tests"])}] if t["tests"] else [],
          "authoredOn": when}
    entries = [qr, sr] + obs
    return {"resourceType": "Bundle", "id": str(uuid.uuid4()), "type": "collection", "timestamp": when,
            "meta": {"tag": [{"system": LOCAL, "code": "ifhas-reproductive-prescreen"},
                             {"system": LOCAL, "code": "screening-not-diagnosis"}]},
            "entry": [{"fullUrl": f"urn:uuid:{r['id']}", "resource": r} for r in entries]}
