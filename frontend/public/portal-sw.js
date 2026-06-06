// portal-sw.js
// Minimal service worker for PWA installability.
// Does not cache any content -- portal requires live authentication.
self.addEventListener('install', (event) => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim())
})

// No fetch handler -- all requests go to network as normal.
