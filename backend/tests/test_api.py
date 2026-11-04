import io
import os
import tempfile
import zipfile

import pytest

os.environ["RIAYA_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["RIAYA_ENABLE_DEMO_CLINICIAN"] = "true"

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


def test_voice_notes(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "aas": "current"}}, headers=h)
    client.post(f"/api/assessments/{aid}/submit", headers=h)
    audio = b"\x1aE\xdf\xa3fake-webm-bytes" * 50
    r = client.post(f"/api/assessments/{aid}/voice-notes", headers=h, files={"file": ("n.webm", audio, "audio/webm")}, data={"seconds": "4.2"})
    assert r.status_code == 200
    assert client.post(f"/api/assessments/{aid}/voice-notes", headers=h, files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 415
    ch = clinician(client)
    msgs = client.get(f"/api/clinician/cases/{aid}/messages", headers=ch).json()
    note = [m for m in msgs if m["voice"]][0]
    assert note["sender"] == "user" and note["seconds"] == 4.2
    got = client.get(f"/api/clinician/cases/{aid}/voice-notes/{note['id']}", headers=ch)
    assert got.content == audio and got.headers["content-type"].startswith("audio/webm")
    from app import db
    with db.tx() as c:
        blob = c.execute("SELECT audio FROM messages WHERE id=?", (note["id"],)).fetchone()["audio"]
    assert b"fake-webm" not in blob
    client.post(f"/api/clinician/cases/{aid}/voice-notes", headers=ch, files={"file": ("r.ogg", b"OggS" * 40, "audio/ogg")})
    mine = client.get(f"/api/assessments/{aid}/messages", headers=h).json()
    reply = [m for m in mine if m["voice"] and m["sender"] == "clinician"][0]
    assert client.get(f"/api/assessments/{aid}/voice-notes/{reply['id']}", headers=h).content.startswith(b"OggS")


def test_whatsapp_flow(client):
    def say(text, frm="whatsapp:+971500000001"):
        r = client.post("/api/whatsapp/twilio", data={"From": frm, "Body": text, "NumMedia": "0"})
        assert r.status_code == 200 and r.text.startswith("<?xml")
        import re
        return re.findall(r"<Message>(.*?)</Message>", r.text, re.S)
    assert "العربية" in say("مرحبا")[0]
    out = say("1")
    assert "رعاية" in out[0] and "طبيب" in out[1]
    for msg in ["نعم", "٣٣", "175", "تخطي", "1 3", "14", "كل يوم", "ابدا", "4", "عشر ساعات", "خمس", "ايوه", "اي", "3", "2", "1"]:
        out = say(msg)
    final = say("لا شيء")[0]
    assert "عيادة صحة الرجل" in final and "#t=" in final and "&amp;a=" in final
    # phone number is not stored anywhere
    from app import db
    with db.tx() as c:
        assert not any("971500000001" in str(dict(r)) for r in c.execute("SELECT * FROM chat_sessions").fetchall())
    # the man can open the full summary on the web with the link
    import html, re
    link = html.unescape(re.search(r"#t=(\S+)", final).group(1))
    tok, aid = link.split("&a=")
    assert client.get(f"/api/assessments/{aid}/result?lang=ar", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    gone = say("حذف")
    assert "مسح" in gone[0]
    assert client.get(f"/api/assessments/{aid}/result", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_conversation_numbers_and_words():
    from app import conversation as cv
    st = cv.new_state()
    cv.handle(st, "2")
    step = cv.current(st)
    assert step["id"] == "consent_review" and cv.interpret(step, "yes please") == "yes"
    assert cv.number("اثنين وثلاثين") == 32 and cv.number("about 7 hours") == 7
    smoke = [s for s in cv.STEPS if s["id"] == "smoking"][0]
    assert cv.interpret(smoke, "every day") is None or cv.interpret(smoke, "daily") == "daily"
    assert cv.interpret(smoke, "4") == "daily" and cv.interpret(smoke, "يومياً") == "daily"


def test_insights_aggregates_and_suppresses(client):
    for i in range(6):
        h, aid = user(client)
        client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "age": 31 + i, "background": "arab"}}, headers=h)
        client.post(f"/api/assessments/{aid}/submit", headers=h)
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "age": 52, "background": "african"}}, headers=h)
    client.post(f"/api/assessments/{aid}/submit", headers=h)
    ch = clinician(client)
    d = client.get("/api/insights", headers=ch).json()
    assert d["tiles"]["completed"] >= 7 and d["funnel"][0]["step"] == "Started"
    bg = {r["group"]: r for r in d["by_background"]}
    assert bg["african"]["suppressed"] and bg["african"]["n"] == "<5"
    assert bg["arab"]["n"] >= 6 and "referred_pct" in bg["arab"]
    assert d["drivers"] and abs(sum(x["share"] for x in d["drivers"])) <= 100.5
    assert "smoking" in [p["node"] for p in d["prevalence"]]
    assert client.get("/api/insights").status_code == 401


def test_explain_whatif_contradictions(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "aas": "never", "diabetes": "no", "sleep_h": 8}}, headers=h)
    client.post(f"/api/assessments/{aid}/labs", headers=h, json={"testosterone": 5.2, "lh": 0.4, "fsh": 0.5, "hba1c": 6.9})
    client.post(f"/api/assessments/{aid}/device-manual", headers=h, json={"sleep_avg_h": 5.6})
    client.post(f"/api/assessments/{aid}/submit", headers=h)
    e = client.get(f"/api/assessments/{aid}/explain", headers=h).json()
    keys = {c["key"] for c in e["contradictions"]}
    assert {"sleep", "diabetes", "hormones"} <= keys
    card = {c["node"]: c for c in e["cards"]}
    assert "smoking" in card and card["smoking"]["evidence"] and card["smoking"]["recommendation"] and card["smoking"]["limitations"]
    assert any("wearables" in l.lower() for l in card["sleep_loss"]["limitations"])
    cov = {c["domain"]: c["status"] for c in e["coverage"]}
    assert cov["hormones"] == "measured" and cov["semen"] == "not_measured" and cov["sleep"] == "measured"
    w = client.post(f"/api/assessments/{aid}/whatif", headers=h, json={"improve": ["smoking", "tight_underwear", "sedentary", "genetic"]}).json()
    assert w["after"] < w["before"] and "genetic" not in w["improved"] and "prediction" in w["note"]
    ar = client.get(f"/api/assessments/{aid}/explain?lang=ar", headers=h).json()
    assert "القدرة على الإنجاب" in ar["cards"][0]["relevance"] or ar["cards"][0]["relevance"] == ""


def test_personal_baseline():
    from datetime import datetime, timedelta
    from app.wearables import summarise_apple
    recs = {"sleep": [], "steps": []}
    start = datetime(2026, 10, 1)
    for d in range(28):
        hours = 7.2 if d < 21 else 5.1
        s = start + timedelta(days=d, hours=23)
        recs["sleep"].append((s, s + timedelta(hours=hours), "HKCategoryValueSleepAnalysisAsleepCore", None))
        recs["steps"].append((start + timedelta(days=d, hours=12), None, "8000" if d < 21 else "3000", None))
    out = summarise_apple(recs)
    b = out["personal_baseline"]
    assert b["sleep_h"]["unusual"] and b["sleep_h"]["recent"] < b["sleep_h"]["baseline"]
    assert b["steps"]["change_pct"] < -50


def test_lab_report_pdf(client):
    from pathlib import Path
    h, aid = user(client)
    pdf = (Path(__file__).resolve().parents[2] / "web" / "samples" / "sample_lab_report.pdf").read_bytes()
    r = client.post(f"/api/assessments/{aid}/lab-report", headers=h, files={"file": ("r.pdf", pdf, "application/pdf")}).json()
    vals = {v["field"]: v["value"] for v in r["values"]}
    assert vals["concentration_m_per_ml"] == 11.5 and vals["progressive_motility_pct"] == 24 and vals["testosterone"] == 9.8
    assert vals["hba1c"] == 5.9 and r["date"] == "2026-10-28" and r["kind"] == "semen"
    assert client.post(f"/api/assessments/{aid}/lab-report", headers=h, files={"file": ("x.png", b"\x89PNG....", "image/png")}).status_code == 415


def test_closed_loop_and_journey(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "smoking": "daily", "cigs_per_day": 20, "underwear": "tight"}}, headers=h)
    client.post(f"/api/assessments/{aid}/submit", headers=h)
    client.post(f"/api/assessments/{aid}/progress", headers=h, json={"status": "booked"})
    client.post(f"/api/assessments/{aid}/progress", headers=h, json={"status": "attended"})
    # three months later: second check with improvements
    aid2 = client.post("/api/assessments", headers=h).json()["id"]
    client.put(f"/api/assessments/{aid2}/answers", json={"answers": {**BASE, "smoking": "former", "underwear": "loose"}}, headers=h)
    client.post(f"/api/assessments/{aid2}/submit", headers=h)
    j = client.get("/api/me/journey", headers=h).json()
    assert len(j["checks"]) == 2 and j["recheck_due"]
    latest, first = j["checks"][0], j["checks"][1]
    assert "Cigarette smoking" in latest["changes"]["improved"] and "Tight underwear / tight trousers" in latest["changes"]["improved"]
    assert [s["step"] for s in first["steps"]][:2] == ["completed", "referred"] and any(s["step"] == "attended" for s in first["steps"])
    assert latest["discuss"] and latest["coverage"]
    client.post(f"/api/assessments/{aid2}/progress", headers=h, json={"status": "declined", "barrier": "embarrassment"})
    ch = clinician(client)
    d = client.get("/api/insights", headers=ch).json()
    assert d["barriers"].get("embarrassment", 0) >= 1 and d["funnel"][-1]["step"] == "Followed up"


def test_override_requires_reason(client):
    h, aid = user(client)
    client.put(f"/api/assessments/{aid}/answers", json={"answers": {**BASE, "aas": "current"}}, headers=h)
    client.post(f"/api/assessments/{aid}/submit", headers=h)
    ch = clinician(client)
    assert client.post(f"/api/clinician/cases/{aid}/review", headers=ch, json={"decision": "modify", "final_level": "primary_care"}).status_code == 400
    r = client.post(f"/api/clinician/cases/{aid}/review", headers=ch, json={"decision": "modify", "final_level": "primary_care", "note": "Stopped 6 months ago; check hormones first"}).json()
    assert r["final_level"] == "primary_care"
    case = client.get(f"/api/clinician/cases/{aid}", headers=ch).json()
    assert case["review_note"].startswith("Stopped") and case["referral"]["final_level"] == "primary_care"


def test_every_observation_has_arabic():
    """Runs many different profiles and checks that every recorded observation has an Arabic version."""
    import itertools
    from app import features, labs, obs_ar, semen
    profiles = [
        {**BASE, "smoking": s, "waterpipe": w, "aas": a, "cannabis": "current", "meds": ["opioid", "ssri"], "fast_food": 2, "fruit_veg": 2, "fish": 2,
         "late_meals": 5, "late_caffeine": 5, "shift": "night", "screen_h": 7, "screen_bed": 2, "underwear": "tight", "underwear_fabric": "synthetic",
         "hot_bath": 2, "laptop_lap": 3, "phone_pocket": "yes", "heat_work": "yes", "chemicals_work": "yes", "near_traffic": "yes", "occupation": "industrial",
         "vitd": v, "indoors": "yes", "mumps": "yes", "cryptorchidism": "yes", "varicocele": "yes", "infection": "untreated", "chemo": "yes", "fever": "yes",
         "parents_related": "yes", "family_history": "yes", "diabetes": "pre", "age": 47, "waist_cm": 105, "audit1": 3, "audit2": 2, "audit3": 1,
         "adam1": "yes", "adam7": "yes", "phq1": 2, "phq2": 2, "pss1": 4, "pss2": 0, "pss3": 0, "pss4": 4, "neck_cm": 44, "bp": "yes", "observed": "yes"}
        for s, w, a, v in itertools.product(["daily", "occasional", "former"], ["daily"], ["current"], ["yes", "no"])]
    wear = {"sleep_avg_h": 5.2, "steps_avg": 3100, "social_jetlag_h": 2.5, "spo2_low_nights": 4, "night_glucose_high_pct": 22, "glucose_cv": 38,
            "late_caffeine_days_per_week": 5, "screen_daily_h": 6}
    sem_sets = [semen.interpret_lab({"volume_ml": 1.0, "concentration_m_per_ml": 3, "progressive_motility_pct": 20, "normal_forms_pct": 2}),
                semen.interpret_lab({"concentration_m_per_ml": 0}), semen.interpret_lab({"concentration_m_per_ml": 12}),
                semen.interpret_home_quantitative({"concentration_m_per_ml": 9, "progressive_motility_pct": 20, "motile_conc_m_per_ml": 2}),
                semen.interpret_home("spermcheck", "below")]
    lb = labs.interpret({"testosterone": 6, "lh": 9, "fsh": 14, "hba1c": 6.8, "vitamin_d": 15})
    missing = set()
    for prof in profiles:
        for sem in sem_sets:
            for w in (wear, {}):
                _, why, _ = features.build_inputs(prof, w, sem, lb)
                for reasons in why.values():
                    for r in reasons:
                        if obs_ar.to_ar(r["reason"]) is None:
                            missing.add(r["reason"])
    assert not missing, missing
