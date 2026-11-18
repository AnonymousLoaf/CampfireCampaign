import { useState } from "react";
import { api } from "../../api/client";
import type { JournalEntry } from "../../api/types";
import { useGame } from "./gameContext";

const SECTIONS: { kind: JournalEntry["kind"]; title: string; icon: string; empty: string }[] = [
  { kind: "clue", title: "Clues & leads", icon: "🔍", empty: "Nothing yet. The DM notes clues and leads here as you find them." },
  { kind: "place", title: "Places", icon: "📍", empty: "No notable places yet." },
  { kind: "moment", title: "Key moments", icon: "✦", empty: "The story's big moments will be written here." },
];

/** The party's journal: quests, what the DM wrote down for you, and your own notes. */
export default function Journal() {
  const { view, gameId, run } = useGame();
  const [draft, setDraft] = useState("");
  const [showDone, setShowDone] = useState(false);
  const journal = view.journal ?? [];
  const notes = view.party_notes ?? [];
  const active = view.quests.filter((q) => q.status === "active");
  const finished = view.quests.filter((q) => q.status !== "active");
  const spectator = view.me.role === "spectator";

  const add = async () => {
    const t = draft.trim();
    if (!t) return;
    if (await run(() => api.addNote(gameId, t))) setDraft("");
  };

  return (
    <div className="journal stack-tight">
      <section>
        <h4 className="journal-h">⚑ Quests</h4>
        {active.length === 0 && <div className="muted small">No active quests.</div>}
        {active.map((q) => (
          <div key={q.title} className="quest active">
            <div className="row-between">
              <strong>{q.title}</strong>
              {q.day ? <span className="muted tiny-text">since day {q.day}</span> : null}
            </div>
            {q.notes && <div className="small">{q.notes}</div>}
            <QuestLeads entries={journal.filter((e) => e.quest && e.quest.toLowerCase() === q.title.toLowerCase())} />
          </div>
        ))}
        {finished.length > 0 && (
          <button className="link-btn small" onClick={() => setShowDone((v) => !v)}>
            {showDone ? "Hide" : "Show"} finished quests ({finished.length}) {showDone ? "▴" : "▾"}
          </button>
        )}
        {showDone &&
          finished.map((q) => (
            <div key={q.title} className={`quest ${q.status}`}>
              <div className="row-between">
                <span>
                  <strong>{q.title}</strong>{" "}
                  <span className={`badge ${q.status === "done" ? "green" : "red"}`}>{q.status === "done" ? "completed" : "failed"}</span>
                </span>
                {q.ended_day ? <span className="muted tiny-text">day {q.ended_day}</span> : null}
              </div>
              {q.notes && <div className="small muted">{q.notes}</div>}
            </div>
          ))}
      </section>

      {SECTIONS.map((sec) => {
        const list = journal.filter((e) => e.kind === sec.kind);
        return (
          <section key={sec.kind}>
            <h4 className="journal-h">
              {sec.icon} {sec.title} {list.length > 0 && <span className="muted small">({list.length})</span>}
            </h4>
            {list.length === 0 ? (
              <div className="muted small">{sec.empty}</div>
            ) : (
              <ul className={`journal-list ${sec.kind}`}>
                {[...list].reverse().map((e) => (
                  <li key={e.id}>
                    <span className="journal-day">Day {e.day ?? "?"}</span>
                    <span>
                      {e.text}
                      {e.quest && <span className="muted tiny-text"> · {e.quest}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}

      <section>
        <h4 className="journal-h" title="Only the players see these. The DM never reads them.">
          ✎ Party notes <span className="muted small">(the DM can't see these)</span>
        </h4>
        {!spectator && (
          <div className="note-compose">
            <textarea
              rows={2}
              value={draft}
              maxLength={1000}
              placeholder="Theories, plans, things to remember…"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void add();
              }}
            />
            <button className="btn small" disabled={!draft.trim()} onClick={() => void add()}>
              Add note
            </button>
          </div>
        )}
        {notes.length === 0 && <div className="muted small">No notes yet.</div>}
        {[...notes].reverse().map((n) => (
          <div key={n.id} className="party-note">
            <div className="row-between">
              <span className="muted tiny-text">
                {n.author} · {new Date(n.ts).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              </span>
              {(n.user_id === view.me.user_id || view.me.is_host) && (
                <button className="chip-x" title="Remove note" onClick={() => void run(() => api.deleteNote(gameId, n.id))}>
                  ×
                </button>
              )}
            </div>
            <div className="small pre">{n.text}</div>
          </div>
        ))}
      </section>
    </div>
  );
}

function QuestLeads({ entries }: { entries: JournalEntry[] }) {
  if (!entries.length) return null;
  return (
    <ul className="journal-list quest-leads">
      {entries.map((e) => (
        <li key={e.id}>
          <span className="journal-day">Day {e.day ?? "?"}</span>
          <span>{e.text}</span>
        </li>
      ))}
    </ul>
  );
}
