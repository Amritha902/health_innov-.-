# Cultural design: how each barrier is handled in the product

| Barrier (from the team's research) | What the product does | Where |
|---|---|---|
| Fertility is equated with virility | The word "infertility" never appears in user screens. The end point is shown as "fertility potential". The check is framed as a men's health check covering energy, hormones and the future family. | `web/js/i18n.js`, `backend/app/assessment.py` (`USER_TERMS`), test `test_full_flow_and_review` asserts no "infertil"/"risk" in output |
| Religious guilt around sample collection | An optional "Questions about how a sample is collected?" panel lists clinic, home and marital collection-device options, notes that many scholars consider collection for medical purposes permissible, and points to the UAE's official fatwa service. Marked for scholar review before launch. | Tests step, `web/js/i18n.js` (`collect`) |
| "It's her problem": men are assessed after the woman | The entry point does not depend on a couple's diagnosis ("planning ahead", "general check" and "fitness" are all valid reasons). When a couple has been trying 12 months (6 if the wife is 35+), the message says the man is assessed **at the same time as**, not after, his wife. | `questionnaire.py` (`reason`), `triage.py` (`fertility_services`) |
| Family honour and a narrow circle of trust | No account, name, phone, email or Emirates ID. A random device token is the only link. No notifications or messages that family could see. A **Quick exit** button clears the screen and replaces the browser history entry. Answers are encrypted at rest. | `main.py` (`/api/session`), `common.js` (`quickExit`), `security.py` |
| Help-seeking seen as weakness | The tone is about taking charge: "Take charge of your health — privately", "a smart next step", "three opportunities". No sympathy language and no "at risk". | `i18n.js`, `plan.py` |
| Assumptions about marriage and children | Goals are multi-select and optional. Partner questions appear only if the man says he is trying for a child now. | `questionnaire.py` (`show_if`) |
| Sensitive topics (alcohol, drugs, steroids, STIs, consanguinity) | Every sensitive item has "Prefer not to say". Alcohol says "many people never do", and consanguinity says "common and nothing to worry about on its own". Short notes explain why each question is asked. | `questionnaire.py` (`sensitive`, `help_*`) |
| Arabic first | The app opens in Arabic, right-to-left, with an Arabic font. English is one tap away. All 68 graph nodes have Arabic labels. | `index.html`, `graph.json` (`label_ar`) |
| Local life | Shisha/midwakh/dokha, karak and late meals, kandura and wizar in the clothing check, outdoor heat and long driving, low vitamin D, and Saturday–Sunday weekends in the social-jetlag calculation. | `questionnaire.py`, `fabric.py`, `wearables.py` |
| Gym culture | A direct, non-judgemental steroid/TRT/SARMs question that explains this is common and usually reversible, plus supervised-recovery guidance and andrology routing. | `questionnaire.py` (`aas`), `triage.py` |

## Before launch
- Arabic copy reviewed by native-speaking clinicians, and the sample-collection text reviewed by a qualified religious scholar.
- Usability sessions with 30–50 men across Emirati, Arab-expat and South-Asian groups, measuring trust, clarity and comfort (the feedback widget already collects these on a 1–5 scale).
- Urdu/Hindi and Malayalam translations for the large South-Asian population.
