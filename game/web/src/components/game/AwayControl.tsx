import { useState } from "react";
import { api } from "../../api/client";
import { useGame } from "./gameContext";
import { awayLabel } from "./PartyPanel";

/** Far-future date sent for "until I'm back" (the contract only has a date or null). */
const UNTIL_BACK_YEARS = 10;

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** "I'm away" — the game stops waiting for me and the AI plays my character cautiously meanwhile. */
export default function AwayControl() {
  const { view, gameId, run } = useGame();
  const [open, setOpen] = useState(false);
  const [until, setUntil] = useState(() => toLocalInput(new Date(Date.now() + 3 * 24 * 3600 * 1000)));
  const meMember = view.members.find((m) => m.user_id === view.me.user_id);
  if (!meMember || meMember.role === "spectator" || !view.me.character_id || view.game.status !== "active") return null;
  const label = awayLabel(meMember.away_until);

  const save = (iso: string | null) =>
    void run(() => api.away(gameId, iso)).then((ok) => {
      if (ok) setOpen(false);
    });

  return (
    <div className="away-control">
      {label ? (
        <div className="away-on">
          <span className="cond away">✈ You're {label}</span>
          <button className="btn tiny" onClick={() => save(null)}>
            I'm back
          </button>
        </div>
      ) : (
        <button className="btn ghost tiny" onClick={() => setOpen(!open)} title="The game won't wait for you; the AI plays your character cautiously.">
          ✈ I'm away…
        </button>
      )}
      {open && !label && (
        <div className="away-pop">
          <p className="small muted">
            While you're away the game won't wait for you — the AI plays your character cautiously each round.
          </p>
          <label className="small">
            Away until
            <input type="datetime-local" value={until} min={toLocalInput(new Date())} onChange={(e) => setUntil(e.target.value)} />
          </label>
          <div className="row gap wrap">
            <button className="btn primary small" disabled={!until} onClick={() => save(new Date(until).toISOString())}>
              Set away
            </button>
            <button
              className="btn small"
              onClick={() => {
                const d = new Date();
                d.setFullYear(d.getFullYear() + UNTIL_BACK_YEARS);
                save(d.toISOString());
              }}
            >
              Until I'm back
            </button>
            <button className="btn ghost small" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
