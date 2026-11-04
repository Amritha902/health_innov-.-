// README images: flowchart and app screenshots. Usage: node demo/shots.js <outdir>
const { chromium } = require("playwright");
const OUT = process.argv[2], BASE = "http://localhost:8000";
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
  await p.goto(BASE + "/_flow.html"); await p.waitForTimeout(500);
  await (await p.$("#sheet")).screenshot({ path: OUT + "/flow.png" });
  const m = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const q = await m.newPage();
  await q.goto(BASE + "/index.html"); await q.evaluate(() => localStorage.setItem("lang", "ar")); await q.reload(); await q.waitForTimeout(900);
  await q.screenshot({ path: OUT + "/screen-landing.png" });
  await q.goto(BASE + "/whatsapp.html"); await q.waitForTimeout(400);
  const d = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const r = await d.newPage();
  await r.goto(BASE + "/clinician.html"); await r.fill("#p", "demo-clinician"); await r.click("#go"); await r.waitForSelector(".qitem");
  await r.click(".qitem"); await r.waitForSelector("#hoView"); await r.waitForTimeout(1500);
  await r.screenshot({ path: OUT + "/screen-clinician.png" });
  await b.close();
})();
