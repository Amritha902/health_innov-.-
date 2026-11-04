"""Creates the demo people through the real API (not the database). Usage: python demo/setup_data.py <workdir>"""
import json
import sys

import httpx

W = sys.argv[1]
c = httpx.Client(base_url="http://localhost:8000", timeout=60)


def person(review=True):
    tok = c.post("/api/session", json={"lang": "ar"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    c.post("/api/consent", json={"core": True, "clinician_review": review, "wearables": True}, headers=h)
    return tok, h


def check(h, answers, channel="web"):
    aid = c.post(f"/api/assessments?channel={channel}", headers=h).json()["id"]
    c.put(f"/api/assessments/{aid}/answers", headers=h, json={"answers": answers})
    return aid


base = {"age": 34, "height_cm": 176, "weight_kg": 94, "reason": ["trying"], "months_trying": 14, "partner_age": 31, "smoking": "daily", "cigs_per_day": 12,
        "waterpipe": "weekly", "sitting_h": 10, "sleep_h": 7.5, "snore": "yes", "tired": "yes", "underwear": "tight", "phq1": 1, "phq2": 1, "pref_language": "ar"}

# 1) result + explanation: watch data and a lab report, so findings and contradictions are rich
tok, h = person()
aid = check(h, base)
c.post(f"/api/assessments/{aid}/device-manual", headers=h, json={"sleep_avg_h": 5.6, "steps_avg": 3900, "spo2_low_nights": 4, "social_jetlag_h": 2.6})
c.post(f"/api/assessments/{aid}/semen", headers=h, json={"source": "lab", "volume_ml": 1.9, "concentration_m_per_ml": 11.5, "total_count_m": 21.9,
                                                           "progressive_motility_pct": 24, "total_motility_pct": 38, "normal_forms_pct": 3})
c.post(f"/api/assessments/{aid}/labs", headers=h, json={"testosterone": 9.8, "fsh": 8.9, "lh": 6.1, "hba1c": 5.9, "vitamin_d": 17, "date": "2026-10-28"})
c.post(f"/api/assessments/{aid}/submit?lang=ar", headers=h)

# 2) lab-report scene: an open check waiting at the tests step
tok_lr, h_lr = person()
aid_lr = check(h_lr, base)

# 3) journey: a first check three months ago (booked and attended), then a follow-up with changes
tok_j, h_j = person()
a1 = check(h_j, base)
c.post(f"/api/assessments/{a1}/submit?lang=ar", headers=h_j)
c.post(f"/api/assessments/{a1}/progress", headers=h_j, json={"status": "booked"})
c.post(f"/api/assessments/{a1}/progress", headers=h_j, json={"status": "attended"})
c.post(f"/api/assessments/{a1}/progress", headers=h_j, json={"status": "tests_done"})
a2 = check(h_j, {**base, "smoking": "former", "underwear": "loose", "sitting_h": 6, "sleep_h": 7})
c.post(f"/api/assessments/{a2}/submit?lang=ar", headers=h_j)
# make the first check three months older so the journey reads as a timeline
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "backend"))
from app import db  # noqa: E402
with db.tx() as con:
    con.execute("UPDATE assessments SET started_at=started_at-7776000, completed_at=completed_at-7776000 WHERE id=?", (a1,))
    con.execute("""UPDATE referrals SET created_at=created_at-7776000, booked_at=booked_at-7200000, attended_at=attended_at-6500000,
                   tests_done_at=tests_done_at-6400000 WHERE assessment_id=?""", (a1,))

# 4) rapid-review case for the doctor workspace
tok2, h2 = person()
aid2 = check(h2, {"age": 29, "height_cm": 180, "weight_kg": 84, "reason": ["fitness", "future"], "aas": "never", "sitting_h": 6, "sleep_h": 8,
                  "parents_related": "yes", "pref_language": "ar", "pref_contact": "app_only", "pref_clinician": "male"})
c.post(f"/api/assessments/{aid2}/device-manual", headers=h2, json={"sleep_avg_h": 6.1})
c.post(f"/api/assessments/{aid2}/semen", headers=h2, json={"source": "home_quant", "kit": "yo", "concentration_m_per_ml": 3, "progressive_motility_pct": 18, "motile_conc_m_per_ml": 1.5})
c.post(f"/api/assessments/{aid2}/labs", headers=h2, json={"testosterone": 5.1, "lh": 0.5, "fsh": 0.6, "date": "2026-10-28"})
c.post(f"/api/assessments/{aid2}/submit?lang=ar", headers=h2)
c.post(f"/api/assessments/{aid2}/messages", headers=h2, json={"body": "هل سأتمكن من الإنجاب في المستقبل؟"})

json.dump({"result": {"token": tok, "aid": aid}, "labreport": {"token": tok_lr, "aid": aid_lr}, "journey": {"token": tok_j, "aid": a2},
           "rapid": {"aid": aid2}}, open(f"{W}/data.json", "w"))
print("ok")
