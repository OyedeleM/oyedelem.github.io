/* Starter page service worker: offline-first app shell, network-first weather. */
const VERSION = 'v1';
const SHELL_CACHE = `shell-${VERSION}`;
const WX_CACHE = `weather-${VERSION}`;
const SHELL_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-192.png',
  './icon-maskable-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(SHELL_CACHE).then(c => c.addAll(SHELL_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== SHELL_CACHE && k !== WX_CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // app shell: cache-first (install-time assets only)
  if (e.request.method === 'GET' && url.origin === self.location.origin) {
    e.respondWith(
      caches.match(e.request, { ignoreSearch: true }).then(hit =>
        hit || fetch(e.request).then(res => {
          const copy = res.clone();
          caches.open(SHELL_CACHE).then(c => c.put(e.request, copy));
          return res;
        })
      )
    );
    return;
  }

  // weather APIs: network-first, fall back to last good response offline
  const isWeather = /open-meteo\.com|bigdatacloud\.net/.test(url.hostname);
  if (isWeather) {
    e.respondWith(
      fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(WX_CACHE).then(c => c.put(e.request, copy));
        return res;
      }).catch(() => caches.match(e.request))
    );
  }
  // everything else (favicons, fonts): network with opportunistic cache
  else if (e.request.method === 'GET') {
    e.respondWith(
      caches.match(e.request).then(hit =>
        hit || fetch(e.request).then(res => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(WX_CACHE).then(c => c.put(e.request, copy));
          }
          return res;
        }).catch(() => hit)
      )
    );
  }
});
