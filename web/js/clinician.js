const LEVELS = ["self_care", "primary_care", "fertility_services", "andrology", "same_day_primary", "urgent_specialist", "emergency"];
const LEVEL_NAME = { self_care: "Self-care plan", primary_care: "Primary care / IFHAS", fertility_services: "Fertility services (couple)", andrology: "Andrology / urology", same_day_primary: "Same-day primary care", urgent_specialist: "Urgent urology", emergency: "Emergency" };
const lvl = l => `<span class="pill lvl-${l}">${LEVEL_NAME[l] || l}</span>`;
const fmt = ts => ts ? new Date(ts * 1000).toLocaleString() : "—";
let GRAPH = null, current = null;

function login() {
  $("#view").innerHTML = `<div class="card" style="max-width:420px;margin:40px auto">
    <h2>Sign in</h2><label class="q">Username</label><input type="text" id="u" value="clinician">
    <label class="q">Password</label><input type="password" id="p">
    <p><button class="btn" id="go">Sign in</button></p><p class="muted small" id="err">All access is logged. You will only see men who consented to clinician review or gave you a share code.</p></div>`;
  $("#go").onclick = async () => {
    try {
      const r = await API.post("/api/clinician/login", { username: $("#u").value, password: $("#p").value });
      API.token = r.token; sessionStorage.setItem("ctoken", r.token); $("#who").textContent = r.name; start();
    } catch (e) { $("#err").textContent = e.message; }
  };
}

async function start() {
  $("#logout").classList.remove("hidden");
  $("#logout").onclick = () => { sessionStorage.removeItem("ctoken"); location.reload(); };
  GRAPH = GRAPH || await API.get("/api/graph");
  $("#view").innerHTML = `<div class="tabs row" style="margin-bottom:12px">
    <button class="chip on" data-t="queue">Review queue</button><button class="chip" data-t="metrics">Outcomes & fairness</button>
    <button class="chip" data-t="audit">Access log</button><a class="chip" href="insights.html">Programme dashboard</a><span class="spacer"></span>
    <input type="text" id="code" placeholder="Share code" style="width:160px"><button class="chip" id="open">Open</button></div><div id="tab"></div>`;
  $$(".tabs [data-t]").forEach(b => b.onclick = () => { $$(".tabs [data-t]").forEach(x => x.classList.toggle("on", x === b)); ({ queue, metrics, audit })[b.dataset.t](); });
  $("#open").onclick = async () => {
    try { const r = await API.post(`/api/clinician/share/${$("#code").value.trim()}`); await queue(); openCase(r.assessment_id); }
    catch (e) { alert(e.message); }
  };
  queue();
}

async function queue() {
  const q = await API.get("/api/clinician/queue");
  $("#tab").innerHTML = `<div class="layout"><div class="qlist">
      <div class="card"><h2>Pending review (${q.pending.length})</h2>${q.pending.map(item).join("") || '<p class="muted">Nothing waiting.</p>'}</div>
      <div class="card"><h3>Recently reviewed</h3>${q.recent.map(item).join("") || '<p class="muted">None yet.</p>'}</div>
    </div><div id="case"><div class="card muted">Select a case.</div></div></div>`;
  $$(".qitem").forEach(el => el.onclick = () => openCase(el.dataset.id));
  if (current) openCase(current);
}

function sla(due) {
  if (!due) return "";
  const h = (due - Date.now() / 1000) / 3600;
  return h < 0 ? `<span class="pill lvl-emergency">overdue ${Math.round(-h)} h</span>` : `<span class="pill lvl-andrology">due in ${Math.round(h)} h</span>`;
}

function item(c) {
  return `<div class="qitem ${c.id === current ? "on" : ""}" data-id="${c.id}">${c.rapid ? '<span class="pill lvl-urgent_specialist">Rapid review</span> ' + (c.status === "pending_review" ? sla(c.due_at) : "") + "<br>" : ""}
    ${lvl(c.final_level || c.level)} <span class="tag">${c.tier}</span>${c.unread ? ` <span class="tag">${c.unread} new message${c.unread > 1 ? "s" : ""}</span>` : ""}
    ${c.simulated ? '<span class="tag">simulated</span>' : ""}<div class="muted small">${esc(c.cohort)} · ${fmt(c.completed_at)} · ${c.status}</div></div>`;
}

async function openCase(id) {
  current = id;
  $$(".qitem").forEach(el => el.classList.toggle("on", el.dataset.id === id));
  const [c, ex] = await Promise.all([API.get(`/api/clinician/cases/${id}`), API.get(`/api/clinician/cases/${id}/explain`)]);
  const r = c.result, t = r.triage, ins = r.instruments, a = c.answers || {}, ref = c.referral;
  const node = n => GRAPH.nodes.find(x => x.id === n) || { label: n };
  const attr = Object.entries(r.attribution);
  const maxA = Math.max(0.0001, ...attr.map(([, v]) => Math.abs(v)));
  const lab = (r.labs || {}).already_done || [];
  const semen = r.semen;
  const stages = [["created_at", "Referred"], ["reviewed_at", "Reviewed"], ["booked_at", "Booked"], ["attended_at", "Attended"], ["tests_done_at", "Tests done"], ["followup_at", "Followed up"]];
  const covCol = st => ({ measured: "var(--good)", screened: "var(--warn)", reported: "var(--info)" })[st] || "var(--muted)";
  const prefs = [a.pref_language && `Language: ${({ ar: "Arabic", en: "English", ur: "Urdu", hi: "Hindi", ml: "Malayalam" })[a.pref_language] || a.pref_language}`,
    a.pref_clinician === "male" && "Prefers a male doctor", a.pref_contact === "app_only" && "Contact through the app only"].filter(Boolean);
  const requested = t.tests.concat((t.genomic && t.genomic.flag) ? t.genomic.tests : []);

  $("#case").innerHTML = `
  <div class="ws">
    <section class="wcol">
      <h3>Patient</h3>
      <div class="card tight"><div class="kv small">
        <span>Cohort</span><b>${esc(c.result && r.instruments ? (a.age ? a.age + " y" : "") : "")} ${esc((a.background || "").replace("_", " "))}</b>
        <span>BMI</span><b>${ins.bmi ?? "—"}</b><span>Reason</span><b>${esc((a.reason || []).join(", ") || "—")}</b>
        ${a.months_trying ? `<span>Trying</span><b>${a.months_trying} months${a.partner_age ? `, wife ${a.partner_age}` : ""}</b>` : ""}
      </div>${prefs.length ? `<p class="small" style="margin:10px 0 0">${prefs.map(p => `<span class="tag">${esc(p)}</span>`).join("")}</p>` : ""}
      ${c.simulated ? '<p class="small"><span class="tag">simulated case</span></p>' : ""}</div>
      <div class="card tight"><b class="small">Data coverage</b><div class="kv small" style="margin-top:8px">
        ${ex.coverage.map(x => `<span>${esc(x.label)}</span><span style="color:${covCol(x.status)}">${esc(x.status_text)}</span>`).join("")}</div></div>
      <div class="card tight"><b class="small">Tests</b>
        <p class="small muted" style="margin:6px 0">Already done</p><ul class="small">${semen ? `<li>${semen.source === "lab" ? "Semen analysis (lab)" : "Home sperm test"}: ${semen.findings.length ? semen.findings.map(f => esc(f[1])).join("; ") : "within WHO 2021 limits"}</li>` : ""}
          ${lab.map(([n, v, d]) => `<li>${esc(n)} ${esc(v)}${d ? ` <span class="muted">${esc(d)}</span>` : ""}</li>`).join("") || (semen ? "" : '<li class="muted">None</li>')}</ul>
        <p class="small muted" style="margin:6px 0">Requested (duplicates removed)</p><ul class="small">${requested.map(x => `<li>${esc(x)}</li>`).join("") || '<li class="muted">None</li>'}</ul></div>
      ${r.wearable ? `<div class="card tight"><b class="small">Devices</b><div class="kv small" style="margin-top:8px">
        ${[["sleep_avg_h", "Sleep (h)"], ["steps_avg", "Steps / day"], ["social_jetlag_h", "Weekend shift (h)"], ["spo2_low_nights", "Nights SpO2 < 90%"], ["night_glucose_high_pct", "Night glucose > 140 (%)"], ["resting_hr_avg", "Resting HR"]]
          .filter(([k]) => r.wearable[k] != null).map(([k, l]) => `<span>${l}</span><b>${r.wearable[k]}</b>`).join("")}</div>
        ${ex.baseline ? `<p class="small muted" style="margin:10px 0 4px">Against his own baseline</p><div class="kv small">${Object.entries(ex.baseline).map(([k, b]) =>
          `<span>${k.replace("_", " ")}</span><b>${b.recent} vs ${b.baseline}${b.unusual ? " ⚑" : ""}</b>`).join("")}</div>` : ""}</div>` : ""}
      <div class="card tight"><b class="small">Signals and sources</b>${Object.entries(r.provenance).map(([n, ps]) =>
        `<p class="small" style="margin:8px 0 0"><a href="#" data-ev="${n}">${esc(node(n).label)}</a><br><span class="muted">${ps.map(p => `${p.source}: ${esc(p.reason)}`).join("; ")}</span></p>`).join("")}</div>
    </section>

    <section class="wcol mid">
      <h3>Clinical review</h3>
      ${t.immediate ? '<div class="banner alert"><b>Red flag, time-critical.</b> The man was already shown immediate instructions.</div>' : ""}
      ${t.rapid_review ? `<div class="banner alert small"><b>Rapid review, ${t.sla_hours} h target.</b> ${t.rapid_reasons.map(esc).join("; ")}</div>` : ""}
      ${ex.contradictions.length ? `<div class="banner"><b class="small">Contradictions to resolve</b>${ex.contradictions.map(x => `<p class="small" style="margin:6px 0 0">${x.severity === "review" ? "⚑ " : ""}${esc(x.text)}</p>`).join("")}</div>` : ""}
      <div class="card tight"><div class="row"><b>Suggested pathway</b> ${lvl(t.level)} <span class="tag">signal tier ${t.tier}</span></div>
        <ul class="small">${t.reasons.map(x => `<li>${esc(x.reason)} <span class="muted">[${x.basis.join(", ")}]</span></li>`).join("")}</ul>
        ${t.genomic && t.genomic.flag ? `<div class="banner info small"><b>Genomic flag.</b> ${t.genomic.reasons.map(x => esc(x.replace(/\.?$/, "."))).join(" ")} Suggested: ${t.genomic.tests.map(esc).join(", ")}.</div>` : ""}</div>
      <div class="card tight"><b>Findings, with evidence</b><p class="small muted">Click a factor to open the evidence explorer.</p>
        ${ex.cards.slice(0, 8).map(cd => `<div class="plan-item small"><a href="#" data-ev="${cd.node}"><b>${esc(cd.label)}</b></a> ${cd.grade ? gradeTag(cd.grade) : ""}
          <span class="muted">contribution ${cd.contribution.toFixed(2)}</span><br>${esc(cd.observation)}${cd.relevance ? `<br><span class="muted">${esc(cd.relevance)}</span>` : ""}
          ${cd.limitations.length ? `<br><i class="muted">${cd.limitations.map(esc).join(" ")}</i>` : ""}</div>`).join("")}</div>
      <div id="evx"></div>
      <div class="grid2">
        <div class="card tight"><b class="small">Evidence-graph attribution</b>${attr.slice(0, 8).map(([k, v]) => `<div class="small" style="margin:6px 0">${esc(node(k).label)}
          <div class="bar" style="width:${Math.abs(v) / maxA * 100}%"></div></div>`).join("")}</div>
        <div class="card tight"><b class="small">Statistical model (SHAP)</b><p class="muted small">P(below-reference semen) ${r.models.simulated_gbm.probability}. Simulated cohort, test AUC ${r.models.simulated_gbm.auc_test}.</p>
          ${waterfall(r.models.simulated_gbm)}<p class="muted small">Real-data model (UCI, n=100): P(altered) ${r.models.uci_logistic.probability}. Context only.</p></div>
      </div>
    </section>

    <section class="wcol">
      <h3>Actions</h3>
      <div class="card tight"><b>Decision</b>
        ${ref && ref.status === "pending_review" ? `
          <p><button class="btn" id="approve" style="width:100%">Approve: ${LEVEL_NAME[t.level]}</button></p>
          <select id="lvl">${LEVELS.map(l => `<option value="${l}" ${l === t.level ? "selected" : ""}>${LEVEL_NAME[l]}</option>`).join("")}</select>
          <textarea id="note" rows="3" placeholder="Reason (required to change or reject)" style="margin-top:8px"></textarea>
          <div class="row" style="margin-top:8px"><button class="btn ghost" id="modify">Change level</button><button class="btn danger" id="reject">Reject referral</button></div><p class="small" id="decErr" style="color:var(--alert)"></p>`
        : ref ? `<p class="small">${ref.status === "rejected" ? "Rejected" : "Approved"}: ${lvl(ref.final_level || ref.level)}<br>by ${esc(ref.reviewer || "—")}, ${fmt(ref.reviewed_at)}</p>${c.review_note ? `<p class="small"><b>Reason:</b> ${esc(c.review_note)}</p>` : ""}`
        : '<p class="small muted">No referral needed: personal plan only.</p>'}</div>
      ${ref ? `<div class="card tight"><b>Referral tracking</b>
        <ol class="steps2">${stages.map(([k, l]) => `<li class="${ref[k] ? "done" : ""}">${l}${ref[k] ? ` <span class="muted">${new Date(ref[k] * 1000).toLocaleDateString("en-GB")}</span>` : ""}</li>`).join("")}
          ${ref.status === "declined" ? `<li class="stop">Could not go: ${esc(ref.barrier || "—")}</li>` : ""}</ol>
        ${ref.self_reported ? '<p class="small muted">Includes steps reported by the patient.</p>' : ""}
        <div class="row">${[["booked", "Booked"], ["attended", "Attended"], ["tests_done", "Tests done"], ["followed_up", "Followed up"]].map(([s, l]) => `<button class="chip" data-s="${s}">${l}</button>`).join("")}</div></div>` : ""}
      <div class="card tight"><b>Messages</b><div id="thread" class="small"></div>
        <div class="row" style="flex-wrap:nowrap;margin-top:8px"><input type="text" id="cmsg" placeholder="Message (encrypted)"><button class="btn" id="csend">Send</button></div>
        <div class="row" style="margin-top:8px"><button class="chip" id="cnote">Record voice reply</button><button class="chip" id="video">${ref && ref.video_url ? "Video room ready" : "Start video consult"}</button></div>
        ${ref && ref.video_url ? `<p class="small"><a href="${esc(ref.video_url)}" target="_blank" rel="noopener noreferrer">Join video room</a></p>` : ""}</div>
      <div class="card tight"><b>Handover</b><p class="small muted">Referral letter and FHIR bundle for the receiving clinic or IFHAS visit.</p>
        <div class="row"><button class="chip" id="hoView">View letter</button><button class="chip" id="hoDl">Download FHIR</button></div><div id="letter"></div></div>
    </section>
  </div>`;

  const decideErr = m => $("#decErr").textContent = m;
  if ($("#approve")) {
    $("#approve").onclick = () => decide("approve");
    $("#modify").onclick = () => $("#note").value.trim() ? decide("modify") : decideErr("Add a reason before changing the level.");
    $("#reject").onclick = () => $("#note").value.trim() ? decide("reject") : decideErr("Add a reason before rejecting.");
  }
  $$("[data-s]").forEach(b => b.onclick = async () => { await API.post(`/api/clinician/cases/${id}/status`, { status: b.dataset.s }); openCase(id); });
  $$("[data-ev]").forEach(x => x.onclick = e => { e.preventDefault(); evidence(x.dataset.ev, r); });
  const thread = ms => { $("#thread").innerHTML = ms.map(m => Notes.render(m, `/api/clinician/cases/${id}/voice-notes`, (m.sender === "user" ? "Patient" : "Clinician") + ", " + fmt(m.ts))).join("") || '<p class="muted">No messages yet.</p>'; Notes.wire($("#thread")); };
  thread(c.messages || []);
  $("#csend").onclick = async () => { const v = $("#cmsg").value.trim(); if (!v) return; await API.post(`/api/clinician/cases/${id}/messages`, { body: v }); $("#cmsg").value = ""; thread(await API.get(`/api/clinician/cases/${id}/messages`)); };
  Notes.attach($("#cnote"), `/api/clinician/cases/${id}/voice-notes`, async () => thread(await API.get(`/api/clinician/cases/${id}/messages`)),
    { record: "Record voice reply", stop: "Send", denied: "Microphone blocked", unsupported: "Not supported" });
  $("#video").onclick = async () => { await API.post(`/api/clinician/cases/${id}/video`); openCase(id); };
  const ho = () => API.get(`/api/clinician/cases/${id}/handover`);
  $("#hoView").onclick = async () => { const h = await ho();
    $("#letter").innerHTML = `<div class="small" style="margin-top:10px"><b>To:</b> ${esc(h.letter.to)}, ${h.letter.date}${h.letter.sections.map(s => `<p style="margin:10px 0 2px"><b>${esc(s.title)}</b></p><ul>${s.lines.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`).join("")}</div>`; };
  $("#hoDl").onclick = async () => { const h = await ho(); const el = document.createElement("a");
    el.href = URL.createObjectURL(new Blob([JSON.stringify(h.bundle, null, 1)], { type: "application/fhir+json" })); el.download = `handover-${id.slice(0, 8)}.fhir.json`; el.click(); };
}

/* Evidence explorer: everything the graph knows about one factor, next to what this patient showed. */
function evidence(nid, r) {
  const n = GRAPH.nodes.find(x => x.id === nid);
  const lab = id => (GRAPH.nodes.find(x => x.id === id) || {}).label || id;
  const out = GRAPH.edges.filter(e => e.source === nid), inc = GRAPH.edges.filter(e => e.target === nid);
  const cite = k => { const t = GRAPH.references[k] || k; return `<li><a href="https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(t.replace(/\s*\(\d{4}\)\.?/, " ").split(". ").slice(0, 2).join(" "))}" target="_blank" rel="noopener">${esc(t)}</a></li>`; };
  const refs = [...new Set([...out, ...inc].flatMap(e => e.refs))];
  const weak = [...out, ...inc].filter(e => "CD".includes(e.grade) || e.kind === "assoc");
  const paths = [];
  (function walk(cur, trail) {
    if (trail.length > 5) return;
    if (cur === "subfertility" && trail.length) { paths.push(trail); return; }
    for (const e of GRAPH.edges.filter(x => x.source === cur && x.sign === "+" && "ABC".includes(x.grade))) {
      if (trail.some(t => t.target === e.target) || e.target === nid) continue;
      walk(e.target, [...trail, e]);
    }
  })(nid, []);
  const rank = { A: 4, B: 3, C: 2, D: 1 };
  const best = paths.map(p => ({ p, g: p.reduce((m, e) => Math.min(m, rank[e.grade]), 4) })).sort((x, y) => y.g - x.g || x.p.length - y.p.length).slice(0, 3);
  $("#evx").innerHTML = `<div class="card tight evx"><div class="row"><b>Evidence explorer: ${esc(n.label)}</b><span class="spacer"></span><button class="chip" id="evClose">Close</button></div>
    <p class="small muted">${n.type}${n.modifiable ? ", modifiable" : n.modifiable === false ? ", not modifiable" : ""}${n.local ? ", " + esc(n.local) : ""}</p>
    ${r.provenance[nid] ? `<p class="small"><b>In this patient:</b> ${r.provenance[nid].map(p => `${p.source}: ${esc(p.reason)}`).join("; ")}</p>` : ""}
    <p class="small"><b>Mechanisms to fertility</b></p><ul class="small">${best.map(({ p, g }) => `<li>${gradeTag("DCBA"[g - 1])} ${[n.label, ...p.map(e => lab(e.target))].map(esc).join(" → ")}</li>`).join("") || "<li>None in the graph</li>"}</ul>
    <div class="grid2 small"><div><b>Leads to</b><ul>${out.map(e => `<li>${gradeTag(e.grade)} ${esc(lab(e.target))}${e.note ? `<br><span class="muted">${esc(e.note)}</span>` : ""}</li>`).join("") || "<li>—</li>"}</ul></div>
      <div><b>Driven by</b><ul>${inc.map(e => `<li>${gradeTag(e.grade)} ${esc(lab(e.source))}</li>`).join("") || "<li>—</li>"}</ul></div></div>
    ${weak.length ? `<p class="small"><b>Uncertain or association-only links</b></p><ul class="small">${weak.map(e => `<li>${esc(lab(e.source))} → ${esc(lab(e.target))}: grade ${e.grade}${e.kind === "assoc" ? ", association" : ""}${e.note ? `. ${esc(e.note)}` : ""}</li>`).join("")}</ul>` : ""}
    <p class="small"><b>Supporting studies (${refs.length})</b></p><ul class="small">${refs.map(cite).join("")}</ul></div>`;
  $("#evClose").onclick = () => $("#evx").innerHTML = "";
  $("#evx").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function decide(decision) {
  try {
    await API.post(`/api/clinician/cases/${current}/review`, { decision, final_level: $("#lvl").value, note: $("#note").value || null });
    queue();
  } catch (e) { $("#decErr").textContent = e.message; }
}

function waterfall(m) {
  const items = m.contributions.slice(0, 10);
  const rest = m.contributions.slice(10).reduce((s, c) => s + c.shap, 0);
  if (Math.abs(rest) > 1e-4) items.push({ feature: `${m.contributions.length - 10} other features`, shap: rest, value: "" });
  let x = m.base_value;
  const steps = items.map(c => { const s = { ...c, from: x, to: x + c.shap }; x += c.shap; return s; });
  const all = steps.flatMap(s => [s.from, s.to]).concat([m.base_value]);
  const lo = Math.min(...all), hi = Math.max(...all), W = 520, L = 170, H = 22 * (steps.length + 2) + 20;
  const sx = v => L + (v - lo) / ((hi - lo) || 1) * (W - L - 50);
  const rows = steps.map((s, i) => {
    const y = 20 + i * 22, a = sx(Math.min(s.from, s.to)), w = Math.max(2, Math.abs(sx(s.to) - sx(s.from)));
    const col = s.shap > 0 ? "var(--alert)" : "var(--info)";
    return `<text x="${L - 8}" y="${y + 12}" text-anchor="end">${esc(s.feature)}${s.value !== "" ? " = " + (+s.value).toFixed(1) : ""}</text>
      <rect x="${a}" y="${y}" width="${w}" height="16" fill="${col}" rx="2"/><text x="${a + w + 4}" y="${y + 12}">${s.shap > 0 ? "+" : ""}${s.shap.toFixed(2)}</text>`;
  }).join("");
  const yEnd = 20 + steps.length * 22 + 6;
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="SHAP waterfall">
    <line x1="${sx(m.base_value)}" y1="10" x2="${sx(m.base_value)}" y2="${yEnd}" stroke="var(--muted)" stroke-dasharray="3 3"/>
    ${rows}<text x="${L - 8}" y="${yEnd + 12}" text-anchor="end">base ${m.base_value.toFixed(2)} → output</text>
    <text x="${sx(x)}" y="${yEnd + 12}">${x.toFixed(2)} log-odds</text></svg>
    <p class="muted small">Red pushes towards a below-reference result, blue away from it.</p>`;
}

async function metrics() {
  const m = await API.get("/api/clinician/metrics");
  const stat = (v, l) => `<div class="card"><div class="stat">${v ?? "—"}</div><div class="muted small">${l}</div></div>`;
  const grp = g => `<table><tr><th>Group</th><th>n</th><th>Tiers</th><th>Referred</th></tr>${Object.entries(g).map(([k, v]) =>
    `<tr><td>${esc(k)}</td><td>${v.n}</td><td class="small">${Object.entries(v.tiers).map(([a, b]) => `${a}: ${b}`).join(", ")}</td><td>${v.referred_pct}%</td></tr>`).join("")}</table>`;
  $("#tab").innerHTML = `<div class="row" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px">
      ${stat(m.completed, "completed checks")}${stat(m.completion_rate != null ? Math.round(m.completion_rate * 100) + "%" : null, "completion rate")}
      ${stat(m.median_minutes_to_complete, "median minutes to complete")}${stat(m.median_hours_to_review, "median hours to clinician review")}
      ${stat(m.median_days_to_evaluation, "median days to evaluation")}${stat(m.referral_completion_rate != null ? Math.round(m.referral_completion_rate * 100) + "%" : null, "referral completion")}
      ${stat(m.pending_review, "awaiting review")}${stat(m.clinician_changed_level, "levels changed by clinician")}
      ${m.user_feedback ? stat(m.user_feedback.t.toFixed(1) + " / 5", "user trust (n=" + m.user_feedback.n + ")") : ""}</div>
    <div class="grid2"><div class="card"><h3>By age band</h3>${grp(m.by_age)}</div><div class="card"><h3>By background</h3>${grp(m.by_background)}</div></div>
    <div class="card"><h3>Referral levels</h3>${Object.entries(m.levels).map(([k, v]) => `${lvl(k)} ${v}`).join(" ")}</div>
    <p class="muted small">Includes simulated cases from the validation run where present (marked "simulated" in the queue).</p>`;
}

async function audit() {
  const rows = await API.get("/api/clinician/audit");
  $("#tab").innerHTML = `<div class="card"><h2>Access log</h2><table><tr><th>Time</th><th>Who</th><th>Action</th><th>Case</th></tr>
    ${rows.map(r => `<tr><td>${fmt(r.ts)}</td><td>${esc(r.actor)}</td><td>${esc(r.action)}</td><td class="small">${esc(r.target || "")}</td></tr>`).join("")}</table></div>`;
}

API.token = sessionStorage.getItem("ctoken");
API.token ? start().catch(login) : login();
