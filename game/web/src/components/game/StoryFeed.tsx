import { useEffect, useRef } from "react";
import type { LogEntry } from "../../api/types";

export function Paragraphs({ text }: { text: string }) {
  const paras = text.split(/\n{2,}|\r\n\r\n/).map((p) => p.trim()).filter(Boolean);
  return (
    <>
      {paras.map((p, i) => (
        <p key={i}>
          {p.split("\n").map((line, j, arr) => (
            <span key={j}>
              {line}
              {j < arr.length - 1 && <br />}
            </span>
          ))}
        </p>
      ))}
    </>
  );
}

function RollChip({ e }: { e: LogEntry }) {
  const d = (e.data ?? {}) as { rolls?: number[]; total?: number; success?: boolean | null; modifier?: number };
  return (
    <div className="log-roll">
      <span className="dice-icon">🎲</span>
      <span className="roll-text">
        {e.author && <strong>{e.author}: </strong>}
        {e.text}
      </span>
      {Array.isArray(d.rolls) && d.rolls.length > 0 && (
        <span className="dice-row inline">
          {d.rolls.map((r, i) => (
            <span key={i} className={`die small ${r === 20 ? "crit" : r === 1 ? "fumble" : ""}`}>
              {r}
            </span>
          ))}
          {typeof d.total === "number" && <span className="roll-total-inline">= {d.total}</span>}
        </span>
      )}
      {d.success === true && <span className="badge green">success</span>}
      {d.success === false && <span className="badge red">fail</span>}
    </div>
  );
}

export function LogItem({ e }: { e: LogEntry }) {
  switch (e.kind) {
    case "narration":
      return (
        <div className="log-narration">
          <Paragraphs text={e.text} />
        </div>
      );
    case "npc":
      return (
        <div className="log-npc">
          {e.author && <div className="npc-name">{e.author}</div>}
          <blockquote>“{e.text.replace(/^["“]|["”]$/g, "")}”</blockquote>
        </div>
      );
    case "action":
      return (
        <div className="log-action">
          <span className="action-author">{e.author ?? "Someone"}</span> <span>{e.text}</span>
        </div>
      );
    case "roll":
      return <RollChip e={e} />;
    case "combat":
      return (
        <div className="log-combat">
          ⚔ {e.author && <strong>{e.author}: </strong>}
          {e.text}
        </div>
      );
    case "event":
      return <div className="log-event">✦ {e.text}</div>;
    default:
      return <div className="log-system">{e.text}</div>;
  }
}

export default function StoryFeed({ log, busy }: { log: LogEntry[]; busy: boolean }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const stick = useRef(true);
  const lastId = log.length ? log[log.length - 1].id : null;

  useEffect(() => {
    const el = ref.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [lastId, busy]);

  return (
    <div
      className="story-feed"
      ref={ref}
      onScroll={(e) => {
        const el = e.currentTarget;
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      }}
    >
      {log.length === 0 && <div className="muted center-text">The story hasn't begun yet.</div>}
      {log.map((e) => (
        <LogItem key={e.id} e={e} />
      ))}
      {busy && (
        <div className="log-writing">
          <span className="quill">✒</span> The DM is writing…
        </div>
      )}
    </div>
  );
}
