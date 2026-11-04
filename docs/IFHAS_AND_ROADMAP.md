# Fitting into Abu Dhabi's system

## Where it sits
In 2025, ADPHC expanded IFHAS (periodic comprehensive screening for Thiqa holders aged 18–75) to include reproductive-health screening for adults aged 20–35. Riaya is designed as the **private digital pre-screen** for that module, not as a parallel service:

1. The man completes the check privately on his phone (about 10 minutes).
2. He chooses to download a **FHIR R4 Bundle** (`GET /api/assessments/{id}/ifhas`) or give the clinic a one-time code. The bundle contains:
   - a `QuestionnaireResponse` with all his answers
   - `Observation`s: BMI, height, weight and waist (LOINC), PHQ-2 and AUDIT-C (LOINC), STOP-Bang, PSS-4, ADAM, semen findings, and every screening signal with its source
   - a `ServiceRequest` with the suggested level, reasons and tests (status `draft` until a clinician approves it)
3. At the IFHAS visit, the clinic imports the bundle into its EMR (or via Malaffi), so the reproductive-health questionnaire is pre-filled and the visit focuses on examination and tests.

No identifiers are included. The clinic links the bundle to his record at the visit. Mapping to the official IFHAS questionnaire fields has to be confirmed with ADPHC; LOINC codes are used only where they are standard.

## Referral levels
| Level | Typical trigger | Review |
|---|---|---|
| Emergency / urgent urology / same-day | Red flags (torsion, lump, haematospermia, fever with pain, self-harm) | Immediate instructions, reviewed afterwards |
| Andrology / urology | Azoospermia, concentration < 5 M/mL, 2+ low parameters, steroids, varicocele, undescended testis, chemo | Clinician approval required |
| Fertility services (couple) | Trying ≥ 12 months (≥ 6 if wife ≥ 35) | Clinician approval required |
| Primary care / IFHAS | Metabolic signals, STOP-Bang, ADAM+, a mild single low result, high signal load | Routine |
| Self-care plan | Few signals | Recheck in 3 months |

## Roadmap
**Phase 1 (0–6 months): IFHAS pilot.** Offer as an optional pre-screen at 2–3 IFHAS providers. Measure completion, time to evaluation, referral completion, the agreement between clinician and suggested level, and the trust score. Hold a blinded vignette review by a panel of UAE clinicians. Get scholar sign-off on the sample-collection content.

**Phase 2 (6–12 months): specialist pathway.** Partner with SEHA/M42 andrology and urology clinics for direct booking and feedback of outcomes (attended, diagnosis). Retrain the statistical model on real pre-screen and lab-result pairs, and report fairness by nationality group on real data. Integrate an at-home device (YO or equivalent) through its result export.

**Phase 3 (12–24 months): primary care and premarital pathway.** Offer it inside primary-care preconception visits and alongside the premarital screening programme. Add native iOS/Android apps for passive HealthKit/Health Connect and screen-time data.

## Value measures (what the pilot reports)
Completed assessments · completion rate · median minutes to complete · median hours to clinician review · median days from check to evaluation (compared with the usual 12+ months) · referral completion rate · clinician-changed levels · user trust, clarity and comfort (1–5) · all of these by age band and background group. The clinician console's "Outcomes & fairness" tab computes these live from the database.
