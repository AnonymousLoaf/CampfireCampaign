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

export default function StoryFeed({
  log,
  busy,
  lastSeenId,
  onAtBottom,
  header,
}: {
  log: LogEntry[];
  busy: boolean;
  /** Entries after this id are "new since your last visit". */
  lastSeenId?: number | null;
  /** Called when the reader has scrolled to the newest entry. */
  onAtBottom?: () => void;
  header?: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const stick = useRef(true);
  const lastId = log.length ? log[log.length - 1].id : null;
  // Freeze the divider position for this visit so it doesn't jump when entries are marked read.
  const dividerAfter = useRef<number | null | undefined>(undefined);
  if (dividerAfter.current === undefined && lastSeenId !== undefined) dividerAfter.current = lastSeenId;
  const firstNewIdx =
    dividerAfter.current !== null && dividerAfter.current !== undefined
      ? log.findIndex((e) => Number(e.id) > Number(dividerAfter.current))
      : -1;

  // Our own scrolling (sticking to the newest entry) also fires scroll events; only the reader's scrolling counts as reading.
  const programmatic = useRef(false);
  const userScrolled = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (el && stick.current) {
      programmatic.current = true;
      el.scrollTop = el.scrollHeight;
    }
    // New entries arriving while the reader sits at the bottom (after they've scrolled once) count as read.
    if (el && onAtBottom && userScrolled.current && stick.current) onAtBottom();
  }, [lastId, busy]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      className="story-feed"
      ref={ref}
      onScroll={(e) => {
        const el = e.currentTarget;
        const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
        stick.current = gap < 80;
        if (programmatic.current) {
          programmatic.current = false;
          return;
        }
        userScrolled.current = true;
        if (gap < 40 && onAtBottom) onAtBottom();
      }}
    >
      {header}
      {log.length === 0 && <div className="muted center-text">The story hasn't begun yet.</div>}
      {log.map((e, i) => (
        <div key={e.id} className="log-wrap">
          {i === firstNewIdx && i > 0 && (
            <div className="new-divider" id="new-since-last-visit">
              New since your last visit
            </div>
          )}
          <LogItem e={e} />
        </div>
      ))}
      {busy && (
        <div className="log-writing">
          <span className="quill">✒</span> The DM is writing…
        </div>
      )}
    </div>
  );
}
