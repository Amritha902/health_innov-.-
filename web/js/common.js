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

function quickExit() {
  // leaves no trace on screen; history entry replaced so "back" does not return here
  document.body.innerHTML = "";
  location.replace("https://www.google.com/search?q=weather+abu+dhabi");
}
