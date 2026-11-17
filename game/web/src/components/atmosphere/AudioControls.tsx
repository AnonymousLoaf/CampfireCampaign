import { useEffect, useState } from "react";
import { usePrefs } from "../../util/prefs";
import { disableSound, isUnlocked, onUnlockChange, play, soundSupported, unlock } from "../../util/sound";
import { canSpeak, speak, stopSpeaking, ttsSupported, useSpeakingId, useVoices } from "../../util/tts";

export function useSoundUnlocked(): boolean {
  const [on, setOn] = useState(isUnlocked());
  useEffect(() => onUnlockChange(setOn), []);
  return on;
}

/** Speaker button on a narration: read it aloud / stop. */
export function SpeakButton({ id, text, audio }: { id: string; text: string; audio?: string | null }) {
  const speaking = useSpeakingId();
  if (!audio && !ttsSupported()) return null;
  if (!canSpeak()) return null;
  const on = speaking === id;
  return (
    <button
      className={`speak-btn ${on ? "on" : ""}`}
      title={on ? "Stop reading" : "Read aloud"}
      aria-label={on ? "Stop reading" : "Read aloud"}
      onClick={(e) => {
        e.stopPropagation();
        if (on) stopSpeaking();
        else speak(id, text, audio);
      }}
    >
      {on ? "⏹" : "🔈"}
    </button>
  );
}

/** "🔊 Enable sound" until the player taps it; then a small speaker that opens the audio settings. */
export function SoundChip({ tv = false, compact = false }: { tv?: boolean; compact?: boolean }) {
  const unlocked = useSoundUnlocked();
  const [open, setOpen] = useState(false);
  const [prefs] = usePrefs();
  if (!soundSupported()) return null;
  if (!unlocked)
    return (
      <button className={`sound-chip ${tv ? "big" : ""}`} onClick={() => unlock()} title="Ambience and sound effects (synthesized in your browser)">
        {compact ? "🔈" : "🔊 Enable sound"}
      </button>
    );
  return (
    <span className="sound-pop-wrap">
      <button className={`sound-chip on ${tv ? "big" : ""}`} onClick={() => setOpen(!open)} title="Sound settings" aria-expanded={open}>
        {prefs.volume === 0 || (!prefs.ambience && !prefs.effects) ? "🔇" : "🔊"}
      </button>
      {open && (
        <div className="sound-pop" onClick={(e) => e.stopPropagation()}>
          <AudioSettings compact tv={tv} />
          <div className="row gap">
            <button className="btn tiny ghost" onClick={() => disableSound()}>
              Turn sound off
            </button>
            <button className="btn tiny" onClick={() => setOpen(false)}>
              Close
            </button>
          </div>
        </div>
      )}
    </span>
  );
}

/** Big "Read the story aloud" toggle for the TV view. */
export function AutoReadToggle({ tv = false, compact = false }: { tv?: boolean; compact?: boolean }) {
  const [prefs, set] = usePrefs();
  if (!ttsSupported()) return null;
  const on = tv ? prefs.tvAutoRead : prefs.autoRead;
  return (
    <button
      className={`autoread-toggle ${on ? "on" : ""} ${tv ? "big" : ""}`}
      onClick={() => {
        if (on) stopSpeaking();
        set(tv ? { tvAutoRead: !on } : { autoRead: !on });
        if (!isUnlocked()) unlock(); // the tap counts as the audio gesture too
      }}
      aria-pressed={on}
      title="Read new narration aloud as it arrives"
    >
      {compact ? "🗣" : on ? "🗣 Reading aloud" : "🗣 Read aloud: off"}
    </button>
  );
}

/** Per-device audio + narration settings. */
export function AudioSettings({ compact = false, tv = false }: { compact?: boolean; tv?: boolean }) {
  const [p, set] = usePrefs();
  const voices = useVoices();
  const unlocked = useSoundUnlocked();
  const tts = ttsSupported();
  return (
    <div className={`audio-settings ${compact ? "compact" : ""}`}>
      {soundSupported() && (
        <>
          <label className="row gap center">
            <span className="audio-label">Volume</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={p.volume}
              onChange={(e) => set({ volume: Number(e.target.value) })}
              onMouseUp={() => play("coins")}
              onTouchEnd={() => play("coins")}
              className="grow"
            />
            <span className="muted small">{Math.round(p.volume * 100)}%</span>
          </label>
          <div className="row gap wrap">
            <label className="toggle">
              <input type="checkbox" checked={p.ambience} onChange={(e) => set({ ambience: e.target.checked })} />
              <span>Ambience</span>
            </label>
            <label className="toggle">
              <input type="checkbox" checked={p.effects} onChange={(e) => set({ effects: e.target.checked })} />
              <span>Sound effects</span>
            </label>
            <label className="toggle">
              <input type="checkbox" checked={p.dice} onChange={(e) => set({ dice: e.target.checked })} />
              <span>Dice animation</span>
            </label>
            {!compact && !unlocked && (
              <button className="btn tiny" onClick={() => unlock()}>
                🔊 Enable sound on this device
              </button>
            )}
          </div>
        </>
      )}
      {tts ? (
        <>
          <label className="toggle">
            <input
              type="checkbox"
              checked={tv ? p.tvAutoRead : p.autoRead}
              onChange={(e) => {
                if (!e.target.checked) stopSpeaking();
                set(tv ? { tvAutoRead: e.target.checked } : { autoRead: e.target.checked });
              }}
            />
            <span>Auto-read new narration{tv ? " (TV)" : ""}</span>
          </label>
          <label className="row gap center">
            <span className="audio-label">Voice</span>
            <select className="grow" value={p.voice} onChange={(e) => set({ voice: e.target.value })}>
              <option value="">Browser default</option>
              {voices.map((v) => (
                <option key={v.voiceURI} value={v.voiceURI}>
                  {v.name} ({v.lang})
                </option>
              ))}
            </select>
          </label>
          <label className="row gap center">
            <span className="audio-label">Speed</span>
            <input type="range" min={0.6} max={1.6} step={0.05} value={p.rate} onChange={(e) => set({ rate: Number(e.target.value) })} className="grow" />
            <span className="muted small">{p.rate.toFixed(2)}×</span>
          </label>
          <div>
            <button className="btn tiny ghost" onClick={() => speak("voice-test", "The torchlight gutters as the door groans open. What do you do?")}>
              ▶ Test voice
            </button>
          </div>
        </>
      ) : (
        <div className="muted small">This browser can't read text aloud.</div>
      )}
      {!compact && <div className="muted small">These settings are saved on this device only.</div>}
    </div>
  );
}
