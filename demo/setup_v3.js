// Creates the demo patients used by the Care Connect, coordinator, lab timeline, plan and lab report scenes,
// and merges their tokens into <outdir>/data.json.
// Usage (server on :8000 with RIAYA_ENABLE_DEMO_CLINICIAN=true): node demo/setup_v3.js <outdir> <sqlite-db-path>
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const [OUT, DB] = process.argv.slice(2);
const B = "http://localhost:8000";
const BASE = { age: 34, height_cm: 175, weight_kg: 98, smoking: "daily", cigs_per_day: 15, sitting_h: 10, sleep_h: 5.5, underwear: "tight",
  snore: "yes", tired: "yes", observed: "no", bp: "no", pss1: 3, pss2: 1, pss3: 1, pss4: 3, phq1: 0, phq2: 1, reason: ["future"] };
const j = async (m, p, body, tok) => {
  const r = await fetch(B + p, { method: m, headers: { "Content-Type": "application/json", ...(tok ? { Authorization: `Bearer ${tok}` } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text(); if (!r.ok) throw new Error(`${m} ${p}: ${t}`); try { return JSON.parse(t); } catch { return t; }
};
async function patient(answers, lang = "ar") {
  const tok = (await j("POST", "/api/session", { lang })).token;
  await j("POST", "/api/consent", { core: true, clinician_review: true, wearables: true }, tok);
  const aid = (await j("POST", "/api/assessments?channel=web", null, tok)).id;
  await j("PUT", `/api/assessments/${aid}/answers`, { answers }, tok);
  await j("POST", `/api/assessments/${aid}/submit`, null, tok);
  return { token: tok, aid };
}
const setWeek = (planId, week) => execFileSync("python3", ["-c",
  `import sqlite3,time,sys; c=sqlite3.connect(sys.argv[1]); c.execute("UPDATE plans SET start_at=? WHERE id=?", (time.time()-(${week}-1)*7*86400-120, sys.argv[2])); c.commit()`, DB, planId]);

(async () => {
  for (let i = 0; i < 40 && !(await fetch(B + "/api/health").then(r => r.ok).catch(() => false)); i++) await new Promise(r => setTimeout(r, 500));
  const ctok = (await j("POST", "/api/clinician/login", { username: "clinician", password: "demo-clinician" })).token;
  const data = fs.existsSync(path.join(OUT, "data.json")) ? JSON.parse(fs.readFileSync(path.join(OUT, "data.json"))) : {};

  // Care Connect: referral approved, ready to choose a clinic
  data.care = await patient({ ...BASE, aas: "current" });
  await j("POST", `/api/clinician/cases/${data.care.aid}/review`, { decision: "approve" }, ctok);
  // a second man who already asked for a visit, so the coordinator queue has a request
  data.coord = await patient({ ...BASE, age: 29, aas: "current" }, "en");
  await j("POST", `/api/clinician/cases/${data.coord.aid}/review`, { decision: "approve" }, ctok);
  await j("POST", `/api/assessments/${data.coord.aid}/appointment`, { provider_id: "ssmc", times: ["evening"], days: ["weekend"] }, data.coord.token);

  // lab report scene: a fresh summary
  data.labreport = await patient(BASE);

  // lab timeline and plan: two reports from different labs, reviewed by a doctor, and five weeks of check-ins
  data.labs = await patient(BASE);
  const L = data.labs;
  await j("POST", "/api/me/labs", { assessment_id: L.aid, collected_on: "2026-07-20", lab_name: "City Lab", abstinence_days: 3, time: "11:40", fasting: false,
    values: [{ field: "concentration_m_per_ml", value: 8.2, ref_low: 16, ref_text: ">= 16" }, { field: "progressive_motility_pct", value: 19, ref_low: 30, ref_text: ">= 30" },
             { field: "testosterone", value: 8.9, ref_low: 8.6, ref_high: 29, ref_text: "8.6-29" }, { field: "vitamin_d", value: 14, ref_low: 30, ref_high: 100, ref_text: "30-100" }] }, L.token);
  await j("POST", "/api/me/labs", { assessment_id: L.aid, collected_on: "2026-10-28", lab_name: "Al Noor Lab", abstinence_days: 3, time: "08:20", fasting: true,
    values: [{ field: "concentration_m_per_ml", value: 11.5, ref_low: 16, ref_text: ">= 16" }, { field: "progressive_motility_pct", value: 24, ref_low: 30, ref_text: ">= 30" },
             { field: "testosterone", value: 9.8, ref_low: 8.6, ref_high: 29, ref_text: "8.6-29" }, { field: "vitamin_d", value: 17, ref_low: 30, ref_high: 100, ref_text: "30-100" }] }, L.token);
  for (const x of (await j("GET", "/api/clinician/labs/pending", null, ctok)).results.filter(x => x.assessment_id === L.aid))
    await j("POST", `/api/clinician/labs/${x.id}`, { action: "accept" }, ctok);
  await j("POST", `/api/assessments/${L.aid}/plan`, { nodes: ["smoking", "sleep_loss", "tight_underwear"] }, L.token);
  const pid = (await j("GET", "/api/clinician/plans", null, ctok)).plans.find(p => p.assessment_id === L.aid).id;
  await j("POST", `/api/clinician/plans/${pid}`, { action: "change", remove: [], note: "Good choices. We will look at your sleep again at week 6." }, ctok);
  const series = { smoking: [14, 11, 9, 6, 5], sleep_loss: [5.6, 6.1, 6.4, 6.8, 7.1], tight_underwear: [2, 4, 5, 6, 7] }, adh = [1, 2, 2, 3, 3];
  for (let w = 1; w <= 5; w++) {
    setWeek(pid, w);
    const items = Object.fromEntries(Object.keys(series).map(n => [n, { adherence: adh[w - 1], value: series[n][w - 1] }]));
    await j("POST", "/api/me/plan/checkin", { items, energy: 3 }, L.token);
  }
  setWeek(pid, 6);
  fs.writeFileSync(path.join(OUT, "data.json"), JSON.stringify(data));
  console.log("ready", Object.keys(data).join(", "));
})();
