import { useEffect, useRef, useState } from "react";
import { getPrefs, prefersReducedMotion } from "../util/prefs";
import type { DiceTable, DieSpec, Sides } from "../dice/physicsDice";

export interface DiceShow {
  /** "attack" shows Hit/Miss instead of Success/Failure; "damage" / "heal" are plain totals of any dice. */
  kind?: "check" | "attack" | "damage" | "heal";
  /** The d20 (checks and attacks). Ignored when `dice` is given. */
  natural?: number | null;
  total: number;
  modifier?: number;
  rolls?: number[];
  /** With advantage or disadvantage two d20s hit the table and one is kept. */
  advantage?: string;
  /** Any dice, e.g. 2d8 healing or a sword's 1d8 plus 2d6 sneak attack. */
  dice?: { sides: number; value: number }[];
  dc?: number | null;
  success?: boolean | null;
  label?: string;
  who?: string;
  color?: string;
}

const subs = new Set<(d: DiceShow) => void>();

/** Queue a roll: real 3D dice are thrown across the screen for everyone and land on the server's results. */
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
const SIDES: Sides[] = [4, 6, 8, 10, 12, 20];

/** The dice to throw for a roll: the d20 (two with advantage/disadvantage, one faded), or the given dice. */
function specsFor(d: DiceShow): DieSpec[] {
  const color = d.color && /^#[0-9a-f]{6}$/i.test(d.color) ? d.color : "#8b1e1e";
  if (d.dice?.length) {
    return d.dice
      .filter((x) => SIDES.includes(x.sides as Sides))
      .slice(0, 12)
      .map((x) => ({ sides: x.sides as Sides, value: x.value, color }));
  }
  if (typeof d.natural !== "number") return [];
  const glow = (v: number) => (v === 20 ? "crit" : v === 1 ? "fumble" : null);
  const pair = d.rolls && d.rolls.length === 2 && (d.advantage === "advantage" || d.advantage === "disadvantage") ? d.rolls : null;
  if (pair) {
    const kept = pair[0] === d.natural ? 0 : 1;
    return pair.map((v, i) => ({ sides: 20 as Sides, value: v, color, dropped: i !== kept, glow: i === kept ? glow(v) : null }));
  }
  return [{ sides: 20, value: d.natural, color, glow: glow(d.natural) }];
}

/** Everyone's dice: thrown from a random edge across the whole screen, with the result shown where they stop.
 * Rolls queue up so a burst of them plays one after another. Click the result to move on. */
export default function DiceRoller({ variant = "game" }: { variant?: "game" | "tv" }) {
  const host = useRef<HTMLDivElement>(null);
  const table = useRef<DiceTable | null>(null);
  const failed = useRef(false);
  const [cur, setCur] = useState<Shown | null>(null);
  const [landed, setLanded] = useState<{ x: number; y: number } | null>(null);
  const q = useRef<Shown[]>([]);
  const n = useRef(0);
  const busy = useRef(false);
  const hold = useRef<number>(0);

  const next = () => {
    window.clearTimeout(hold.current);
    const d = q.current.shift();
    if (!d) {
      busy.current = false;
      table.current?.clear();
      setCur(null);
      setLanded(null);
      return;
    }
    busy.current = true;
    setCur(d);
    setLanded(null);
  };

  useEffect(() => {
    const on = (d: DiceShow) => {
      q.current.push({ ...d, key: ++n.current });
      if (q.current.length > 6) q.current.splice(0, q.current.length - 6); // don't fall far behind
      if (!busy.current) next();
    };
    subs.add(on);
    if (new URLSearchParams(location.search).has("dicetest"))
      (window as unknown as { __showDice?: typeof showDice }).__showDice = showDice; // manual testing only
    const onResize = () => table.current?.resize();
    window.addEventListener("resize", onResize);
    return () => {
      subs.delete(on);
      window.removeEventListener("resize", onResize);
      window.clearTimeout(hold.current);
      table.current?.dispose();
      table.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Throw the dice for the current roll (the 3D code loads the first time it's needed).
  useEffect(() => {
    if (!cur) return;
    let alive = true;
    const specs = specsFor(cur);
    const finish = (at: { x: number; y: number }) => {
      if (!alive) return;
      setLanded(at);
      hold.current = window.setTimeout(next, q.current.length ? 1500 : 2800);
    };
    const centre = () => ({ x: (host.current?.clientWidth ?? 400) / 2, y: (host.current?.clientHeight ?? 400) / 2 });
    (async () => {
      if (!specs.length || failed.current || !host.current) return finish(centre());
      try {
        if (!table.current) {
          const mod = await import("../dice/physicsDice");
          if (!mod.webglAvailable()) throw new Error("no WebGL");
          if (!alive || !host.current) return;
          table.current = new mod.DiceTable(host.current);
        }
        table.current.resize();
        const still = prefersReducedMotion() && !new URLSearchParams(location.search).has("forcemotion");
        finish(await table.current.throw(specs, still));
      } catch {
        failed.current = true; // no WebGL here: just show the result
        finish(centre());
      }
    })();
    return () => {
      alive = false;
    };
  }, [cur?.key]); // eslint-disable-line react-hooks/exhaustive-deps

  const d = cur;
  const verdict = !d || d.success == null ? null : d.kind === "attack" ? (d.success ? "Hit" : "Miss") : d.success ? "Success" : "Failure";
  const dieSum = d?.dice?.length ? d.dice.reduce((a, x) => a + x.value, 0) : d?.natural ?? 0;
  const mod = d ? d.modifier ?? d.total - dieSum : 0;
  const pair = d && !d.dice?.length && d.rolls?.length === 2 && (d.advantage === "advantage" || d.advantage === "disadvantage");
  const W = host.current?.clientWidth ?? 0;
  const H = host.current?.clientHeight ?? 0;
  const pos = landed
    ? { left: Math.max(130, Math.min(W - 130, landed.x)), top: Math.max(60, Math.min(H - 150, landed.y + 70)) }
    : null;

  return (
    <div className={`dice-layer ${variant}`} ref={host} aria-live="polite">
      {d && landed && pos && (
        <div
          key={d.key}
          className={`dice-caption ${d.natural === 20 && !d.dice?.length ? "crit" : d.natural === 1 && !d.dice?.length ? "fumble" : ""}`}
          style={pos}
          onClick={() => next()}
          title="Click to continue"
        >
          {(d.who || d.label) && (
            <div className="dice-label">
              {d.color && <span className="char-dot" style={{ background: d.color }} />}
              {d.who && <strong>{d.who}</strong>}
              {d.who && d.label ? " — " : ""}
              {d.label}
            </div>
          )}
          {pair && (
            <div className="dice-adv small">
              {d.advantage === "advantage" ? "Advantage" : "Disadvantage"}: {d.rolls![0]} and {d.rolls![1]}, keeps the{" "}
              {d.advantage === "advantage" ? "higher" : "lower"}
            </div>
          )}
          <div className="dice-total">
            {d.dice?.length ? d.dice.map((x) => x.value).join(" + ") : d.natural}
            {mod !== 0 && <span className="dice-mod"> {mod > 0 ? `+ ${mod}` : `− ${-mod}`}</span>} = <strong>{d.total}</strong>
            {d.kind === "heal" && <span className="dice-mod"> healing</span>}
            {d.kind === "damage" && <span className="dice-mod"> damage</span>}
            {d.dc != null && <span className="dice-dc"> vs DC {d.dc}</span>}
          </div>
          {(verdict || (!d.dice?.length && (d.natural === 20 || d.natural === 1))) && (
            <div className="dice-verdict-row">
              {!d.dice?.length && d.natural === 20 && <span className="dice-flag crit">Natural 20!</span>}
              {!d.dice?.length && d.natural === 1 && <span className="dice-flag fumble">Natural 1</span>}
              {verdict && <span className={`dice-verdict ${d.success ? "ok" : "bad"}`}>{verdict}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
