// Seeds a realistic state through the API, then captures every feature screen for the README.
const { chromium } = require('playwright');
const OUT = process.argv[2];
const B = 'http://localhost:8000';
const BASE = { age: 34, height_cm: 175, weight_kg: 98, smoking: "daily", cigs_per_day: 15, sitting_h: 10, sleep_h: 5.5, underwear: "tight",
  snore: "yes", tired: "yes", observed: "no", bp: "no", pss1: 3, pss2: 1, pss3: 1, pss4: 3, phq1: 0, phq2: 1, reason: ["future"] };
const j = async (m, p, body, tok) => {
  const r = await fetch(B + p, { method: m, headers: { "Content-Type": "application/json", ...(tok ? { Authorization: `Bearer ${tok}` } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text(); try { return JSON.parse(t); } catch { return t; }
};
async function patient(lang, answers) {
  const tok = (await j("POST", "/api/session", { lang })).token;
  await j("POST", "/api/consent", { core: true, clinician_review: true, wearables: true }, tok);
  const aid = (await j("POST", "/api/assessments?channel=web", null, tok)).id;
  await j("PUT", `/api/assessments/${aid}/answers`, { answers }, tok);
  await j("POST", `/api/assessments/${aid}/submit`, null, tok);
  return { tok, aid };
}
const errs = [];
async function shot(page, name, full = false) {
  await page.waitForTimeout(700);
  if (full) await page.addStyleTag({ content: '#top,header,.top{position:static !important}' });
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
  console.log('saved', name);
}

(async () => {
  // a small population so dashboards have data (k-anonymity hides groups under 5)
  const ages = [24, 27, 29, 31, 33, 35, 26, 30, 28, 32];
  for (const a of ages) await patient("en", { ...BASE, age: a, smoking: a % 2 ? "never" : "daily", sleep_h: a % 3 ? 7 : 5 });
  const me = await patient("en", { ...BASE, aas: "current" });
  const ctok = (await j("POST", "/api/clinician/login", { username: "clinician", password: "demo-clinician" })).token;
  await j("POST", `/api/clinician/cases/${me.aid}/review`, { decision: "approve" }, ctok);

  const b = await chromium.launch();
  const phone = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const p = await phone.newPage();
  p.on('pageerror', e => errs.push('patient: ' + e.message));
  await p.goto(B + '/');
  // landing in Arabic, fresh visitor
  await p.evaluate(() => { localStorage.clear(); localStorage.setItem("lang", "ar"); });
  await p.goto(B + '/'); await shot(p, 'landing-ar');
  await p.evaluate(() => { localStorage.setItem("lang", "en"); }); await p.goto(B + '/'); await shot(p, 'landing-en');
  await p.evaluate(() => consent()); await shot(p, 'consent');
  // signed-in patient
  await p.evaluate(({ tok, aid }) => { localStorage.setItem("token", tok); localStorage.setItem("aid", aid); localStorage.setItem("done", "1"); localStorage.setItem("lang", "en"); }, me);
  await p.goto(B + '/'); await p.waitForTimeout(1500); await shot(p, 'result');
  await shot(p, 'result-full', true);
  await p.evaluate(() => renderJourney()); await shot(p, 'journey');
  await p.evaluate(aid => renderCare(aid), me.aid); await p.waitForTimeout(500);
  await p.click('input[name=prov]'); await p.click('[data-v=evening]'); await p.click('[data-v=weekend]');
  await shot(p, 'care-choose', true);
  await p.click('#ccSend'); await shot(p, 'care-requested');
  await p.evaluate(() => renderPrivacy()); await shot(p, 'privacy');
  await p.evaluate(() => { S.section = 0; intake(); }); await shot(p, 'intake');
  await p.evaluate(() => devices()); await shot(p, 'devices');
  await p.evaluate(() => tests()); await shot(p, 'tests');

  // coordinator / clinician on desktop
  const desk = await b.newContext({ viewport: { width: 1360, height: 860 }, deviceScaleFactor: 1.5 });
  const c = await desk.newPage();
  c.on('pageerror', e => errs.push('clinician: ' + e.message));
  await c.goto(B + '/clinician.html'); await shot(c, 'clinician-login');
  await c.evaluate(t => sessionStorage.setItem("ctoken", t), ctok); await c.goto(B + '/clinician.html'); await c.waitForTimeout(1200);
  await c.evaluate(aid => openCase(aid), me.aid); await shot(c, 'clinician-case');
  await c.click('[data-t=appointments]'); await shot(c, 'coordinator-requests');
  const d = new Date(Date.now() + 3 * 86400e3); d.setHours(17, 30, 0, 0);
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  await c.fill('.slot', local); await c.fill('.place', 'Urology outpatients, level 2');
  await c.click('.conf'); await shot(c, 'coordinator-confirmed');
  await c.click('[data-t=clinics]'); await shot(c, 'coordinator-clinics');
  await c.click('[data-t=metrics]'); await shot(c, 'clinician-metrics', true);
  await c.click('[data-t=audit]'); await shot(c, 'clinician-audit');
  await c.goto(B + '/insights.html'); await c.waitForTimeout(1500); await shot(c, 'programme-dashboard', true);
  await c.goto(B + '/graph.html'); await c.waitForTimeout(2500); await shot(c, 'evidence-map');

  await p.evaluate(aid => renderCare(aid), me.aid); await shot(p, 'care-confirmed');
  const link = await j("POST", `/api/assessments/${me.aid}/partner-link`, null, me.tok);
  await p.goto(B + link.path); await p.waitForTimeout(1000); await shot(p, 'partner');
  await p.goto(B + '/chat.html'); await p.waitForTimeout(1200); await shot(p, 'voice-chat');
  await p.goto(B + '/whatsapp.html'); await p.waitForTimeout(1200); await shot(p, 'whatsapp');
  await p.goto(B + '/fabric.html'); await p.waitForTimeout(1000); await shot(p, 'fabric');
  console.log('errors:', JSON.stringify(errs));
  await b.close();
})();
