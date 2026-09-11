const CACHE_NAME = "pocket-arcade-v3";

const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./2048/",
  "./2048/index.html",
  "./2048/css/style.css",
  "./2048/js/game.js",
  "./stack/",
  "./stack/index.html",
  "./stack/css/style.css",
  "./stack/js/game.js",
  "./sokoban/",
  "./sokoban/index.html",
  "./sokoban/css/style.css",
  "./sokoban/js/game.js",
  "./picross/",
  "./picross/index.html",
  "./picross/css/style.css",
  "./picross/js/game.js",
  "./fifteen/",
  "./fifteen/index.html",
  "./fifteen/css/style.css",
  "./fifteen/js/game.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
