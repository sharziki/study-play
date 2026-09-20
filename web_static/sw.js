/* Intellect service worker.
 *
 * Strategy, chosen so a phone on bad campus Wi-Fi still opens instantly:
 *   - App shell (HTML, CSS, JS, fonts, KaTeX): cache-first, refreshed in the
 *     background. These change only on deploy.
 *   - GET API reads: network-first with a cache fallback, so a dropped
 *     connection shows the last known queue instead of an error page.
 *   - POST and every other mutation: never cached. Answers must reach SQLite,
 *     which owns mastery and scheduling. A stale write would corrupt progress.
 */

/* Bumped automatically by the build (see ui/scripts/stamp-sw.mjs).
 * Hand-editing this was a real source of "I shipped a fix and the phone kept
 * showing the old screen", twice in one session. */
const VERSION = "intellect-d0983a52c6b4";
const SHELL_CACHE = `${VERSION}-shell`;
const DATA_CACHE = `${VERSION}-data`;

const SHELL_ASSETS = [
  "/",
  "/index.html",
  "/index.css",
  // One bundle now. Vite emits a single entry, so a missing sibling module is
  // no longer a way to get a blank screen offline.
  "/app.js",
  "/manifest.webmanifest",
  "/vendor/katex/katex.min.css",
  "/vendor/katex/katex.min.js",
  "/vendor/katex/auto-render.min.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // Individual failures must not abort the install, or one missing font
      // permanently blocks the worker from taking over.
      .then((cache) => Promise.allSettled(SHELL_ASSETS.map((asset) => cache.add(asset))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => !key.startsWith(VERSION)).map((key) => caches.delete(key))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request));
    return;
  }

  event.respondWith(cacheFirst(request));
});

async function networkFirst(request) {
  const cache = await caches.open(DATA_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ error: "offline", offline: true }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  if (cached) {
    // Refresh in the background so the next launch is current.
    fetch(request)
      .then((response) => {
        if (response.ok) cache.put(request, response.clone());
      })
      .catch(() => {});
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const shell = await cache.match("/index.html");
    if (shell) return shell;
    throw error;
  }
}
