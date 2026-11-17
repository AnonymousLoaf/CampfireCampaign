/* Campfire Campaign service worker: shows push notifications and opens the game when one is clicked. */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "Campfire Campaign", body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "Campfire Campaign";
  const options = {
    body: data.body || "",
    icon: "/favicon.svg",
    badge: "/favicon.svg",
    tag: data.url || "dnd",
    renotify: true,
    data: { url: data.url || "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin).href;
  event.waitUntil(
    (async () => {
      const all = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      // Prefer a tab already showing this game; otherwise any tab of the app; otherwise open a new one.
      const exact = all.find((c) => c.url === target);
      const any = exact || all.find((c) => new URL(c.url).origin === self.location.origin);
      if (any) {
        await any.focus();
        if (!exact && "navigate" in any) {
          try {
            await any.navigate(target);
          } catch (e) {
            /* cross-origin or not allowed — ignore */
          }
        }
        return;
      }
      await self.clients.openWindow(target);
    })(),
  );
});
