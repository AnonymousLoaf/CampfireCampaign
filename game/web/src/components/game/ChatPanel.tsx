import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { ChatMessage, GameView } from "../../api/types";
import { onChat } from "../../api/ws";

const MAX = 1000;

function timeLabel(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const t = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return sameDay ? t : `${d.toLocaleDateString([], { month: "short", day: "numeric" })}, ${t}`;
}

function upsert(list: ChatMessage[], m: ChatMessage): ChatMessage[] {
  const i = list.findIndex((x) => x.id === m.id);
  if (i >= 0) {
    const copy = list.slice();
    copy[i] = m;
    return copy;
  }
  return [...list, m].sort((a, b) => a.id - b.id);
}

/** Out-of-character table talk. Persists between sessions; the DM never reads it. */
export default function ChatPanel({ gameId, view, onSeen }: { gameId: string; view: GameView; onSeen: () => void }) {
  const [msgs, setMsgs] = useState<ChatMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [editing, setEditing] = useState<{ id: number; text: string } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const seenRef = useRef<number>(view.me.last_chat_seen_id ?? 0);
  // Where the "New" divider goes: what was read when the panel opened (doesn't move as you read).
  const firstUnreadRef = useRef<number>(view.me.last_chat_seen_id ?? 0);
  const myId = view.me.user_id;
  const spectator = view.me.role === "spectator";
  const isHost = view.me.is_host;

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  // First page.
  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .chat(gameId)
      .then((r) => {
        if (!alive) return;
        setMsgs(r.messages);
        setHasMore(r.has_more);
        setErr(null);
        requestAnimationFrame(scrollToBottom);
      })
      .catch((e) => alive && setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [gameId]);

  // Live messages, edits and deletions.
  useEffect(
    () =>
      onChat((m) => {
        setMsgs((list) => upsert(list, m));
        if (atBottom.current) requestAnimationFrame(scrollToBottom);
      }),
    [],
  );

  // Mark read while the newest messages are on screen.
  const markSeen = useCallback(() => {
    const newest = msgs.length ? msgs[msgs.length - 1].id : 0;
    if (!atBottom.current || newest <= seenRef.current) return;
    seenRef.current = newest;
    api
      .chatSeen(gameId, newest)
      .then(onSeen)
      .catch(() => {
        seenRef.current = 0;
      });
  }, [msgs, gameId, onSeen]);
  useEffect(() => {
    if (!document.hidden) markSeen();
  }, [markSeen]);
  useEffect(() => {
    const h = () => !document.hidden && markSeen();
    document.addEventListener("visibilitychange", h);
    return () => document.removeEventListener("visibilitychange", h);
  }, [markSeen]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    if (atBottom.current) markSeen();
  };

  const loadOlder = async () => {
    if (!msgs.length) return;
    const el = scrollRef.current;
    const prevHeight = el?.scrollHeight ?? 0;
    try {
      const r = await api.chat(gameId, msgs[0].id);
      setMsgs((list) => [...r.messages, ...list]);
      setHasMore(r.has_more);
      requestAnimationFrame(() => {
        if (el) el.scrollTop = el.scrollHeight - prevHeight;
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const send = async () => {
    const t = text.trim();
    if (!t || sending) return;
    setSending(true);
    try {
      const m = await api.chatPost(gameId, t);
      setMsgs((list) => upsert(list, m));
      setText("");
      setErr(null);
      atBottom.current = true;
      seenRef.current = Math.max(seenRef.current, m.id);
      requestAnimationFrame(scrollToBottom);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  };

  const saveEdit = async () => {
    if (!editing) return;
    try {
      const m = await api.chatEdit(gameId, editing.id, editing.text);
      setMsgs((list) => upsert(list, m));
      setEditing(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm("Delete this message for everyone?")) return;
    try {
      const m = await api.chatDelete(gameId, id);
      setMsgs((list) => upsert(list, m));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const firstUnread = firstUnreadRef.current;
  let dividerShown = false;

  return (
    <div className="chat-panel">
      <div className="chat-scroll" ref={scrollRef} onScroll={onScroll}>
        <div className="chat-note muted small">
          💬 Table talk: plan, joke, and say what you're up to. The DM can't see this.
        </div>
        {hasMore && (
          <button className="btn ghost small chat-older" onClick={() => void loadOlder()}>
            Load older messages
          </button>
        )}
        {loading && <div className="spinner" />}
        {!loading && msgs.length === 0 && <div className="muted small chat-empty">No messages yet. Say hello!</div>}
        {msgs.map((m, i) => {
          const prev = msgs[i - 1];
          const mine = m.user_id === myId;
          const grouped = prev && prev.user_id === m.user_id && !prev.deleted &&
            m.ts && prev.ts && new Date(m.ts).getTime() - new Date(prev.ts).getTime() < 5 * 60_000;
          const showDivider = !dividerShown && firstUnread > 0 && m.id > firstUnread && !mine;
          if (showDivider) dividerShown = true;
          return (
            <div key={m.id}>
              {showDivider && <div className="new-divider">New</div>}
              <div className={`chat-msg ${mine ? "mine" : ""} ${grouped ? "grouped" : ""}`}>
                {!grouped && (
                  <div className="chat-meta">
                    <strong>{m.author}</strong>
                    <span className="muted small">{timeLabel(m.ts)}</span>
                  </div>
                )}
                {editing?.id === m.id ? (
                  <div className="chat-edit">
                    <textarea
                      value={editing.text}
                      maxLength={MAX}
                      rows={2}
                      autoFocus
                      onChange={(e) => setEditing({ id: m.id, text: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          void saveEdit();
                        } else if (e.key === "Escape") setEditing(null);
                      }}
                    />
                    <div className="row gap">
                      <button className="btn small primary" onClick={() => void saveEdit()}>
                        Save
                      </button>
                      <button className="btn small ghost" onClick={() => setEditing(null)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : m.deleted ? (
                  <div className="chat-text muted small">
                    <em>message deleted</em>
                  </div>
                ) : (
                  <div className="chat-text">
                    {m.text}
                    {m.edited && <span className="muted small"> (edited)</span>}
                    {(mine || isHost) && (
                      <span className="chat-actions">
                        {mine && (
                          <button title="Edit" onClick={() => setEditing({ id: m.id, text: m.text })}>
                            ✎
                          </button>
                        )}
                        <button title="Delete" onClick={() => void remove(m.id)}>
                          🗑
                        </button>
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {err && (
        <div className="error-text small chat-err" onClick={() => setErr(null)}>
          {err}
        </div>
      )}
      {spectator ? (
        <div className="chat-compose muted small">Spectators can read the chat but not post.</div>
      ) : (
        <form
          className="chat-compose"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <textarea
            value={text}
            maxLength={MAX}
            rows={2}
            placeholder="Message the party…"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <div className="chat-compose-row">
            <span className="muted small">{text.length > MAX - 150 ? `${MAX - text.length} left` : "Enter to send · Shift+Enter for a new line"}</span>
            <button className="btn primary small" disabled={sending || !text.trim()}>
              Send
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
