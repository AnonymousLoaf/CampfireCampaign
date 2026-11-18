import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { GameSettings, Meta, SettingsPatch } from "../../api/types";
import Modal from "../Modal";
import ErrorText, { useAction } from "../ErrorText";
import { Field, INPUT, NARRATION, ROLLS, Seg, TIMEOUT, TimerPicker } from "../lobby/CreateGameModal";
import { useGame } from "./gameContext";
import { endCampaign } from "./Epilogue";

const KEYS: (keyof SettingsPatch)[] = [
  "round_timer_minutes",
  "combat_timer_minutes",
  "live_timer_minutes",
  "live",
  "input_mode",
  "speaker_id",
  "timeout_policy",
  "rolls",
  "narration_length",
  "dm_engine",
  "dm_model",
  "discord_webhook",
  "ai_art",
  "voices",
];

export default function HostSettingsModal({ onClose }: { onClose: () => void }) {
  const { view, gameId, refresh, run } = useGame();
  const orig = view.game.settings;
  const [s, setS] = useState<GameSettings>({ ...orig });
  const [meta, setMeta] = useState<Meta | null>(null);
  const set = <K extends keyof GameSettings>(k: K, v: GameSettings[K]) => setS((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  const changed: SettingsPatch = {};
  for (const k of KEYS) {
    const a = k === "discord_webhook" ? (s[k]?.trim() || null) : s[k];
    if (a !== orig[k]) (changed as Record<string, unknown>)[k] = a;
  }
  const dirty = Object.keys(changed).length > 0;

  const [save, saving, error] = useAction(async () => {
    await api.patchSettings(gameId, changed);
    refresh();
    onClose();
  });

  const engines: { value: GameSettings["dm_engine"]; label: string; ok: boolean }[] = [
    { value: "claude_code", label: "Claude Code (host PC)", ok: meta?.engines.claude_code ?? true },
    { value: "api_key", label: "My API key", ok: meta?.engines.api_key ?? true },
    { value: "offline", label: "Offline test DM", ok: true },
  ];

  return (
    <Modal
      title="Game settings"
      wide
      onClose={onClose}
      footer={
        <>
          <ErrorText error={error} />
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={!dirty || saving} onClick={() => void save()}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </>
      }
    >
      <div className="create-game">
        <p className="muted small">Pace and table settings can change at any time. New timers apply from the next phase.</p>
        <fieldset>
          <legend>AI art</legend>
          <label className="toggle">
            <input type="checkbox" checked={s.ai_art ?? true} onChange={(e) => set("ai_art", e.target.checked)} />
            <span>Paint scenes and monsters with my Grok (xAI) key</span>
          </label>
          <div className="muted small">
            Needs a Grok key in your Settings. About $0.02 a picture, at most 60 per game; pictures are reused when a scene or
            monster comes back.
          </div>
        </fieldset>
        <fieldset>
          <legend>Voices</legend>
          <label className="toggle">
            <input type="checkbox" checked={s.voices ?? true} onChange={(e) => set("voices", e.target.checked)} />
            <span>Read narration aloud in character voices (made on the host PC; free)</span>
          </label>
          <div className="muted small">Each player turns read-aloud on or off for themselves with the 🗣 button.</div>
        </fieldset>
        <fieldset>
          <legend>Live session</legend>
          <label className="toggle">
            <input type="checkbox" checked={s.live} onChange={(e) => set("live", e.target.checked)} />
            <span>Live session on — everyone's at the table, rounds use the live timer</span>
          </label>
          <Field label={`Live timer: ${s.live_timer_minutes} min`}>
            <input type="range" min={1} max={60} value={s.live_timer_minutes} onChange={(e) => set("live_timer_minutes", Number(e.target.value))} />
          </Field>
        </fieldset>
        <fieldset>
          <legend>Pace</legend>
          <Field label="Round timer">
            <TimerPicker minutes={s.round_timer_minutes} onChange={(m) => set("round_timer_minutes", m ?? 1440)} />
          </Field>
          <Field label="Combat timer">
            <TimerPicker minutes={s.combat_timer_minutes} onChange={(m) => set("combat_timer_minutes", m)} allowSame />
          </Field>
          <Field label="When someone misses the deadline">
            <Seg options={TIMEOUT} value={s.timeout_policy} onChange={(v) => set("timeout_policy", v)} />
          </Field>
        </fieldset>
        <fieldset>
          <legend>Table</legend>
          <Field label="Who acts">
            <Seg options={INPUT} value={s.input_mode} onChange={(v) => set("input_mode", v)} />
          </Field>
          {s.input_mode === "single" && (
            <Field label="Table speaker">
              <select value={s.speaker_id ?? ""} onChange={(e) => set("speaker_id", e.target.value || null)}>
                <option value="">Host</option>
                {view.members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.display_name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Field label="Who rolls">
            <Seg options={ROLLS} value={s.rolls} onChange={(v) => set("rolls", v)} />
          </Field>
          <Field label="Combat">
            <div className="muted small">Fights go in initiative order, one character at a time. On your turn you type what you do; the DM moves tokens and asks for your rolls.</div>
          </Field>
          <Field label="Narration length">
            <Seg options={NARRATION} value={s.narration_length} onChange={(v) => set("narration_length", v)} />
          </Field>
        </fieldset>
        <fieldset>
          <legend>Dungeon Master</legend>
          <div className="seg">
            {engines.map((e) => (
              <button key={e.value} type="button" disabled={!e.ok} className={s.dm_engine === e.value ? "active" : ""} onClick={() => set("dm_engine", e.value)}>
                {e.label}
              </button>
            ))}
          </div>
          {s.dm_engine !== "offline" && (meta?.models.length ?? 0) > 0 && (
            <Field label="Model">
              <select value={s.dm_model} onChange={(e) => set("dm_model", e.target.value)}>
                {meta!.models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Field label="Discord webhook">
            <input value={s.discord_webhook ?? ""} onChange={(e) => set("discord_webhook", e.target.value)} placeholder="https://discord.com/api/webhooks/…" />
          </Field>
        </fieldset>
        {view.game.status === "active" && (
          <fieldset>
            <legend>End the campaign</legend>
            <div className="muted small">
              When the story is over, the DM writes an epilogue: what became of the world and of each hero, with everyone's stats and
              awards. After that the game is finished and can't be played on.
              {view.story_complete ? " The DM says the main story has reached its end." : ""}
            </div>
            <button
              className="btn danger small"
              disabled={!!view.encounter || view.epilogue?.status === "writing"}
              title={view.encounter ? "Finish the fight first" : ""}
              onClick={() => void endCampaign(gameId, run).then((ok) => ok && onClose())}
            >
              End campaign &amp; write the epilogue
            </button>
          </fieldset>
        )}
      </div>
    </Modal>
  );
}
