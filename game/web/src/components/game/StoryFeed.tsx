import { useEffect, useRef } from "react";
import type { LogEntry } from "../../api/types";
import { D20Icon } from "../DiceRoller";
import { SpeakButton } from "../atmosphere/AudioControls";

/** **bold** and *italic* / _italic_ from the DM's prose, as React nodes (no HTML is ever injected). */
function inlineMarks(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|\*(?!\s)(.+?)\*|(?<![\w])_(?!\s)(.+?)_(?![\w])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1] !== undefined) out.push(<strong key={m.index}>{m[1]}</strong>);
    else out.push(<em key={m.index}>{m[2] ?? m[3]}</em>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Paragraphs({ text }: { text: string }) {
  const paras = text.split(/\n{2,}|\r\n\r\n/).map((p) => p.trim()).filter(Boolean);
  return (
    <>
      {paras.map((p, i) => (
        <p key={i}>
          {p.split("\n").map((line, j, arr) => (
            <span key={j}>
              {inlineMarks(line.replace(/^#{1,6}\s+/, ""))}
              {j < arr.length - 1 && <br />}
            </span>
          ))}
        </p>
      ))}
    </>
  );
}

type RollData = {
  roll?: { rolls?: number[]; natural?: number; total?: number; modifier?: number };
  dc?: number | null;
  // older entries kept the numbers at the top level
  rolls?: number[];
  total?: number;
  success?: boolean | null;
};

function RollChip({ e }: { e: LogEntry }) {
  const d = (e.data ?? {}) as RollData;
  const rolls = d.roll?.rolls ?? d.rolls;
  const total = d.roll?.total ?? d.total;
  const natural = d.roll?.natural ?? (rolls && rolls.length === 1 ? rolls[0] : undefined);
  const success = typeof d.success === "boolean" ? d.success : typeof d.dc === "number" && typeof total === "number" ? total >= d.dc : null;
  const tone = natural === 20 ? "crit" : natural === 1 ? "fumble" : "";
  return (
    <div className={`log-roll ${tone}`}>
      {typeof natural === "number" ? (
        <D20Icon value={natural} size={26} tone={tone} title={`Natural ${natural}`} />
      ) : (
        <span className="dice-icon">🎲</span>
      )}
      <span className="roll-text">
        {e.author && <strong>{e.author}: </strong>}
        {e.text}
      </span>
      {Array.isArray(rolls) && rolls.length > 1 && (
        <span className="dice-row inline">
          {rolls.map((r, i) => (
            <span key={i} className={`die small ${r === 20 ? "crit" : r === 1 ? "fumble" : ""} ${r === natural ? "kept" : "dropped"}`}>
              {r}
            </span>
          ))}
        </span>
      )}
      {typeof total === "number" && <span className="roll-total-inline">= {total}</span>}
      {success === true && <span className="badge green">success</span>}
      {success === false && <span className="badge red">fail</span>}
    </div>
  );
}

export function LogItem({ e, speak = true }: { e: LogEntry; speak?: boolean }) {
  switch (e.kind) {
    case "narration":
      return (
        <div className="log-narration">
          {speak && <SpeakButton id={String(e.id)} text={e.text} />}
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
  const firstLastId = useRef(lastId);

  useEffect(() => {
    const el = ref.current;
    if (el && stick.current) {
      programmatic.current = true;
      el.scrollTop = el.scrollHeight;
    }
    // New entries arriving while the reader is here and sitting at the bottom count as read: after they've
    // scrolled once, or as soon as anything new arrives while the page is on screen (they're playing live).
    const arrivedWhileHere = lastId !== firstLastId.current && document.visibilityState === "visible";
    if (el && onAtBottom && stick.current && (userScrolled.current || arrivedWhileHere)) onAtBottom();
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
