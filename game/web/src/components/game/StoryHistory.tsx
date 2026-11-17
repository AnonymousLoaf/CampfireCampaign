import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import type { LogEntry } from "../../api/types";
import { LogItem } from "./StoryFeed";
import { useGame } from "./gameContext";

const KINDS = "narration,event";

function dayKey(ts: string): string {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
}

/**
 * The story so far: a summary the DM keeps up to date (rewritten when there's new narration),
 * with the full word-for-word log one click away.
 */
export default function StoryHistory() {
  const { gameId, view } = useGame();
  const [summary, setSummary] = useState<{ text: string; updated_at: string | null; upto_id: number } | null>(null);
  const [writing, setWriting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showLog, setShowLog] = useState(false);

  const refresh = useCallback(async () => {
    setWriting(true);
    setErr(null);
    try {
      setSummary(await api.storySummary(gameId));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setWriting(false);
    }
  }, [gameId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // New narration since the summary was written → offer to bring it up to date.
  const newestNarration = [...view.log].reverse().find((l) => l.kind === "narration");
  const behind = !!summary && !!newestNarration && Number(newestNarration.id) > summary.upto_id;
  const paragraphs = (summary?.text ?? "").split(/\n\s*\n/).filter((p) => p.trim());

  return (
    <div className="story-history">
      <section className="story-summary">
        <div className="row-between">
          <h3>The story so far</h3>
          {behind && !writing && (
            <button className="btn tiny" onClick={() => void refresh()}>
              Bring it up to date
            </button>
          )}
        </div>
        {writing && !summary?.text && <div className="muted small">The DM is writing up the story so far…</div>}
        {err && <div className="error-text small">{err}</div>}
        {!writing && !err && summary && !summary.text && <div className="muted">The story hasn't begun yet.</div>}
        {paragraphs.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
        {summary?.updated_at && (
          <div className="muted tiny-text">
            {writing ? "Updating with the latest events…" : `Written by the DM · ${new Date(summary.updated_at).toLocaleString()}`}
          </div>
        )}
      </section>
      <div className="center-text">
        <button className="btn ghost small" onClick={() => setShowLog(!showLog)}>
          {showLog ? "Hide the full story log" : "Read the full story log"}
        </button>
      </div>
      {showLog && <FullLog />}
    </div>
  );
}

/** Every narration and event, oldest at the top, with "Load older" paging. */
function FullLog() {
  const { gameId, view } = useGame();
  const [entries, setEntries] = useState<LogEntry[]>([]); // newest first, as the server returns them
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(
    async (before?: number | string) => {
      setLoading(true);
      setErr(null);
      try {
        const r = await api.log(gameId, { before_id: before, limit: 50, kinds: KINDS });
        setEntries((prev) => (before === undefined ? r.entries : [...prev, ...r.entries]));
        setHasMore(r.has_more);
      } catch (e) {
        // Older servers have no /log endpoint: fall back to what the view already holds.
        setErr(e instanceof Error ? e.message : String(e));
        if (before === undefined) {
          setEntries([...view.log].filter((l) => l.kind === "narration" || l.kind === "event").reverse());
          setHasMore(false);
        }
      } finally {
        setLoading(false);
      }
    },
    [gameId], // eslint-disable-line react-hooks/exhaustive-deps
  );

  // Initial load, and refresh the newest page when new log entries arrive.
  const newest = view.log.length ? view.log[view.log.length - 1].id : null;
  useEffect(() => {
    void load();
  }, [load, newest]);

  const oldestFirst = [...entries].reverse();
  let lastDay = "";
  return (
    <div className="story-full-log">
      {hasMore && (
        <div className="center-text">
          <button className="btn small" disabled={loading} onClick={() => void load(entries[entries.length - 1]?.id)}>
            {loading ? "Loading…" : "Load older"}
          </button>
        </div>
      )}
      {err && entries.length === 0 && <div className="error-text small">{err}</div>}
      {oldestFirst.map((e) => {
        const d = dayKey(e.ts);
        const header = d && d !== lastDay ? d : null;
        lastDay = d || lastDay;
        return (
          <div key={e.id}>
            {header && <div className="day-divider">{header}</div>}
            <LogItem e={e} />
          </div>
        );
      })}
    </div>
  );
}
