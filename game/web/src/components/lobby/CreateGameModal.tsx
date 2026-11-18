import { useEffect, useState, type ReactNode } from "react";
import { api } from "../../api/client";
import { DEFAULT_SETTINGS, type CharacterView, type CustomEntry, type GameSettings, type Meta, type PlotPreset } from "../../api/types";
import Modal from "../Modal";
import ErrorText, { useAction } from "../ErrorText";
import CharacterPicker from "./CharacterPicker";

type Opt<T extends string> = { value: T; label: string; hint?: string };

const STORY: Opt<GameSettings["story_type"]>[] = [
  { value: "sandbox", label: "Open sandbox", hint: "No set storyline. The DM offers hooks (rumours, jobs, strange places) and the party picks its own goals." },
  { value: "dungeon_crawl", label: "Dungeon crawl", hint: "Delves into ruins, caves and tombs: traps, monsters, secret doors and treasure, floor by floor." },
  { value: "mystery", label: "Mystery", hint: "A crime or secret to uncover. Expect clues, suspects, lies and questioning more than fights." },
  { value: "heist", label: "Heist", hint: "Plan and pull off a daring theft: scout the target, gather a crew and tools, then execute while things go wrong." },
  { value: "war", label: "War", hint: "Factions at war: battles, sieges, missions behind the lines and hard choices about loyalty." },
  { value: "horror", label: "Horror", hint: "Dread and the unknown. Threats are often better avoided than fought, and not everything can be killed." },
  { value: "wilderness", label: "Wilderness survival", hint: "Harsh lands, scarce food and water, weather, beasts and long journeys between safe places." },
  { value: "intrigue", label: "Political intrigue", hint: "Nobles, guilds and spies. Talking, scheming and secrets matter more than swords." },
  { value: "seafaring", label: "Seafaring", hint: "Ships, coasts and islands: pirates, storms, sea monsters and ports of call." },
];
const TONE: Opt<GameSettings["tone"]>[] = [
  { value: "heroic", label: "Heroic", hint: "Classic adventure. The heroes are heroes, good usually wins, and danger is exciting rather than grim." },
  { value: "gritty", label: "Gritty", hint: "Grounded and harsh. Wounds hurt, money is tight, people are complicated, and victories cost something." },
  { value: "dark", label: "Dark", hint: "Bleak and frightening. Cruel villains, tragic choices, and no promise of a happy ending." },
  { value: "lighthearted", label: "Lighthearted", hint: "Playful and funny. Silly NPCs, comic mishaps and low stakes most of the time." },
];
const LENGTH: Opt<GameSettings["length"]>[] = [
  { value: "one_shot", label: "One-shot", hint: "A single story the DM wraps up in about 3-5 sessions." },
  { value: "short", label: "Short campaign", hint: "One main storyline with a clear ending." },
  { value: "open", label: "Open-ended", hint: "No planned end. When one story finishes, the next one begins." },
];
const DIFFICULTY: Opt<GameSettings["difficulty"]>[] = [
  { value: "story", label: "Story", hint: "Gentle fights and plenty of healing, for enjoying the story." },
  { value: "normal", label: "Normal", hint: "Fair fights that take some care, as the rules intend." },
  { value: "hard", label: "Hard", hint: "Tougher, more numerous enemies. Rest and plan, or you'll go down." },
  { value: "deadly", label: "Deadly", hint: "Smart monsters, little mercy. Characters will die if you play carelessly." },
];
const DEATH: Opt<GameSettings["death_rule"]>[] = [
  { value: "heroic", label: "Heroic", hint: "At 0 hit points a character is knocked out, never killed." },
  { value: "standard", label: "Standard death saves", hint: "At 0 hit points you make death saving throws: three successes and you're stable, three failures and you die. If the whole party falls, you wake later with 1 HP." },
  { value: "permadeath", label: "Permadeath", hint: "Death saves as usual, but if the whole party falls, nobody gets back up. Death is final." },
];
const REST: Opt<GameSettings["rest_rule"]>[] = [
  { value: "standard", label: "Standard", hint: "Short rest: 1 hour. Long rest (full hit points and spell slots): 8 hours." },
  { value: "gritty", label: "Gritty", hint: "Short rest: 8 hours. Long rest: a full week. Every fight wears you down." },
  { value: "epic", label: "Epic", hint: "Short rest: a few minutes. Long rest: 1 hour. Recover fast and keep going." },
];
const LEVELING: Opt<GameSettings["leveling"]>[] = [
  { value: "xp", label: "XP", hint: "Earn experience points for fights and deeds; level up when you have enough." },
  { value: "milestone", label: "Milestone", hint: "The DM levels the whole party up together at big story moments." },
];
const MAGIC: Opt<GameSettings["magic_level"]>[] = [
  { value: "low", label: "Low", hint: "Magic is rare: few potions in loot or shops and almost no magic items." },
  { value: "standard", label: "Standard", hint: "The usual amount of potions and the occasional magic item." },
  { value: "high", label: "High", hint: "Magic is everywhere: more potions, and magic items turn up in loot and shops much more often." },
];
const ECONOMY: Opt<GameSettings["economy"]>[] = [
  { value: "scarce", label: "Scarce", hint: "Shop prices are 25% higher and coin is hard to come by." },
  { value: "standard", label: "Standard", hint: "Normal prices." },
  { value: "rich", label: "Rich", hint: "Shop prices are 10% lower and the world is prosperous." },
];
export const ROLLS: Opt<GameSettings["rolls"]>[] = [
  { value: "players", label: "Players roll on the site" },
  { value: "auto", label: "Automatic" },
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
          <button key={o.value} type="button" className={o.value === value ? "active" : ""} onClick={() => onChange(o.value)} title={o.hint}>
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
  const [charId, setCharId] = useState(characters.find((c) => (c.ruleset ?? "2014") === DEFAULT_SETTINGS.ruleset)?.id ?? "");
  const [plots, setPlots] = useState<CustomEntry[]>([]);
  const [plotId, setPlotId] = useState("");
  const [presets, setPresets] = useState<PlotPreset[]>([]);
  useEffect(() => {
    api
      .plotPresets()
      .then(setPresets)
      .catch(() => setPresets([]));
  }, []);
  const preset = presets.find((p) => p.id === plotId);
  const pickPlot = (id: string) => {
    setPlotId(id);
    const p = presets.find((x) => x.id === id);
    if (p?.suggest) setS((prev) => ({ ...prev, ...p.suggest })); // the story type and tone it plays best with
  };
  useEffect(() => {
    api
      .customList()
      .then((l) => setPlots(l.filter((e) => e.kind === "plot")))
      .catch(() => setPlots([]));
  }, []);
  const set = <K extends keyof GameSettings>(k: K, v: GameSettings[K]) => setS((prev) => ({ ...prev, [k]: v }));

  const [create, busy, error] = useAction(async () => {
    const res = await api.createGame(name.trim() || "Untitled campaign", { ...s, discord_webhook: s.discord_webhook?.trim() || null }, charId, plotId);
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
          <Field label="Campaign plot">
            <select value={plotId} onChange={(e) => pickPlot(e.target.value)}>
              <option value="">None: the DM invents the story</option>
              {presets.length > 0 && (
                <optgroup label="Ready-made">
                  {presets.map((p) => (
                    <option key={p.id} value={p.id} title={p.pitch}>
                      {p.name}
                    </option>
                  ))}
                </optgroup>
              )}
              {plots.length > 0 && (
                <optgroup label="My plots">
                  {plots.map((pl) => (
                    <option key={pl.id} value={pl.id} title={pl.description}>
                      {pl.name}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            <div className="muted small hint">
              {preset
                ? `${preset.pitch} (Story type and tone set to suit it; change them if you like.)`
                : plotId
                  ? "Your outline steers the DM. Players never see it."
                  : "A plot is a secret story outline (villain, story beats, secrets, twists) that the DM follows while letting your choices bend it. Players never see it. Pick a ready-made one, write your own under My content → New entry → Campaign plot, or leave it to the DM."}
            </div>
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
                  { value: "2014", label: "2014 (SRD 5.1)", hint: "The older rules: ability increases come from your race. Only 2014 characters can join." },
                  { value: "2024", label: "2024 (SRD 5.2)", hint: "The newer rules: ability increases from your background, an origin feat and weapon mastery. Only 2024 characters can join." },
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
            <div className="muted small">Fights go in initiative order, one character at a time. On your turn you type what you do; the DM moves tokens and asks for your rolls.</div>
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
