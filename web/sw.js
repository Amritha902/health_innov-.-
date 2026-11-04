/* Caches the app shell so it opens instantly and offline. API responses (health data) are never cached. */
const SHELL = "riaya-shell-v3";
const FILES = ["/", "/index.html", "/chat.html", "/fabric.html", "/partner.html", "/css/app.css", "/js/common.js", "/js/i18n.js",
  "/js/app.js", "/js/chat.js", "/js/nlu.js", "/js/voice.js", "/manifest.webmanifest", "/icons/icon-192.png",
  "/fonts/ibm-plex-sans-latin-400-normal.woff2", "/fonts/ibm-plex-sans-arabic-arabic-400-normal.woff2", "/fonts/noto-kufi-arabic-arabic-500-normal.woff2"];
self.addEventListener("install", e => e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(SHELL).then(c => c.put(e.request, copy)); return r; })
    .catch(() => caches.match(e.request)));
});
