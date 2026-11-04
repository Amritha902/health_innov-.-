"""Runs every validation step and writes validation/results.json and validation/REPORT.md.

  python validation/run_validation.py            # report only
  python validation/run_validation.py --seed-demo # also loads simulated cases into the app database (flagged simulated)
"""
import json
import random
import sys
import time
import uuid
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "validation"))

from app import assessment, ml, semen, synth  # noqa: E402
from app.knowledge import graph  # noqa: E402
from app.triage import LEVELS  # noqa: E402
from vignettes import VIGNETTES  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

OUT = ROOT / "validation"


def run_vignettes():
    rows = []
    for name, answers, sem, lo, hi in VIGNETTES:
        s = None
        if sem:
            s = semen.interpret_lab(sem) if sem["source"] == "lab" else semen.interpret_home_quantitative(sem, sem.get("kit", "yo"))
        t = assessment.run(answers, None, s, with_models=False)["triage"]
        got = LEVELS.index(t["level"])
        status = "under" if got < LEVELS.index(lo) else "over" if got > LEVELS.index(hi) else "ok"
        rows.append({"case": name, "expected": lo if lo == hi else f"{lo}..{hi}", "got": t["level"], "status": status,
                     "review": t["requires_review"]})
    return rows


def ml_real():
    return ml.evaluate(repeats=20)


def synthetic(n=20000):
    from sklearn.metrics import brier_score_loss
    m, meta, (Xte, yte, gte, p) = synth.train(n)
    feats = synth.FEATURES
    age, bmi = Xte[:, feats.index("age")], Xte[:, feats.index("bmi")]
    # calibration by decile
    order = np.argsort(p)
    cal = []
    for chunk in np.array_split(order, 10):
        cal.append({"predicted": round(float(p[chunk].mean()), 3), "observed": round(float(yte[chunk].mean()), 3), "n": int(len(chunk))})
    # operating point for "flag for testing": predicted >= 0.4
    thr = 0.4
    flag = p >= thr
    tp, fn = int((flag & (yte == 1)).sum()), int((~flag & (yte == 1)).sum())
    tn, fp = int((~flag & (yte == 0)).sum()), int((flag & (yte == 0)).sum())

    def sub(mask):
        if mask.sum() < 50 or len(set(yte[mask])) < 2:
            return None
        return {"n": int(mask.sum()), "prevalence": round(float(yte[mask].mean()), 3), "auc": round(float(roc_auc_score(yte[mask], p[mask])), 3),
                "mean_predicted": round(float(p[mask].mean()), 3), "flag_rate": round(float(flag[mask].mean()), 3),
                "sensitivity": round(float((flag & (yte == 1) & mask).sum() / max(1, ((yte == 1) & mask).sum())), 3)}
    fairness = {
        "age": {k: sub(msk) for k, msk in (("20-29", age < 30), ("30-39", (age >= 30) & (age < 40)), ("40-45", age >= 40))},
        "bmi": {k: sub(msk) for k, msk in (("<25", bmi < 25), ("25-30", (bmi >= 25) & (bmi < 30)), (">=30", bmi >= 30))},
        "background": {k: sub(gte == k) for k in synth.GROUPS},
    }
    return {"meta": meta, "calibration": cal, "brier": round(float(brier_score_loss(yte, p)), 3),
            "operating_point": {"threshold": thr, "sensitivity": round(tp / (tp + fn), 3), "specificity": round(tn / (tn + fp), 3),
                                "ppv": round(tp / max(1, tp + fp), 3), "npv": round(tn / max(1, tn + fn), 3)},
            "fairness": fairness}


def engine_consistency(n=2000, seed=3):
    """Does the evidence-graph index (built from the literature graph, no training) rank simulated men
    the same way their simulated semen outcome does?"""
    X, y, extra = synth.simulate(n, seed)
    f = {k: i for i, k in enumerate(synth.FEATURES)}
    g = graph()
    scores = []
    for row in X:
        a = {"age": row[f["age"]], "height_cm": 175, "weight_kg": row[f["bmi"]] * 1.75 ** 2,
             "smoking": "daily" if row[f["smoker"]] else "never", "sleep_h": row[f["sleep_h"]], "sitting_h": row[f["sitting_h"]],
             "underwear": "tight" if row[f["tight"]] else "loose", "hot_bath": 2 if row[f["hot_bath"]] else 0,
             "aas": "current" if row[f["aas"]] else "never", "varicocele": "yes" if row[f["varicocele"]] else "no",
             "cryptorchidism": "yes" if row[f["cryptorchid"]] else "no", "mumps": "yes" if row[f["mumps"]] else "no",
             "diabetes": "yes" if row[f["diabetes"]] else "no", "vitd": "yes" if row[f["vitd_low"]] else "no"}
        u = row[f["alcohol_units"]]
        a["audit1"] = 0 if u == 0 else 3 if u >= 14 else 2
        a["audit2"] = 2 if u >= 25 else 0
        a["audit3"] = 0
        pss = int(row[f["pss4"]])
        a.update({"pss1": min(4, pss // 4), "pss2": max(0, 4 - pss // 4), "pss3": max(0, 4 - pss // 4), "pss4": min(4, pss // 4)})
        sb = int(row[f["stop_bang"]])
        a.update({"snore": "yes" if sb >= 3 else "no", "tired": "yes" if sb >= 4 else "no", "observed": "yes" if sb >= 5 else "no"})
        from app import features
        inp, _, _ = features.build_inputs(a)
        scores.append(g.score(inp)["subfertility"])
    return {"n": n, "auc_engine_index_vs_simulated_outcome": round(float(roc_auc_score(y, scores)), 3)}


def workflow(n=400, seed=11, seed_db=False):
    """Simulated pathway timings. Rates are ASSUMPTIONS (listed in the output), not observations."""
    rng = random.Random(seed)
    assumptions = {"completion_rate": 0.82, "minutes_to_complete": "lognormal median ~9", "review_hours": "uniform 1-24",
                   "booked_given_referral": 0.75, "attended_given_booked": 0.85, "days_to_attend": "uniform 3-21",
                   "comparator_days_to_male_evaluation": "12+ months (usual pathway: male assessed after female work-up)"}
    X, y, extra = synth.simulate(n, seed)
    f = {k: i for i, k in enumerate(synth.FEATURES)}
    groups = extra["group"]
    rows, now = [], time.time()
    for i, row in enumerate(X):
        a = {"age": int(row[f["age"]]), "height_cm": 175, "weight_kg": round(row[f["bmi"]] * 1.75 ** 2), "sleep_h": round(row[f["sleep_h"]], 1),
             "smoking": "daily" if row[f["smoker"]] else "never", "sitting_h": round(row[f["sitting_h"]]), "underwear": "tight" if row[f["tight"]] else "loose",
             "aas": "current" if row[f["aas"]] else "never", "varicocele": "yes" if row[f["varicocele"]] else "no",
             "background": {"Emirati": "arab", "Arab expat": "arab", "South Asian": "south_asian", "Western": "european"}.get(groups[i], "other")}
        if rng.random() < 0.15:
            a.update(reason=["trying"], months_trying=rng.choice([4, 8, 13, 18]), partner_age=rng.choice([26, 31, 36]))
        started = now - rng.uniform(1, 60) * 86400
        completed = rng.random() < assumptions["completion_rate"]
        res = assessment.run(a, with_models=False) if completed else None
        rows.append((a, started, completed, res))
    done = [r for r in rows if r[2]]
    referred = [r for r in done if r[3]["triage"]["level"] != "self_care"]
    reviewed = [r for r in referred if r[3]["triage"]["requires_review"]]
    attended, days = 0, []
    for r in referred:
        if rng.random() < assumptions["booked_given_referral"] and rng.random() < assumptions["attended_given_booked"]:
            attended += 1
            days.append(rng.uniform(3, 21) + (rng.uniform(1, 24) / 24 if r[3]["triage"]["requires_review"] else 0))
    levels = {}
    for r in done:
        levels[r[3]["triage"]["level"]] = levels.get(r[3]["triage"]["level"], 0) + 1
    out = {"assumptions": assumptions, "started": n, "completed": len(done), "referred": len(referred),
           "clinician_reviewed": len(reviewed), "referral_completion_rate": round(attended / max(1, len(referred)), 3),
           "median_days_to_evaluation": round(float(np.median(days)), 1) if days else None, "levels": levels}
    if seed_db:
        out["seeded"] = seed_database(rows, rng)
    return out


def seed_database(rows, rng):
    from app import db, security
    db.init()
    n = 0
    with db.tx() as c:
        c.execute("DELETE FROM referrals WHERE simulated=1")
        c.execute("DELETE FROM assessments WHERE simulated=1")
        for a, started, completed, res in rows:
            aid = str(uuid.uuid4())
            fin = started + rng.lognormvariate(np.log(9), 0.4) * 60 if completed else None
            t = res["triage"] if res else None
            channel = rng.choices(["chat", "watch", "web", "whatsapp"], weights=[40, 15, 20, 25])[0]  # assumed mix for the simulation
            c.execute("""INSERT INTO assessments (id,user_id,started_at,completed_at,answers,result,tier,level,requires_review,review_consent,cohort,simulated,channel)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)""",
                      (aid, "simulated", started, fin, security.seal(a), security.seal(res) if res else None,
                       t and t["tier"], t and t["level"], int(bool(t and t["requires_review"])), 1,
                       f"{a['age'] // 10 * 10}s|{a['background']}", channel))
            if t and t["level"] != "self_care":
                reviewed_at = fin + rng.uniform(1, 24) * 3600 if t["requires_review"] else None
                status, booked, attended = ("approved" if t["requires_review"] else "suggested"), None, None
                if rng.random() < 0.75:
                    status, booked = "booked", (reviewed_at or fin) + rng.uniform(0.5, 3) * 86400
                    if rng.random() < 0.85:
                        status, attended = "attended", booked + rng.uniform(3, 18) * 86400
                if t["requires_review"] and rng.random() < 0.15:
                    status, reviewed_at = "pending_review", None
                rapid = int(bool(t.get("rapid_review")))
                due = fin + (t.get("sla_hours") or 48) * 3600 if rapid else None
                c.execute("""INSERT INTO referrals (id,assessment_id,level,status,created_at,reviewed_at,reviewer,final_level,booked_at,attended_at,simulated,rapid,due_at)
                             VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                          (str(uuid.uuid4()), aid, t["level"], status, fin, reviewed_at, "clinician" if reviewed_at else None,
                           t["level"] if reviewed_at else None, booked, attended, rapid, due))
            n += 1
    return n


def write_report(r):
    v = r["vignettes"]
    ok = sum(x["status"] == "ok" for x in v)
    under = [x for x in v if x["status"] == "under"]
    over = [x for x in v if x["status"] == "over"]
    s, fair = r["synthetic"], r["synthetic"]["fairness"]
    L = []
    L.append("# Validation report\n")
    L.append(f"Generated {time.strftime('%Y-%m-%d %H:%M')}. Re-run with `python validation/run_validation.py`.\n")
    L.append("## 1. Triage safety on clinical vignettes\n")
    L.append(f"{len(v)} vignettes, with the expected next step taken from guidelines (WHO 2021, AUA/ASRM 2021, EAU 2024, ASRM 2020).\n")
    L.append(f"- Agreement: **{ok}/{len(v)}**\n- Under-triage (safety failures): **{len(under)}**\n- Over-triage: **{len(over)}**\n")
    L.append("| Case | Expected | Got | Clinician review |\n|---|---|---|---|")
    L += [f"| {x['case']} | {x['expected']} | {x['got']} {'' if x['status'] == 'ok' else '**(' + x['status'] + ')**'} | {'yes' if x['review'] else 'no'} |" for x in v]
    L.append("\nThe vignettes were written by the same team that wrote the rules, so this shows the rules do what the guidelines say. "
             "It is not an independent accuracy estimate. Next step: a panel of UAE andrologists and family physicians sets the expected answers blind.\n")
    m = r["uci"]
    L.append("## 2. Model on real data: UCI Fertility dataset\n")
    L.append(f"100 men, 12 with altered semen analysis (Gil et al. 2012). Repeated stratified 5-fold cross-validation (×20).\n")
    L.append(f"| Model | AUC (mean) | AUC 95% range across folds | Brier |\n|---|---|---|---|")
    for k in ("logistic", "gbm"):
        L.append(f"| {k} | {m[k]['auc_mean']} | {m[k]['auc_ci95'][0]}–{m[k]['auc_ci95'][1]} | {m[k]['brier']} |")
    L.append("\nThis is a small dataset. The model gives clinicians a second opinion and does not drive triage on its own.\n")
    L.append("## 3. Gradient boosting + SHAP on the simulated cohort\n")
    L.append(f"n = {s['meta']['n_train'] + s['meta']['n_test']} simulated men; effect sizes come from the literature (see `backend/app/synth.py`). "
             f"Prevalence of below-reference semen: {s['meta']['prevalence']}.\n")
    L.append(f"- Test AUC **{s['meta']['auc_test']}**, Brier {s['brier']}\n- At threshold {s['operating_point']['threshold']}: "
             f"sensitivity {s['operating_point']['sensitivity']}, specificity {s['operating_point']['specificity']}, "
             f"PPV {s['operating_point']['ppv']}, NPV {s['operating_point']['npv']}\n")
    L.append("Calibration by decile:\n\n| Predicted | Observed | n |\n|---|---|---|")
    L += [f"| {c['predicted']} | {c['observed']} | {c['n']} |" for c in s["calibration"]]
    L.append("\nThe AUC is moderate because semen quality varies a lot even in healthy men. A questionnaire can point to who should test; it cannot replace the test.\n")
    L.append("### Fairness across subgroups\n")
    for dim, groups in fair.items():
        L.append(f"\n**{dim}**\n\n| Group | n | Prevalence | AUC | Mean predicted | Flag rate | Sensitivity |\n|---|---|---|---|---|---|---|")
        L += [f"| {k} | {g['n']} | {g['prevalence']} | {g['auc']} | {g['mean_predicted']} | {g['flag_rate']} | {g['sensitivity']} |" for k, g in groups.items() if g]
    L.append("\nBackground (nationality group) has no causal effect in the simulation, so similar AUC and calibration across groups is the expected result. "
             "This checks that the pipeline does not introduce bias; real-world fairness needs real data.\n")
    e = r["engine"]
    L.append("## 4. Evidence-graph engine consistency\n")
    L.append(f"The graph engine is not trained. It is built only from the cited links. On {e['n']} simulated men its index ranks outcomes with AUC "
             f"**{e['auc_engine_index_vs_simulated_outcome']}**, close to the trained model. This shows the graph and the literature effect sizes agree.\n")
    w = r["workflow"]
    L.append("## 5. Pathway simulation (assumed rates)\n")
    L.append(f"{w['started']} simulated men started; {w['completed']} completed; {w['referred']} were routed beyond self-care; "
             f"{w['clinician_reviewed']} needed clinician review. Simulated referral completion is {w['referral_completion_rate']} and the median time to evaluation is "
             f"{w['median_days_to_evaluation']} days. Under the usual pathway the man is often assessed only after his wife's work-up (12+ months).\n")
    L.append("Assumptions: " + "; ".join(f"{k} = {v}" for k, v in w["assumptions"].items()) + "\n")
    L.append("Levels: " + ", ".join(f"{k}: {v}" for k, v in sorted(w["levels"].items())) + "\n")
    L.append("## Limitations, stated plainly\n")
    L += ["- The simulated cohort reproduces published effect sizes; it is not evidence of real-world accuracy.",
          "- The UCI dataset is small (n=100), from Spain, and uses WHO 2010 criteria.",
          "- At-home device performance figures come from the manufacturers' published studies and were not re-tested here.",
          "- User trust and usability need a real study (target: 30–50 men in Abu Dhabi, with a validated trust scale).",
          "- Next step: a prospective pilot with an Abu Dhabi clinical partner, comparing the pre-screen result with laboratory semen analysis."]
    (OUT / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    t0 = time.time()
    results = {"vignettes": run_vignettes(), "uci": ml_real(), "synthetic": synthetic(), "engine": engine_consistency(),
               "workflow": workflow(seed_db="--seed-demo" in sys.argv)}
    (OUT / "results.json").write_text(json.dumps(results, indent=1, default=str))
    write_report(results)
    print(json.dumps({"vignettes_ok": sum(x["status"] == "ok" for x in results["vignettes"]),
                      "under": [x["case"] for x in results["vignettes"] if x["status"] == "under"],
                      "over": [x["case"] for x in results["vignettes"] if x["status"] == "over"],
                      "uci": results["uci"], "gbm_auc": results["synthetic"]["meta"]["auc_test"],
                      "engine_auc": results["engine"], "workflow": {k: v for k, v in results["workflow"].items() if k != "assumptions"},
                      "seconds": round(time.time() - t0)}, indent=1, default=str))
