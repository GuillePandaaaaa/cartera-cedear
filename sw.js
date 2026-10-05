// Red primero (para tener siempre precios frescos); si no hay conexión, usa lo guardado.
const CACHE = "cedear-v2";
const BASE = ["./", "index.html", "manifest.webmanifest", "data/mercado.json",
              "icons/icon-192.png", "icons/icon-512.png"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const mismoSitio = url.origin === location.origin;
  e.respondWith(
    fetch(req).then(res => {
      if (res.ok && (mismoSitio || url.hostname.endsWith("gstatic.com") || url.hostname.endsWith("googleapis.com"))) {
        const copia = res.clone();
        const clave = mismoSitio ? url.pathname : req;   // ignora ?t= al guardar
        caches.open(CACHE).then(c => c.put(clave, copia));
      }
      return res;
    }).catch(() => caches.match(mismoSitio ? url.pathname : req).then(r => r || caches.match(req)))
  );
});
