// Records every scene of the demo video from the running app (http://localhost:8000).
// Usage: node demo/record.js <outdir>
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const OUT = process.argv[2];
const BASE = "http://localhost:8000";
const script = JSON.parse(fs.readFileSync(path.join(__dirname, "script.json")));
const dur = JSON.parse(fs.readFileSync(path.join(OUT, "vo", "durations.json")));
const data = JSON.parse(fs.readFileSync(path.join(OUT, "data.json")));
const PAD = 1.6;
const wait = ms => new Promise(r => setTimeout(r, ms));
fs.mkdirSync(path.join(OUT, "raw"), { recursive: true });

async function typeSlow(page, sel, text) {
  for (const ch of text) { await page.type(sel, ch); await wait(55); }
}

let rec = async function (b, id, viewport, fn, opts = {}) {
  const ctx = await b.newContext({ viewport, recordVideo: { dir: path.join(OUT, "raw", id), size: viewport }, locale: opts.phone ? "ar-AE" : "en-GB" });
  if (opts.phone && id !== "privacy") await ctx.addInitScript(() => document.addEventListener("DOMContentLoaded", () => {
    const st = document.createElement("style"); st.textContent = ".hidebtn{display:none!important}"; document.head.appendChild(st); }));
  const page = await ctx.newPage();
  const t0 = Date.now();
  await fn(page);
  const need = (dur[id] + PAD) * 1000 + 600 - (Date.now() - t0);
  if (need > 0) await wait(need);
  const v = page.video();
  await ctx.close();
  fs.renameSync(await v.path(), path.join(OUT, "raw", id + ".webm"));
  console.log("recorded", id);
}

async function prep(page, lang, extra = {}) {
  await page.goto(BASE + "/index.html");
  await page.evaluate(([l, e]) => { localStorage.clear(); localStorage.setItem("lang", l); for (const k in e) localStorage.setItem(k, e[k]); }, [lang, extra]);
}

async function caption(page, sc) {
  await page.evaluate(({ head, sub }) => {
    const d = document.createElement("div");
    d.innerHTML = `<div style="font:300 54px/1.05 Plex,sans-serif;letter-spacing:-.02em;margin-bottom:12px">${head}</div><div style="font:400 24px/1.4 Plex,sans-serif;color:#b9c8d1">${sub.replace(/ · /g, ", ")}</div>`;
    Object.assign(d.style, { position: "fixed", left: "48px", bottom: "48px", zIndex: 999, background: "rgba(15,42,58,.94)", color: "#eef0ec", padding: "28px 34px", borderRadius: "22px", maxWidth: "760px", opacity: 0, transform: "translateY(16px)", transition: "all .7s cubic-bezier(.2,.7,.2,1)" });
    document.body.appendChild(d);
    requestAnimationFrame(() => setTimeout(() => { d.style.opacity = 1; d.style.transform = "none"; }, 300));
    document.querySelectorAll(".hidebtn").forEach(x => x.style.display = "none");
  }, sc);
}

(async () => {
  const only = process.argv[3] ? process.argv[3].split(",") : null;
  const b = await chromium.launch();
  const _rec = rec; rec = async (b2, id, ...rest) => (!only || only.includes(id)) ? _rec(b2, id, ...rest) : null;
  const S = Object.fromEntries(script.map(s => [s.id, s]));
  const PHONE = { width: 430, height: 932 }, PHONE_OPTS = { phone: true }, DESK = { width: 1920, height: 1080 };

  // cards
  for (const id of ["title", "problem", "proof", "end"]) {
    await rec(b, id, DESK, async p => {
      await p.goto(`${BASE}/_stage.html?mode=card&head=${encodeURIComponent(S[id].head)}&sub=${encodeURIComponent(S[id].sub)}`);
    });
  }

  await rec(b, "landing", PHONE, async p => {
    await prep(p, "ar"); await p.goto(BASE + "/index.html"); await wait(1800);
    await p.mouse.wheel(0, 420); await wait(1600); await p.mouse.wheel(0, 380); await wait(1600); await p.mouse.wheel(0, -900);
  }, PHONE_OPTS);

  await rec(b, "chat", PHONE, async p => {
    await prep(p, "ar"); await p.goto(BASE + "/chat.html"); await wait(500);
    await p.click("#startText"); await wait(700);
    for (const t of ["نعم", "نعم", "عمري ٣٤", "176", "94"]) { await typeSlow(p, "#text", t); await p.press("#text", "Enter"); await wait(650); }
    await p.click('#chips .opt[data-i="2"]'); await wait(250); await p.click("#done"); await wait(700);
    for (const t of ["١٤ شهر", "كل يوم"]) { await typeSlow(p, "#text", t); await p.press("#text", "Enter"); await wait(650); }
  }, PHONE_OPTS);

  await rec(b, "watch", PHONE, async p => {
    await prep(p, "ar"); await p.goto(BASE + "/index.html"); await wait(600);
    await p.click("#watch"); await wait(900); await p.click("#sample");
    await p.waitForSelector(".next", { timeout: 20000 }); await wait(800);
    for (let i = 0; i < 6; i++) { await p.mouse.wheel(0, 260); await wait(700); }
  }, PHONE_OPTS);

  await rec(b, "graph", DESK, async p => {
    await p.goto(BASE + "/graph.html"); await wait(2600);
    await p.evaluate(() => { const g = document.querySelector("#svg > g"); g.style.transition = "transform 2.4s cubic-bezier(.2,.7,.2,1)"; g.setAttribute("transform", "translate(-260,-170) scale(1.55)"); });
    await caption(p, S.graph); await wait(900);
    await p.evaluate(() => select("osa")); await wait(2600);
    await p.evaluate(() => select("aas")); await wait(2000);
  });

  await rec(b, "result", PHONE, async p => {
    await prep(p, "ar", { token: data.result.token, aid: data.result.aid, done: "1" });
    await p.goto(BASE + "/index.html"); await p.waitForSelector(".next"); await wait(1500);
    for (let i = 0; i < 5; i++) { await p.mouse.wheel(0, 300); await wait(800); }
  }, PHONE_OPTS);

  await rec(b, "clinician", DESK, async p => {
    await p.goto(BASE + "/clinician.html"); await p.fill("#p", "demo-clinician"); await p.click("#go");
    await p.waitForSelector(".qitem"); await caption(p, S.clinician); await wait(700);
    await p.click(".qitem"); await p.waitForSelector("#hoView"); await wait(2200);
    await p.mouse.move(1100, 600); await p.mouse.wheel(0, 420); await wait(1500);
    await p.click("#hoView"); await wait(500); await p.mouse.wheel(0, 380); await wait(1800); await p.mouse.wheel(0, 500); await wait(1500);
  });

  await rec(b, "dashboard", DESK, async p => {
    await p.goto(BASE + "/clinician.html"); await p.fill("#p", "demo-clinician"); await p.click("#go"); await p.waitForSelector(".qitem");
    await p.goto(BASE + "/insights.html"); await p.waitForSelector(".tiles");
    await p.evaluate(() => { document.querySelector(".dash").style.zoom = "1.32"; });
    await caption(p, S.dashboard); await wait(3200);
    await p.mouse.move(700, 640); await wait(1200);
    for (let i = 0; i < 4; i++) { await p.mouse.wheel(0, 300); await wait(1300); }
    await p.mouse.move(560, 560); await wait(1400);
    for (let i = 0; i < 3; i++) { await p.mouse.wheel(0, 420); await wait(1300); }
  });

  await rec(b, "whatsapp", DESK, async p => {
    await p.goto(BASE + "/index.html"); await p.evaluate(() => { localStorage.setItem("lang", "en"); sessionStorage.clear(); });
    await p.goto(BASE + "/whatsapp.html"); await wait(900);
    for (const t of ["1", "نعم", "29", "180", "78"]) { await typeSlow(p, "#msg", t); await p.press("#msg", "Enter"); await wait(900); }
  });

  await rec(b, "privacy", PHONE, async p => {
    await prep(p, "ar", { token: data.result.token, aid: data.result.aid, done: "1" });
    await p.goto(BASE + "/index.html"); await p.waitForSelector(".next"); await wait(1800);
    await p.click(".hidebtn"); await wait(2600);
    await p.click(".pcover button"); await wait(800);
  }, PHONE_OPTS);

  await b.close();
})();
