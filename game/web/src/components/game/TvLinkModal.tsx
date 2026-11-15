import { useState } from "react";
import { api } from "../../api/client";
import Modal from "../Modal";
import ErrorText from "../ErrorText";
import { useGame } from "./gameContext";

/** Turns a server URL (absolute, a path, or a hash) into something openable from this browser. */
function absolute(url: string): string {
  if (/^https?:\/\//.test(url)) return url;
  if (url.startsWith("#")) return `${window.location.origin}${window.location.pathname}${url}`;
  if (url.startsWith("/")) return `${window.location.origin}${url}`;
  return url;
}

export default function TvLinkModal({ onClose }: { onClose: () => void }) {
  const { view, gameId, refresh } = useGame();
  const [url, setUrl] = useState<string | null>(view.tv_url ? absolute(view.tv_url) : null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Creates/rotates the link. Opens a window synchronously first so popup blockers allow it. */
  const create = async (open: boolean) => {
    const win = open ? window.open("about:blank", "_blank") : null;
    setBusy(true);
    setError(null);
    try {
      const res = await api.tvLink(gameId);
      const u = absolute(res.url || `#/tv/${res.tv_token}`);
      setUrl(u);
      if (win) win.location.href = u;
      refresh();
    } catch (e) {
      win?.close();
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      window.prompt("Copy this link:", url);
    }
  };

  return (
    <Modal title="TV view" onClose={onClose}>
      <div className="stack">
        <p className="muted small">
          Open this link on a TV, tablet or laptop across the room. It shows the map, the party and the story in big text — no
          login needed, and it can't take any actions. Anyone with the link can watch, so rotate it if it gets shared.
        </p>
        {url ? (
          <>
            <div className="row gap">
              <input readOnly value={url} className="grow" onFocus={(e) => e.currentTarget.select()} />
              <button className="btn" onClick={() => void copy()}>
                {copied ? "Copied ✓" : "Copy"}
              </button>
            </div>
            <div className="row gap">
              <a className="btn primary" href={url} target="_blank" rel="noreferrer">
                Open TV view
              </a>
              <button className="btn ghost" disabled={busy} onClick={() => void create(false)}>
                Rotate link
              </button>
            </div>
          </>
        ) : (
          <button className="btn primary" disabled={busy} onClick={() => void create(true)}>
            {busy ? "Creating…" : "Create TV link and open it"}
          </button>
        )}
        <ErrorText error={error} />
      </div>
    </Modal>
  );
}
