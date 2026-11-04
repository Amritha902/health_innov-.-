import io
import os
import tempfile
import zipfile

import pytest

os.environ["RIAYA_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

BASE = {"age": 34, "height_cm": 175, "weight_kg": 98, "smoking": "daily", "cigs_per_day": 15, "sitting_h": 10,
        "sleep_h": 5.5, "underwear": "tight", "snore": "yes", "tired": "yes", "observed": "no", "bp": "no",
        "pss1": 3, "pss2": 1, "pss3": 1, "pss4": 3, "phq1": 0, "phq2": 1, "reason": ["future"]}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def user(client, review=True, wearables=True):
    tok = client.post("/api/session", json={"lang": "en"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    client.post("/api/consent", json={"core": True, "clinician_review": review, "wearables": wearables}, headers=h)
    aid = client.post("/api/assessments", headers=h).json()["id"]
    return h, aid


def clinician(client):
    tok = client.post("/api/clinician/login", json={"username": "clinician", "password": "demo-clinician"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_graph_valid(client):
    from app.knowledge import graph
    assert graph().validate() == []


def test_requires_consent(client):
    tok = client.post("/api/session", json={}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.post("/api/assessments", headers=h).status_code == 403
    assert client.post("/api/consent", json={"core": False}, headers=h).status_code == 400


def test_full_flow_and_review(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "unexpected_field": "dropped"}}, headers=h)
    r = client.post(f"/api/assessments/{aid}/semen", headers=h,
                    json={"source": "lab", "volume_ml": 2.5, "concentration_m_per_ml": 3, "progressive_motility_pct": 22})
    assert r.json()["normal"] is False
    v = client.post(f"/api/assessments/{aid}/submit?lang=ar", headers=h).json()
    assert v["level"] == "andrology" and v["clinician_review"] == "queued"
    assert "تشخيص" in v["disclaimer"]
    text = str(v).lower()
    assert "infertil" not in text and "risk" not in text

    ch = clinician(client)
    q = client.get("/api/clinician/queue", headers=ch).json()
    assert aid in [x["id"] for x in q["pending"]]
    case = client.get(f"/api/clinician/cases/{aid}", headers=ch).json()
    assert "unexpected_field" not in case["answers"]
    assert case["result"]["models"]["simulated_gbm"]["contributions"]
    assert client.post(f"/api/clinician/cases/{aid}/review", headers=ch, json={"decision": "approve"}).json()["final_level"] == "andrology"
    client.post(f"/api/clinician/cases/{aid}/status", headers=ch, json={"status": "attended"})
    m = client.get("/api/clinician/metrics", headers=ch).json()
    assert m["completed"] >= 1 and m["referral_completion_rate"] is not None


def test_no_review_consent_hidden_from_clinician(client):
    h, aid = user(client, review=False)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "aas": "current"}}, headers=h)
    v = client.post(f"/api/assessments/{aid}/submit", headers=h).json()
    assert v["clinician_review"] == "available"
    ch = clinician(client)
    assert client.get(f"/api/clinician/cases/{aid}", headers=ch).status_code == 404
    code = client.post(f"/api/assessments/{aid}/share", headers=h).json()["code"]
    assert client.post(f"/api/clinician/share/{code}", headers=ch).status_code == 200
    assert client.get(f"/api/clinician/cases/{aid}", headers=ch).status_code == 200
    client.delete(f"/api/shares/{code}", headers=h)
    assert client.get(f"/api/clinician/cases/{aid}", headers=ch).status_code == 404


def test_red_flag_emergency(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {"age": 25, "red_flags": ["rf_torsion"]}}, headers=h)
    v = client.post(f"/api/assessments/{aid}/submit", headers=h).json()
    assert v["level"] == "emergency" and v["immediate"]


def test_apple_health_import(client):
    h, aid = user(client)
    recs = []
    for d in range(1, 15):
        day = f"2026-10-{d:02d}"
        nxt = f"2026-10-{d + 1:02d}"
        recs.append(f'<Record type="HKCategoryTypeIdentifierSleepAnalysis" startDate="{day} 23:30:00 +0400" endDate="{nxt} 05:00:00 +0400" value="HKCategoryValueSleepAnalysisAsleepCore"/>')
        recs.append(f'<Record type="HKQuantityTypeIdentifierStepCount" startDate="{day} 10:00:00 +0400" endDate="{day} 11:00:00 +0400" value="3200"/>')
        recs.append(f'<Record type="HKQuantityTypeIdentifierDietaryCaffeine" startDate="{day} 20:00:00 +0400" endDate="{day} 20:00:00 +0400" value="95" unit="mg"/>')
        recs.append(f'<Record type="HKQuantityTypeIdentifierBloodGlucose" startDate="{day} 23:00:00 +0400" endDate="{day} 23:00:00 +0400" value="168" unit="mg/dL"/>')
        recs.append(f'<Record type="HKQuantityTypeIdentifierOxygenSaturation" startDate="{nxt} 03:00:00 +0400" endDate="{nxt} 03:00:00 +0400" value="0.87" unit="%"/>')
    xml = '<?xml version="1.0"?><HealthData>' + "".join(recs) + "</HealthData>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("apple_health_export/export.xml", xml)
    r = client.post(f"/api/assessments/{aid}/wearables", headers=h, files={"file": ("export.zip", buf.getvalue())})
    s = r.json()
    assert s["sleep_avg_h"] == 5.5 and s["steps_avg"] == 3200 and s["spo2_low_nights"] >= 3
    assert s["late_caffeine_days_per_week"] > 3 and s["night_glucose_high_pct"] == 100
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {"age": 30, "sleep_h": 8}}, headers=h)
    client.post(f"/api/assessments/{aid}/submit", headers=h)
    ch = clinician(client)
    res = client.get(f"/api/clinician/cases/{aid}", headers=ch).json()["result"]
    assert res["inputs"]["sleep_loss"] == 0.8  # watch overrides self-report
    assert "glycaemic_spikes" in res["inputs"] and "caffeine_late" in res["inputs"]


def test_cgm_csv(client):
    from app.wearables import parse_cgm_csv
    dex = "Index,Timestamp (YYYY-MM-DDThh:mm:ss),Event Type,Glucose Value (mg/dL)\n" + "\n".join(
        f"{i},2026-10-0{1 + i // 24}T{i % 24:02d}:00:00,EGV,{180 if i % 24 >= 22 else 100}" for i in range(72))
    s = parse_cgm_csv(dex)
    assert s["night_glucose_high_pct"] > 0 and s["glucose_readings"] == 72
    libre = "Glucose Data,Generated on,10-30-2026\nDevice,Serial Number,Device Timestamp,Record Type,Historic Glucose mmol/L\n" + "\n".join(
        f"FreeStyle,X,30-10-2026 {h:02d}:00,0,{9.5 if h >= 22 else 5.5}" for h in range(24))
    s2 = parse_cgm_csv(libre)
    assert s2["glucose_readings"] == 24 and s2["night_glucose_peak"] == 171


def test_ifhas_bundle_and_delete(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": BASE}, headers=h)
    client.post(f"/api/assessments/{aid}/submit", headers=h)
    b = client.get(f"/api/assessments/{aid}/ifhas", headers=h).json()
    types = [e["resource"]["resourceType"] for e in b["entry"]]
    assert b["resourceType"] == "Bundle" and "QuestionnaireResponse" in types and "ServiceRequest" in types
    assert "39156-5" in str(b)
    assert client.delete("/api/me", headers=h).json()["deleted"]
    assert client.get("/api/me/export", headers=h).status_code == 401


def test_fabric(client):
    r = client.post("/api/fabric", json={"text": "Shell: Cotton 95%, Elastane 5%", "garment": "underwear", "fit": "loose"}).json()
    assert r["composition"] == {"cotton": 95, "elastane": 5} and r["verdict"] == "good"
    r = client.post("/api/fabric", json={"text": "80% polyamide 20% elastane", "garment": "underwear", "fit": "tight"}).json()
    assert r["verdict"] == "caution"


def test_data_encrypted_at_rest(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {"age": 41, "aas": "current"}}, headers=h)
    from app import db
    with db.tx() as c:
        blob = c.execute("SELECT answers FROM assessments WHERE id=?", (aid,)).fetchone()[0]
    assert b"aas" not in blob and b"current" not in blob


def test_labs_genomic_rapid_handover(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "parents_related": "yes", "pref_language": "ar",
                                                                    "pref_contact": "app_only", "pref_clinician": "male"}}, headers=h)
    client.post(f"/api/assessments/{aid}/semen", headers=h, json={"source": "lab", "volume_ml": 1.0, "concentration_m_per_ml": 0, "ph": 6.8})
    lab = client.post(f"/api/assessments/{aid}/labs", headers=h, json={"testosterone": 9.5, "fsh": 14, "lh": 11, "hba1c": 5.9, "date": "2026-10-20"}).json()
    assert {f[0] for f in lab["findings"]} >= {"t_borderline", "fsh_high", "t_pattern", "a1c_pre"}
    v = client.post(f"/api/assessments/{aid}/submit", headers=h).json()
    assert v["rapid_review"] and v["sla_hours"] == 48 and v["genomic"]
    ch = clinician(client)
    q = client.get("/api/clinician/queue", headers=ch).json()["pending"]
    assert q[0]["rapid"] and q[0]["due_at"]
    case = client.get(f"/api/clinician/cases/{aid}", headers=ch).json()
    gen = case["result"]["triage"]["genomic"]
    assert gen["flag"] and "Karyotype" in gen["tests"] and any("CFTR" in t for t in gen["tests"])
    # labs already done are not re-requested
    assert not any(t.startswith("FSH, LH") for t in case["result"]["triage"]["tests"])
    client.post(f"/api/clinician/cases/{aid}/review", headers=ch, json={"decision": "approve"})
    ho = client.get(f"/api/clinician/cases/{aid}/handover", headers=ch).json()
    assert ho["bundle"]["type"] == "document" and ho["bundle"]["entry"][0]["resource"]["resourceType"] == "Composition"
    titles = [s["title"] for s in ho["letter"]["sections"]]
    assert "Results already available" in titles and "Genomic flag" in titles
    text = str(ho["letter"])
    assert "do not repeat" in text and "no phone calls or SMS" in text and "male doctor" in text
    # messaging + video
    client.post(f"/api/clinician/cases/{aid}/messages", headers=ch, json={"body": "Hello, I have reviewed your results."})
    url = client.post(f"/api/clinician/cases/{aid}/video", headers=ch).json()["url"]
    assert url.startswith("https://meet.jit.si/riaya-")
    msgs = client.get(f"/api/assessments/{aid}/messages", headers=h).json()
    assert msgs[0]["body"].startswith("Hello") and len(msgs) == 2
    client.post(f"/api/assessments/{aid}/messages", headers=h, json={"body": "Thank you"})
    assert client.get(f"/api/assessments/{aid}/result", headers=h).json()["referral"]["video_url"] == url


def test_partner_link_status_only(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "reason": ["trying"], "months_trying": 14}}, headers=h)
    client.post(f"/api/assessments/{aid}/submit", headers=h)
    tok = client.post(f"/api/assessments/{aid}/partner-link", headers=h).json()["token"]
    p = client.get(f"/api/partner/{tok}").json()
    assert p["status"] == "together" and set(p) == {"completed_on", "status", "message"}
    assert "smok" not in str(p).lower() and "bmi" not in str(p).lower()
    client.delete(f"/api/assessments/{aid}/partner-link", headers=h)
    assert client.get(f"/api/partner/{tok}").status_code == 404


def test_request_review_after_declining(client):
    h, aid = user(client, review=False)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "aas": "current"}}, headers=h)
    client.post(f"/api/assessments/{aid}/submit", headers=h)
    assert client.post(f"/api/assessments/{aid}/messages", headers=h, json={"body": "hi"}).status_code == 403
    client.post(f"/api/assessments/{aid}/request-review", headers=h)
    ch = clinician(client)
    assert aid in [x["id"] for x in client.get("/api/clinician/queue", headers=ch).json()["pending"]]
