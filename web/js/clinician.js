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
    <button class="chip" data-t="audit">Access log</button><span class="spacer"></span>
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
  $("#tab").innerHTML = `<div class="layout"><div>
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
  const c = await API.get(`/api/clinician/cases/${id}`);
  const r = c.result, t = r.triage, ins = r.instruments, refs = c.references;
  const refList = ids => ids.map(x => `<li>${esc(refs[x] || GRAPH.references[x] || x)}</li>`).join("");
  const label = n => GRAPH.nodes.find(x => x.id === n)?.label || n;
  const attr = Object.entries(r.attribution);
  const maxA = Math.max(0.0001, ...attr.map(([, v]) => Math.abs(v)));
  $("#case").innerHTML = `
    <div class="card">${t.immediate ? '<div class="banner alert"><b>Red flag / time-critical.</b> The man was already shown immediate instructions.</div>' : ""}
      <div class="row"><h2 style="margin:0">Suggested: ${lvl(t.level)}</h2><span class="tag">signal tier: ${t.tier}</span><span class="tag">index ${t.index}</span>
      ${c.simulated ? '<span class="tag">simulated case</span>' : ""}</div>
      <h3>Why (rules fired)</h3><ul>${t.reasons.map(x => `<li>${lvl(x.level)} ${esc(x.reason)} <span class="muted small">[${x.basis.join(", ")}]</span></li>`).join("")}</ul>
      ${t.tests.length ? `<h3>Suggested tests</h3><ul>${t.tests.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      ${t.parallel.length ? `<p>Parallel: ${t.parallel.map(p => `<span class="tag">${p}</span>`).join("")}</p>` : ""}
      ${t.genomic && t.genomic.flag ? `<div class="banner info"><b>Genomic flag: offer genetic counselling</b><ul>${t.genomic.reasons.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
        ${t.genomic.tests.length ? `<p class="small">Suggested: ${t.genomic.tests.map(esc).join(" · ")}</p>` : ""}</div>` : ""}
      ${t.rapid_review ? `<div class="banner alert small"><b>Rapid clinical review: ${t.sla_hours} h target.</b> ${t.rapid_reasons.map(esc).join("; ")}. Use secure messages or a video consult below.</div>` : ""}
      ${c.referral ? `<h3>Decision</h3>
        ${c.referral.status === "pending_review" ? `<div class="row">
          <button class="btn" id="approve">Approve ${LEVEL_NAME[t.level]}</button>
          <select id="lvl" style="width:auto">${LEVELS.map(l => `<option value="${l}" ${l === t.level ? "selected" : ""}>${LEVEL_NAME[l]}</option>`).join("")}</select>
          <button class="btn ghost" id="modify">Change level</button></div>
          <textarea id="note" rows="2" placeholder="Note for the record (encrypted)" style="margin-top:8px"></textarea>`
        : `<p>Status: <b>${c.referral.status}</b> · final ${lvl(c.referral.final_level || c.referral.level)} · reviewed ${fmt(c.referral.reviewed_at)} by ${esc(c.referral.reviewer || "—")}</p>
          <div class="row"><button class="chip" data-s="booked">Mark booked</button><button class="chip" data-s="attended">Mark attended</button><button class="chip" data-s="declined">Declined</button></div>`}` : ""}
    </div>

    <div class="grid2">
      <div class="card"><h3>Secure messages</h3><div id="thread" class="small"></div>
        <div class="row" style="flex-wrap:nowrap;margin-top:8px"><input type="text" id="cmsg" placeholder="Message to patient (encrypted)"><button class="btn" id="csend">Send</button></div>
        <p class="row" style="margin-top:10px"><button class="btn ghost" id="cnote">Record voice reply</button><button class="btn ghost" id="video">${c.referral && c.referral.video_url ? "Video room ready" : "Start video consult"}</button>
        ${c.referral && c.referral.video_url ? `<a href="${esc(c.referral.video_url)}" target="_blank" rel="noopener noreferrer">${esc(c.referral.video_url)}</a>` : ""}</p></div>
      <div class="card"><h3>Care navigation: handover package</h3>
        <p class="muted small">Structured referral letter and FHIR document bundle for the receiving clinic. It lists results already available so tests are not repeated, the genomic flag, and the patient's preferences.</p>
        <div class="row"><button class="btn ghost" id="hoView">View letter</button><button class="btn ghost" id="hoDl">Download FHIR bundle</button></div><div id="letter"></div></div>
    </div>

    <div class="grid2">
      <div class="card"><h3>Evidence-graph attribution (Shapley)</h3><p class="muted small">Contribution of each active input to the signal index, computed exactly over the knowledge graph.</p>
        ${attr.map(([k, v]) => `<div class="small" style="margin:6px 0">${esc(label(k))} <span class="muted">${v.toFixed(3)}</span>
          <div class="bar ${v < 0 ? "neg" : ""}" style="width:${Math.abs(v) / maxA * 100}%"></div></div>`).join("") || '<p class="muted">No active inputs.</p>'}</div>
      <div class="card"><h3>Gradient-boosting SHAP waterfall</h3>
        <p class="muted small">${esc(r.models.simulated_gbm.model)} · test AUC ${r.models.simulated_gbm.auc_test} · P(below-reference semen) = <b>${r.models.simulated_gbm.probability}</b></p>
        ${waterfall(r.models.simulated_gbm)}</div>
    </div>

    <div class="grid2">
      <div class="card"><h3>Signals and where they came from</h3><table><tr><th>Node</th><th>Value</th><th>Source</th></tr>
        ${Object.entries(r.provenance).map(([n, ps]) => `<tr><td>${esc(label(n))}</td><td>${r.inputs[n] ?? ""}</td><td class="small">${ps.map(p => `<span class="tag">${p.source}</span>${esc(p.reason)}`).join("<br>")}</td></tr>`).join("")}</table></div>
      <div class="card"><h3>Validated instruments</h3><div class="kv">
        ${[["BMI", ins.bmi], ["STOP-Bang (0–8)", ins.stop_bang], ["AUDIT-C (0–12)", ins.audit_c], ["PSS-4 (0–16)", ins.pss4], ["PHQ-2 (0–6)", ins.phq2], ["ADAM", ins.adam_positive == null ? null : (ins.adam_positive ? "positive" : "negative")]]
          .filter(([, v]) => v != null).map(([k, v]) => `<span>${k}</span><b>${v}</b>`).join("")}</div>
        <h3>Second opinion: model on real data</h3>
        <p class="small">${esc(r.models.uci_logistic.model)} · P(altered) = <b>${r.models.uci_logistic.probability}</b></p>
        <div class="kv small">${Object.entries(r.models.uci_logistic.contributions).slice(0, 5).map(([k, v]) => `<span>${k}</span><span>${v > 0 ? "+" : ""}${v}</span>`).join("")}</div>
        <p class="muted small">Small dataset (n=100): use as context only.</p>
      </div>
    </div>

    ${r.semen ? `<div class="card"><h3>Semen result (${esc(r.semen.source)}${r.semen.kit ? " · " + esc(r.semen.kit) : ""})</h3>
      ${r.semen.findings.length ? `<ul>${r.semen.findings.map(f => `<li>${esc(f[1])} <span class="tag">${f[2]}</span></li>`).join("")}</ul>` : "<p>Within WHO 2021 reference limits.</p>"}
      ${r.semen.notes.map(n => `<p class="muted small">${esc(n)}</p>`).join("")}</div>` : ""}
    ${r.wearable ? `<div class="card"><h3>Device summary</h3><div class="kv small">${Object.entries(r.wearable).filter(([k]) => k !== "sources").map(([k, v]) => `<span>${k}</span><b>${esc(v)}</b>`).join("")}</div></div>` : ""}

    <div class="card"><h3>Main pathways (knowledge graph)</h3>
      ${Object.entries(c.paths).map(([n, ps]) => ps.length ? `<p><b>${esc(label(n))}</b></p><ul>${ps.map(p => `<li>${gradeTag(p.grade)} ${esc(p.labels.join(" → "))}<details class="small"><summary>sources</summary><ul>${refList(p.refs)}</ul></details></li>`).join("")}</ul>` : "").join("")}
    </div>
    <details class="card"><summary>All answers</summary><div class="kv small">${Object.entries(c.answers || {}).map(([k, v]) => `<span>${k}</span><span>${esc(Array.isArray(v) ? v.join(", ") : v)}</span>`).join("")}</div></details>`;

  if ($("#approve")) {
    $("#approve").onclick = () => decide("approve");
    $("#modify").onclick = () => decide("modify");
  }
  $$("[data-s]").forEach(b => b.onclick = async () => { await API.post(`/api/clinician/cases/${id}/status`, { status: b.dataset.s }); openCase(id); });
  const thread = ms => { $("#thread").innerHTML = ms.map(m => Notes.render(m, `/api/clinician/cases/${id}/voice-notes`, (m.sender === "user" ? "Patient" : "Clinician") + " · " + fmt(m.ts))).join("") || '<p class="muted">No messages yet.</p>'; Notes.wire($("#thread")); };
  thread(c.messages || []);
  $("#csend").onclick = async () => {
    const v = $("#cmsg").value.trim(); if (!v) return;
    await API.post(`/api/clinician/cases/${id}/messages`, { body: v }); $("#cmsg").value = "";
    thread(await API.get(`/api/clinician/cases/${id}/messages`));
  };
  Notes.attach($("#cnote"), `/api/clinician/cases/${id}/voice-notes`, async () => thread(await API.get(`/api/clinician/cases/${id}/messages`)),
    { record: "Record voice reply", stop: "Send", denied: "Microphone blocked", unsupported: "Not supported" });
  $("#video").onclick = async () => { await API.post(`/api/clinician/cases/${id}/video`); openCase(id); };
  const ho = () => API.get(`/api/clinician/cases/${id}/handover`);
  $("#hoView").onclick = async () => {
    const h = await ho();
    $("#letter").innerHTML = `<div class="card" style="box-shadow:none"><p><b>To:</b> ${esc(h.letter.to)} · <b>Date:</b> ${h.letter.date}</p>
      ${h.letter.sections.map(s => `<h3>${esc(s.title)}</h3><ul>${s.lines.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`).join("")}</div>`;
  };
  $("#hoDl").onclick = async () => {
    const h = await ho();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(h.bundle, null, 1)], { type: "application/fhir+json" }));
    a.download = `handover-${id.slice(0, 8)}.fhir.json`; a.click();
  };
}

async function decide(decision) {
  await API.post(`/api/clinician/cases/${current}/review`, { decision, final_level: $("#lvl").value, note: $("#note").value || null });
  queue();
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
