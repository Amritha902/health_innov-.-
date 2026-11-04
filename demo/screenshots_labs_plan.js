// Captures the Lab Intelligence and 12-week companion screens for the README.
// Usage (server running on :8000 with RIAYA_ENABLE_DEMO_CLINICIAN=true): node demo/screenshots_labs_plan.js <out-dir> <sqlite-db-path>
// The database path is used only to move a plan's start date back, so several weeks of check-ins can be shown.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const [OUT, DB] = process.argv.slice(2);
const B = 'http://localhost:8000';
const BASE = { age: 34, height_cm: 175, weight_kg: 98, smoking: "daily", cigs_per_day: 15, sitting_h: 10, sleep_h: 5.5, underwear: "tight",
  snore: "yes", tired: "yes", observed: "no", bp: "no", pss1: 3, pss2: 1, pss3: 1, pss4: 3, phq1: 0, phq2: 1, reason: ["future"] };
const j = async (m, p, body, tok) => {
  const r = await fetch(B + p, { method: m, headers: { "Content-Type": "application/json", ...(tok ? { Authorization: `Bearer ${tok}` } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text(); if (!r.ok) throw new Error(`${m} ${p}: ${t}`); try { return JSON.parse(t); } catch { return t; }
};
const shot = async (page, name, full = false) => { await page.waitForTimeout(800); await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full }); console.log('saved', name); };
const setWeek = (planId, week) => execFileSync('python3', ['-c',
  `import sqlite3,time,sys; c=sqlite3.connect(sys.argv[1]); c.execute("UPDATE plans SET start_at=? WHERE id=?", (time.time()-(${week}-1)*7*86400-120, sys.argv[2])); c.commit()`, DB, planId]);

(async () => {
  for (let i = 0; i < 40 && !(await fetch(B + '/api/health').then(r => r.ok).catch(() => false)); i++) await new Promise(r => setTimeout(r, 500));
  const tok = (await j("POST", "/api/session", { lang: "en" })).token;
  await j("POST", "/api/consent", { core: true, clinician_review: true, wearables: true }, tok);
  const aid = (await j("POST", "/api/assessments?channel=web", null, tok)).id;
  await j("PUT", `/api/assessments/${aid}/answers`, { answers: BASE }, tok);
  await j("POST", `/api/assessments/${aid}/submit`, null, tok);
  // an earlier report from a different lab, so the timeline has a trend
  await j("POST", "/api/me/labs", { assessment_id: aid, collected_on: "2026-07-20", lab_name: "City Lab", abstinence_days: 3, time: "11:40", fasting: false,
    values: [{ field: "concentration_m_per_ml", value: 8.2, ref_low: 16, ref_text: ">= 16" }, { field: "progressive_motility_pct", value: 19, ref_low: 30, ref_text: ">= 30" },
             { field: "testosterone", value: 8.9, ref_low: 8.6, ref_high: 29, ref_text: "8.6-29" }, { field: "vitamin_d", value: 14, ref_low: 30, ref_high: 100, ref_text: "30-100" }] }, tok);
  const ctok = (await j("POST", "/api/clinician/login", { username: "clinician", password: "demo-clinician" })).token;

  const b = await chromium.launch();
  const phone = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const p = await phone.newPage();
  const errs = []; p.on('pageerror', e => errs.push('patient: ' + e.message));
  await p.goto(B + '/');
  await p.evaluate(({ tok, aid }) => { localStorage.setItem("token", tok); localStorage.setItem("aid", aid); localStorage.setItem("done", "1"); localStorage.setItem("lang", "en"); }, { tok, aid });
  await p.goto(B + '/'); await p.waitForTimeout(1200);
  // lab report: read the sample PDF, review values, ranges, confidence and collection details
  await p.evaluate(() => tests()); await p.waitForTimeout(500);
  await p.click('#lrs'); await p.waitForSelector('#lrok', { timeout: 20000 });
  await p.fill('#lrLab', 'Al Noor Lab');
  await p.evaluate(() => document.querySelector('#lrout').scrollIntoView());
  await shot(p, 'lab-report-review');
  await p.click('#lrok'); await p.waitForSelector('#lrTl');
  await p.evaluate(async () => { await renderLabs(); window.scrollTo(0, 0); }); await shot(p, 'lab-timeline');
  await shot(p, 'lab-timeline-full', true);

  // 12-week plan: choose goals
  await p.evaluate(() => renderPlan()); await p.waitForTimeout(600);
  for (const n of ["smoking", "sleep_loss", "tight_underwear"]) await p.check(`#pnOpts input[value=${n}]`);
  await shot(p, 'plan-choose');
  await p.click('#pnGo'); await p.waitForTimeout(600);

  // doctor side
  const desk = await b.newContext({ viewport: { width: 1360, height: 860 }, deviceScaleFactor: 1.5 });
  const c = await desk.newPage(); c.on('pageerror', e => errs.push('clinician: ' + e.message));
  await c.goto(B + '/clinician.html'); await c.evaluate(t => sessionStorage.setItem("ctoken", t), ctok); await c.goto(B + '/clinician.html'); await c.waitForTimeout(1000);
  await c.click('[data-t=labReview]'); await shot(c, 'clinician-lab-review');
  // correct one value to show reconciliation reaching the patient
  const first = await c.$('#tab tr[data-id]');
  await first.$eval('.cv', (el) => { el.value = el.closest('tr').querySelector('td:nth-child(2)').textContent.split(' ')[0]; });
  await c.click('[data-t=plans]'); await shot(c, 'clinician-plans');
  await c.fill('.note', 'Good choices. Start with these and we will look at your sleep again at week 6.');
  await c.click('.ap'); await c.waitForTimeout(500);
  const pend = (await j("GET", "/api/clinician/labs/pending", null, ctok)).results.filter(x => x.assessment_id === aid);
  const fsh = pend.find(x => x.field === "fsh"); if (fsh) await j("POST", `/api/clinician/labs/${fsh.id}`, { action: "correct", value: 8.6, note: "The report reads 8.6; the scan misread it" }, ctok);
  for (const x of pend.filter(x => x !== fsh)) await j("POST", `/api/clinician/labs/${x.id}`, { action: "accept" }, ctok);

  // five weeks of check-ins
  const plan = (await j("GET", "/api/me/plan", null, tok)).plan;
  const series = { smoking: [14, 11, 9, 6, 5], sleep_loss: [5.6, 6.1, 6.4, 6.8, 7.1], tight_underwear: [2, 4, 5, 6, 7] };
  const adh = [1, 2, 2, 3, 3];
  for (let w = 1; w <= 5; w++) {
    setWeek(plan.id, w);
    const items = {};
    for (const it of plan.items) items[it.node] = { adherence: adh[w - 1], value: series[it.node] ? series[it.node][w - 1] : null };
    await j("POST", "/api/me/plan/checkin", { items, energy: Math.min(5, 2 + Math.floor(w / 2)) }, tok);
  }
  setWeek(plan.id, 6);
  await p.evaluate(() => renderPlan()); await shot(p, 'plan-checkin');
  await p.evaluate(() => document.querySelectorAll('.card')[2].scrollIntoView()); await shot(p, 'plan-trend');
  await c.click('[data-t=labReview]'); await c.click('[data-t=plans]'); await shot(c, 'clinician-plans-running');
  await p.evaluate(async () => { await renderLabs(); window.scrollTo(0, 0); }); await shot(p, 'lab-timeline-reviewed');
  console.log('errors:', JSON.stringify(errs));
  await b.close();
})();
