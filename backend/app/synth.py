"""Simulated cohort + gradient-boosted model with SHAP explanations.

The cohort is generated from a structural model whose effect sizes are taken from the literature
(EFFECTS below, each with its source). Exposure prevalences are rough Abu Dhabi adult-male figures and
are assumptions, listed in PREVALENCE. This cohort exists to (1) test the pipeline end to end,
(2) produce SHAP explanations, and (3) run fairness checks. It is not evidence of real-world accuracy.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODEL_FILE = ROOT / "data" / "gbm_model.joblib"
META_FILE = ROOT / "data" / "gbm_meta.json"

# multiplicative effect on sperm concentration (approximate, from the cited study's headline estimate)
EFFECTS = {
    "obese":        (0.80, "sermondade2013", "BMI >= 30"),
    "overweight":   (0.93, "sermondade2013", "BMI 25-30"),
    "smoker":       (0.85, "sharma2016", "daily smoking"),
    "alcohol_high": (0.67, "jensen2014", ">= 25 units/week: ~33% lower concentration"),
    "alcohol_mod":  (0.90, "jensen2014", "5-24 units/week"),
    "short_sleep":  (0.71, "jensen2013", "high sleep disturbance: ~29% lower concentration"),
    "high_stress":  (0.70, "nordkap2016", "highest stress group: up to ~38% lower; 0.70 used conservatively"),
    "sedentary":    (0.80, "gaskins2015", "high TV/sitting time; 44% lower in the extreme group, 0.80 used conservatively"),
    "tight":        (0.80, "minguez2018", "boxers had 25% higher concentration -> tight = 1/1.25"),
    "hot_bath":     (0.85, "shefi2007", "regular wet heat; small study"),
    "aas":          (0.10, "christou2017", "current anabolic steroid use; frequent azoospermia"),
    "varicocele":   (0.70, "eau2024", "clinical varicocele"),
    "cryptorchid":  (0.70, "eau2024", "history of undescended testis"),
    "mumps":        (0.80, "masarani2006", "post-pubertal orchitis"),
}
# effect on progressive motility (percentage points)
MOTILITY = {"smoker": (-4, "sharma2016"), "obese": (-3, "sermondade2013"), "diabetes": (-4, "ding2015"),
            "osa": (-3, "torres2014"), "vitd_low": (-3, "blomberg2011"), "aas": (-10, "christou2017")}

# assumed prevalences (Abu Dhabi adult men, rounded; for simulation only)
PREVALENCE = {"obese": 0.30, "overweight": 0.38, "smoker": 0.22, "alcohol_mod": 0.08, "alcohol_high": 0.02,
              "short_sleep": 0.30, "high_stress": 0.20, "sedentary": 0.40, "tight": 0.45, "hot_bath": 0.10,
              "aas": 0.03, "varicocele": 0.12, "cryptorchid": 0.02, "mumps": 0.02, "diabetes": 0.12,
              "osa": 0.20, "vitd_low": 0.45}
GROUPS = {"Emirati": 0.20, "Arab expat": 0.20, "South Asian": 0.40, "Western": 0.08, "Other": 0.12}

FEATURES = ["age", "bmi", "smoker", "alcohol_units", "sleep_h", "pss4", "sitting_h", "tight", "hot_bath",
            "aas", "varicocele", "cryptorchid", "mumps", "diabetes", "stop_bang", "vitd_low"]


def simulate(n=20000, seed=42):
    rng = np.random.default_rng(seed)
    b = lambda p: rng.random(n) < p
    age = rng.uniform(20, 45, n)
    group = rng.choice(list(GROUPS), n, p=list(GROUPS.values()))
    bmi = np.clip(rng.normal(27.5, 4.5, n), 17, 50)
    obese, overweight = bmi >= 30, (bmi >= 25) & (bmi < 30)
    smoker = b(PREVALENCE["smoker"])
    alc = np.where(b(0.10), rng.gamma(2, 7, n), 0)
    sleep_h = np.clip(rng.normal(6.6, 1.0, n), 3.5, 10)
    pss4 = np.clip(np.round(rng.normal(6, 3, n)), 0, 16)
    sitting = np.clip(rng.normal(7, 2.5, n), 1, 16)
    tight, hot = b(PREVALENCE["tight"]), b(PREVALENCE["hot_bath"])
    aas, vari, crypt, mumps = b(0.03), b(0.12), b(0.02), b(0.02)
    diabetes = b(np.clip(0.04 + 0.01 * (bmi - 25), 0.02, 0.4))
    osa_true = b(np.clip(0.05 + 0.02 * (bmi - 25) + 0.004 * (age - 20), 0.02, 0.7))
    stop_bang = np.clip(np.round(1 + 2.5 * osa_true + 0.08 * (bmi - 25) + 0.03 * (age - 30) + rng.normal(0, 1, n)), 1, 8)
    vitd = b(PREVALENCE["vitd_low"])

    f = np.ones(n)
    f *= np.where(obese, EFFECTS["obese"][0], np.where(overweight, EFFECTS["overweight"][0], 1))
    f *= np.where(smoker, EFFECTS["smoker"][0], 1)
    f *= np.where(alc >= 25, EFFECTS["alcohol_high"][0], np.where(alc >= 5, EFFECTS["alcohol_mod"][0], 1))
    f *= np.where(sleep_h < 6, EFFECTS["short_sleep"][0], 1)
    f *= np.where(pss4 >= 10, EFFECTS["high_stress"][0], 1)
    f *= np.where(sitting >= 9, EFFECTS["sedentary"][0], 1)
    f *= np.where(tight, EFFECTS["tight"][0], 1)
    f *= np.where(hot, EFFECTS["hot_bath"][0], 1)
    f *= np.where(aas, EFFECTS["aas"][0], 1)
    f *= np.where(vari, EFFECTS["varicocele"][0], 1)
    f *= np.where(crypt, EFFECTS["cryptorchid"][0], 1)
    f *= np.where(mumps, EFFECTS["mumps"][0], 1)
    # baseline: median ~55 M/mL, wide biological + measurement variation
    conc = np.exp(rng.normal(np.log(55), 0.85, n)) * f
    pm = rng.normal(50, 12, n) + sum(np.where(m, MOTILITY[k][0], 0) for k, m in
                                     (("smoker", smoker), ("obese", obese), ("diabetes", diabetes), ("osa", osa_true),
                                      ("vitd_low", vitd), ("aas", aas)))
    below = (conc < 16) | (pm < 30)
    X = np.column_stack([age, bmi, smoker, alc, sleep_h, pss4, sitting, tight, hot, aas, vari, crypt, mumps,
                         diabetes, stop_bang, vitd]).astype(float)
    return X, below.astype(int), {"group": group, "conc": conc, "pm": pm}


def train(n=20000, seed=42):
    import joblib
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.model_selection import train_test_split
    X, y, extra = simulate(n, seed)
    Xtr, Xte, ytr, yte, gtr, gte = train_test_split(X, y, extra["group"], test_size=0.25, random_state=seed, stratify=y)
    m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=250, random_state=seed).fit(Xtr, ytr)
    p = m.predict_proba(Xte)[:, 1]
    meta = {"features": FEATURES, "n_train": len(ytr), "n_test": len(yte), "prevalence": round(float(y.mean()), 3),
            "auc_test": round(float(roc_auc_score(yte, p)), 3), "brier_test": round(float(brier_score_loss(yte, p)), 3),
            "effects": {k: {"factor": v[0], "ref": v[1], "note": v[2]} for k, v in EFFECTS.items()},
            "prevalence_assumptions": PREVALENCE}
    MODEL_FILE.parent.mkdir(exist_ok=True)
    joblib.dump(m, MODEL_FILE)
    META_FILE.write_text(json.dumps(meta, indent=1))
    return m, meta, (Xte, yte, gte, p)


_cache = {}


def load():
    if "m" not in _cache:
        import joblib
        if not MODEL_FILE.exists():
            train()
        _cache["m"] = joblib.load(MODEL_FILE)
        _cache["meta"] = json.loads(META_FILE.read_text())
        import shap
        bg, _, _ = simulate(300, seed=1)
        _cache["explainer"] = shap.TreeExplainer(_cache["m"], bg[:100])
    return _cache


def encode(answers, ins, wearable=None):
    wearable = wearable or {}
    g = lambda k, d=0.0: _f(answers.get(k), d)
    audit = ins.get("audit_c", 0)
    units = {0: 0, 1: 1, 2: 3, 3: 6, 4: 10, 5: 15, 6: 20, 7: 25}.get(min(audit, 7), 30)
    return [g("age", 30), ins.get("bmi") or 26, float(answers.get("smoking") == "daily"), float(units),
            wearable.get("sleep_avg_h") or g("sleep_h", 7), float(ins.get("pss4", 6)), g("sitting_h", 7),
            float(answers.get("underwear") == "tight"), float(_f(answers.get("hot_bath"), 0) >= 1),
            float(answers.get("aas") == "current"), float(answers.get("varicocele") == "yes"),
            float(answers.get("cryptorchidism") == "yes"), float(answers.get("mumps") == "yes"),
            float(answers.get("diabetes") == "yes"), float(ins.get("stop_bang", 1)), float(answers.get("vitd") == "yes")]


def explain(answers, ins, wearable=None):
    c = load()
    x = np.array([encode(answers, ins, wearable)])
    p = float(c["m"].predict_proba(x)[0, 1])
    sv = c["explainer"](x)
    vals = sv.values[0]
    base = float(np.ravel(sv.base_values)[0])
    contrib = sorted(({"feature": f, "value": float(x[0, i]), "shap": round(float(vals[i]), 4)}
                      for i, f in enumerate(FEATURES)), key=lambda d: -abs(d["shap"]))
    return {"probability": round(p, 3), "base_value": round(base, 4), "contributions": contrib,
            "units": "log-odds", "model": "Gradient boosting on simulated cohort (literature effect sizes)",
            "auc_test": c["meta"]["auc_test"]}


def _f(v, d):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d
