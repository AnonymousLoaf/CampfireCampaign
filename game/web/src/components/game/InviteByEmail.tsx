import { useEffect, useState } from "react";
import { api } from "../../api/client";

/** "✉ Invite" button in the game header: emails a friend the invite code and a join link.
 *  Hidden when the server has no SMTP settings. */
export default function InviteByEmail({ gameId }: { gameId: string }) {
  const [available, setAvailable] = useState(false);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    let live = true;
    api
      .meta()
      .then((m) => live && setAvailable(!!m.email_available))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  if (!available) return null;

  const send = async () => {
    const to = email.trim();
    if (!to) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.inviteByEmail(gameId, to);
      setMsg({ ok: true, text: `Invite sent to ${to}.` });
      setEmail("");
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="live-toggle">
      <button className="btn ghost small" onClick={() => setOpen((v) => !v)} title="Email a friend the invite">
        ✉ Invite
      </button>
      {open && (
        <div className="popover invite-popover">
          <div className="small muted">We'll email them the invite code and a link to join.</div>
          <form
            className="row gap"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="friend@example.com"
              autoFocus
            />
            <button className="btn small primary" disabled={busy || !email.trim()}>
              {busy ? "Sending…" : "Send"}
            </button>
          </form>
          {msg && <div className={`small ${msg.ok ? "muted" : "error-text"}`}>{msg.text}</div>}
          <button className="btn ghost small" onClick={() => setOpen(false)}>
            Close
          </button>
        </div>
      )}
    </div>
  );
}
