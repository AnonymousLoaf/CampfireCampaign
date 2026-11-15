import { api } from "../api/client";

/** Push needs a secure context (HTTPS or localhost), a service worker and the Push API. */
export function pushSupported(): boolean {
  return typeof window !== "undefined" && window.isSecureContext && "serviceWorker" in navigator && "PushManager" in window;
}

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  const existing = await navigator.serviceWorker.getRegistration("/");
  if (existing) return existing;
  await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  return navigator.serviceWorker.ready;
}

/** Ask permission, subscribe this browser and send the subscription to the server. */
export async function enablePush(): Promise<void> {
  if (!pushSupported()) throw new Error("This browser can't receive push notifications here — it needs HTTPS (or localhost).");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Notifications were blocked. Allow them in the browser's site settings and try again.");
  const reg = await registration();
  const { public_key } = await api.pushKey();
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key) as BufferSource,
    });
  }
  await api.pushSubscribe(sub.toJSON());
}

/** Unsubscribe this browser (server and browser). */
export async function disablePush(): Promise<void> {
  if (!pushSupported()) return;
  const reg = await navigator.serviceWorker.getRegistration("/");
  const sub = await reg?.pushManager.getSubscription();
  if (sub) {
    try {
      await api.pushUnsubscribe(sub.endpoint);
    } finally {
      await sub.unsubscribe();
    }
  }
}

/** Is this browser currently subscribed? */
export async function pushSubscribed(): Promise<boolean> {
  if (!pushSupported()) return false;
  const reg = await navigator.serviceWorker.getRegistration("/");
  return !!(await reg?.pushManager.getSubscription());
}
