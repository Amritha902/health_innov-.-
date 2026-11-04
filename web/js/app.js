const S = { schema: null, answers: {}, aid: null, section: 0, consent: null, result: null };
const view = () => $("#view");
const setWide = on => $("#view").className = on ? "hero-wrap" : "wrap";

async function boot() {
  applyLang();
  const claim = new URLSearchParams(location.hash.slice(1));
  if (claim.get("t") && claim.get("a")) {
    store.set("token", claim.get("t")); store.set("aid", claim.get("a")); store.set("done", "1"); store.del("draft");
    history.replaceState(null, "", "index.html");
  }
  API.token = store.get("token");
  S.aid = store.get("aid");
  try { S.answers = JSON.parse(store.get("draft") || "{}"); } catch { S.answers = {}; }
  S.schema = await API.get("/api/questionnaire");
  renderTop();
  if (location.hash === "#more" && API.token && S.aid) { history.replaceState(null, "", "index.html"); store.del("done"); return devices(); }
  if (API.token && S.aid && store.get("done") === "1") return showResult();
  welcome();
}

function renderTop() {
  $("#top").innerHTML = `<div class="brand"><i></i>${t("app")}</div>
    <div class="spacer"></div>
    <a class="chip" href="graph.html">${LANG === "ar" ? "خريطة الأدلة" : "Evidence map"}</a>
    <button class="chip" id="langBtn">${t("lang")}</button>`;
  $("#langBtn").onclick = () => { LANG = LANG === "ar" ? "en" : "ar"; store.set("lang", LANG); applyLang(); renderTop(); rerender(); };
}
let rerender = welcome;

const LATTICE = `<svg class="lattice" viewBox="0 0 240 252" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <defs><pattern id="mash" width="40" height="40" patternUnits="userSpaceOnUse">
    <g fill="none" stroke="#c9932e" stroke-opacity=".55" stroke-width="1">
      <path d="M20 4 L24 16 L36 20 L24 24 L20 36 L16 24 L4 20 L16 16 Z"/>
      <rect x="11" y="11" width="18" height="18" transform="rotate(45 20 20)"/>
      <path d="M0 0 L4 4 M40 0 L36 4 M0 40 L4 36 M40 40 L36 36 M20 0 V4 M20 36 V40 M0 20 H4 M36 20 H40"/>
    </g></pattern></defs>
  <rect width="240" height="252" fill="url(#mash)"/></svg>`;

function welcome() {
  rerender = welcome;
  setWide(true);
  const resumable = API.token && S.aid && Object.keys(S.answers).length;
  document.body.classList.add("landing");
  view().innerHTML = `<div class="hero">
      <div>
        <h1>${t("hero")}</h1><p class="lead">${t("heroSub")}</p>
        <div class="paths">
          <a class="path primary" href="chat.html"><span><b>${t("talkT")}</b><span class="d">${t("talkS")}</span></span><span class="len">${t("talkTime")}</span></a>
          <button class="path" id="watch"><span><b>${t("watchT")}</b><span class="d">${t("watchS")}</span></span><span class="len">${t("watchTime")}</span></button>
          <button class="path" id="go"><span><b>${resumable ? t("resume") : t("formT")}</b><span class="d">${t("formS")}</span></span><span class="len">${t("formTime")}</span></button>
        </div>
        ${resumable ? `<button class="chip" id="fresh">${t("restart")}</button>` : ""}
        <p class="proof" id="proof"></p>
      </div>
      <div class="screen">${LATTICE}
        <div class="window"><div class="voice">${"<span></span>".repeat(7)}</div><b>${t("windowT")}</b><p>${t("windowS")}</p></div>
      </div>
    </div>
    <div class="steps">
      ${[1, 2, 3].map(i => `<div><span class="n">${LANG === "ar" ? "٠١٢٣"[i] : i}</span><b>${t("how" + i + "t")}</b><span class="muted">${t("how" + i)}</span></div>`).join("")}
    </div>
    <p class="muted small" style="margin-top:48px">${t("alsoTry")}: <a href="whatsapp.html">${LANG === "ar" ? "رعاية على واتساب" : "Riaya on WhatsApp"}</a>, <a href="fabric.html">${t("fabricLink")}</a>, <a href="graph.html">${t("graphLink")}</a>, <a href="clinician.html">${LANG === "ar" ? "بوابة الأطباء" : "clinician console"}</a></p>`;
  $("#go").onclick = () => { document.body.classList.remove("landing"); resumable ? intake() : consent(); };
  $("#watch").onclick = () => { document.body.classList.remove("landing"); passiveStart(); };
  if ($("#fresh")) $("#fresh").onclick = () => { ["aid", "draft", "done"].forEach(store.del); S.answers = {}; S.aid = null; document.body.classList.remove("landing"); consent(); };
  API.get("/api/graph").then(g => {
    $("#proof").innerHTML = t("proof")({ edges: g.edges.length, nodes: g.nodes.length, refs: Object.keys(g.references).length });
  }).catch(() => {});
}

async function ensureSession(wearables) {
  if (!API.token) { API.token = (await API.post("/api/session", { lang: LANG })).token; store.set("token", API.token); }
  S.consent = await API.post("/api/consent", { core: true, clinician_review: false, wearables, research: false });
  S.aid = (await API.post("/api/assessments")).id; store.set("aid", S.aid); store.del("done"); store.set("passive_aid", S.aid);
}

function passiveStart() {
  rerender = passiveStart;
  setWide(false);
  view().innerHTML = `<h1>${t("pwT")}</h1><p class="lead">${t("pwS")}</p>
    <div class="card"><p>${t("pwHow")}</p><p class="muted small">${t("pwConsent")}</p>
      <div class="row" style="margin-top:16px"><label class="btn" for="pf">${t("pwPick")}</label><input type="file" id="pf" accept=".zip,.xml,.csv" class="hidden">
      <button class="btn ghost" id="sample">${t("pwSample")}</button></div><p class="muted small" id="ps"></p></div>
    <div id="pres"></div>`;
  const run = async file => {
    $("#ps").textContent = t("pwReading");
    try {
      await ensureSession(true);
      await API.upload(`/api/assessments/${S.aid}/wearables`, file);
      const r = await API.post(`/api/assessments/${S.aid}/passive?lang=${LANG}`);
      $("#ps").textContent = "";
      const stats = Object.entries(r.summary).map(([k, v]) => `<div style="min-width:130px"><div style="font-family:var(--display);font-size:30px">${v}</div><div class="muted small">${t("pwStat")[k] || k}</div></div>`).join("");
      $("#pres").innerHTML = `<div class="card"><div class="row" style="gap:28px;align-items:flex-start">${stats}</div></div>
        <h2 style="margin-top:28px">${t("pwFound")}</h2>
        ${r.findings.length ? r.findings.map(f => `<div class="plan-item"><b>${esc(f.text)}</b>
          <div class="why">${f.evidence ? gradeTag(f.evidence) + " " : ""}${LANG === "ar" ? (LANG === "ar" ? "من بيانات جهازك" : "") : f.sources.map(esc).join("; ")}</div></div>`).join("") : `<p>${t("pwNone")}</p>`}
        <div class="card next" style="margin-top:24px"><p>${t("pwNext")}</p>
          <div class="row"><a class="btn" style="background:#eef0ec;color:#0f2a3a" href="chat.html">${t("pwTalk")}</a>
          <button class="btn ghost" style="color:#eef0ec;box-shadow:inset 0 0 0 1px #3b5361" id="pform">${t("pwForm")}</button></div></div>`;
      $("#pform").onclick = () => { S.section = 0; intake(); };
    } catch (e) { $("#ps").textContent = `${t("uploadErr")}: ${e.message}`; }
  };
  $("#pf").onchange = e => e.target.files[0] && run(e.target.files[0]);
  $("#sample").onclick = async () => {
    const blob = await (await fetch("samples/apple_health_sample.zip")).blob();
    run(new File([blob], "export.zip", { type: "application/zip" }));
  };
}

function consent() {
  rerender = consent;
  setWide(false);
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
  setWide(false);
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
  setWide(false);
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
  setWide(false);
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
    <div class="card"><h2>${t("labsTitle")}</h2><p class="muted small">${t("labsSub")}</p>
      <div class="grid2">
        <div><label class="q">${t("tT")}</label><div class="row" style="flex-wrap:nowrap"><input type="number" step="0.1" id="l_t"><select id="l_tu" style="width:110px"><option>nmol/L</option><option>ng/dL</option></select></div></div>
        <div><label class="q">${t("tFSH")}</label><input type="number" step="0.1" id="l_fsh"></div>
        <div><label class="q">${t("tLH")}</label><input type="number" step="0.1" id="l_lh"></div>
        <div><label class="q">${t("tA1c")}</label><input type="number" step="0.1" id="l_a1c"></div>
        <div><label class="q">${t("tVD")}</label><div class="row" style="flex-wrap:nowrap"><input type="number" step="0.1" id="l_vd"><select id="l_vdu" style="width:110px"><option>ng/mL</option><option>nmol/L</option></select></div></div>
        <div><label class="q">${t("tDate")}</label><input type="text" id="l_date" placeholder="YYYY-MM-DD" dir="ltr"></div>
      </div><div class="row" style="margin-top:14px"><button class="btn ghost" id="saveL">${t("saveLabs")}</button><span id="ls" class="muted small"></span></div></div>
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
  $("#saveL").onclick = async () => {
    const n = id => $(id).value === "" ? null : Number($(id).value);
    const body = { testosterone: n("#l_t"), testosterone_unit: $("#l_tu").value, fsh: n("#l_fsh"), lh: n("#l_lh"), hba1c: n("#l_a1c"),
      vitamin_d: n("#l_vd"), vitamin_d_unit: $("#l_vdu").value, date: $("#l_date").value || null };
    Object.keys(body).forEach(k => body[k] == null && delete body[k]);
    try { const r = await API.post(`/api/assessments/${S.aid}/labs`, body); $("#ls").textContent = r.findings.length ? r.findings.map(f => f[1]).join("; ") : "✓"; }
    catch (e) { $("#ls").textContent = e.message; }
  };
  $("#b").onclick = devices;
  $("#n").onclick = submit;
}

async function submit() {
  if (!S.answers.age) { alert(t("errAge")); S.section = 0; return intake(); }
  await API.put(`/api/assessments/${S.aid}/answers`, { answers: S.answers });
  await API.post(`/api/assessments/${S.aid}/submit?lang=${LANG}`);
  store.set("done", "1");
  await showResult();
}

async function showResult() {
  try { S.result = await API.get(`/api/assessments/${S.aid}/result?lang=${LANG}`); renderResult(); }
  catch { store.del("done"); welcome(); }
}

function renderResult() {
  rerender = showResult;
  setWide(false);
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
    ${r.rapid_review || r.clinician_review === "queued" || (r.referral && r.referral.video_url) ? `<div class="card ${r.rapid_review ? "next" : ""}" id="rapid">
      ${r.rapid_review ? `<h2>${t("rapidTitle")}</h2><p class="small">${t("rapidSub")(r.sla_hours)}</p>` : ""}
      ${r.review_consent === false || r.clinician_review === "available" ? `<p class="muted small">${t("reqReviewSub")}</p><button class="btn" id="reqRev">${t("reqReview")}</button>` : `
        ${r.referral && r.referral.video_url ? `<div class="banner info"><b>${t("videoReady")}</b><br><a class="btn" style="margin-top:8px" href="${esc(r.referral.video_url)}" target="_blank" rel="noopener noreferrer">${t("joinVideo")}</a></div>` : ""}
        <h3>${t("msgTitle")}</h3><p class="muted small">${t("noteHint")}</p><div id="msgs" class="small"></div>
        <p><button class="btn ghost" id="noteBtn">${t("noteRec")}</button></p>
        <div class="row" style="flex-wrap:nowrap;margin-top:8px"><input type="text" id="msg" placeholder="${t("msgPh")}"><button class="btn" id="sendMsg">${t("send")}</button></div>`}
    </div>` : r.clinician_review === "available" ? `<div class="card"><p class="muted small">${t("reqReviewSub")}</p><button class="btn" id="reqRev">${t("reqReview")}</button></div>` : ""}
    ${r.genomic ? `<div class="card"><p class="small">${t("genomicNote")}</p></div>` : ""}
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
    <div class="card"><h3>${t("partnerTitle")}</h3><p class="muted small">${t("partnerSub")}</p><div id="partner"><button class="btn ghost" id="mkP">${t("partnerBtn")}</button></div></div>
    <div class="card"><h3>${t("fbTitle")}</h3>${["fbTrust", "fbClarity", "fbComfort"].map(k => `<p class="small">${t(k)}</p><div class="stars" data-k="${k}">${[1, 2, 3, 4, 5].map(n => `<button data-n="${n}">${n}</button>`).join("")}</div>`).join("")}<p id="fbok" class="muted"></p></div>
    <div class="card"><h3>${t("delTitle")}</h3><p class="muted small">${t("delSub")}</p><button class="btn danger" id="del">${t("delBtn")}</button></div>
    <p><button class="btn ghost" id="again">${t("restart")}</button></p>`;
  $("#fhir").onclick = async () => {
    const b = await API.get(`/api/assessments/${S.aid}/ifhas`);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(b, null, 1)], { type: "application/fhir+json" }));
    a.download = "prescreen-summary.fhir.json"; a.click();
  };
  if ($("#reqRev")) $("#reqRev").onclick = async () => { await API.post(`/api/assessments/${S.aid}/request-review`); showResult(); };
  const loadMsgs = async () => {
    if (!$("#msgs")) return;
    const ms = await API.get(`/api/assessments/${S.aid}/messages`);
    $("#msgs").innerHTML = ms.map(m => Notes.render(m, `/api/assessments/${S.aid}/voice-notes`, m.sender === "user" ? t("you") : t("doctor"))).join("") || `<p class="muted">—</p>`;
    Notes.wire($("#msgs"));
  };
  loadMsgs();
  if ($("#noteBtn")) Notes.attach($("#noteBtn"), `/api/assessments/${S.aid}/voice-notes`, loadMsgs,
    { record: t("noteRec"), stop: t("noteStop"), denied: t("noteDenied"), unsupported: t("noteNo") });
  if ($("#sendMsg")) $("#sendMsg").onclick = async () => {
    const v = $("#msg").value.trim(); if (!v) return;
    await API.post(`/api/assessments/${S.aid}/messages`, { body: v }); $("#msg").value = ""; loadMsgs();
  };
  $("#mkP").onclick = async () => {
    const p = await API.post(`/api/assessments/${S.aid}/partner-link`);
    const url = location.origin + p.path;
    $("#partner").innerHTML = `<input type="text" readonly value="${url}" dir="ltr"><div class="row" style="margin-top:8px"><button class="btn ghost" id="cpP">${t("partnerCopy")}</button><button class="btn danger" id="rvP">${t("partnerRevoke")}</button></div>`;
    $("#cpP").onclick = async () => { try { await navigator.clipboard.writeText(url); $("#cpP").textContent = t("partnerCopied"); } catch {} };
    $("#rvP").onclick = async () => { await API.del(`/api/assessments/${S.aid}/partner-link`); $("#partner").innerHTML = `<p class="muted">✓</p>`; };
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
