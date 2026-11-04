# Male Reproductive Health — Early Risk Front Door (Future Health Challenge)

Explainable, culturally sensitive early-risk tool for men. Its core is an evidence-graded **causal knowledge graph** (exposure → condition → mechanism → outcome). Every signal and referral the app produces traces back to a cited edge in that graph.

- `knowledge/graph.js`: the graph (62 nodes, 132 graded and cited edges, 8 red flags, 67 sources)
- `js/engine.js`: pathway tracing (up/downstream, strongest paths to reduced fertility)
- `js/fabric.js`: garment check (fit + fibre → groin-heat index, with evidence-graded notes)
- `index.html`: interactive graph explorer + fabric check (works offline; d3 is vendored)
- `docs/RESEARCH_VERIFICATION.md`: claims checked against the literature, plus the gaps that were added
- `node scripts/validate.js`: graph integrity checks + smoke tests

Open `index.html` in a browser.
