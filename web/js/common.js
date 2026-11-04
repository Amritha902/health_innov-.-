const API = {
  token: null,
  headers(extra = {}) { return this.token ? { Authorization: "Bearer " + this.token, ...extra } : extra; },
  async req(method, path, body, isForm) {
    const opts = { method, headers: this.headers(isForm || body === undefined ? {} : { "Content-Type": "application/json" }) };
    if (body !== undefined) opts.body = isForm ? body : JSON.stringify(body);
    const r = await fetch(path, opts);
    const data = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
    if (!r.ok) throw Object.assign(new Error(data?.detail || r.statusText), { status: r.status, data });
    return data;
  },
  get(p) { return this.req("GET", p); },
  post(p, b) { return this.req("POST", p, b ?? {}); },
  put(p, b) { return this.req("PUT", p, b); },
  del(p) { return this.req("DELETE", p); },
  upload(p, file) { const f = new FormData(); f.append("file", file); return this.req("POST", p, f, true); },
};

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const gradeTag = g => `<span class="grade g${g}">${g}</span>`;

/* Privacy screen. "Hide" covers the page with a neutral wellness card; the page also blurs whenever it
   loses focus or the phone switches apps, so nothing readable shows in the app switcher. */
(function privacyScreen() {
  const css = document.createElement("style");
  css.textContent = `
    .pcover { position: fixed; inset: 0; z-index: 99; background: var(--bg, #f2f3f0); display: none; align-items: center; justify-content: center; padding: 24px; }
    .pcover.on { display: flex; }
    .pcover .tip { max-width: 360px; text-align: center; color: var(--ink, #0f2a3a); font: 400 17px/1.6 system-ui, sans-serif; }
    .pcover .tip b { display: block; font-size: 22px; margin-bottom: 8px; }
    .pcover button { margin-top: 22px; background: transparent; border: 1px solid var(--line, #d9dbd5); border-radius: 10px; padding: 10px 18px; color: inherit; font: inherit; }
    body.pblur > *:not(.pcover):not(.hidebtn) { filter: blur(18px); }
    .hidebtn { position: fixed; bottom: 16px; inset-inline-start: 16px; z-index: 98; width: 44px; height: 44px; border-radius: 50%; border: 1px solid var(--line, #d9dbd5);
      background: var(--surface, #fff); color: var(--ink, #0f2a3a); display: grid; place-items: center; cursor: pointer; }
    body.has-dock .hidebtn { bottom: 150px; }`;
  document.head.appendChild(css);
  const ar = () => (document.documentElement.lang || "ar") === "ar";
  const cover = document.createElement("div");
  cover.className = "pcover";
  const btn = document.createElement("button");
  btn.className = "hidebtn";
  btn.setAttribute("aria-label", "Hide screen");
  btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M3 3l18 18M10.6 5.1A9.8 9.8 0 0 1 12 5c5 0 9 5 9 7 0 .9-.8 2.4-2.2 3.8M6.2 6.2C4.2 7.6 3 9.9 3 12c0 2 4 7 9 7 1.6 0 3.1-.4 4.4-1.1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
  const tips = [["Stay hydrated", "In UAE heat, aim for a glass of water every hour you're outdoors.", "اشرب الماء", "في حرارة الإمارات، اشرب كوب ماء كل ساعة تقضيها في الخارج."],
                ["Take a walk", "Ten minutes of walking after meals helps steady energy through the day.", "امشِ قليلاً", "عشر دقائق من المشي بعد الوجبات تساعد على ثبات طاقتك خلال اليوم."]];
  function show() {
    const tip = tips[new Date().getHours() % tips.length];
    cover.innerHTML = `<div class="tip"><b>${ar() ? tip[2] : tip[0]}</b>${ar() ? tip[3] : tip[1]}<br><button type="button">${ar() ? "متابعة" : "Continue"}</button></div>`;
    cover.querySelector("button").onclick = () => { cover.classList.remove("on"); document.title = saved; };
    cover.classList.add("on");
    if (window.speechSynthesis) speechSynthesis.cancel();
    saved = document.title; document.title = ar() ? "نصيحة اليوم" : "Daily tip";
  }
  let saved = document.title;
  btn.onclick = show;
  document.addEventListener("keydown", e => { if (e.key === "Escape") show(); });
  document.addEventListener("visibilitychange", () => document.body.classList.toggle("pblur", document.hidden));
  window.addEventListener("blur", () => document.body.classList.add("pblur"));
  window.addEventListener("focus", () => document.body.classList.remove("pblur"));
  const mount = () => { if (!document.body.dataset.noHide) { document.body.append(cover, btn); } };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", mount) : mount();
  window.hideScreen = show;
})();

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}


/* Voice notes: hold-free recording (tap to start, tap to send). Works on iOS Safari 14.3+, Android, desktop. */
const Notes = {
  supported: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder),
  attach(btn, uploadPath, onSent, labels) {
    if (!Notes.supported) { btn.disabled = true; btn.title = labels.unsupported; return; }
    let rec = null, t0 = 0, timer = null;
    btn.onclick = async () => {
      if (rec) { rec.stop(); return; }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const type = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm", "audio/ogg"].find(x => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(x)) || "";
        rec = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
        const chunks = [];
        rec.ondataavailable = e => e.data.size && chunks.push(e.data);
        rec.onstop = async () => {
          clearInterval(timer); stream.getTracks().forEach(x => x.stop());
          const secs = (Date.now() - t0) / 1000;
          const mime = (rec.mimeType || type || "audio/webm").split(";")[0];
          rec = null; btn.classList.remove("live"); btn.textContent = labels.record;
          if (secs < 0.8) return;
          const f = new FormData();
          f.append("file", new File([new Blob(chunks, { type: mime })], "note." + (mime.includes("mp4") ? "m4a" : mime.split("/")[1]), { type: mime }));
          f.append("seconds", secs.toFixed(1));
          await API.req("POST", uploadPath, f, true);
          onSent && onSent();
        };
        t0 = Date.now(); rec.start(); btn.classList.add("live");
        timer = setInterval(() => { const s = Math.round((Date.now() - t0) / 1000); btn.textContent = `${labels.stop} ${s}s`; if (s >= 120) rec && rec.stop(); }, 250);
      } catch { btn.textContent = labels.denied; }
    };
  },
  async play(path, el) {
    const r = await fetch(path, { headers: API.headers() });
    const a = document.createElement("audio");
    a.controls = true; a.src = URL.createObjectURL(await r.blob()); a.style.width = "100%";
    el.replaceWith(a); a.play().catch(() => {});
  },
  render(m, basePath, who) {
    return m.voice
      ? `<p><b>${who}</b> <button class="chip notebtn" data-src="${basePath}/${m.id}">▶ ${m.seconds ? Math.round(m.seconds) + "s" : ""}</button></p>`
      : `<p><b>${who}:</b> ${esc(m.body)}</p>`;
  },
  wire(container) { $$(".notebtn", container).forEach(b => b.onclick = () => Notes.play(b.dataset.src, b)); },
};
