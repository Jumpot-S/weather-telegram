/* เก็บตัวแอปไว้ในเครื่อง เปิดได้แม้ออฟไลน์ (ข้อมูลอากาศล่าสุดเก็บใน localStorage ของตัวหน้าเว็บ) */
const V = "fafa-v1";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icons/icon-192.png", "./icons/icon-512.png", "./icons/icon.svg"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(V).then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => {})))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === location.origin;
  const font = url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com";
  if (!sameOrigin && !font) return; // ข้อมูลอากาศ/คุณภาพอากาศดึงสดเสมอ
  if (sameOrigin && url.pathname.includes("/data/")) return;
  e.respondWith(
    caches.open(V).then(async c => {
      const hit = await c.match(req, { ignoreSearch: true });
      const net = fetch(req).then(r => { if (r && (r.ok || r.type === "opaque")) c.put(req, r.clone()); return r }).catch(() => null);
      if (hit) { e.waitUntil(net); return hit }
      const r = await net;
      if (r) return r;
      if (req.mode === "navigate") return (await c.match("./index.html")) || Response.error();
      return Response.error();
    })
  );
});
