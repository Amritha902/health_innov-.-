# Validation report

Generated 2026-11-04 12:32. Re-run with `python validation/run_validation.py`.

## 1. Triage safety on clinical vignettes

26 vignettes, with the expected next step taken from guidelines (WHO 2021, AUA/ASRM 2021, EAU 2024, ASRM 2020).

- Agreement: **26/26**
- Under-triage (safety failures): **0**
- Over-triage: **0**

| Case | Expected | Got | Clinician review |
|---|---|---|---|
| Healthy 28-year-old, general check | self_care | self_care  | no |
| Sudden severe testicular pain | emergency | emergency  | yes |
| New testicular lump | urgent_specialist | urgent_specialist  | yes |
| Painful swollen scrotum with fever | same_day_primary | same_day_primary  | yes |
| Thoughts of self-harm | emergency | emergency  | yes |
| Dry orgasm | andrology | andrology  | yes |
| Lab: no sperm seen | andrology | andrology  | yes |
| Lab: concentration 3 M/mL | andrology | andrology  | yes |
| Lab: mild single low value | primary_care | primary_care  | yes |
| Lab: two parameters low | andrology | andrology  | yes |
| Lab: normal | self_care | self_care  | no |
| Home device below cut-off | primary_care | primary_care  | no |
| Trying 14 months | fertility_services | fertility_services  | yes |
| Trying 7 months, wife 37 | fertility_services | fertility_services  | yes |
| Trying 5 months, wife 29 | self_care | self_care  | no |
| Current anabolic steroid cycle | andrology | andrology  | yes |
| Steroids more than a year ago, otherwise well | self_care..primary_care | self_care  | no |
| Known varicocele | andrology | andrology  | yes |
| Undescended testis as a child | andrology | andrology  | yes |
| Past chemotherapy | andrology | andrology  | yes |
| Loud snoring, apnoeas, BMI 36, age 52 | primary_care | primary_care  | yes |
| Obese with pre-diabetes | primary_care | primary_care  | no |
| Low libido + weaker erections (ADAM+) | primary_care | primary_care  | no |
| Smoker, shisha, short sleep, tight underwear | self_care..primary_care | self_care  | no |
| Possibly untreated past infection | primary_care | primary_care  | no |
| Low mood (PHQ-2 = 4), otherwise well | self_care..primary_care | self_care  | no |

The vignettes were written by the same team that wrote the rules, so this shows the rules do what the guidelines say. It is not an independent accuracy estimate. Next step: a panel of UAE andrologists and family physicians sets the expected answers blind.

## 2. Model on real data: UCI Fertility dataset

100 men, 12 with altered semen analysis (Gil et al. 2012). Repeated stratified 5-fold cross-validation (×20).

| Model | AUC (mean) | AUC 95% range across folds | Brier |
|---|---|---|---|
| logistic | 0.615 | 0.214–0.959 | 0.225 |
| gbm | 0.685 | 0.361–0.944 | 0.122 |

This is a small dataset. The model gives clinicians a second opinion and does not drive triage on its own.

## 3. Gradient boosting + SHAP on the simulated cohort

n = 20000 simulated men; effect sizes come from the literature (see `backend/app/synth.py`). Prevalence of below-reference semen: 0.308.

- Test AUC **0.682**, Brier 0.189
- At threshold 0.4: sensitivity 0.246, specificity 0.933, PPV 0.62, NPV 0.736

Calibration by decile:

| Predicted | Observed | n |
|---|---|---|
| 0.178 | 0.158 | 500 |
| 0.209 | 0.166 | 500 |
| 0.225 | 0.174 | 500 |
| 0.246 | 0.228 | 500 |
| 0.265 | 0.286 | 500 |
| 0.285 | 0.294 | 500 |
| 0.31 | 0.31 | 500 |
| 0.337 | 0.372 | 500 |
| 0.382 | 0.416 | 500 |
| 0.621 | 0.672 | 500 |

The AUC is moderate because semen quality varies a lot even in healthy men. A questionnaire can point to who should test; it cannot replace the test.

### Fairness across subgroups


**age**

| Group | n | Prevalence | AUC | Mean predicted | Flag rate | Sensitivity |
|---|---|---|---|---|---|---|
| 20-29 | 1988 | 0.311 | 0.677 | 0.313 | 0.139 | 0.269 |
| 30-39 | 1967 | 0.3 | 0.69 | 0.301 | 0.109 | 0.231 |
| 40-45 | 1045 | 0.316 | 0.675 | 0.3 | 0.114 | 0.23 |

**bmi**

| Group | n | Prevalence | AUC | Mean predicted | Flag rate | Sensitivity |
|---|---|---|---|---|---|---|
| <25 | 1495 | 0.248 | 0.667 | 0.276 | 0.069 | 0.173 |
| 25-30 | 2134 | 0.297 | 0.674 | 0.292 | 0.086 | 0.196 |
| >=30 | 1371 | 0.389 | 0.654 | 0.36 | 0.236 | 0.356 |

**background**

| Group | n | Prevalence | AUC | Mean predicted | Flag rate | Sensitivity |
|---|---|---|---|---|---|---|
| Emirati | 1009 | 0.298 | 0.676 | 0.299 | 0.114 | 0.243 |
| Arab expat | 997 | 0.318 | 0.669 | 0.315 | 0.146 | 0.297 |
| South Asian | 1993 | 0.302 | 0.693 | 0.306 | 0.121 | 0.246 |
| Western | 417 | 0.324 | 0.712 | 0.305 | 0.106 | 0.222 |
| Other | 584 | 0.315 | 0.655 | 0.303 | 0.11 | 0.179 |

Background (nationality group) has no causal effect in the simulation, so similar AUC and calibration across groups is the expected result. This checks that the pipeline does not introduce bias; real-world fairness needs real data.

## 4. Evidence-graph engine consistency

The graph engine is not trained. It is built only from the cited links. On 2000 simulated men its index ranks outcomes with AUC **0.664**, close to the trained model. This shows the graph and the literature effect sizes agree.

## 5. Pathway simulation (assumed rates)

400 simulated men started; 335 completed; 164 were routed beyond self-care; 95 needed clinician review. Simulated referral completion is 0.652 and the median time to evaluation is 12.1 days. Under the usual pathway the man is often assessed only after his wife's work-up (12+ months).

Assumptions: completion_rate = 0.82; minutes_to_complete = lognormal median ~9; review_hours = uniform 1-24; booked_given_referral = 0.75; attended_given_booked = 0.85; days_to_attend = uniform 3-21; comparator_days_to_male_evaluation = 12+ months (usual pathway: male assessed after female work-up)

Levels: andrology: 54, fertility_services: 29, primary_care: 81, self_care: 171

## Limitations, stated plainly

- The simulated cohort reproduces published effect sizes; it is not evidence of real-world accuracy.
- The UCI dataset is small (n=100), from Spain, and uses WHO 2010 criteria.
- At-home device performance figures come from the manufacturers' published studies and were not re-tested here.
- User trust and usability need a real study (target: 30–50 men in Abu Dhabi, with a validated trust scale).
- Next step: a prospective pilot with an Abu Dhabi clinical partner, comparing the pre-screen result with laboratory semen analysis.
