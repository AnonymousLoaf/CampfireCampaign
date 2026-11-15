import { useState, type ReactNode } from "react";
import { api } from "../../api/client";
import { DEFAULT_SETTINGS, type CharacterView, type GameSettings, type Meta } from "../../api/types";
import Modal from "../Modal";
import ErrorText, { useAction } from "../ErrorText";
import CharacterPicker from "./CharacterPicker";

type Opt<T extends string> = { value: T; label: string; hint?: string };

const STORY: Opt<GameSettings["story_type"]>[] = [
  { value: "sandbox", label: "Open sandbox" },
  { value: "dungeon_crawl", label: "Dungeon crawl" },
  { value: "mystery", label: "Mystery" },
  { value: "heist", label: "Heist" },
  { value: "war", label: "War" },
  { value: "horror", label: "Horror" },
  { value: "wilderness", label: "Wilderness survival" },
  { value: "intrigue", label: "Political intrigue" },
  { value: "seafaring", label: "Seafaring" },
];
const TONE: Opt<GameSettings["tone"]>[] = [
  { value: "heroic", label: "Heroic" },
  { value: "gritty", label: "Gritty" },
  { value: "dark", label: "Dark" },
  { value: "lighthearted", label: "Lighthearted" },
];
const LENGTH: Opt<GameSettings["length"]>[] = [
  { value: "one_shot", label: "One-shot" },
  { value: "short", label: "Short campaign" },
  { value: "open", label: "Open-ended" },
];
const DIFFICULTY: Opt<GameSettings["difficulty"]>[] = [
  { value: "story", label: "Story", hint: "Gentle fights, plenty of healing" },
  { value: "normal", label: "Normal" },
  { value: "hard", label: "Hard" },
  { value: "deadly", label: "Deadly", hint: "Smart monsters, little mercy" },
];
const DEATH: Opt<GameSettings["death_rule"]>[] = [
  { value: "heroic", label: "Heroic", hint: "Knocked out, never killed" },
  { value: "standard", label: "Standard death saves" },
  { value: "permadeath", label: "Permadeath" },
];
const REST: Opt<GameSettings["rest_rule"]>[] = [
  { value: "standard", label: "Standard" },
  { value: "gritty", label: "Gritty" },
  { value: "epic", label: "Epic" },
];
const LEVELING: Opt<GameSettings["leveling"]>[] = [
  { value: "xp", label: "XP" },
  { value: "milestone", label: "Milestone" },
];
const MAGIC: Opt<GameSettings["magic_level"]>[] = [
  { value: "low", label: "Low" },
  { value: "standard", label: "Standard" },
  { value: "high", label: "High" },
];
const ECONOMY: Opt<GameSettings["economy"]>[] = [
  { value: "scarce", label: "Scarce" },
  { value: "standard", label: "Standard" },
  { value: "rich", label: "Rich" },
];
export const ROLLS: Opt<GameSettings["rolls"]>[] = [
  { value: "players", label: "Players roll on the site" },
  { value: "auto", label: "Automatic" },
];
export const COMBAT: Opt<GameSettings["combat_mode"]>[] = [
  { value: "side", label: "Side initiative", hint: "Party acts together, then monsters — best for async" },
  { value: "classic", label: "Classic initiative", hint: "One turn at a time — best for live play" },
];
export const NARRATION: Opt<GameSettings["narration_length"]>[] = [
  { value: "short", label: "Short" },
  { value: "medium", label: "Medium" },
  { value: "long", label: "Long" },
];
export const INPUT: Opt<GameSettings["input_mode"]>[] = [
  { value: "individual", label: "Each player", hint: "Everyone submits their own actions" },
  { value: "single", label: "One table speaker", hint: "One person types and acts for the whole party — great at a shared table" },
];
export const TIMEOUT: Opt<GameSettings["timeout_policy"]>[] = [
  { value: "ai", label: "AI plays them", hint: "A cautious, in-character action" },
  { value: "skip", label: "Skip their turn" },
  { value: "pause", label: "Pause the game" },
];

export const TIMER_PRESETS = [
  { label: "Live", minutes: 5, hint: "5 min" },
  { label: "Quick", minutes: 60, hint: "1 hour" },
  { label: "Daily", minutes: 1440, hint: "24 hours" },
  { label: "Relaxed", minutes: 4320, hint: "3 days" },
];

export function Seg<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Opt<T>[];
  value: T;
  onChange: (v: T) => void;
}) {
  const hint = options.find((o) => o.value === value)?.hint;
  return (
    <div>
      <div className="seg">
        {options.map((o) => (
          <button key={o.value} type="button" className={o.value === value ? "active" : ""} onClick={() => onChange(o.value)}>
            {o.label}
          </button>
        ))}
      </div>
      {hint && <div className="muted small hint">{hint}</div>}
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="field">
      <div className="label">{label}</div>
      {children}
    </div>
  );
}

export function TimerPicker({
  minutes,
  onChange,
  allowSame,
}: {
  minutes: number | null;
  onChange: (m: number | null) => void;
  allowSame?: boolean;
}) {
  const preset = TIMER_PRESETS.find((p) => p.minutes === minutes);
  const [custom, setCustom] = useState(minutes !== null && !preset);
  const unit = minutes !== null && minutes % 1440 === 0 ? "days" : minutes !== null && minutes % 60 === 0 ? "hours" : "minutes";
  const [customUnit, setCustomUnit] = useState<"minutes" | "hours" | "days">(unit);
  const factor = customUnit === "days" ? 1440 : customUnit === "hours" ? 60 : 1;
  return (
    <div>
      <div className="seg">
        {allowSame && (
          <button
            type="button"
            className={minutes === null ? "active" : ""}
            onClick={() => {
              setCustom(false);
              onChange(null);
            }}
          >
            Same as round
          </button>
        )}
        {TIMER_PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            className={!custom && minutes === p.minutes ? "active" : ""}
            onClick={() => {
              setCustom(false);
              onChange(p.minutes);
            }}
            title={p.hint}
          >
            {p.label} <span className="muted small">{p.hint}</span>
          </button>
        ))}
        <button type="button" className={custom ? "active" : ""} onClick={() => setCustom(true)}>
          Custom
        </button>
      </div>
      {custom && (
        <div className="row gap center hint">
          <input
            type="number"
            min={1}
            className="num"
            value={minutes === null ? "" : Math.max(1, Math.round(minutes / factor))}
            onChange={(e) => {
              const v = Math.max(1, Number(e.target.value) || 1);
              onChange(Math.min(7200, Math.max(5, v * factor)));
            }}
          />
          <select
            value={customUnit}
            onChange={(e) => {
              const u = e.target.value as "minutes" | "hours" | "days";
              setCustomUnit(u);
              const f = u === "days" ? 1440 : u === "hours" ? 60 : 1;
              const cur = minutes ?? 60;
              onChange(Math.min(7200, Math.max(5, Math.max(1, Math.round(cur / factor)) * f)));
            }}
          >
            <option value="minutes">minutes</option>
            <option value="hours">hours</option>
            <option value="days">days</option>
          </select>
          <span className="muted small">5 minutes to 5 days</span>
        </div>
      )}
    </div>
  );
}

export default function CreateGameModal({
  meta,
  characters,
  onClose,
  onCreated,
}: {
  meta: Meta;
  characters: CharacterView[];
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const [name, setName] = useState("");
  const [s, setS] = useState<GameSettings>({
    ...DEFAULT_SETTINGS,
    dm_engine: meta.engines.api_key ? "api_key" : meta.engines.claude_code ? "claude_code" : "offline",
    dm_model: meta.models[0]?.id ?? DEFAULT_SETTINGS.dm_model,
  });
  const [charId, setCharId] = useState(characters.find((c) => (c.ruleset ?? "2014") === "2014")?.id ?? "");
  const set = <K extends keyof GameSettings>(k: K, v: GameSettings[K]) => setS((prev) => ({ ...prev, [k]: v }));

  const [create, busy, error] = useAction(async () => {
    const res = await api.createGame(name.trim() || "Untitled campaign", { ...s, discord_webhook: s.discord_webhook?.trim() || null }, charId);
    onCreated(res.id);
  });

  const engines: { value: GameSettings["dm_engine"]; label: string; hint: string; available: boolean }[] = [
    { value: "claude_code", label: "Claude Code (this PC)", hint: "Uses the host PC's Claude Code login", available: meta.engines.claude_code },
    { value: "api_key", label: "My API key", hint: "Uses the Claude API key saved in your settings", available: meta.engines.api_key },
    { value: "offline", label: "Offline test DM", hint: "No AI — canned narration for trying the game out", available: meta.engines.offline },
  ];

  return (
    <Modal
      title="New game"
      wide
      onClose={onClose}
      footer={
        <>
          <ErrorText error={error} />
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={busy || !charId} onClick={() => void create()}>
            {busy ? "Creating…" : "Create game"}
          </button>
        </>
      }
    >
      <div className="create-game">
        <div className="field">
          <div className="label">Campaign name</div>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="The Ashen Crown" autoFocus />
        </div>

        <fieldset>
          <legend>Story</legend>
          <Field label="Story type">
            <Seg options={STORY} value={s.story_type} onChange={(v) => set("story_type", v)} />
          </Field>
          <Field label="Tone">
            <Seg options={TONE} value={s.tone} onChange={(v) => set("tone", v)} />
          </Field>
          <Field label="Length">
            <Seg options={LENGTH} value={s.length} onChange={(v) => set("length", v)} />
          </Field>
        </fieldset>

        <fieldset>
          <legend>Challenge</legend>
          <Field label="Difficulty">
            <Seg options={DIFFICULTY} value={s.difficulty} onChange={(v) => set("difficulty", v)} />
          </Field>
          <Field label="Death">
            <Seg options={DEATH} value={s.death_rule} onChange={(v) => set("death_rule", v)} />
          </Field>
          <Field label="Rest rules">
            <Seg options={REST} value={s.rest_rule} onChange={(v) => set("rest_rule", v)} />
          </Field>
        </fieldset>

        <fieldset>
          <legend>Party</legend>
          <div className="row gap wrap">
            <Field label="Max players">
              <input type="number" className="num" min={1} max={6} value={s.max_players} onChange={(e) => set("max_players", Math.min(6, Math.max(1, Number(e.target.value) || 1)))} />
            </Field>
            <Field label="Starting level">
              <select value={s.starting_level} onChange={(e) => set("starting_level", Number(e.target.value))}>
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((l) => (
                  <option key={l} value={l}>
                    Level {l}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Leveling">
              <Seg options={LEVELING} value={s.leveling} onChange={(v) => set("leveling", v)} />
            </Field>
          </div>
        </fieldset>

        <fieldset>
          <legend>World</legend>
          <div className="row gap wrap">
            <Field label="Magic level">
              <Seg options={MAGIC} value={s.magic_level} onChange={(v) => set("magic_level", v)} />
            </Field>
            <Field label="Economy">
              <Seg options={ECONOMY} value={s.economy} onChange={(v) => set("economy", v)} />
            </Field>
            <Field label={`Sell price: ${Math.round(s.sell_rate * 100)}% of value`}>
              <input type="range" min={10} max={100} step={5} value={Math.round(s.sell_rate * 100)} onChange={(e) => set("sell_rate", Number(e.target.value) / 100)} />
            </Field>
            <Field label="Ruleset">
              <Seg
                options={[
                  { value: "2014", label: "2014 (SRD 5.1)" },
                  { value: "2024", label: "2024 (SRD 5.2)", hint: "Background ability scores, origin feats, weapon mastery" },
                ]}
                value={s.ruleset}
                onChange={(v) => {
                  set("ruleset", v);
                  const pick = characters.find((c) => (c.ruleset ?? "2014") === v);
                  setCharId(pick?.id ?? "");
                }}
              />
            </Field>
          </div>
        </fieldset>

        <fieldset>
          <legend>Table</legend>
          <Field label="Who acts">
            <Seg options={INPUT} value={s.input_mode} onChange={(v) => set("input_mode", v)} />
          </Field>
          <Field label="Who rolls">
            <Seg options={ROLLS} value={s.rolls} onChange={(v) => set("rolls", v)} />
          </Field>
          <Field label="Combat">
            <Seg options={COMBAT} value={s.combat_mode} onChange={(v) => set("combat_mode", v)} />
          </Field>
          <Field label="Narration length">
            <Seg options={NARRATION} value={s.narration_length} onChange={(v) => set("narration_length", v)} />
          </Field>
          <Field label="Content limits (lines & veils)">
            <input value={s.content_limits} onChange={(e) => set("content_limits", e.target.value)} placeholder="e.g. no spiders, fade to black on gore" />
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
          <Field label="Dungeon Master">
            <div className="engine-list">
              {engines.map((e) => (
                <button
                  type="button"
                  key={e.value}
                  disabled={!e.available}
                  className={`engine ${s.dm_engine === e.value ? "selected" : ""}`}
                  onClick={() => set("dm_engine", e.value)}
                  title={e.available ? e.hint : "Not available"}
                >
                  <strong>{e.label}</strong>
                  <span className="muted small">{e.available ? e.hint : e.value === "api_key" ? "Save an API key in Settings first" : "Claude Code isn't installed on the host"}</span>
                </button>
              ))}
            </div>
          </Field>
          {s.dm_engine !== "offline" && meta.models.length > 0 && (
            <Field label="Model">
              <select value={s.dm_model} onChange={(e) => set("dm_model", e.target.value)}>
                {meta.models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Field label="Discord webhook (optional — posts 'your move' notices)">
            <input value={s.discord_webhook ?? ""} onChange={(e) => set("discord_webhook", e.target.value)} placeholder="https://discord.com/api/webhooks/…" />
          </Field>
        </fieldset>

        <fieldset>
          <legend>Your character</legend>
          <CharacterPicker characters={characters} value={charId} onChange={setCharId} ruleset={s.ruleset} />
        </fieldset>
      </div>
    </Modal>
  );
}
