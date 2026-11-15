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

/** The whole story so far — narration and events, oldest at the top, with "Load older" paging. */
export default function StoryHistory() {
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
    <div className="story-history">
      {hasMore && (
        <div className="center-text">
          <button className="btn small" disabled={loading} onClick={() => void load(entries[entries.length - 1]?.id)}>
            {loading ? "Loading…" : "Load older"}
          </button>
        </div>
      )}
      {err && entries.length === 0 && <div className="error-text small">{err}</div>}
      {!loading && entries.length === 0 && !err && <div className="muted center-text">The story hasn't begun yet.</div>}
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
