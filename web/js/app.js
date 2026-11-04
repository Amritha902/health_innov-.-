const S = { schema: null, answers: {}, aid: null, section: 0, consent: null, result: null };
const view = () => $("#view");
const setWide = on => $("#view").className = on ? "hero-wrap" : "wrap";

async function boot() {
  applyLang();
  if (store.get("big")) document.documentElement.classList.add("big");
  const claim = new URLSearchParams(location.hash.slice(1));
  if (claim.get("t") && claim.get("a")) {
    store.set("token", claim.get("t")); store.set("aid", claim.get("a")); store.set("done", "1"); store.del("draft");
    history.replaceState(null, "", "index.html");
  }
  API.token = store.get("token");
  S.aid = store.get("aid");
  try { S.answers = JSON.parse(store.get("draft") || "{}"); } catch { S.answers = {}; }
  S.schema = await API.get("/api/questionnaire");
  try { S.config = await API.get("/api/config"); } catch { S.config = {}; }
  demoBanner();
  renderTop();
  if (location.hash === "#more" && API.token && S.aid) { history.replaceState(null, "", "index.html"); store.del("done"); return devices(); }
  if (API.token && S.aid && store.get("done") === "1") return showResult();
  welcome();
}

function renderTop() {
  $("#top").innerHTML = `<div class="brand"><i></i>${t("app")}</div>
    <div class="spacer"></div>
    ${API.token ? `<button class="chip" id="jBtn">${t("jOpen")}</button><button class="chip" id="pvBtn">${pv("privacyChip")}</button>` : ""}
    <button class="chip" id="bigBtn" aria-pressed="${document.documentElement.classList.contains("big")}">${t("bigger")}</button>
    <a class="chip" href="graph.html">${LANG === "ar" ? "خريطة الأدلة" : "Evidence map"}</a>
    <button class="chip" id="langBtn">${t("lang")}</button>`;
  if ($("#jBtn")) $("#jBtn").onclick = () => renderJourney();
  if ($("#pvBtn")) $("#pvBtn").onclick = () => renderPrivacy();
  $("#bigBtn").onclick = () => { document.documentElement.classList.toggle("big"); store.set("big", document.documentElement.classList.contains("big") ? "1" : ""); };
  $("#langBtn").onclick = () => { LANG = LANG === "ar" ? "en" : "ar"; store.set("lang", LANG); applyLang(); demoBanner(); renderTop(); rerender(); };
}
let rerender = welcome;

function demoBanner() {
  if (S.config && S.config.uae_hosted) return;
  let b = document.getElementById("demoBar");
  if (!b) { b = document.createElement("div"); b.id = "demoBar"; b.className = "demo-bar"; b.setAttribute("role", "note"); document.body.prepend(b); }
  b.textContent = LANG === "ar" ? "خادم تجريبي: لا تُدخل معلومات صحية حقيقية." : "Demonstration server: please don't enter real health information.";
}

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
    ${API.token ? "" : `<p class="small" style="margin-top:32px"><a href="#" id="restoreLink">${pv("restoreLink")}</a></p>`}
    <p class="muted small" style="margin-top:48px">${t("alsoTry")}: <a href="whatsapp.html">${LANG === "ar" ? "رعاية على واتساب" : "Riaya on WhatsApp"}</a>, <a href="fabric.html">${t("fabricLink")}</a>, <a href="graph.html">${t("graphLink")}</a>, <a href="clinician.html">${LANG === "ar" ? "بوابة الأطباء" : "clinician console"}</a></p>`;
  $("#go").onclick = () => { document.body.classList.remove("landing"); resumable ? intake() : consent(); };
  $("#watch").onclick = () => { document.body.classList.remove("landing"); passiveStart(); };
  if ($("#restoreLink")) $("#restoreLink").onclick = e => { e.preventDefault(); document.body.classList.remove("landing"); renderRestore(); };
  if ($("#fresh")) $("#fresh").onclick = () => { ["aid", "draft", "done"].forEach(store.del); S.answers = {}; S.aid = null; document.body.classList.remove("landing"); consent(); };
  API.get("/api/graph").then(g => {
    $("#proof").innerHTML = t("proof")({ edges: g.edges.length, nodes: g.nodes.length, refs: Object.keys(g.references).length });
  }).catch(() => {});
}

async function ensureSession(wearables) {
  if (!API.token) { API.token = (await API.post("/api/session", { lang: LANG })).token; store.set("token", API.token); }
  S.consent = await API.post("/api/consent", { core: true, clinician_review: false, wearables, research: false });
  S.aid = (await API.post("/api/assessments?channel=watch")).id; store.set("aid", S.aid); store.del("done"); store.set("passive_aid", S.aid);
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
          <div class="why">${f.evidence ? gradeTag(f.evidence) + " " : ""}${f.sources.map(esc).join(LANG === "ar" ? "؛ " : "; ")}</div></div>`).join("") : `<p>${t("pwNone")}</p>`}
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
      <div class="card"><h2>${t("weStore")}</h2><ul>${t("weStoreList").map(x => `<li>${x}</li>`).join("")}<li>${S.config && S.config.uae_hosted ? (LANG === "ar" ? "محفوظة على خوادم داخل الدولة." : "Kept on servers in the UAE.") : (LANG === "ar" ? "هذا خادم تجريبي خارج الدولة؛ لا تُدخل بيانات حقيقية." : "This is a demonstration server outside the UAE; don't enter real data.")}</li></ul></div>
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
    $$("input[data-q]", box).forEach(i => i.oninput = () => {
      const v = i.value === "" ? null : Number(i.value), lo = i.min === "" ? null : Number(i.min), hi = i.max === "" ? null : Number(i.max);
      let hint = i.nextElementSibling && i.nextElementSibling.classList.contains("hint") ? i.nextElementSibling : null;
      if (!hint) { hint = document.createElement("div"); hint.className = "hint help"; i.after(hint); }
      const bad = v != null && (Number.isNaN(v) || (lo != null && v < lo) || (hi != null && v > hi));
      hint.textContent = bad ? (LANG === "ar" ? `أدخل رقماً بين ${lo} و${hi}` : `Enter a number between ${lo} and ${hi}`) : "";
      i.style.borderColor = bad ? "var(--alert)" : "";
      S.answers[i.dataset.q] = bad ? null : v; saveDraft();
    });
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
    <div class="card next"><h2>${t("lrTitle")}</h2><p class="small">${t("lrSub")}</p>
      <div class="row"><label class="btn" style="background:#eef0ec;color:#0f2a3a" for="lrf">${t("lrPick")}</label><input type="file" id="lrf" accept=".pdf,.txt,image/*" class="hidden">
      <button class="btn ghost" style="color:#eef0ec;box-shadow:inset 0 0 0 1px #3b5361" id="lrs">${t("lrSample")}</button></div><div id="lrout" class="small"></div></div>
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
  const showReport = r => {
    if (!r.values.length) { $("#lrout").innerHTML = `<p>${t("lrNone")}</p>`; return; }
    $("#lrout").innerHTML = `<table style="margin-top:14px;color:inherit"><tr><th style="color:#a9bac4">${t("lrField")}</th><th style="color:#a9bac4">${t("lrValue")}</th><th style="color:#a9bac4">${t("lrFrom")}</th></tr>
      ${r.values.map(v => `<tr><td>${t("lrNames")[v.field] || v.field}<br><span class="tag">${esc(lx("conf")[v.confidence] || v.confidence)}</span>${v.lab_flag ? ` <span class="tag">${esc(v.lab_flag)}</span>` : ""}</td>
        <td><input type="number" step="0.01" data-f="${v.field}" data-t="${v.target}" data-x="${v.value}" value="${v.value}" style="width:96px;padding:6px 8px"> ${v.unit}
          ${v.ref ? `<br><span style="color:#a9bac4;font-size:12px">${lx("range")}: ${esc(v.reference)}</span>` : ""}</td>
        <td style="color:#a9bac4;font-size:12px" dir="ltr">${esc(v.line)}</td></tr>`).join("")}</table>
      <h3 style="margin-top:14px">${lx("ctxT")}</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px">
        <label class="small">${lx("abst")}<input type="number" id="lrAb" min="0" max="60" value="${r.context.abstinence_days ?? ""}"></label>
        <label class="small">${lx("time")}<input type="time" id="lrTm" value="${r.context.time || ""}"></label>
        <label class="small">${lx("labName")}<input type="text" id="lrLab" maxlength="80"></label></div>
      <label class="check small"><input type="checkbox" id="lrFa" ${r.context.fasting ? "checked" : ""}><div>${lx("fasting")}</div></label>
      <label class="check small"><input type="checkbox" id="lrFv"><div>${lx("fever")}</div></label>
      <p><button class="btn" style="background:#eef0ec;color:#0f2a3a" id="lrok">${t("lrConfirm")}</button></p>`;
    $("#lrok").onclick = async () => {
      const semen = { source: "lab" }, labs = { date: r.date || null };
      $$("#lrout input[data-f]").forEach(i => { if (i.value !== "") (i.dataset.t === "semen" ? semen : labs)[i.dataset.f] = Number(i.value); });
      if (Object.keys(semen).length > 1) await API.post(`/api/assessments/${S.aid}/semen`, semen);
      if (Object.keys(labs).some(k => k !== "date" && labs[k] != null)) { Object.keys(labs).forEach(k => labs[k] == null && delete labs[k]); await API.post(`/api/assessments/${S.aid}/labs`, labs); }
      const byF = Object.fromEntries(r.values.map(v => [v.field, v]));
      const values = $$("#lrout input[data-f]").filter(i => i.value !== "" && i.dataset.f !== "abstinence_days").map(i => { const v = byF[i.dataset.f];
        return { field: i.dataset.f, value: Number(i.value), extracted_value: Number(i.dataset.x), ref_low: v.ref ? v.ref.low : null, ref_high: v.ref ? v.ref.high : null,
          ref_text: v.reference, score: v.score, line: v.line, lab_flag: v.lab_flag }; });
      const ab = $("#lrAb").value;
      if (values.length) await API.post("/api/me/labs", { assessment_id: S.aid, collected_on: r.date || null, lab_name: $("#lrLab").value || null, source: "report",
        abstinence_days: ab === "" ? null : Number(ab), time: $("#lrTm").value || null, fasting: $("#lrFa").checked ? true : (r.context.fasting === false ? false : null),
        fever_recent: $("#lrFv").checked || null, values });
      $("#lrout").innerHTML = `<p>✓ ${t("lrSaved")} ${lx("saveTl")}</p><p><button class="btn ghost" style="color:inherit" id="lrTl">${lx("openLabs")}</button></p>`;
      $("#lrTl").onclick = () => renderLabs();
    };
  };
  const readReport = async file => {
    $("#lrout").textContent = t("lrReading");
    try {
      let r;
      if (file.type.startsWith("image/")) {
        if (!window.Tesseract) await new Promise((ok, no) => { const sc = document.createElement("script"); sc.src = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.0/dist/tesseract.min.js"; sc.onload = ok; sc.onerror = no; document.head.appendChild(sc); });
        const { data } = await Tesseract.recognize(file, "eng+ara");
        const f = new FormData(); f.append("text", data.text);
        r = await API.req("POST", `/api/assessments/${S.aid}/lab-report`, f, true);
      } else r = await API.upload(`/api/assessments/${S.aid}/lab-report`, file);
      showReport(r);
    } catch (e) { $("#lrout").textContent = e.message; }
  };
  $("#lrf").onchange = e => e.target.files[0] && readReport(e.target.files[0]);
  $("#lrs").onclick = async () => readReport(new File([await (await fetch("samples/sample_lab_report.pdf")).blob()], "report.pdf", { type: "application/pdf" }));
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
    <div class="row" style="margin:-4px 0 8px"><button class="chip" id="readBtn">🔊 ${t("readAloud")}</button><button class="chip" id="jBtn2">${t("jOpen")}</button></div>
    <div id="explain"></div>
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
  $("#readBtn").onclick = () => window.Voice ? Voice.speak([r.summary, r.next_step, ...r.plan.map(p => p.action)].join(". "), { lang: LANG })
    : speechSynthesis.speak(Object.assign(new SpeechSynthesisUtterance([r.summary, r.next_step].join(". ")), { lang: LANG === "ar" ? "ar-AE" : "en-GB" }));
  $("#jBtn2").onclick = () => renderJourney();
  loadExplain();
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


const refLink = e => `<a href="https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(e.text.replace(/\s*\(\d{4}\)\.?/, " ").split(". ").slice(0, 2).join(" "))}" target="_blank" rel="noopener">${esc(e.text)}</a>`;

async function loadExplain() {
  const box = $("#explain"); if (!box) return;
  const e = await API.get(`/api/assessments/${S.aid}/explain?lang=${LANG}`);
  const covColor = st => ({ measured: "var(--good)", screened: "var(--warn)", reported: "var(--info)", not_answered: "var(--muted)", not_measured: "var(--muted)" })[st];
  box.innerHTML = `
    ${e.contradictions.length ? `<div class="card"><h3>${t("conTitle")}</h3>${e.contradictions.map(c => `<p class="small">${c.severity === "review" ? "⚑ " : ""}${esc(c.text)}</p>`).join("")}</div>` : ""}
    <div class="card"><h2>${t("exTitle")}</h2>
      ${e.cards.slice(0, 6).map(c => `<details class="plan-item"><summary style="text-decoration:none;color:var(--ink)"><b>${esc(c.label)}</b> ${c.grade ? gradeTag(c.grade) : ""}</summary>
        <div class="small" style="margin-top:10px">
          <p><b>${t("exObs")}:</b> ${esc(c.observation)}</p>
          ${c.relevance ? `<p><b>${t("exWhy")}:</b> ${esc(c.relevance)}</p>` : ""}
          ${c.recommendation ? `<p><b>${t("exDo")}:</b> ${esc(c.recommendation)}</p>` : ""}
          ${c.limitations.length ? `<p><b>${t("exLim")}:</b> ${c.limitations.map(esc).join(" ")}</p>` : ""}
          ${c.evidence.length ? `<p><b>${t("exEv")}:</b></p><ul>${c.evidence.slice(0, 4).map(x => `<li>${refLink(x)}</li>`).join("")}</ul>` : ""}
        </div></details>`).join("")}
    </div>
    <div class="card"><h3>${t("covTitle")}</h3><div style="display:grid;grid-template-columns:1fr auto;gap:6px 16px" class="small">
      ${e.coverage.map(c => `<span>${esc(c.label)}</span><span style="color:${covColor(c.status)}">${esc(c.status_text)}</span>`).join("")}</div></div>
    <div class="card" id="wi"><h2>${t("wiTitle")}</h2><p class="muted small">${t("wiSub")}</p><div class="opts" id="wiOpts"></div><div id="wiOut" style="margin-top:16px"></div></div>`;
  const base = await API.post(`/api/assessments/${S.aid}/whatif?lang=${LANG}`, { improve: [] });
  const picked = new Set();
  $("#wiOpts").innerHTML = base.options.map(o => `<span class="opt" data-n="${o.node}">${esc(o.label)}</span>`).join("");
  const draw = w => {
    const bar = (v, col) => `<div style="height:10px;background:var(--line);border-radius:5px;overflow:hidden"><div style="width:${Math.round(100 * v)}%;height:100%;background:${col}"></div></div>`;
    $("#wiOut").innerHTML = `<div class="small" style="display:grid;grid-template-columns:140px 1fr 150px;gap:8px 12px;align-items:center">
      <span>${t("wiNow")}</span>${bar(w.before, "var(--ink-2)")}<span>${t("tierWord")[w.before_tier]}</span>
      <span>${t("wiThen")}</span>${bar(w.after, "var(--saffron)")}<span>${t("tierWord")[w.after_tier]}${w.reduction_pct ? ` (−${w.reduction_pct}%)` : ""}</span></div>
      <p class="muted small">${esc(w.note)}</p>`;
  };
  draw(base);
  $$("#wiOpts .opt").forEach(o => o.onclick = async () => {
    o.classList.toggle("on"); o.classList.contains("on") ? picked.add(o.dataset.n) : picked.delete(o.dataset.n);
    draw(await API.post(`/api/assessments/${S.aid}/whatif?lang=${LANG}`, { improve: [...picked] }));
  });
}

async function renderJourney() {
  rerender = renderJourney;
  setWide(false);
  const j = await API.get(`/api/me/journey?lang=${LANG}`);
  const d = ts => new Date(ts * 1000).toLocaleDateString(LANG === "ar" ? "ar-AE" : "en-GB", { day: "numeric", month: "short", year: "numeric" });
  view().innerHTML = `<h1>${t("jTitle")}</h1>
    <p class="row"><button class="btn ghost" id="jLabs">${lx("openLabs")}</button><button class="btn ghost" id="jPlan">${lx("openPlan")}</button></p>
    ${j.recheck_due ? `<p class="lead">${t("jRecheck")(d(j.recheck_due))}</p><p><button class="btn" id="follow">${t("jFollow")}</button></p>` : `<p>${t("none")}</p>`}
    ${j.checks.map((c, i) => `<div class="card" style="${i === 0 ? "border-inline-start:4px solid var(--saffron)" : ""}">
      <div class="muted small">${d(c.completed_at)}</div><h2>${esc(c.next_step)}</h2><p class="small">${esc(c.summary)}</p>
      ${c.changes ? `<h3>${t("jChanged")}</h3><p class="small">${c.changes.improved.length ? `<b>${t("jImproved")}:</b> ${c.changes.improved.map(esc).join("، ")}<br>` : ""}${c.changes.new.length ? `<b>${t("jNew")}:</b> ${c.changes.new.map(esc).join("، ")}` : ""}</p>` : ""}
      ${c.discuss.length ? `<h3>${t("jDiscuss")}</h3><p class="small">${c.discuss.map(esc).join("، ")}</p>` : ""}
      ${c.tests_have.length ? `<h3>${t("jHave")}</h3><p class="small">${c.tests_have.map(x => `${esc(x.name)}${x.value ? ": " + esc(x.value) : ""}`).join("<br>")}</p>` : ""}
      <h3>${LANG === "ar" ? "المسار" : "Timeline"}</h3>
      <ol class="small" style="padding-inline-start:18px">${c.steps.map(s => `<li>${t("jSteps")[s.step] || s.step}${s.at ? ` <span class="muted">${d(s.at)}</span>` : ""}${s.barrier ? ` (${t("barrier")[s.barrier] || s.barrier})` : ""}</li>`).join("")}</ol>
      ${c.referral_status && c.level !== "self_care" ? `<p><button class="btn" data-care="${c.id}">${c.referral_status === "booked" ? cc("see") : cc("open")}</button></p>` : ""}
      ${c.referral_status && !["attended", "tests_done", "followed_up", "declined"].includes(c.referral_status) ? `<div class="row" data-aid="${c.id}">
        <button class="chip" data-p="booked">${t("jBooked")}</button><button class="chip" data-p="attended">${t("jWent")}</button><button class="chip" data-p="tests_done">${t("jTests")}</button>
        <button class="chip" data-p="declined">${t("jCouldnt")}</button></div>` : ""}
    </div>`).join("")}`;
  $$("[data-care]").forEach(b => b.onclick = () => renderCare(b.dataset.care));
  $("#jLabs").onclick = () => renderLabs();
  $("#jPlan").onclick = () => renderPlan();
  $$("[data-aid] [data-p]").forEach(b => b.onclick = async () => {
    const aid = b.parentElement.dataset.aid;
    if (b.dataset.p === "declined") {
      b.parentElement.innerHTML = `<p class="small">${t("jWhy")}</p><div class="opts">${j.barriers.map(x => `<span class="opt" data-b="${x}">${t("barrier")[x]}</span>`).join("")}</div>`;
      $$("[data-b]").forEach(o => o.onclick = async () => { await API.post(`/api/assessments/${aid}/progress`, { status: "declined", barrier: o.dataset.b }); renderJourney(); });
      return;
    }
    await API.post(`/api/assessments/${aid}/progress`, { status: b.dataset.p }); renderJourney();
  });
  if ($("#follow")) $("#follow").onclick = async () => {
    S.aid = (await API.post("/api/assessments?channel=web")).id; store.set("aid", S.aid); store.del("done");
    S.section = 0; intake();
  };
}


const PV = {
  en: { title: "Privacy & sharing", sub: "Change what Riaya may do with your information at any time. Changes take effect immediately.",
    review: "A licensed doctor may review my summary when it needs a doctor", reviewOff: "Turning this off removes your checks from every doctor's view, including pending reviews and share codes.",
    devices: "I may add data from my watch, phone or glucose sensor", research: "My anonymous results may help improve this service", save: "Save changes", saved: "Saved.",
    rcTitle: "Recovery code", rcSub: "If you change or lose your phone, this code brings your checks back. No name or number is needed. Write it down; it is shown only once, and it works once.",
    rcMake: "Create a recovery code", rcNew: "Your recovery code", rcKeep: "Write this down and keep it somewhere private. A new code replaces the old one.",
    exportT: "Download my data", exportS: "Everything Riaya holds about you, in one file.", exportB: "Download",
    restoreT: "Restore my checks", restoreS: "Enter the recovery code you wrote down. Your old phone will be signed out.", restoreB: "Restore", restored: "Restored. Welcome back.",
    restoreLink: "Have a recovery code? Restore your checks", privacyChip: "Privacy" },
  ar: { title: "الخصوصية والمشاركة", sub: "غيّر ما يُسمح لرعاية بفعله بمعلوماتك في أي وقت. تُطبّق التغييرات فوراً.",
    review: "يمكن لطبيب مرخّص مراجعة ملخصي عندما يحتاج إلى طبيب", reviewOff: "إيقاف هذا يزيل فحوصاتك من عرض جميع الأطباء، بما في ذلك المراجعات المعلقة ورموز المشاركة.",
    devices: "يمكنني إضافة بيانات ساعتي أو هاتفي أو جهاز السكر", research: "يمكن لنتائجي مجهولة الهوية أن تساعد في تحسين الخدمة", save: "حفظ التغييرات", saved: "تم الحفظ.",
    rcTitle: "رمز الاسترداد", rcSub: "إذا غيّرت هاتفك أو فقدته، يعيد هذا الرمز فحوصاتك. لا حاجة لاسم أو رقم. اكتبه؛ يظهر مرة واحدة فقط ويعمل مرة واحدة.",
    rcMake: "أنشئ رمز استرداد", rcNew: "رمز الاسترداد الخاص بك", rcKeep: "اكتبه واحفظه في مكان خاص. الرمز الجديد يحل محل القديم.",
    exportT: "تحميل بياناتي", exportS: "كل ما تحتفظ به رعاية عنك في ملف واحد.", exportB: "تحميل",
    restoreT: "استعادة فحوصاتي", restoreS: "أدخل رمز الاسترداد الذي كتبته. سيتم تسجيل خروج هاتفك القديم.", restoreB: "استعادة", restored: "تمت الاستعادة. أهلاً بعودتك.",
    restoreLink: "لديك رمز استرداد؟ استعد فحوصاتك", privacyChip: "الخصوصية" },
};
const pv = k => PV[LANG][k];

async function renderPrivacy() {
  rerender = renderPrivacy;
  setWide(false);
  const c = await API.get("/api/consent");
  const box = (id, text, on) => `<label class="check"><input type="checkbox" id="${id}" ${on ? "checked" : ""}><div>${text}</div></label>`;
  view().innerHTML = `<h1>${pv("title")}</h1><p class="lead">${pv("sub")}</p>
    <div class="card">${box("pvReview", pv("review"), c.clinician_review)}<p class="muted small" id="pvWarn" style="display:none">${pv("reviewOff")}</p>
      ${box("pvDev", pv("devices"), c.wearables)}${box("pvRes", pv("research"), c.research)}
      <p class="row"><button class="btn" id="pvSave">${pv("save")}</button><span class="small" id="pvMsg"></span></p></div>
    <div class="card"><h2>${pv("rcTitle")}</h2><p class="muted small">${pv("rcSub")}</p><div id="rc"><button class="btn ghost" id="rcMake">${pv("rcMake")}</button></div></div>
    <div class="card"><h2>${pv("exportT")}</h2><p class="muted small">${pv("exportS")}</p><button class="btn ghost" id="pvExport">${pv("exportB")}</button></div>
    <div class="card"><h3>${t("delTitle")}</h3><p class="muted small">${t("delSub")}</p><button class="btn danger" id="pvDel">${t("delBtn")}</button></div>`;
  $("#pvReview").onchange = e => $("#pvWarn").style.display = e.target.checked ? "none" : "block";
  $("#pvSave").onclick = async () => {
    try {
      S.consent = await API.post("/api/consent", { core: true, clinician_review: $("#pvReview").checked, wearables: $("#pvDev").checked, research: $("#pvRes").checked });
      $("#pvMsg").textContent = pv("saved");
    } catch (e) { $("#pvMsg").textContent = e.message; }
  };
  $("#rcMake").onclick = async () => {
    const r = await API.post("/api/me/recovery");
    $("#rc").innerHTML = `<p class="small">${pv("rcNew")}</p><div class="code" dir="ltr" style="font-size:22px;letter-spacing:2px">${esc(r.code)}</div><p class="muted small">${pv("rcKeep")}</p>`;
  };
  $("#pvExport").onclick = async () => {
    const data = await API.get("/api/me/export");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: "application/json" }));
    a.download = "riaya-my-data.json"; a.click();
  };
  $("#pvDel").onclick = async () => {
    if (!confirm(t("delConfirm"))) return;
    await API.del("/api/me");
    ["token", "aid", "draft", "done", "passive_aid"].forEach(store.del);
    API.token = null; S.answers = {}; S.aid = null; renderTop();
    view().innerHTML = `<div class="card"><h2>${t("deleted")}</h2><button class="btn" onclick="welcome()">${t("start")}</button></div>`;
  };
}

function renderRestore() {
  rerender = renderRestore;
  setWide(false);
  view().innerHTML = `<h1>${pv("restoreT")}</h1><p class="lead">${pv("restoreS")}</p>
    <div class="card"><input type="text" id="rcIn" dir="ltr" autocomplete="off" placeholder="XXXXX-XXXXX-XXXXX-XXXXX" style="font-size:20px;letter-spacing:2px">
    <p class="row"><button class="btn" id="rcGo">${pv("restoreB")}</button><span class="small" id="rcMsg"></span></p></div>`;
  $("#rcGo").onclick = async () => {
    try {
      const r = await API.post("/api/recover", { code: $("#rcIn").value });
      API.token = r.token; store.set("token", r.token);
      if (r.aid) { S.aid = r.aid; store.set("aid", r.aid); store.set("done", "1"); }
      renderTop(); $("#rcMsg").textContent = pv("restored");
      setTimeout(() => renderJourney(), 600);
    } catch (e) { $("#rcMsg").textContent = e.message; }
  };
}


const CC = {
  en: { title: "Book your visit", open: "Choose a clinic", see: "Your appointment",
    awaiting: "A doctor is reviewing your summary. Once they approve it you can choose a clinic here.",
    emergency: "This needs emergency care now. Go to the nearest emergency department or call 998.",
    notNeeded: "No clinic visit is needed for this check.",
    pick: "Choose where you'd like to go", pickSub: "These clinics offer the care your referral needs. We don't show availability: the coordinator agrees a time with the clinic and tells you.",
    listed: "Listed from the clinic's own website. Not yet confirmed by the Riaya team.", confirmed: d => `Confirmed by the Riaya team on ${d}`,
    public: "Public", private: "Private", site: "Official website",
    when: "When suits you?", morning: "Morning", afternoon: "Afternoon", evening: "Evening", weekday: "Weekdays", weekend: "Weekends",
    how: "How should we reach you?", inApp: "Riaya messages only", phone: "A phone call", phonePh: "Mobile number",
    share: "Send my summary to the clinic with a one-time code (valid 14 days)", note: "Anything the clinic should know? (optional)",
    send: "Send request", choose: "Choose a clinic first.",
    requested: n => `Request sent to ${n}. We'll message you here when the clinic confirms a time.`, code: "Your handover code for the clinic",
    cancel: "Cancel request", cancelAppt: "Cancel appointment", cancelConfirm: "Cancel this request?",
    confirmedT: "Your appointment is confirmed", cal: "Add to calendar", calNote: "The calendar entry only says “Appointment”.",
    went: "I went", missed: "I couldn't go", why: "What got in the way? You can choose another time straight after.",
    attended: "You've been seen. Thank you for following through.", back: "Back to my journey",
    reasons: { forgot: "Forgot", clinic_cancelled: "Clinic cancelled", felt_better: "Felt better" } },
  ar: { title: "احجز زيارتك", open: "اختر عيادة", see: "موعدك",
    awaiting: "يراجع طبيب ملخصك الآن. بعد موافقته يمكنك اختيار عيادة من هنا.",
    emergency: "هذا يحتاج إلى رعاية طارئة الآن. توجّه إلى أقرب قسم طوارئ أو اتصل بالرقم ٩٩٨.",
    notNeeded: "لا حاجة لزيارة عيادة في هذا الفحص.",
    pick: "اختر المكان الذي تفضّله", pickSub: "تقدّم هذه العيادات الرعاية التي تحتاجها إحالتك. لا نعرض مواعيد متاحة: يتفق المنسّق على وقت مع العيادة ثم يبلغك.",
    listed: "مأخوذة من الموقع الرسمي للعيادة. لم يؤكدها فريق رعاية بعد.", confirmed: d => `أكدها فريق رعاية في ${d}`,
    public: "حكومي", private: "خاص", site: "الموقع الرسمي",
    when: "ما الوقت المناسب لك؟", morning: "صباحاً", afternoon: "بعد الظهر", evening: "مساءً", weekday: "أيام الأسبوع", weekend: "عطلة نهاية الأسبوع",
    how: "كيف نتواصل معك؟", inApp: "رسائل رعاية فقط", phone: "اتصال هاتفي", phonePh: "رقم الجوال",
    share: "أرسل ملخصي إلى العيادة برمز يُستخدم مرة واحدة (صالح ١٤ يوماً)", note: "هل هناك ما يجب أن تعرفه العيادة؟ (اختياري)",
    send: "أرسل الطلب", choose: "اختر عيادة أولاً.",
    requested: n => `أُرسل الطلب إلى ${n}. سنراسلك هنا عندما تؤكد العيادة الوقت.`, code: "رمز التسليم الخاص بك للعيادة",
    cancel: "ألغِ الطلب", cancelAppt: "ألغِ الموعد", cancelConfirm: "هل تريد إلغاء هذا الطلب؟",
    confirmedT: "تم تأكيد موعدك", cal: "أضف إلى التقويم", calNote: "يظهر في التقويم بعنوان «موعد» فقط.",
    went: "ذهبت", missed: "لم أتمكن من الذهاب", why: "ما الذي منعك؟ يمكنك اختيار وقت آخر مباشرة بعد ذلك.",
    attended: "تمت معاينتك. شكراً لمتابعتك.", back: "العودة إلى مساري",
    reasons: { forgot: "نسيت", clinic_cancelled: "ألغت العيادة", felt_better: "تحسّنت" } },
};
const cc = k => CC[LANG][k];

async function renderCare(aid) {
  rerender = () => renderCare(aid);
  setWide(false);
  const s = await API.get(`/api/assessments/${aid}/care?lang=${LANG}`);
  const d = ts => new Date(ts * 1000).toLocaleDateString(LANG === "ar" ? "ar-AE" : "en-GB", { day: "numeric", month: "long", year: "numeric" });
  const dt = ts => new Date(ts * 1000).toLocaleString(LANG === "ar" ? "ar-AE" : "en-GB", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
  const back = `<p><button class="btn ghost" id="ccBack">${cc("back")}</button></p>`;
  const a = s.appointment;
  let body = "";
  if (s.stage === "awaiting_review") body = `<div class="card"><p>${cc("awaiting")}</p></div>`;
  else if (s.stage === "emergency") body = `<div class="card" style="border-inline-start:4px solid var(--danger,#b3261e)"><p><b>${cc("emergency")}</b></p></div>`;
  else if (s.stage === "not_needed" || s.stage === "no_referral") body = `<div class="card"><p>${cc("notNeeded")}</p></div>`;
  else if (s.stage === "requested") body = `<div class="card"><p>${esc(cc("requested")(a.provider.name))}</p>
      ${a.share_code ? `<p class="small">${cc("code")}</p><div class="code" dir="ltr">${esc(a.share_code)}</div>` : ""}
      <p><button class="btn ghost" id="ccCancel">${cc("cancel")}</button></p></div>`;
  else if (s.stage === "confirmed") body = `<div class="card" style="border-inline-start:4px solid var(--saffron)"><h2>${cc("confirmedT")}</h2>
      <p style="font-size:1.15em"><b>${esc(dt(a.slot_at))}</b></p><p>${esc(a.provider.name)}${a.place_note ? `<br><span class="muted">${esc(a.place_note)}</span>` : ""}</p>
      ${a.share_code ? `<p class="small">${cc("code")}: <span class="code" dir="ltr">${esc(a.share_code)}</span></p>` : ""}
      <p class="row"><button class="btn" id="ccCal">${cc("cal")}</button><span class="muted small">${cc("calNote")}</span></p>
      <div class="row" id="ccOut"><button class="chip" data-o="attended">${cc("went")}</button><button class="chip" data-o="missed">${cc("missed")}</button>
      <button class="chip" id="ccCancel">${cc("cancelAppt")}</button></div></div>`;
  else if (s.stage === "attended") body = `<div class="card"><p>${cc("attended")}</p><p class="muted small">${esc(a.provider.name)}</p></div>`;
  else {
    const chip = (g, v) => `<span class="opt" data-g="${g}" data-v="${v}">${cc(v)}</span>`;
    body = `<h2>${cc("pick")}</h2><p class="muted small">${cc("pickSub")}</p>
      <div id="ccList">${s.providers.map(p => `<label class="card check" style="cursor:pointer;display:flex;gap:12px;align-items:flex-start">
        <input type="radio" name="prov" value="${esc(p.id)}" style="margin-top:6px"><div><b>${esc(p.name)}</b>
        <div class="small">${esc(p.area)} · ${cc(p.sector)}</div>
        <div class="small ${p.confirmed_at ? "" : "muted"}">${p.confirmed_at ? esc(cc("confirmed")(d(p.confirmed_at))) + (p.confirm_note ? ` — ${esc(p.confirm_note)}` : "") : cc("listed")}</div>
        <a class="small" href="${esc(p.website)}" target="_blank" rel="noopener noreferrer">${cc("site")}</a></div></label>`).join("")}</div>
      <div class="card"><h3>${cc("when")}</h3><div class="opts">${["morning", "afternoon", "evening"].map(v => chip("times", v)).join("")}</div>
        <div class="opts" style="margin-top:8px">${["weekday", "weekend"].map(v => chip("days", v)).join("")}</div>
        <h3>${cc("how")}</h3><div class="opts"><span class="opt on" data-c="messages">${cc("inApp")}</span><span class="opt" data-c="phone">${cc("phone")}</span></div>
        <input type="tel" id="ccPhone" dir="ltr" placeholder="${cc("phonePh")}" style="display:none;margin-top:8px" autocomplete="tel">
        <label class="check" style="margin-top:12px"><input type="checkbox" id="ccShare" checked><div>${cc("share")}</div></label>
        <textarea id="ccNote" rows="2" maxlength="500" placeholder="${cc("note")}"></textarea>
        <p class="row"><button class="btn" id="ccSend">${cc("send")}</button><span class="small" id="ccMsg" role="status"></span></p></div>`;
  }
  view().innerHTML = `<h1>${cc("title")}</h1>${body}${back}`;
  $("#ccBack").onclick = () => renderJourney();
  if ($("#ccCancel")) $("#ccCancel").onclick = async () => { if (!confirm(cc("cancelConfirm"))) return; await API.del(`/api/assessments/${aid}/appointment`); renderCare(aid); };
  if ($("#ccCal")) $("#ccCal").onclick = async () => {
    const r = await fetch(`/api/assessments/${aid}/appointment.ics`, { headers: { Authorization: `Bearer ${API.token}` } });
    const el = document.createElement("a"); el.href = URL.createObjectURL(await r.blob()); el.download = "appointment.ics"; el.click();
  };
  $$("#ccOut [data-o]").forEach(b => b.onclick = async () => {
    if (b.dataset.o === "attended") { await API.post(`/api/assessments/${aid}/appointment/outcome`, { outcome: "attended" }); return renderCare(aid); }
    $("#ccOut").innerHTML = `<p class="small">${cc("why")}</p><div class="opts">${s.missed_reasons.map(x => `<span class="opt" data-r="${x}">${esc((cc("reasons")[x]) || t("barrier")[x] || x)}</span>`).join("")}</div>`;
    $$("#ccOut [data-r]").forEach(o => o.onclick = async () => { await API.post(`/api/assessments/${aid}/appointment/outcome`, { outcome: "missed", reason: o.dataset.r }); renderCare(aid); });
  });
  $$("[data-g]").forEach(o => o.onclick = () => o.classList.toggle("on"));
  $$("[data-c]").forEach(o => o.onclick = () => { $$("[data-c]").forEach(x => x.classList.toggle("on", x === o)); $("#ccPhone").style.display = o.dataset.c === "phone" ? "block" : "none"; });
  if ($("#ccSend")) $("#ccSend").onclick = async () => {
    const pick = document.querySelector("input[name=prov]:checked");
    if (!pick) { $("#ccMsg").textContent = cc("choose"); return; }
    const sel = g => $$(`[data-g="${g}"].on`).map(x => x.dataset.v);
    const contact = $("[data-c].on").dataset.c;
    try {
      await API.post(`/api/assessments/${aid}/appointment`, { provider_id: pick.value, times: sel("times"), days: sel("days"), contact,
        phone: contact === "phone" ? $("#ccPhone").value : null, share_summary: $("#ccShare").checked, note: $("#ccNote").value || null });
      renderCare(aid);
    } catch (e) { $("#ccMsg").textContent = e.message; }
  };
}


const LX = {
  en: { labsT: "My lab results", labsSub: "Every result you have saved, in date order. Each one is compared with the range printed on its own report.",
    labsNone: "No saved results yet. Upload a report on the tests step, check the values, and save them here.",
    latest: "Latest", lab: "lab's range", typical: "typical range (your lab's may differ)", since: d => `since ${d}`,
    st: { low: "Below range", high: "Above range", normal: "Within range", borderline: "Borderline" },
    dir: { better: "Moving the right way", worse: "Moving the wrong way", same: "No change", changed: "Changed" },
    rev: { pending: "Waiting for a doctor to check", accepted: "Checked by a doctor", corrected: "Corrected by a doctor", rejected: "Set aside by a doctor" },
    pendingN: n => `${n} value${n === 1 ? "" : "s"} waiting for a doctor to check against your report.`,
    ctxT: "How was the sample taken? (optional)", abst: "Days since last ejaculation", time: "Time the sample was taken", fasting: "I was fasting",
    fever: "I had a fever in the 3 months before", labName: "Lab name (optional)", range: "Lab's range", conf: { high: "Read clearly", medium: "Please check", low: "Unsure, check carefully", check: "Looks unusual" },
    saveTl: "Saved to My lab results.", openLabs: "My lab results", del: "Remove", table: "Show as table", date: "Date", value: "Value", status: "Status",
    planT: "12-week plan", planSub: "Sperm take about 74 days to develop, so changes in habits show in results after about three months. Pick up to three goals from your summary.",
    planPick: "Choose up to three goals", planStart: "Start my plan", planReview: "A doctor will look over your plan before it starts. You'll get a message.",
    planSelf: "You haven't asked for doctor review, so this plan is self-guided.", planWait: "Your plan is with a doctor for review. You'll get a message when it starts.",
    week: (w, n) => `Week ${w} of ${n}`, due: "This week's check-in", howWent: "How did it go?", energy: "Your energy this week",
    saveCheck: "Save this week", saved: "Saved. See you next week.", trend: "Your weeks so far", noTrend: "Your trend appears after your first check-in.",
    doctorSays: "From your doctor", remind: "Weekly reminder", remindSub: "Adds a calendar entry that says only “Weekly check-in”, every week at 8 pm.",
    remindB: "Add to calendar", stop: "Stop plan", stopC: "Stop this plan? Your check-ins are kept.", done: "Your 12 weeks are complete. A follow-up check will show what changed.",
    recheck: "Start a follow-up check", first: "Start", now: "Now", logged: n => `${n} of 12 weeks logged`, openPlan: "12-week plan",
    adherence: ["Not this week", "A few days", "Most days", "Every day"] },
  ar: { labsT: "نتائج فحوصاتي", labsSub: "كل نتيجة حفظتها بترتيب التاريخ. تُقارن كل نتيجة بالمعدل المطبوع على تقريرها.",
    labsNone: "لا توجد نتائج محفوظة بعد. ارفع تقريراً في خطوة الفحوصات، وتحقق من القيم، ثم احفظها هنا.",
    latest: "الأحدث", lab: "معدل المختبر", typical: "المعدل المعتاد (قد يختلف معدل مختبرك)", since: d => `منذ ${d}`,
    st: { low: "أقل من المعدل", high: "أعلى من المعدل", normal: "ضمن المعدل", borderline: "حدّي" },
    dir: { better: "يتحسن", worse: "يتراجع", same: "بلا تغيير", changed: "تغيّر" },
    rev: { pending: "بانتظار مراجعة الطبيب", accepted: "راجعه طبيب", corrected: "صحّحه طبيب", rejected: "استبعده طبيب" },
    pendingN: n => `${n} قيمة بانتظار أن يطابقها طبيب مع تقريرك.`,
    ctxT: "كيف أُخذت العينة؟ (اختياري)", abst: "أيام منذ آخر قذف", time: "وقت أخذ العينة", fasting: "كنت صائماً",
    fever: "أصبت بحمّى خلال الأشهر الثلاثة السابقة", labName: "اسم المختبر (اختياري)", range: "معدل المختبر", conf: { high: "قُرئت بوضوح", medium: "يرجى التحقق", low: "غير مؤكدة، تحقق بعناية", check: "تبدو غير معتادة" },
    saveTl: "حُفظت في نتائج فحوصاتي.", openLabs: "نتائج فحوصاتي", del: "إزالة", table: "اعرضها كجدول", date: "التاريخ", value: "القيمة", status: "الحالة",
    planT: "خطة ١٢ أسبوعاً", planSub: "تحتاج الحيوانات المنوية نحو ٧٤ يوماً لتتكوّن، لذا يظهر أثر تغيير العادات في النتائج بعد نحو ثلاثة أشهر. اختر حتى ثلاثة أهداف من ملخصك.",
    planPick: "اختر حتى ثلاثة أهداف", planStart: "ابدأ خطتي", planReview: "سيراجع طبيب خطتك قبل أن تبدأ. ستصلك رسالة.",
    planSelf: "لم تطلب مراجعة طبيب، لذا هذه خطة ذاتية.", planWait: "خطتك لدى طبيب للمراجعة. ستصلك رسالة عندما تبدأ.",
    week: (w, n) => `الأسبوع ${w} من ${n}`, due: "متابعة هذا الأسبوع", howWent: "كيف كان الأسبوع؟", energy: "طاقتك هذا الأسبوع",
    saveCheck: "احفظ هذا الأسبوع", saved: "تم الحفظ. نراك الأسبوع القادم.", trend: "أسابيعك حتى الآن", noTrend: "يظهر مسارك بعد أول متابعة.",
    doctorSays: "من طبيبك", remind: "تذكير أسبوعي", remindSub: "يضيف موعداً في التقويم بعنوان «متابعة أسبوعية» فقط، كل أسبوع الساعة ٨ مساءً.",
    remindB: "أضف إلى التقويم", stop: "أوقف الخطة", stopC: "هل تريد إيقاف هذه الخطة؟ تبقى متابعاتك محفوظة.", done: "اكتملت أسابيعك الاثنا عشر. سيُظهر فحص المتابعة ما تغيّر.",
    recheck: "ابدأ فحص متابعة", first: "البداية", now: "الآن", logged: n => `سُجّل ${n} من ١٢ أسبوعاً`, openPlan: "خطة ١٢ أسبوعاً",
    adherence: ["ليس هذا الأسبوع", "بضعة أيام", "معظم الأيام", "كل يوم"] },
};
const lx = k => LX[LANG][k];
const fmtD = iso => iso ? new Date(iso + "T00:00:00").toLocaleDateString(LANG === "ar" ? "ar-AE" : "en-GB", { day: "numeric", month: "short", year: "numeric" }) : "";

// one series, one hue; the lab's range is a band; status is always written in words, never colour alone
function labChart(s) {
  const pts = s.points.filter(p => p.review_status !== "rejected");
  if (pts.length < 2) return "";
  const W = 320, H = 132, L = 36, R = 12, T = 12, B = 26;
  const vals = pts.map(p => p.value), ref = (s.latest && s.latest.ref) || {};
  const bounds = [ref.low, ref.high].filter(v => v != null);
  const lo = Math.min(...vals, ...bounds), hi = Math.max(...vals, ...bounds);
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.18, y0 = Math.max(0, lo - pad), y1 = hi + pad;
  const x = i => pts.length === 1 ? (L + W - R) / 2 : L + i * (W - L - R) / (pts.length - 1);
  const y = v => T + (H - T - B) * (1 - (v - y0) / (y1 - y0));
  const band = (ref.low != null || ref.high != null) ? `<rect x="${L}" y="${y(ref.high ?? y1)}" width="${W - L - R}" height="${Math.max(0, y(ref.low ?? y0) - y(ref.high ?? y1))}" fill="var(--good)" opacity=".12"/>` : "";
  const line = pts.length > 1 ? `<polyline points="${pts.map((p, i) => `${x(i)},${y(p.value)}`).join(" ")}" fill="none" stroke="var(--brand)" stroke-width="2" stroke-linejoin="round"/>` : "";
  const dots = pts.map((p, i) => `<circle cx="${x(i)}" cy="${y(p.value)}" r="5" fill="var(--brand)" stroke="var(--surface)" stroke-width="2"><title>${esc(fmtD(p.date))}: ${p.value} ${esc(s.unit)} (${esc(lx("st")[p.status])})</title></circle>`).join("");
  const ticks = pts.map((p, i) => `<text x="${x(i)}" y="${H - 8}" font-size="10" text-anchor="${i === 0 ? "start" : i === pts.length - 1 ? "end" : "middle"}" fill="var(--muted)">${esc(new Date(p.date + "T00:00:00").toLocaleDateString(LANG === "ar" ? "ar-AE" : "en-GB", { month: "short", year: "2-digit" }))}</text>`).join("");
  const limits = bounds.map(v => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--good)" stroke-dasharray="4 3"/><text x="${W - R}" y="${y(v) - 4}" font-size="10" text-anchor="end" fill="var(--muted)">${LANG === "ar" ? "حد المختبر" : "lab limit"} ${v}</text>`).join("");
  const axis = [y0, y1].map(v => `<text x="${L - 6}" y="${y(v) + 3}" font-size="10" text-anchor="end" fill="var(--muted)">${+v.toFixed(1)}</text>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(s.name)}: ${pts.map(p => `${fmtD(p.date)} ${p.value}`).join(", ")}" style="max-width:420px;display:block" dir="ltr">
    ${band}${limits}<line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" stroke="var(--line)"/>${axis}${line}${dots}${ticks}</svg>`;
}

async function renderLabs() {
  rerender = renderLabs;
  setWide(false);
  const tl = await API.get(`/api/me/labs?lang=${LANG}`);
  const card = s => {
    const l = s.latest;
    const refTxt = l ? (l.ref_used === "lab" ? `${lx("lab")}: ${esc(l.ref.text || [l.ref.low, l.ref.high].filter(v => v != null).join("–"))}` : lx("typical")) : "";
    return `<div class="card"><div class="row"><h2 style="margin:0">${esc(s.name)}</h2><span class="spacer"></span>
        ${l ? `<span class="tag">${esc(lx("st")[l.status])}</span>` : ""}</div>
      ${l ? `<p style="margin:6px 0"><b style="font-size:1.4em">${l.value}</b> ${esc(s.unit)} <span class="muted small">${lx("latest")}, ${esc(fmtD(l.date))}</span></p>
        <p class="muted small" style="margin:0">${refTxt}</p>` : ""}
      ${s.change ? `<p class="small">${esc(lx("dir")[s.change.direction])} (${s.change.diff > 0 ? "+" : ""}${s.change.diff} ${esc(s.unit)} ${esc(lx("since")(fmtD(s.change.since)))})</p>` : ""}
      ${labChart(s)}
      ${l && l.notes.length ? `<ul class="small">${l.notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
      ${s.advice.length ? `<p class="small"><b>${s.advice.map(esc).join("<br>")}</b></p>` : ""}
      <details><summary class="small">${lx("table")}</summary><table class="small"><tr><th>${lx("date")}</th><th>${lx("value")}</th><th>${lx("status")}</th><th></th></tr>
        ${s.points.map(p => `<tr style="${p.review_status === "rejected" ? "text-decoration:line-through;opacity:.6" : ""}"><td>${esc(fmtD(p.date))}${p.lab_name ? `<br><span class="muted">${esc(p.lab_name)}</span>` : ""}</td>
          <td>${p.value} ${esc(s.unit)}</td><td>${esc(lx("st")[p.status])}<br><span class="muted">${esc(lx("rev")[p.review_status])}${p.review_note ? `: ${esc(p.review_note)}` : ""}</span></td>
          <td><button class="chip" data-del="${p.id}">${lx("del")}</button></td></tr>`).join("")}</table></details></div>`;
  };
  view().innerHTML = `<h1>${lx("labsT")}</h1><p class="lead">${lx("labsSub")}</p>
    ${tl.pending_review ? `<p class="small muted">${esc(lx("pendingN")(tl.pending_review))}</p>` : ""}
    ${tl.series.length ? tl.series.map(card).join("") : `<div class="card"><p>${lx("labsNone")}</p></div>`}
    <p class="muted small">${esc(tl.note)}</p><p><button class="btn ghost" id="lxBack">${t("jOpen")}</button></p>`;
  $("#lxBack").onclick = () => renderJourney();
  $$("[data-del]").forEach(b => b.onclick = async () => { await API.del(`/api/me/labs/${b.dataset.del}`); renderLabs(); });
}

// adherence bars: one hue, height = days kept; empty weeks drawn as a faint outline
function weekBars(it) {
  const W = 300, H = 70, gap = 4, bw = (W - gap * 11) / 12;
  return `<svg viewBox="0 0 ${W} ${H + 14}" width="100%" style="max-width:380px;display:block" dir="ltr" role="img" aria-label="${esc(it.label)}: ${it.weeks.filter(w => w.adherence != null).map(w => `week ${w.week} ${lx("adherence")[w.adherence]}`).join(", ")}">
    ${it.weeks.map((w, i) => { const x = i * (bw + gap); const h = w.adherence == null ? 0 : 8 + (H - 8) * w.adherence / 3;
      return w.adherence == null ? `<rect x="${x}" y="${H - 6}" width="${bw}" height="6" rx="2" fill="none" stroke="var(--line)"/>`
        : `<rect x="${x}" y="${H - h}" width="${bw}" height="${h}" rx="3" fill="var(--brand)"><title>${lx("week")(w.week, 12)}: ${esc(lx("adherence")[w.adherence])}${w.value != null ? `, ${w.value}` : ""}</title></rect>`; }).join("")}
    <text x="0" y="${H + 12}" font-size="10" fill="var(--muted)">1</text><text x="${W}" y="${H + 12}" font-size="10" text-anchor="end" fill="var(--muted)">12</text></svg>`;
}

async function renderPlan() {
  rerender = renderPlan;
  setWide(false);
  const { plan } = await API.get(`/api/me/plan?lang=${LANG}`);
  const back = `<p><button class="btn ghost" id="pnBack">${t("jOpen")}</button></p>`;
  if (!plan || plan.status === "stopped") {
    const aid = S.aid;
    const o = await API.get(`/api/assessments/${aid}/plan-options?lang=${LANG}`);
    view().innerHTML = `<h1>${lx("planT")}</h1><p class="lead">${lx("planSub")}</p>
      <div class="card"><h3>${lx("planPick")}</h3><div id="pnOpts">${o.options.map(x => `<label class="check"><input type="checkbox" value="${esc(x.node)}"><div><b>${esc(x.label)}</b><br><span class="small">${esc(x.action)}</span></div></label>`).join("")}</div>
      <p class="muted small">${o.doctor_review ? lx("planReview") : lx("planSelf")}</p>
      <p class="row"><button class="btn" id="pnGo">${lx("planStart")}</button><span class="small" id="pnMsg" role="status"></span></p></div>${back}`;
    const boxes = $$("#pnOpts input");
    boxes.forEach(b => b.onchange = () => { const n = boxes.filter(x => x.checked).length; boxes.forEach(x => { x.disabled = !x.checked && n >= o.max; }); });
    $("#pnGo").onclick = async () => {
      const nodes = boxes.filter(x => x.checked).map(x => x.value);
      if (!nodes.length) { $("#pnMsg").textContent = lx("planPick"); return; }
      try { await API.post(`/api/assessments/${aid}/plan?lang=${LANG}`, { nodes }); renderPlan(); } catch (e) { $("#pnMsg").textContent = e.message; }
    };
    $("#pnBack").onclick = () => renderJourney();
    return;
  }
  const head = `<h1>${lx("planT")}</h1>`;
  if (plan.status === "proposed") {
    view().innerHTML = `${head}<div class="card"><p>${lx("planWait")}</p><ul>${plan.items.map(i => `<li><b>${esc(i.label)}</b>: ${esc(i.action)}</li>`).join("")}</ul></div>${back}`;
    $("#pnBack").onclick = () => renderJourney();
    return;
  }
  const done = plan.status === "completed";
  const form = plan.due ? `<div class="card" style="border-inline-start:4px solid var(--saffron)"><h2>${lx("due")}</h2>
      ${plan.items.map(i => `<div class="pn-item" data-n="${esc(i.node)}"><h3>${esc(i.label)}</h3><p class="small muted">${esc(i.action)}</p>
        <p class="small">${lx("howWent")}</p><div class="opts">${lx("adherence").map((a, k) => `<span class="opt" data-a="${k}">${esc(a)}</span>`).join("")}</div>
        ${i.measure ? `<label class="small">${esc(i.measure.label)} <input type="number" class="pn-val" min="${i.measure.min}" max="${i.measure.max}" step="0.1" style="width:110px"></label>` : ""}</div>`).join("")}
      <p class="small">${lx("energy")}</p><div class="opts" id="pnEnergy">${[1, 2, 3, 4, 5].map(k => `<span class="opt" data-e="${k}">${k}</span>`).join("")}</div>
      <p class="row"><button class="btn" id="pnSave">${lx("saveCheck")}</button><span class="small" id="pnMsg" role="status"></span></p></div>` : "";
  view().innerHTML = `${head}<p class="lead">${done ? lx("done") : esc(lx("week")(plan.week, plan.weeks))}</p>
    ${done ? `<p><button class="btn" id="pnRecheck">${lx("recheck")}</button></p>` : ""}
    ${plan.doctor_note ? `<div class="card"><h3>${lx("doctorSays")}</h3><p>${esc(plan.doctor_note)}</p></div>` : ""}
    ${form}
    <div class="card"><h2>${lx("trend")}</h2>${plan.items.map(i => `<h3>${esc(i.label)}</h3>
      <p class="small muted">${esc(lx("logged")(i.summary.weeks_logged))}${i.measure && i.summary.first != null ? `. ${esc(i.measure.label)}: ${lx("first")} ${i.summary.first}, ${lx("now")} ${i.summary.latest}` : ""}</p>
      ${i.summary.weeks_logged ? weekBars(i) : `<p class="small muted">${lx("noTrend")}</p>`}`).join("")}</div>
    ${done ? "" : `<div class="card"><h3>${lx("remind")}</h3><p class="small muted">${lx("remindSub")}</p><p class="row"><button class="btn ghost" id="pnCal">${lx("remindB")}</button>
      <button class="chip" id="pnStop">${lx("stop")}</button></p></div>`}${back}`;
  $("#pnBack").onclick = () => renderJourney();
  $$(".pn-item .opt").forEach(o => o.onclick = () => { o.parentElement.querySelectorAll(".opt").forEach(x => x.classList.toggle("on", x === o)); });
  $$("#pnEnergy .opt").forEach(o => o.onclick = () => $$("#pnEnergy .opt").forEach(x => x.classList.toggle("on", x === o)));
  if ($("#pnSave")) $("#pnSave").onclick = async () => {
    const items = {};
    for (const el of $$(".pn-item")) {
      const a = el.querySelector(".opt.on"), v = el.querySelector(".pn-val");
      if (!a) { $("#pnMsg").textContent = lx("howWent"); return; }
      items[el.dataset.n] = { adherence: Number(a.dataset.a), value: v && v.value !== "" ? Number(v.value) : null };
    }
    const e = $("#pnEnergy .opt.on");
    try { await API.post(`/api/me/plan/checkin?lang=${LANG}`, { items, energy: e ? Number(e.dataset.e) : null }); renderPlan(); }
    catch (err) { $("#pnMsg").textContent = err.message; }
  };
  if ($("#pnCal")) $("#pnCal").onclick = async () => {
    await API.post("/api/me/plan/reminders", { enabled: true });
    const r = await fetch("/api/me/plan/reminders.ics", { headers: { Authorization: `Bearer ${API.token}` } });
    const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = "weekly-check-in.ics"; a.click();
  };
  if ($("#pnStop")) $("#pnStop").onclick = async () => { if (!confirm(lx("stopC"))) return; await API.del("/api/me/plan"); renderPlan(); };
  if ($("#pnRecheck")) $("#pnRecheck").onclick = async () => {
    S.aid = (await API.post("/api/assessments?channel=web")).id; store.set("aid", S.aid); store.del("done"); S.section = 0; intake();
  };
}
