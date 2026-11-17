import { useEffect, useState } from "react";
import type { Me } from "../api/types";
import DiceRoller, { getDiceProblem, onDiceProblem, showDice } from "../components/DiceRoller";
import SettingsPanel from "../components/lobby/SettingsPanel";
import VoiceTester from "../components/VoiceTester";
import { navigate } from "../router";
import { usePrefs } from "../util/prefs";

const SIDES = [4, 6, 8, 10, 12, 20] as const;

/** Throw practice dice: pick a die and how many, see them roll. Nothing is saved or sent anywhere. */
function DiceTray({ me }: { me: Me }) {
  const [sides, setSides] = useState<(typeof SIDES)[number]>(20);
  const [count, setCount] = useState(1);
  const [prefs, setPrefs] = usePrefs();
  const [problem, setProblem] = useState(getDiceProblem());
  useEffect(() => onDiceProblem(setProblem), []);
  const roll = (dice: { sides: number; value: number }[], label: string) => {
    showDice({
      kind: "damage",
      dice,
      total: dice.reduce((a, d) => a + d.value, 0),
      modifier: 0,
      label,
      who: me.display_name,
      color: "#8b1e1e",
    });
  };
  const d = (s: number) => 1 + Math.floor(Math.random() * s);
  return (
    <section className="panel dice-tray">
      <div className="panel-head">
        <h2>Test dice</h2>
      </div>
      <p className="muted small">Throw some practice dice to see how they roll on this device. Nothing here counts in a game.</p>
      {problem && <div className="small error-text">The 3D dice can't run on this device: {problem}. Only the result is shown.</div>}
      {!prefs.dice && (
        <div className="small error-text">
          Dice animation is switched off below (Sound &amp; narration → Animated dice), so only the result shows.
        </div>
      )}
      <div className="field">
        <div className="label">Die</div>
        <div className="seg">
          {SIDES.map((s) => (
            <button key={s} type="button" className={s === sides ? "active" : ""} onClick={() => setSides(s)}>
              d{s}
            </button>
          ))}
        </div>
      </div>
      <div className="field">
        <div className="label">How many</div>
        <div className="row gap center">
          <button type="button" className="btn small" disabled={count <= 1} onClick={() => setCount((c) => Math.max(1, c - 1))} aria-label="Fewer">
            −
          </button>
          <strong className="dice-tray-count">{count}</strong>
          <button type="button" className="btn small" disabled={count >= 10} onClick={() => setCount((c) => Math.min(10, c + 1))} aria-label="More">
            ＋
          </button>
        </div>
      </div>
      <div className="row gap wrap">
        <button
          type="button"
          className="btn primary"
          onClick={() => roll(Array.from({ length: count }, () => ({ sides, value: d(sides) })), `${count}d${sides}`)}
        >
          🎲 Roll {count}d{sides}
        </button>
        <button type="button" className="btn ghost" onClick={() => roll(SIDES.map((s) => ({ sides: s, value: d(s) })), "One of each")}>
          Roll one of each
        </button>
      </div>
      <label className="toggle">
        <input type="checkbox" checked={prefs.diceMotion === "always"} onChange={(e) => setPrefs({ diceMotion: e.target.checked ? "always" : "auto" })} />
        <span>Roll the dice even when this device asks for reduced motion</span>
      </label>
      <div className="muted small">
        With reduced motion on (an accessibility setting in Windows, macOS, iOS or Android), the dice appear already landed
        instead of tumbling. Tick this to see them roll anyway.
      </div>
    </section>
  );
}

export default function SettingsScreen({ me, onMeChange, onLogout }: { me: Me; onMeChange: (m: Me) => void; onLogout: () => void }) {
  return (
    <div className="lobby">
      <header className="topbar">
        <div className="row gap center">
          <button className="icon-btn" title="Back" onClick={() => navigate({ name: "lobby" })}>
            ←
          </button>
          <div className="brand-inline">Settings</div>
        </div>
        <div className="topbar-right">
          <span className="muted signed-in">Signed in as {me.display_name}</span>
          <button className="btn ghost small" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="lobby-grid settings-grid">
        <div className="muted small settings-who">Signed in as {me.display_name}</div>
        <DiceTray me={me} />
        <VoiceTester />
        <SettingsPanel me={me} onMeChange={onMeChange} />
      </main>
      <DiceRoller />
    </div>
  );
}
