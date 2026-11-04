# System layers: what Abu Dhabi says it needs, and what the product does

| Stated gap | Layer | What works today | Where |
|---|---|---|---|
| Men enter the pathway late | **Digital front door** | Private 10-minute check, Arabic-first, no identity data, linked to IFHAS (FHIR export) | `web/index.html`, `/api/assessments/*`, `ifhas.py` |
| Care is fragmented across screening, genetics, fertility and maternity | **Care navigation** | After clinician approval, a handover package for the receiving clinic: a referral letter (FHIR `Composition`, LOINC 57133-1) plus all observations and an active `ServiceRequest`. It lists **results already available, with source and date, marked "do not repeat"**; requested tests are de-duplicated against blood tests the man has already entered. It also carries his language, doctor-gender and contact preferences and the consent scope. | `handover.py`, `/api/clinician/cases/{id}/handover`, console "Care navigation" card |
| Genomic information rarely reaches routine reproductive care | **Genomic flag** | Automatic flag with reasons and suggested tests: azoospermia or < 5 M/mL → karyotype + Y-microdeletion (AZFa/b/c); no sperm with low volume → CFTR (and partner testing); FSH > 12 IU/L → karyotype; consanguinity or family history combined with an abnormal result → genetic counselling. A flag always requires clinician review. The man sees only a gentle note that a genetics specialist explains some results. | `triage.py` (`genomic`) |
| Holistic, future-ready risk model (environment, biochemistry, omics) | **Extensible evidence graph** | Environment inputs (occupation type, living or working near heavy traffic or industry → air-pollution node, Lafuente 2016) and optional blood results (testosterone with LH pattern, FSH, HbA1c, vitamin D) feed the same graph as observed nodes. New data types such as sperm DNA fragmentation, metabolomics or polygenic scores slot in as new signal → node mappings in `graph.json`, without code changes to scoring or explanation. | `labs.py`, `graph.json` (`signals`), `features.py` |
| "It's her problem": sequential, female-first investigation | **Partner mode** | The man can create a link (30 days, revocable) that shows his wife only that he completed the check and the broad next step ("a joint fertility visit is recommended so you can both be seen at the same time"). No answers, scores or results. The token is carried in the URL fragment, so it never reaches server logs or Referer headers. | `/api/assessments/{id}/partner-link`, `/api/partner/{token}`, `web/partner.html` |
| Red flags, clinical boundaries, human oversight | **Rapid clinical review** | Critical findings (severe semen result, lump, blood in semen, dry orgasm, breast changes after steroids) open a rapid review with a **24 h or 48 h target**. These cases go to the top of the queue with a live due/overdue timer. The patient and clinician have an encrypted message thread, and the clinician can open a private video room (Jitsi; set `RIAYA_VIDEO_BASE` to a UAE-hosted instance). A man who declined review consent at the start can request it for this one case with a single tap. | `triage.py` (`rapid_review`, `sla_hours`), `/api/.../messages`, `/video`, `/request-review` |

## Tested behaviour
`backend/tests/test_api.py` covers all of the above end to end (13 tests):
- the genomic flag and its tests (including CFTR)
- the rapid-review SLA and its queue order
- that tests already done are not requested again
- the handover letter's sections, preferences and "do not repeat" wording
- two-way messaging and the video link reaching the man
- that the partner view contains only status and stops working when revoked
- requesting review after first declining it
