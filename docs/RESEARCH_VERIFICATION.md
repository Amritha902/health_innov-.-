# Research verification: your claims checked

Everything below is encoded in `knowledge/graph.json` as cited, graded edges. Grades: **A** meta-analysis/guideline · **B** human observational · **C** animal/small/extrapolated · **D** plausible only.

## 1. Your 10 factors: verified, kept

| Factor | Verdict | Strongest anchor | Grade |
|---|---|---|---|
| Obesity | Confirmed | Sermondade 2013 meta-analysis (oligo-/azoospermia ↑ with BMI) | A |
| Diet | Confirmed | Salas-Huetos 2017 systematic review; Gaskins 2012 (prudent diet) | B |
| Psychological stress | Confirmed (human data is observational) | Nordkap 2016, 1,215 Danish men | B |
| RF-EMR / phones / laptops | **Mixed.** Keep it, but label it "inconsistent evidence." The laptop **heat** effect is the stronger one (Sheynkin 2005) | Kim 2021 meta (motility) | B/C |
| Sleep apnoea | Confirmed. Strong pitch point because it's under-recognised and treatable | Luboshitzky 2002; Torres 2014 | A/B |
| Sleep deprivation / circadian | Confirmed | Jensen 2013; Leproult 2011 (1 week of 5 h sleep → T −10–15%) | B |
| Smoking | Confirmed | Sharma 2016 meta, 5,865 men | A |
| Alcohol | Confirmed | Jensen 2014 (≥5 units/wk); Ricci 2017 meta | A/B |
| Recreational drugs | Anabolic steroids strongest; cannabis conflicting | WHO 1990; Christou 2017 | A |
| EDCs | Confirmed (mostly mechanistic + epidemiological) | Skakkebaek 2016 | B |

## 2. Fabric / polyester idea: keep it, but reframe

| Your claim | What the evidence says | How we use it |
|---|---|---|
| "Polyester is bad for sperm" | Only Shafik's small studies from 1992–93 (static-charge theory). **Never replicated.** | Shown as grade C. Never drives the score alone |
| "Tight, no breathing room" | **Strongest part of the idea.** Mínguez-Alarcón 2018 (Hum Reprod, 656 men): boxer wearers had 25% higher concentration and 17% higher total count than men in tight underwear. Heat is well established (Durairajanayagam 2015) | **Fit drives the score** (grade B) |
| "Plastic enters your blood from clothes" | **Not established.** Microplastics *are* found in human testes (Hu 2024) and semen (Montano 2023), but they mainly come from food, water and air. Textiles shed fibres mostly in washing (De Falco 2019). BPA has been found in some polyester-spandex sportswear (CEH 2022, grey literature) | Shown only as a grade-D "precautionary" note, with that caveat stated plainly |
| "Polyester pants are the worst thing ever" | Overclaim. Clinician judges will mark this down | Tone: "consider an alternative," with simple swaps |

**Why this framing wins:** the brief asks for *explainable, evidence-graded* signals with screening clearly separated from diagnosis. A tool that rates the strength of its own evidence comes across as trustworthy, while an alarmist one does not.

## 3. Gaps I added (you didn't list these; judges will expect them)

- **Upstream causes of sleep loss:** late caffeine (Drake 2013), night screens → melatonin suppression (Chang 2015), shift work, alcohol, stress, OSA
- **Heat sources:** hot tubs/sauna (reversible; Shefi 2007), laptop on lap, prolonged sitting, **occupational heat and long driving (UAE climate)**
- **Clinical/treatable conditions:** **varicocele** (~35–40% of infertile men; treatable), **genital infections/STIs** (obstruction; treatable early), **mumps orchitis**, **undescended testis** (also raises cancer risk), **chemotherapy** (sperm banking), **diabetes**, **low testosterone**, **erectile dysfunction**
- **Gym culture: anabolic steroids and TRT.** This is the single most avoidable cause of azoospermia, and it is very relevant to the UAE
- **UAE-specific:** shisha/midwakh (dokha), vitamin D deficiency despite the sunshine, consanguinity → genetic causes (handled sensitively and optionally), kandura/wizar clothing
- **Non-modifiable:** paternal age > 40 (de-novo mutations; Kong 2012), genetics
- **Feedback loops:** infertility → stress → worse sleep and hormones; obesity ↔ OSA ↔ sleep loss
- **Male infertility as a marker of wider health:** Eisenberg 2014 (mortality). This is a strong "why screen early" argument
- **8 red flags** that bypass scoring entirely (torsion, testicular lump, haematospermia, fever with pain, dry orgasm, breast enlargement, steroid crash, self-harm). These cover the brief's "safe triage" requirement

## 4. Wearable and phone signals (added)

| Claim | Verdict | How it is used |
|---|---|---|
| Night screens cause poor sleep | Supported: evening light-emitting screens suppress melatonin and delay sleep (Chang 2015) | screen_night → melatonin suppression → sleep loss |
| Heavy screen time causes eye problems and stress | Eye strain is well supported (Sheppard 2018). Links to stress and low mood are cross-sectional only (Madhav 2017) | eye strain grade A, mood grade C (association) |
| Late caffeine shows up as a blood-sugar spike | **Partly wrong.** Caffeine itself lowers insulin sensitivity a little (Lane 2004) but does not cause a large spike. Night-time spikes come mostly from late meals and sugary drinks (Gu 2020), including sweetened karak/coffee | CGM night spikes → glycaemic spikes node. Caffeine timing is read from Apple Health caffeine logs or the questionnaire, not from glucose |
| A watch can screen for sleep apnoea | A watch can give a supporting signal (oxygen dips), but it does not diagnose. STOP-Bang is the validated screen (Chung 2008/2016) | STOP-Bang drives the decision; low-oxygen nights only add weight; the result is a referral for a sleep study |
| A watch can measure stress | Weak. HRV varies a lot between people; it is used only against the man's own baseline and never alone | PSS-4 drives the decision |

Every measurable signal is listed in `knowledge/graph.json` under `signals`, each with its threshold and source.

## 5. Claims in the strategy brief that were checked

| Claim | Status |
|---|---|
| IFHAS added reproductive-health screening for adults aged 20–35 (2025) | Confirmed: ADPHC announcement and provider summaries. The exact test list should be confirmed on ifhas.gov.ae |
| A 2026 Abu Dhabi preconception-care standard exists | **Not found.** There is the DoH Premarital Screening Standard (v3, 2024), mandatory premarital genetic testing, and the Abu Dhabi reproductive-health programme roadmap to 2030. Refer to it as "the direction of DoH's reproductive-health programme", not as a 2026 standard, unless the team has the document |
| ADGM Data Protection Regulations govern this | **Wrong regime.** ADGM rules apply only inside the ADGM free zone. For health data in Abu Dhabi the relevant rules are UAE Federal Law No. 2 of 2019 (health ICT; data stays in the UAE), its implementing decisions, and the DoH ADHICS standard. The federal PDPL (Decree-Law 45/2021) treats health data as sensitive, but it defers to sector-specific health-data law. See `docs/PRIVACY_AND_REGULATION.md` |
| YO 3.0: >97% accuracy, r > 0.88 lay vs technician | Not independently verified here. Quote it as the manufacturer's published figures |
| "Shafafiya platform" for submitting IFHAS questionnaires | Not verified. Shafafiya is DoH's e-claims/transparency platform; Malaffi is Abu Dhabi's health-information exchange. The integration route must be confirmed with ADPHC/DoH. We built a standards-based FHIR R4 export that either route can accept |
| Only 49% of men discuss health with their doctor (CCAD survey) | Source not located. Cite it only with the original link |
| Masturbation for sample collection is religiously fraught for some men | Consistent with published work on Muslim men and infertility. The guidance text is marked for review by a qualified scholar |

## 6. Still to do on your side
- The `u_*` references in `graph.json` are your uploaded reviews. Please send full author/title/DOI details so I can complete them.
- `levine2023` (global sperm-count decline) and `who2023` (1 in 6 affected) are the opening numbers for the pitch deck.
