import { useEffect, useRef, useState } from "react";
import { getPrefs, prefersReducedMotion } from "../util/prefs";

export interface DiceShow {
  natural: number;
  total: number;
  modifier?: number;
  rolls?: number[];
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

/** Overlay that tumbles a d20 for each queued roll, then shows the result (total, DC verdict). */
export default function DiceRoller({ variant = "game" }: { variant?: "game" | "tv" }) {
  const [cur, setCur] = useState<Shown | null>(null);
  const [phase, setPhase] = useState<"tumble" | "land">("tumble");
  const [face, setFace] = useState(1);
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
    const reduced = prefersReducedMotion();
    setCur(d);
    setPhase(reduced ? "land" : "tumble");
    setFace(reduced ? d.natural : 1 + Math.floor(Math.random() * 20));
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

  // Tumble → land → hold → next.
  useEffect(() => {
    if (!cur) return;
    if (phase === "tumble") {
      const spin = window.setInterval(() => setFace(1 + Math.floor(Math.random() * 20)), 70);
      const land = window.setTimeout(() => {
        window.clearInterval(spin);
        setFace(cur.natural);
        setPhase("land");
      }, 1000);
      return () => {
        window.clearInterval(spin);
        window.clearTimeout(land);
      };
    }
    const hold = window.setTimeout(next, q.current.length ? 1300 : 2200);
    return () => window.clearTimeout(hold);
  }, [cur, phase]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!cur) return null;
  const landed = phase === "land";
  const tone = landed ? (cur.natural === 20 ? "crit" : cur.natural === 1 ? "fumble" : "") : "";
  const verdict = cur.success === true ? "Success" : cur.success === false ? "Failure" : null;
  const mod = cur.modifier ?? cur.total - cur.natural;

  return (
    <div className={`dice-overlay ${variant}`} aria-live="polite" onClick={() => next()} title="Click to skip">
      <div key={cur.key} className={`dice-stage ${phase} ${tone}`}>
        <div className="dice-die">
          <D20Icon value={face} size={variant === "tv" ? 200 : 104} tone={tone as "crit" | "fumble" | ""} />
          {tone === "crit" && (
            <span className="dice-rays" aria-hidden>
              {Array.from({ length: 12 }).map((_, i) => (
                <i key={i} style={{ transform: `rotate(${i * 30}deg)` }} />
              ))}
            </span>
          )}
          {tone === "fumble" && (
            <svg className="dice-crack" viewBox="0 0 100 100" aria-hidden>
              <path d="M38,8 L46,30 L36,44 L52,58 L44,74 L56,94" />
              <path d="M52,58 L68,62 L74,76" />
            </svg>
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
