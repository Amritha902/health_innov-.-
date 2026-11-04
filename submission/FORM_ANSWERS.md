# Submission form answers

Copy each answer into the Hack2skill form. Character counts are within the form's limits.

## Challenges
Choose the male reproductive health sub-challenge (identifying male reproductive health risks early).

## Solution summary (1774 / 2,000 characters)

Riaya (رعاية, "care") is a private, Arabic-first front door to men's reproductive health for Abu Dhabi. Men usually reach fertility care late, after months of trying and after their wife has been assessed, because of stigma, privacy and inconvenience. Riaya lets a man check the everyday things that affect his reproductive health without giving a name, phone number or ID: by voice or chat in Gulf Arabic or English, a detailed form, his watch or glucose sensor, an uploaded lab report, or WhatsApp.

It screens; it never diagnoses. Every finding shows what was seen, why it matters, the strength of the evidence (an evidence map of 148 cause-and-effect links graded A–D from 95 sources) and its limits. Ordered guideline rules (WHO 2021, AUA/ASRM, EAU) suggest the level of care; red flags go straight to urgent advice; a licensed doctor approves every specialist referral and must give a reason for any change.

Riaya then closes the loop. Care Connect lets him choose a clinic after approval; a coordinator confirms the time with the clinic, he gets a calendar entry that says only "Appointment", and attendance and the reasons for missed visits are recorded. Lab Intelligence keeps every result against its own lab's range, checks how the sample was taken and lets a doctor reconcile each value. A doctor-reviewed 12-week companion tracks the habits he chose, because sperm take about three months to develop. A FHIR R4 hand-off feeds the IFHAS screening visit, and a k-anonymised dashboard gives ADPHC and DoH the funnel, time to care, barriers and fairness.

Privacy is built in: consent per purpose that can be withdrawn, encryption at rest, a hide button, one-time share codes, export and delete everything, and a deployment template for Microsoft Azure in the UAE.

## Solution stage
Working prototype (choose the closest option, for example "Prototype" or "MVP").

## What has been built during the challenge? (1197 / 1,500 characters)

A complete, working prototype (open source on GitHub, 32 automated tests passing on SQLite and PostgreSQL):
- Patient web app (installable, Arabic-first, accessible) with voice/chat intake in Gulf Arabic and English, validated questionnaires, Apple Health and glucose-sensor import, and WhatsApp via Twilio.
- Lab report reader: table-aware extraction with each lab's own reference range, confidence, and collection checks; results timeline with doctor reconciliation.
- Explainable screening engine: graded evidence map, Shapley attribution, gradient boosting with SHAP, guideline triage with red flags.
- Doctor console: review queue with deadlines, evidence explorer, override with reason, messages and voice notes, lab review, plan review, access log.
- Care Connect: verified clinic directory, appointment requests, coordinator confirmation, discreet calendar file, attendance and barrier tracking.
- 12-week companion: doctor-reviewed goals, weekly check-ins, trends, discreet reminders.
- Privacy: per-purpose consent and withdrawal, encryption, recovery code, export, delete, k-anonymised programme dashboard.
- FHIR R4 hand-off, CI on GitHub Actions, and an Azure UAE deployment template.

## Technology type
Tick: **Software application**, **Machine learning**, **Analytics**.
Do not tick AI agent (Riaya uses no generative AI agent), Wearable, Sensor, Connected device or Other hardware. It reads data exported from devices but is not hardware.

## Prototype / Deployment link
The live address of the deployed app: the Azure UAE address from `docs/AZURE.md` step 3, or the Render address.

## Upload your solution deck
`submission/Riaya_submission.pdf` (1.6 MB, under the 5 MB limit). First fill in the four red placeholders in `submission/Riaya_submission.pptx`:
- country;
- organisation;
- age confirmation;
- prototype link.

Then export to PDF again.

## Conflict of interest
None. No member of our team has a conflict of interest to declare.

## Software, hardware or both
Software.

## Demo video link
Upload `docs/media/riaya-demo.mp4` (2:40) to YouTube as **Unlisted**, and paste the link.
