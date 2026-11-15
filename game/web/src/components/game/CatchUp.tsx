import { useState } from "react";
import { api } from "../../api/client";
import { useGame } from "./gameContext";
import { Paragraphs } from "./StoryFeed";
import { useAction } from "../ErrorText";

/** "Since you were last here" — shown at the top of the feed when there are unread entries. */
export default function CatchUp({ onMarkRead }: { onMarkRead: () => void }) {
  const { view, gameId } = useGame();
  const [recap, setRecap] = useState<string | null>(null);
  const [getRecap, busy, err] = useAction(async () => {
    const r = await api.recap(gameId);
    setRecap(r.text);
  });
  const unseen = view.me.unseen_count ?? 0;
  if (unseen <= 0 && !recap) return null;

  return (
    <div className="catch-up">
      <div className="row-between">
        <strong>✦ Since you were last here</strong>
        {unseen > 0 && <span className="badge gold">{unseen} new</span>}
      </div>
      {recap ? (
        <div className="catch-up-recap">
          <Paragraphs text={recap} />
        </div>
      ) : (
        <p className="small muted">
          {unseen} new entr{unseen === 1 ? "y" : "ies"} in the story. Scroll down to read them, or let the DM sum them up.
        </p>
      )}
      {err && <div className="error-text small">{err}</div>}
      <div className="row gap wrap">
        {!recap && (
          <button className="btn small primary" disabled={busy} onClick={() => void getRecap()}>
            {busy ? "Summarising…" : "Catch me up"}
          </button>
        )}
        {unseen > 0 && (
          <button
            className="btn small"
            onClick={() => document.getElementById("new-since-last-visit")?.scrollIntoView({ behavior: "smooth", block: "start" })}
          >
            Jump to new
          </button>
        )}
        <button
          className="btn small ghost"
          onClick={() => {
            setRecap(null);
            onMarkRead();
          }}
        >
          Mark as read
        </button>
      </div>
    </div>
  );
}
