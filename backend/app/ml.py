"""Statistical model trained on real data: UCI Fertility dataset (Gil et al. 2012; 100 men, WHO 2010 semen
analysis, 12 'altered'). Small, so it is used as a second opinion for clinicians, never on its own.

Features (as encoded in the dataset):
 season (-1 winter, -0.33 spring, 0.33 summer, 1 autumn), age (18-36 -> 0-1), childhood disease, accident/trauma,
 surgery, high fever (-1 <3 months, 0 >3 months, 1 none), alcohol frequency (0.2 several/day .. 1 hardly ever),
 smoking (-1 never, 0 occasional, 1 daily), sitting hours/day (/16)
"""
import json
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "uci_fertility" / "fertility_Diagnosis.txt"
MODEL_PATH = ROOT / "data" / "uci_model.json"
FEATURES = ["season", "age", "childhood_disease", "trauma", "surgery", "fever", "alcohol_freq", "smoking", "sitting"]


def load():
    X, y = [], []
    for line in DATA.read_text().strip().splitlines():
        parts = line.split(",")
        X.append([float(v) for v in parts[:9]])
        y.append(1 if parts[9].strip() == "O" else 0)
    return np.array(X), np.array(y)


def _pipeline():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.3, class_weight="balanced", max_iter=1000))


def evaluate(seed=0, repeats=20):
    """Repeated stratified 5-fold CV; returns AUC mean and 95% interval for logistic regression and gradient boosting."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score, brier_score_loss
    from sklearn.model_selection import RepeatedStratifiedKFold
    X, y = load()
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=repeats, random_state=seed)
    res = {}
    for name, make in (("logistic", _pipeline),
                       ("gbm", lambda: GradientBoostingClassifier(n_estimators=100, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=seed))):
        aucs, briers = [], []
        for tr, te in cv.split(X, y):
            m = make().fit(X[tr], y[tr])
            p = m.predict_proba(X[te])[:, 1]
            aucs.append(roc_auc_score(y[te], p))
            briers.append(brier_score_loss(y[te], p))
        aucs = np.array(aucs)
        res[name] = {"auc_mean": round(float(aucs.mean()), 3), "auc_ci95": [round(float(np.percentile(aucs, 2.5)), 3), round(float(np.percentile(aucs, 97.5)), 3)],
                     "brier": round(float(np.mean(briers)), 3)}
    res["n"] = int(len(y)); res["positives"] = int(y.sum())
    return res


def train():
    X, y = load()
    m = _pipeline().fit(X, y)
    sc, lr = m.named_steps["standardscaler"], m.named_steps["logisticregression"]
    model = {"features": FEATURES, "mean": sc.mean_.tolist(), "scale": sc.scale_.tolist(),
             "coef": lr.coef_[0].tolist(), "intercept": float(lr.intercept_[0]),
             "train_prevalence": float(y.mean()), "x_mean": X.mean(0).tolist()}
    MODEL_PATH.write_text(json.dumps(model, indent=1))
    return model


_model = None


def model():
    global _model
    if _model is None:
        _model = json.loads(MODEL_PATH.read_text()) if MODEL_PATH.exists() else train()
    return _model


def encode(answers, today=None):
    today = today or date.today()
    season = {12: -1, 1: -1, 2: -1, 3: -0.33, 4: -0.33, 5: -0.33, 6: 0.33, 7: 0.33, 8: 0.33}.get(today.month, 1)
    age = float(answers.get("age") or 30)
    audit1 = answers.get("audit1")
    alcohol = {0: 1.0, 1: 0.8, 2: 0.8, 3: 0.6, 4: 0.4}.get(int(audit1) if audit1 not in (None, "skip") else 0, 1.0)
    smoke = {"daily": 1, "occasional": 0, "former": -1, "never": -1}.get(answers.get("smoking"), -1)
    return [season, min(1, max(0, (age - 18) / 18)),
            1 if answers.get("mumps") == "yes" else 0,
            1 if answers.get("testis_injury") == "yes" else 0,
            1 if answers.get("testis_injury") == "yes" or answers.get("cryptorchidism") == "yes" else 0,
            -1 if answers.get("fever") == "yes" else 1,
            alcohol, smoke, min(1, float(answers.get("sitting_h") or 6) / 16)]


def predict(answers):
    """Probability of an altered semen analysis + exact per-feature contributions (log-odds).
    For a linear model with standardised inputs, coef * (x - mean) is the exact SHAP value."""
    m = model()
    x = np.array(encode(answers))
    z = (x - np.array(m["mean"])) / np.array(m["scale"])
    coef = np.array(m["coef"])
    logit = m["intercept"] + float(coef @ z)
    p = 1 / (1 + np.exp(-logit))
    contrib = {f: round(float(c * v), 3) for f, c, v in zip(m["features"], coef, z)}
    # class_weight='balanced' shifts the intercept; recalibrate to the training prevalence
    base_logit = m["intercept"]
    prior = m["train_prevalence"]
    adj = np.log(prior / (1 - prior))
    p_cal = 1 / (1 + np.exp(-(logit - base_logit + adj + float(coef @ ((np.array(m["x_mean"]) - np.array(m["mean"])) / np.array(m["scale"]))))))
    return {"probability": round(float(p_cal), 3), "balanced_score": round(float(p), 3),
            "contributions": dict(sorted(contrib.items(), key=lambda kv: -abs(kv[1]))),
            "model": "Logistic regression, UCI Fertility dataset (n=100)", "ref": "gil2012"}
