import { useEffect, useRef, useState } from "react";
import { getPrefs, prefersReducedMotion } from "../util/prefs";
import Dice3D from "./Dice3D";

export interface DiceShow {
  /** "attack" shows Hit/Miss instead of Success/Failure. */
  kind?: "check" | "attack";
  natural: number;
  total: number;
  modifier?: number;
  rolls?: number[];
  /** With advantage or disadvantage two d20s hit the table and one is kept. */
  advantage?: string;
  dc?: number | null;
  success?: boolean | null;
  label?: string;
  who?: string;
  color?: string;
}

const subs = new Set<(d: DiceShow) => void>();

/** Queue an animated d20 roll on every mounted DiceRoller. */
export function showDice(d: DiceShow): void {
  if (!getPrefs().dice) return;
  subs.forEach((s) => s(d));
}

/** A flat d20 face (the classic icosahedron silhouette) with a number. */
export function D20Icon({ value, size = 22, tone, title }: { value?: number | string; size?: number; tone?: "crit" | "fumble" | ""; title?: string }) {
  return (
    <svg className={`d20-icon ${tone ?? ""}`} width={size} height={size} viewBox="0 0 100 100" aria-hidden={title ? undefined : true} role={title ? "img" : undefined}>
      {title && <title>{title}</title>}
      <polygon className="d20-body" points="50,3 91,26 91,74 50,97 9,74 9,26" />
      <g className="d20-edges">
        <polygon points="50,22 77,67 23,67" />
        <path d="M50,3 L50,22 M91,26 L77,67 M91,74 L77,67 M50,97 L77,67 M50,97 L23,67 M9,74 L23,67 M9,26 L23,67 M9,26 L50,22 M91,26 L50,22" />
      </g>
      {value !== undefined && (
        <text x="50" y="55" className="d20-num" textAnchor="middle" dominantBaseline="middle" fontSize={String(value).length > 1 ? 26 : 30}>
          {value}
        </text>
      )}
    </svg>
  );
}

type Shown = DiceShow & { key: number };

/** The table size for the rolling die. */
function tableSize(variant: "game" | "tv"): { w: number; h: number } {
  if (variant === "tv") return { w: Math.min(760, window.innerWidth * 0.8), h: Math.min(400, window.innerHeight * 0.45) };
  return { w: Math.min(380, window.innerWidth - 56), h: 210 };
}

/** Overlay for everyone in the game: a d20 rolls across a felt table, lands on the real result, then the total
 * and verdict appear. Rolls queue up so a burst of them plays one after another. */
export default function DiceRoller({ variant = "game" }: { variant?: "game" | "tv" }) {
  const [cur, setCur] = useState<Shown | null>(null);
  const [phase, setPhase] = useState<"tumble" | "land">("tumble");
  const [reduced, setReduced] = useState(false);
  const q = useRef<Shown[]>([]);
  const n = useRef(0);
  const busy = useRef(false);

  const next = () => {
    const d = q.current.shift();
    if (!d) {
      busy.current = false;
      setCur(null);
      return;
    }
    busy.current = true;
    const r = prefersReducedMotion();
    setReduced(r);
    setCur(d);
    setPhase(r ? "land" : "tumble");
  };

  useEffect(() => {
    const on = (d: DiceShow) => {
      q.current.push({ ...d, key: ++n.current });
      if (q.current.length > 6) q.current.splice(0, q.current.length - 6); // don't fall far behind
      if (!busy.current) next();
    };
    subs.add(on);
    return () => {
      subs.delete(on);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // The die calls back when it lands; then hold the result a moment → next.
  useEffect(() => {
    if (!cur || phase !== "land") return;
    const hold = window.setTimeout(next, q.current.length ? 1400 : 2600);
    return () => window.clearTimeout(hold);
  }, [cur, phase]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!cur) return null;
  const landed = phase === "land";
  const finalTone = cur.natural === 20 ? "crit" : cur.natural === 1 ? "fumble" : "";
  const tone = landed ? finalTone : "";
  const verdict =
    cur.success == null ? null : cur.kind === "attack" ? (cur.success ? "Hit" : "Miss") : cur.success ? "Success" : "Failure";
  const mod = cur.modifier ?? cur.total - cur.natural;
  const size = tableSize(variant);
  const dieColor = cur.color && /^#[0-9a-f]{6}$/i.test(cur.color) ? cur.color : "#8b1e1e";
  const pair =
    cur.rolls && cur.rolls.length === 2 && (cur.advantage === "advantage" || cur.advantage === "disadvantage") ? cur.rolls : null;
  const kept = pair ? (pair[0] === cur.natural ? 0 : 1) : 0;
  const dieTone = (v: number) => (v === 20 ? "crit" : v === 1 ? "fumble" : "");

  return (
    <div className={`dice-overlay ${variant}`} aria-live="polite" onClick={() => next()} title="Click to skip">
      <div key={cur.key} className={`dice-stage ${phase} ${tone}`}>
        <div className={`dice-table ${pair ? "pair" : ""}`}>
          {pair ? (
            pair.map((v, i) => (
              <div key={i} className={`dice-slot ${landed && i !== kept ? "dropped" : ""}`}>
                <Dice3D
                  value={v}
                  color={dieColor}
                  tone={dieTone(v)}
                  width={size.w / 2}
                  height={size.h}
                  from={i === 0 ? "left" : "right"}
                  duration={i === 0 ? 1700 : 1900}
                  instant={reduced}
                  onLanded={i === 1 ? () => setPhase("land") : undefined}
                />
              </div>
            ))
          ) : (
            <Dice3D
              value={cur.natural}
              color={dieColor}
              tone={finalTone}
              width={size.w}
              height={size.h}
              instant={reduced}
              onLanded={() => setPhase("land")}
            />
          )}
        </div>
        <div className="dice-info">
          {(cur.who || cur.label) && (
            <div className="dice-label">
              {cur.color && <span className="char-dot" style={{ background: cur.color }} />}
              {cur.who && <strong>{cur.who}</strong>}
              {cur.who && cur.label ? " — " : ""}
              {cur.label}
            </div>
          )}
          {pair && (
            <div className="dice-adv small">
              {cur.advantage === "advantage" ? "Advantage" : "Disadvantage"} — two d20s
              {landed ? `: ${pair[0]} and ${pair[1]}, keeps the ${cur.advantage === "advantage" ? "higher" : "lower"} (${cur.natural})` : ", keep the " + (cur.advantage === "advantage" ? "higher" : "lower")}
            </div>
          )}
          <div className={`dice-total ${landed ? "shown" : ""}`}>
            {landed ? (
              <>
                {cur.natural}
                {mod !== 0 && <span className="dice-mod"> {mod > 0 ? `+ ${mod}` : `− ${-mod}`}</span>} = <strong>{cur.total}</strong>
                {cur.dc != null && <span className="dice-dc"> vs DC {cur.dc}</span>}
              </>
            ) : (
              <span className="muted">rolling…</span>
            )}
          </div>
          {landed && (
            <div className="dice-verdict-row">
              {cur.natural === 20 && <span className="dice-flag crit">Natural 20!</span>}
              {cur.natural === 1 && <span className="dice-flag fumble">Natural 1</span>}
              {verdict && <span className={`dice-verdict ${cur.success ? "ok" : "bad"}`}>{verdict}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
