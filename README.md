# Riaya (رعاية): a private front door to men's reproductive health

A privacy-first, Arabic-first pre-screen that helps men in Abu Dhabi understand and act on reproductive-health signals early. It routes each man to the right level of care, with a clinician approving every referral. It is built to plug into the IFHAS reproductive-health screening module.

## What's in it
- **Evidence graph** (`knowledge/graph.json`): 69 factors and 148 cause→effect links, each with an evidence grade (A–D) and a source (95 references). It also holds 23 measurable signals (watch, phone, CGM, questionnaire, lab) with thresholds, and 8 red flags. The graph drives scoring and explanations, and is validated at server start.
- **Intake** in Arabic and English, using validated instruments: STOP-Bang, AUDIT-C, PHQ-2, PSS-4 and ADAM.
- **Device data**: Apple Health export (sleep, steps, HRV, SpO2, glucose, caffeine, alcohol), Dexcom/Libre CGM CSV, a generic daily CSV (Fitbit/Garmin/Health Connect/screen time), or manual entry. Raw files are never stored.
- **Test results**: interpreted against WHO 2021 reference limits, from a lab report, a quantitative smartphone device (YO-type) or a simple home test.
- **Explainability**: Shapley attribution over the evidence graph, a gradient-boosting model with a SHAP waterfall (simulated cohort with literature effect sizes), and a logistic model trained on real data (UCI Fertility, n=100) as a second opinion.
- **Triage**: deterministic, ordered rules, each citing its guideline. Red flags override everything. Clinician approval is required for specialist referrals.
- **Clinician console**: review queue, case explanation, approve/modify, booking and attendance tracking, outcome and fairness metrics, access log.
- **IFHAS hand-off**: FHIR R4 Bundle export.
- **Privacy**: no identity data, granular consent, encryption at rest, revocable share codes, delete/export, audit log.
- **Care navigation**: after approval, a handover package (FHIR referral document plus a readable letter) for the receiving clinic. It includes results already available (so tests are not repeated) and the man's preferences.
- **Genomic flag**: automatic karyotype / AZF / CFTR and genetic-counselling flags for severe results, high FSH or a family pattern.
- **Rapid clinical review**: 24–48 h target with a live timer, encrypted patient–clinician messages, and a private video room.
- **Partner mode**: a revocable link that shows his wife only that he completed the check and the kind of next step.
- **Blood results and environment**: optional testosterone/LH/FSH/HbA1c/vitamin D entry, plus occupation and traffic/industry proximity.
- **Clothing check**: reads a care label (typed, or photographed with on-device OCR) and gives a groin-heat index with evidence-graded notes.

## Run it
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
```
- User app: http://localhost:8000 · Clinician console: http://localhost:8000/clinician.html (demo login `clinician` / `demo-clinician`; set `RIAYA_CLINICIAN_PASSWORD` for anything real) · Evidence map: /graph.html · Clothing check: /fabric.html · API docs: /api/docs

```bash
.venv/bin/python -m pytest -q backend/tests          # end-to-end API tests
.venv/bin/python validation/run_validation.py         # writes validation/REPORT.md
.venv/bin/python validation/run_validation.py --seed-demo   # also loads simulated cases into the console
```

## Docs
- `validation/REPORT.md`: triage vignettes, real-data model, simulated cohort, calibration, fairness, pathway simulation, limitations
- `docs/RESEARCH_VERIFICATION.md`: every claim checked against the literature, including corrections
- `docs/CULTURAL_DESIGN.md`: each cultural/religious barrier and how the product handles it
- `docs/PRIVACY_AND_REGULATION.md`: applicable UAE rules and the controls in the code
- `docs/SYSTEM_LAYERS.md`: each gap Abu Dhabi has named, mapped to a working feature
- `docs/IFHAS_AND_ROADMAP.md`: integration, referral levels, pilot roadmap and value measures
