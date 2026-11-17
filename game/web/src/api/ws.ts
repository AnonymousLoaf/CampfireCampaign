// Live-update socket: subscribe to a game id, "lobby", or a TV token; call onMessage when the server says something changed.
import type { ChatMessage } from "./types";

export type Msg =
  | { type: "update"; game_id?: string }
  | { type: "lobby" }
  | { type: "chat"; game_id: string; message: ChatMessage };

export type Topic = string | { tv: string };

export function subscribe(topic: Topic, onMessage: (m: Msg) => void): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let attempt = 0;
  let timer: number | undefined;

  const connect = () => {
    if (closed) return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${window.location.host}/api/ws`);
    ws.onopen = () => {
      attempt = 0;
      const msg = typeof topic === "string" ? { subscribe: topic } : { subscribe_tv: topic.tv };
      ws?.send(JSON.stringify(msg));
      // Something may have changed while we were (re)connecting.
      onMessage({ type: "update" });
    };
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data as string) as Msg;
        if (m && (m.type === "update" || m.type === "lobby" || (m.type === "chat" && m.message))) onMessage(m);
      } catch {
        /* ignore malformed */
      }
    };
    ws.onclose = () => {
      ws = null;
      if (closed) return;
      const delay = Math.min(15000, 500 * 2 ** attempt) + Math.random() * 300;
      attempt += 1;
      timer = window.setTimeout(connect, delay);
    };
    ws.onerror = () => {
      ws?.close();
    };
  };
  connect();

  return () => {
    closed = true;
    if (timer) window.clearTimeout(timer);
    ws?.close();
  };
}

/** Chat messages arrive over the game's socket; the open chat panel listens for them here. */
const CHAT_EVENT = "campfire:chat";

export function emitChat(m: ChatMessage): void {
  window.dispatchEvent(new CustomEvent<ChatMessage>(CHAT_EVENT, { detail: m }));
}

export function onChat(fn: (m: ChatMessage) => void): () => void {
  const h = (e: Event) => fn((e as CustomEvent<ChatMessage>).detail);
  window.addEventListener(CHAT_EVENT, h);
  return () => window.removeEventListener(CHAT_EVENT, h);
}
