import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

const SAMPLE = '"Patrons don\'t descend," the steward says, and his smile never reaches his eyes. "Do mind the forty-third rung."';

/** "af_bella" → "Bella (American, female)" */
function label(v: string): string {
  const [code, name] = v.split("_");
  const accent = code[0] === "b" ? "British" : "American";
  const who = code[1] === "f" ? "female" : "male";
  return `${name.charAt(0).toUpperCase()}${name.slice(1)} (${accent}, ${who})`;
}

const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)];

/** Settings → Test voices: hear the character voices the host PC makes, and play with blend, speed and pitch. */
export default function VoiceTester() {
  const [voices, setVoices] = useState<string[] | null>(null);
  const [available, setAvailable] = useState(true);
  const [text, setText] = useState(SAMPLE);
  const [voice, setVoice] = useState("narrator");
  const [blend, setBlend] = useState("");
  const [weight, setWeight] = useState(0.3);
  const [speed, setSpeed] = useState(1);
  const [pitch, setPitch] = useState(0);
  const [fx, setFx] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    api
      .voices()
      .then((r) => {
        setVoices(r.voices);
        setAvailable(r.available);
      })
      .catch(() => setAvailable(false));
    return () => audio.current?.pause();
  }, []);

  const play = async (o?: { voice: string; blend: string; weight: number; speed: number; pitch: number; fx: string }) => {
    const p = o ?? { voice, blend, weight, speed, pitch, fx };
    setBusy(true);
    setErr(null);
    try {
      const blob = await api.testVoice({
        text: text.trim() || SAMPLE,
        voice: p.voice,
        blend: p.blend || null,
        blend_weight: p.weight,
        speed: p.speed,
        pitch: p.pitch,
        fx: p.fx || null,
      });
      audio.current?.pause();
      const a = new Audio(URL.createObjectURL(blob));
      audio.current = a;
      await a.play();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const surprise = async () => {
    if (!voices?.length) return;
    // a random recipe that fits the speaker in the line ("the steward says" → a man's voice), like a new NPC gets
    const r = await api.suggestVoice(text).catch(() => null);
    const v = r?.voice ?? pick(voices);
    const o = { voice: v, blend: r?.blend ?? "", weight: r?.blend_weight ?? 0.3, speed: r?.speed ?? 1, pitch: r?.pitch ?? 0, fx: r?.fx ?? "" };
    setVoice(o.voice);
    setBlend(o.blend);
    setWeight(o.weight);
    setSpeed(o.speed);
    setPitch(o.pitch);
    setFx(o.fx);
    void play(o);
  };

  return (
    <section className="panel voice-tester">
      <div className="panel-head">
        <h2>Test voices</h2>
      </div>
      {!available ? (
        <p className="muted small">Character voices aren&apos;t set up on this server, so games use each browser&apos;s own voice.</p>
      ) : (
        <>
          <p className="muted small">
            The voices the host PC reads narration with. Every NPC gets their own recipe like this (a voice, maybe a
            second one blended in, a speed and a pitch) and keeps it for the whole campaign. As in a game, words in
            &quot;quotes&quot; are spoken in the voice below and the rest by the narrator. For creatures, try Surprise me on
            a line like &quot;…,&quot; the dragon rumbles (or the goblin, the orc, the wraith).
          </p>
          <textarea rows={3} maxLength={300} value={text} onChange={(e) => setText(e.target.value)} />
          <div className="row gap wrap">
            <label className="field grow">
              <span className="label">Voice</span>
              <select value={voice} onChange={(e) => setVoice(e.target.value)}>
                <option value="narrator">Narrator (George, British)</option>
                {(voices ?? []).map((v) => (
                  <option key={v} value={v}>
                    {label(v)}
                  </option>
                ))}
              </select>
            </label>
            {voice !== "narrator" && (
              <label className="field grow">
                <span className="label">Blend in</span>
                <select value={blend} onChange={(e) => setBlend(e.target.value)}>
                  <option value="">Nothing</option>
                  {(voices ?? [])
                    .filter((v) => v !== voice)
                    .map((v) => (
                      <option key={v} value={v}>
                        {label(v)}
                      </option>
                    ))}
                </select>
              </label>
            )}
          </div>
          {voice !== "narrator" && blend && (
            <label className="field">
              <span className="label">Blend: {Math.round(weight * 100)}% of the second voice</span>
              <input type="range" min={0.05} max={0.9} step={0.05} value={weight} onChange={(e) => setWeight(Number(e.target.value))} />
            </label>
          )}
          <label className="field">
            <span className="label">Speed: {speed.toFixed(2)}×</span>
            <input type="range" min={0.6} max={1.5} step={0.02} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} />
          </label>
          <label className="field">
            <span className="label">
              Pitch: {pitch > 0 ? "+" : ""}
              {pitch} semitones
            </span>
            <input type="range" min={-6} max={6} step={0.5} value={pitch} onChange={(e) => setPitch(Number(e.target.value))} />
          </label>
          {voice !== "narrator" && (
            <label className="field">
              <span className="label">Texture</span>
              <select value={fx} onChange={(e) => setFx(e.target.value)}>
                <option value="">Clean</option>
                <option value="rasp">Gravelly (orcs, goblins, demons)</option>
                <option value="boom">Booming (dragons)</option>
                <option value="hollow">Hollow echo (undead)</option>
              </select>
            </label>
          )}
          <div className="row gap wrap">
            <button className="btn primary" disabled={busy} onClick={() => void play()}>
              {busy ? "Speaking…" : "▶ Play"}
            </button>
            <button className="btn ghost" disabled={busy || !voices?.length} onClick={() => void surprise()} title="A random recipe for whoever speaks in the line, like a new NPC gets">
              🎲 Surprise me
            </button>
            <button
              className="btn ghost small"
              onClick={() => {
                setVoice("narrator");
                setBlend("");
                setSpeed(1);
                setPitch(0);
                setFx("");
              }}
            >
              Reset
            </button>
          </div>
          {err && <div className="error-text small">{err}</div>}
        </>
      )}
    </section>
  );
}
