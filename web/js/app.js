const S = { schema: null, answers: {}, aid: null, section: 0, consent: null, result: null };
const view = () => $("#view");

async function boot() {
  applyLang();
  API.token = store.get("token");
  S.aid = store.get("aid");
  try { S.answers = JSON.parse(store.get("draft") || "{}"); } catch { S.answers = {}; }
  S.schema = await API.get("/api/questionnaire");
  renderTop();
  if (API.token && S.aid && store.get("done") === "1") return showResult();
  welcome();
}

function renderTop() {
  $("#top").innerHTML = `<div class="brand"><i></i>${t("app")}<span class="muted" style="font-weight:400">· ${t("tagline")}</span></div>
    <div class="spacer"></div>
    <button class="chip" id="langBtn">${t("lang")}</button>
    <button class="chip exit" onclick="quickExit()">${t("exit")}</button>`;
  $("#langBtn").onclick = () => { LANG = LANG === "ar" ? "en" : "ar"; store.set("lang", LANG); applyLang(); renderTop(); rerender(); };
}
let rerender = welcome;

function welcome() {
  rerender = welcome;
  const resumable = API.token && S.aid && Object.keys(S.answers).length;
  view().innerHTML = `
    <h1>${t("hero")}</h1><p class="lead">${t("heroSub")}</p>
    <div class="card">
      ${[1, 2, 3].map(i => `<div class="promise"><span class="dot"></span><div><b>${t("p" + i + "t")}</b><span class="muted">${t("p" + i)}</span></div></div>`).join("")}
    </div>
    <div class="row">
      <button class="btn" id="go">${resumable ? t("resume") : t("start")}</button>
      ${resumable ? `<button class="btn ghost" id="fresh">${t("restart")}</button>` : ""}
    </div>
    <p class="muted" style="margin-top:28px">${t("alsoTry")}: <a href="fabric.html">${t("fabricLink")}</a> · <a href="graph.html">${t("graphLink")}</a></p>`;
  $("#go").onclick = () => resumable ? intake() : consent();
  if ($("#fresh")) $("#fresh").onclick = () => { ["aid", "draft", "done"].forEach(store.del); S.answers = {}; S.aid = null; consent(); };
}

function consent() {
  rerender = consent;
  const item = (id, title, sub, checked, req) => `<label class="check"><input type="checkbox" id="${id}" ${checked ? "checked" : ""} ${req ? "required" : ""}><div><b>${title}</b><div class="muted">${sub}</div></div></label>`;
  view().innerHTML = `<h1>${t("consentTitle")}</h1>
    <div class="grid2">
      <div class="card"><h2>${t("weStore")}</h2><ul>${t("weStoreList").map(x => `<li>${x}</li>`).join("")}</ul></div>
      <div class="card"><h2>${t("weNever")}</h2><ul>${t("weNeverList").map(x => `<li>${x}</li>`).join("")}</ul></div>
    </div>
    ${item("cCore", t("cCore"), t("cCoreSub"), true, true)}
    ${item("cReview", t("cReview"), t("cReviewSub"), true)}
    ${item("cDev", t("cDev"), t("cDevSub"), false)}
    ${item("cRes", t("cRes"), t("cResSub"), false)}
    <div class="row" style="margin-top:16px"><button class="btn ghost" id="b">${t("back")}</button><button class="btn" id="ok">${t("agree")}</button></div>`;
  $("#cCore").onchange = e => $("#ok").disabled = !e.target.checked;
  $("#b").onclick = welcome;
  $("#ok").onclick = async () => {
    if (!API.token) { API.token = (await API.post("/api/session", { lang: LANG })).token; store.set("token", API.token); }
    S.consent = await API.post("/api/consent", { core: true, clinician_review: $("#cReview").checked, wearables: $("#cDev").checked, research: $("#cRes").checked });
    S.aid = (await API.post("/api/assessments")).id; store.set("aid", S.aid); store.del("done");
    S.section = 0; intake();
  };
}

function visible(q) {
  if (!q.show_if) return true;
  return Object.entries(q.show_if).every(([k, v]) => {
    const a = S.answers[k];
    const vals = Array.isArray(v) ? v : [v];
    return Array.isArray(a) ? a.some(x => vals.includes(x)) : vals.includes(a);
  });
}

function intake() {
  rerender = intake;
  const secs = S.schema.sections, sec = secs[S.section];
  const qs = S.schema.questions.filter(q => q.section === sec.id);
  view().innerHTML = `<div class="muted">${t("sectionOf")(S.section + 1, secs.length)}</div>
    <div class="progress"><div style="width:${100 * S.section / secs.length}%"></div></div>
    <h1>${sec[LANG]}</h1><div class="card" id="qs"></div>
    <div class="row"><button class="btn ghost" id="b">${t("back")}</button><button class="btn" id="n">${S.section === secs.length - 1 ? t("next") : t("next")}</button>
    <span class="spacer"></span><button class="chip" id="skip">${t("skipSection")}</button></div>`;
  const box = $("#qs");
  const draw = () => {
    box.innerHTML = qs.filter(visible).map(q => {
      const help = q[`help_${LANG}`] ? `<div class="help">${esc(q["help_" + LANG])}</div>` : "";
      const label = `<label class="q">${esc(q[LANG])}${q.unit ? ` <span class="muted">(${q.unit})</span>` : ""}</label>${help}`;
      if (q.type === "number")
        return label + `<input type="number" inputmode="decimal" data-q="${q.id}" min="${q.min ?? ""}" max="${q.max ?? ""}" value="${S.answers[q.id] ?? ""}">`;
      const multi = q.type === "multi";
      const cur = S.answers[q.id];
      return label + `<div class="opts">${(q.options || []).map(o => {
        const on = multi ? (cur || []).includes(o.value) : cur === o.value;
        return `<span class="opt ${on ? "on" : ""} ${o.value === "skip" ? "skip" : ""}" data-q="${q.id}" data-v='${JSON.stringify(o.value)}' data-m="${multi ? 1 : 0}">${esc(o[LANG])}</span>`;
      }).join("")}</div>`;
    }).join("");
    $$("input[data-q]", box).forEach(i => i.oninput = () => { S.answers[i.dataset.q] = i.value === "" ? null : Number(i.value); saveDraft(); });
    $$(".opt", box).forEach(o => o.onclick = () => {
      const id = o.dataset.q, v = JSON.parse(o.dataset.v);
      if (o.dataset.m === "1") {
        const arr = new Set(S.answers[id] || []);
        arr.has(v) ? arr.delete(v) : arr.add(v);
        S.answers[id] = [...arr];
      } else S.answers[id] = S.answers[id] === v ? null : v;
      saveDraft(); draw();
    });
  };
  draw();
  $("#b").onclick = () => S.section ? (S.section--, intake()) : consent();
  const go = async () => {
    await API.put(`/api/assessments/${S.aid}/answers`, { answers: S.answers });
    if (S.section < secs.length - 1) { S.section++; intake(); window.scrollTo(0, 0); } else devices();
  };
  $("#n").onclick = go;
  $("#skip").onclick = go;
}

function saveDraft() { store.set("draft", JSON.stringify(S.answers)); }

async function devices() {
  rerender = devices;
  if (!S.consent) S.consent = await API.get("/api/consent");
  const allowed = S.consent.wearables;
  view().innerHTML = `<h1>${t("devTitle")}</h1><p class="muted">${t("devSub")}</p>
    ${allowed ? `<div class="card">
      <p>${t("devApple")}</p><p>${t("devCgm")}</p><p>${t("devCsv")} <a href="templates/daily_template.csv" download>${t("devTemplate")}</a></p>
      <input type="file" id="f" accept=".zip,.xml,.csv"><div id="fs" class="muted"></div></div>` : `<div class="banner info">${t("devNoConsent")}</div>`}
    <div class="card"><h2>${t("devManual")}</h2>
      <div class="grid2">
        <div><label class="q">${t("sleepAvg")}</label><input type="number" id="m_sleep" step="0.1"></div>
        <div><label class="q">${t("stepsAvg")}</label><input type="number" id="m_steps"></div>
        <div><label class="q">${t("screenAvg")}</label><input type="number" id="m_screen" step="0.5"></div>
        <div><label class="q">${t("spo2Nights")}</label><input type="number" id="m_spo2"></div>
      </div></div>
    <div class="row"><button class="btn ghost" id="b">${t("back")}</button><button class="btn" id="n">${t("next")}</button></div>`;
  if (allowed) $("#f").onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    $("#fs").textContent = "…";
    try {
      const s = await API.upload(`/api/assessments/${S.aid}/wearables`, f);
      const show = ["sleep_avg_h", "steps_avg", "social_jetlag_h", "spo2_low_nights", "late_caffeine_days_per_week", "night_glucose_high_pct", "glucose_cv", "screen_daily_h"]
        .filter(k => s[k] != null).map(k => `${k.replace(/_/g, " ")}: <b>${s[k]}</b>`).join(" · ");
      $("#fs").innerHTML = `${t("uploaded")}: ${show}`;
    } catch (err) { $("#fs").textContent = `${t("uploadErr")}: ${err.message}`; }
  };
  $("#b").onclick = () => { S.section = S.schema.sections.length - 1; intake(); };
  $("#n").onclick = async () => {
    const v = id => $(id).value === "" ? null : Number($(id).value);
    const body = { sleep_avg_h: v("#m_sleep"), steps_avg: v("#m_steps"), screen_daily_h: v("#m_screen"), spo2_low_nights: v("#m_spo2") };
    if (Object.values(body).some(x => x != null)) await API.post(`/api/assessments/${S.aid}/device-manual`, body);
    tests();
  };
}

function tests() {
  rerender = tests;
  const field = (id, key) => `<div><label class="q">${t(key)}</label><input type="number" step="0.1" data-k="${id}"></div>`;
  view().innerHTML = `<h1>${t("testTitle")}</h1><p class="muted">${t("testSub")}</p>
    <div class="card">
      <div class="opts" id="kind">
        <span class="opt on" data-k="home_quant">${t("tHomeQ")}</span><span class="opt" data-k="home_simple">${t("tHomeS")}</span><span class="opt" data-k="lab">${t("tLab")}</span>
      </div>
      <div id="fields_home_quant" class="grid2">${field("concentration_m_per_ml", "conc")}${field("total_motility_pct", "motTot")}${field("progressive_motility_pct", "motProg")}${field("motile_conc_m_per_ml", "msc")}</div>
      <div id="fields_home_simple" class="hidden"><label class="q">${t("homeResult")}</label>
        <div class="opts"><span class="opt" data-r="normal">${t("above")}</span><span class="opt" data-r="below">${t("below")}</span></div></div>
      <div id="fields_lab" class="grid2 hidden">${field("volume_ml", "vol")}${field("concentration_m_per_ml", "conc")}${field("total_motility_pct", "motTot")}${field("progressive_motility_pct", "motProg")}${field("normal_forms_pct", "morph")}${field("ph", "ph")}${field("abstinence_days", "abst")}</div>
      <div class="row" style="margin-top:14px"><button class="btn ghost" id="saveT">${t("save")}</button><span id="ts" class="muted"></span></div>
    </div>
    <details class="card"><summary><b>${t("collectTitle")}</b></summary>
      ${t("collect").map((x, i) => i === 0 ? `<p>${x}</p>` : `<p>• ${x}</p>`).join("")}<p class="muted small">${t("collectNote")}</p></details>
    <div class="row"><button class="btn ghost" id="b">${t("back")}</button><button class="btn" id="n">${t("finish")}</button></div>`;
  let kind = "home_quant", simple = null;
  $$("#kind .opt").forEach(o => o.onclick = () => {
    kind = o.dataset.k; $$("#kind .opt").forEach(x => x.classList.toggle("on", x === o));
    ["home_quant", "home_simple", "lab"].forEach(k => $("#fields_" + k).classList.toggle("hidden", k !== kind));
  });
  $$("[data-r]").forEach(o => o.onclick = () => { simple = o.dataset.r; $$("[data-r]").forEach(x => x.classList.toggle("on", x === o)); });
  $("#saveT").onclick = async () => {
    const body = { source: kind, kit: kind === "lab" ? null : "yo" };
    if (kind === "home_simple") { body.kit = "other"; body.result = simple; }
    else $$(`#fields_${kind} input`).forEach(i => { if (i.value !== "") body[i.dataset.k] = Number(i.value); });
    try {
      const r = await API.post(`/api/assessments/${S.aid}/semen`, body);
      $("#ts").textContent = r.normal ? "✓" : r.findings.map(f => f[1]).join("; ");
    } catch (e) { $("#ts").textContent = e.message; }
  };
  $("#b").onclick = devices;
  $("#n").onclick = submit;
}

async function submit() {
  if (!S.answers.age) { alert(t("errAge")); S.section = 0; return intake(); }
  await API.put(`/api/assessments/${S.aid}/answers`, { answers: S.answers });
  S.result = await API.post(`/api/assessments/${S.aid}/submit?lang=${LANG}`);
  store.set("done", "1");
  renderResult();
}

async function showResult() {
  try { S.result = await API.get(`/api/assessments/${S.aid}/result?lang=${LANG}`); renderResult(); }
  catch { store.del("done"); welcome(); }
}

function renderResult() {
  rerender = showResult;
  const r = S.result;
  const urgent = r.immediate;
  const pathText = w => w ? `${w.labels.join(" → ")} ${gradeTag(w.grade)}` : "";
  view().innerHTML = `
    <h1>${t("resultTitle")}</h1>
    <div class="banner info small">${esc(r.disclaimer)}</div>
    <div class="card next ${urgent ? "banner alert" : ""}"><div class="muted">${t("nextStep")}</div><h2>${esc(r.next_step)}</h2>
      <div class="muted">${esc(r.summary)}</div>
      ${t("review")[r.clinician_review || (r.referral ? "queued" : "not_needed")] ? `<p class="small">${t("review")[r.clinician_review || "queued"]}</p>` : ""}
      ${r.referral && r.referral.status !== "pending_review" && r.referral.status !== "suggested" ? `<p class="small"><span class="tag">✓</span>${LANG === "ar" ? "راجع الطبيب ملخصك" : "A doctor has reviewed your summary"}</p>` : ""}
      ${r.parallel.length ? `<ul>${r.parallel.map(p => `<li>${t("parallel")[p] || p}</li>`).join("")}</ul>` : ""}
    </div>
    ${r.plan.length ? `<div class="card"><h2>${t("planTitle")}</h2><p class="muted small">${t("planSub")}</p>
      ${r.plan.map(p => `<div class="plan-item"><b>${esc(p.action)}</b>
        <details class="why"><summary>${t("whyThis")}</summary>${pathText(p.why)}</details></div>`).join("")}</div>` : ""}
    ${r.strengths.length ? `<div class="card"><h3>${t("strengths")}</h3>${r.strengths.map(s => `<span class="tag">${esc(s.label)}</span>`).join("")}</div>` : ""}
    ${r.more.length ? `<details class="card"><summary><b>${t("moreTitle")}</b></summary><ul>${r.more.map(p => `<li>${esc(p.action)}</li>`).join("")}</ul></details>` : ""}
    ${r.tests.length ? `<div class="card"><h3>${t("testsTitle")}</h3><ul>${r.tests.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
      ${r.semen_notes.map(n => `<p class="muted small">${esc(n)}</p>`).join("")}</div>` : ""}
    <div class="grid2">
      <div class="card"><h3>${t("ifhasTitle")}</h3><p class="muted small">${t("ifhasSub")}</p><button class="btn ghost" id="fhir">${t("ifhasBtn")}</button></div>
      <div class="card"><h3>${t("shareTitle")}</h3><p class="muted small">${t("shareSub")}</p><div id="share"><button class="btn ghost" id="mk">${t("shareBtn")}</button></div></div>
    </div>
    <div class="card"><h3>${t("fbTitle")}</h3>${["fbTrust", "fbClarity", "fbComfort"].map(k => `<p class="small">${t(k)}</p><div class="stars" data-k="${k}">${[1, 2, 3, 4, 5].map(n => `<button data-n="${n}">${n}</button>`).join("")}</div>`).join("")}<p id="fbok" class="muted"></p></div>
    <div class="card"><h3>${t("delTitle")}</h3><p class="muted small">${t("delSub")}</p><button class="btn danger" id="del">${t("delBtn")}</button></div>
    <p><button class="btn ghost" id="again">${t("restart")}</button></p>`;
  $("#fhir").onclick = async () => {
    const b = await API.get(`/api/assessments/${S.aid}/ifhas`);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(b, null, 1)], { type: "application/fhir+json" }));
    a.download = "prescreen-summary.fhir.json"; a.click();
  };
  $("#mk").onclick = async () => {
    const s = await API.post(`/api/assessments/${S.aid}/share`);
    $("#share").innerHTML = `<div class="code">${s.code}</div><p class="muted small">72 h</p><button class="btn danger" id="rv">${t("revoke")}</button>`;
    $("#rv").onclick = async () => { await API.del(`/api/shares/${s.code}`); $("#share").innerHTML = `<p class="muted">✓</p>`; };
  };
  const fb = {};
  $$(".stars").forEach(st => $$("button", st).forEach(b => b.onclick = async () => {
    fb[st.dataset.k] = +b.dataset.n; $$("button", st).forEach(x => x.classList.toggle("on", +x.dataset.n <= +b.dataset.n));
    if (Object.keys(fb).length === 3) { await API.post(`/api/assessments/${S.aid}/feedback`, { trust: fb.fbTrust, clarity: fb.fbClarity, comfort: fb.fbComfort }); $("#fbok").textContent = t("fbThanks"); }
  }));
  $("#del").onclick = async () => {
    if (!confirm(t("delConfirm"))) return;
    await API.del("/api/me");
    ["token", "aid", "draft", "done"].forEach(store.del);
    API.token = null; S.answers = {}; S.aid = null;
    view().innerHTML = `<div class="card"><h2>${t("deleted")}</h2><button class="btn" onclick="welcome()">${t("start")}</button></div>`;
  };
  $("#again").onclick = () => { ["aid", "draft", "done"].forEach(store.del); S.answers = {}; S.aid = null; consent(); };
}

boot();
