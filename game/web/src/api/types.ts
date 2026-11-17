// Types mirroring docs/game/API.md (M1).

export type Ability = "STR" | "DEX" | "CON" | "INT" | "WIS" | "CHA";
export const ABILITIES: Ability[] = ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
export type AbilityMap = Record<Ability, number>;

export type Ruleset = "2014" | "2024";

export interface NotifyPrefs {
  email: boolean;
  push: boolean;
  remind_minutes: number;
}

export interface Me {
  id: string;
  username: string;
  display_name: string;
  has_api_key: boolean;
  api_key_last4: string | null;
  // M3
  email?: string | null;
  notify?: NotifyPrefs;
}

export interface NotificationsPatch {
  email?: string | null;
  notify_email?: boolean;
  notify_push?: boolean;
  remind_minutes?: number;
}

export interface Meta {
  engines: { offline: boolean; claude_code: boolean; api_key: boolean };
  models: { id: string; label: string }[];
  // M3
  email_available?: boolean;
  push_available?: boolean;
}

// ---------- Rules ----------

export type SpellArea = { shape: "sphere" | "cube" | "cone" | "line"; size_ft: number };

export interface Spell {
  index: string;
  name: string;
  level: number;
  school: string;
  kind: "attack" | "save" | "auto" | "heal" | "utility";
  range_ft: number | null;
  description: string;
  combat: boolean;
  // M2 (optional so M1 responses still render)
  concentration?: boolean;
  target?: "enemy" | "ally" | "self" | "point" | "none";
  area?: SpellArea | null;
  ritual?: boolean;
  casting_time?: string;
}

export interface NamedOption {
  index?: string;
  name: string;
  description: string;
}

export interface Subrace {
  index: string;
  name: string;
  ability_bonuses: Partial<AbilityMap>;
  traits: string[];
}

export interface Race {
  index: string;
  name: string;
  speed: number;
  size: string;
  ability_bonuses: Partial<AbilityMap>;
  traits: string[];
  languages: string[];
  subraces: Subrace[];
  ability_choices?: null | { count: number; amount: number; exclude: Ability[] };
  ancestries?: null | { name: string; damage_type: string }[];
}

export interface ClassSpellcasting {
  ability: Ability;
  cantrips_known: number;
  spells_at_l1: number;
  prepares: boolean;
  known?: boolean;
  pact?: boolean;
  cantrips: Spell[];
  spells: Spell[];
}

export interface ClassOption {
  index: string;
  name: string;
  hit_die: number;
  saves: Ability[];
  description: string;
  skill_choices: { count: number; options: string[] };
  armor: string[];
  weapons: string[];
  equipment_options: { id: string; label: string; items: string[] }[];
  features: { name: string; description: string }[];
  spellcasting: ClassSpellcasting | null;
  subclass_level?: number;
  subclasses?: NamedOption[];
  fighting_styles?: null | NamedOption[];
  expertise_at_l1?: number;
  // M3 (2024)
  weapon_mastery?: number;
  mastery_options?: MasteryOption[];
}

export interface MasteryOption {
  weapon_key: string;
  name: string;
  mastery: string;
}

export interface Feat {
  name: string;
  description: string;
  category?: "origin" | "general" | "fighting_style";
}

export interface Background {
  index: string;
  name: string;
  skills: string[];
  description: string;
  gold_cp: number;
  // M3 (2024)
  ability_options?: Ability[];
  /** `list` is the class spell list a Magic Initiate origin feat draws from (e.g. "Cleric"), when the server knows it. */
  origin_feat?: { name: string; description: string; list?: string | null } | null;
  tool?: string | null;
}

export interface CreatorOptions {
  races: Race[];
  classes: ClassOption[];
  backgrounds: Background[];
  skills: Record<string, Ability>;
  standard_array: number[];
  point_buy: { budget: number; min: number; max: number; costs: Record<string, number> };
  alignments: string[];
  // M3
  feats?: Feat[];
  ruleset?: Ruleset;
}

// ---------- Characters ----------

export interface Item {
  id: string;
  key: string;
  name: string;
  qty: number;
  equipped: boolean;
  equippable: boolean;
  usable: boolean;
  category: string;
  weight: number;
  value_cp: number;
  damage: string;
  ac: string;
  properties: string[];
  description: string;
}

export interface Attack {
  id: string;
  name: string;
  to_hit: number;
  damage: string;
  damage_type: string;
  range_ft: number;
  long_range_ft: number | null;
  kind: "melee" | "ranged" | "spell";
  properties: string[];
  // M3 (2024)
  mastery?: string | null;
}

export interface Issue {
  issue: string;
  fix: string;
}

export interface CharacterSpellcasting {
  ability: Ability;
  save_dc: number;
  attack_bonus: number;
  slots: Record<string, { max: number; used: number }>;
  cantrips: Spell[];
  spells: Spell[];
  // M2
  prepares?: boolean;
  prepared_max?: number | null;
  known?: boolean;
  spellbook?: Spell[] | null;
  options?: Spell[];
  max_spell_level?: number;
  pact?: null | { level: number; max: number; used: number };
  concentrating_on?: string | null;
}

export interface LevelUpOffer {
  to_level: number;
  hit_die: number;
  hp_average: number;
  con_mod: number;
  asi: boolean;
  subclass_options: null | NamedOption[];
  fighting_style_options: null | NamedOption[];
  expertise: number;
  expertise_options: string[];
  cantrips: number;
  cantrip_options: Spell[];
  spells: number;
  spell_options: Spell[];
  max_spell_level: number;
  features: { name: string; description: string }[];
  // M3
  feat_options?: null | { name: string; description: string }[];
  masteries?: number;
  mastery_options?: MasteryOption[];
}

export interface LevelUpBody {
  character_id?: string;
  hp_method: "average" | "roll";
  asi: null | Partial<AbilityMap>;
  subclass?: string;
  fighting_style?: string;
  expertise?: string[];
  cantrips?: string[];
  spells?: string[];
  // M3
  feat?: string;
  masteries?: string[];
}

export interface ClassAction {
  id: string;
  name: string;
  kind: "action" | "bonus" | "reaction" | "free";
  description: string;
  target: "enemy" | "ally" | "self" | "point" | "none";
  range_ft: number | null;
  uses: null | { max: number; used: number; per: string };
  available: boolean;
}

export interface Feature {
  name: string;
  description: string;
  uses: null | { max: number; used: number; per: "short" | "long" };
}

export interface CharacterView {
  id: string;
  name: string;
  owner_id: string;
  game_id: string | null;
  race: string;
  subrace: string | null;
  class: string;
  subclass: string | null;
  background: string;
  alignment: string;
  backstory: string;
  color: string;
  level: number;
  xp: number;
  xp_next: number | null;
  prof_bonus: number;
  hp: number;
  hp_max: number;
  temp_hp: number;
  ac: number;
  speed: number;
  initiative: number;
  abilities: AbilityMap;
  mods: AbilityMap;
  saves: AbilityMap;
  save_profs: Ability[];
  skills: Record<string, number>;
  skill_profs: string[];
  passive_perception: number;
  conditions: string[];
  death_saves: { success: number; fail: number };
  down: boolean;
  dead: boolean;
  inspiration: boolean;
  gold_cp: number;
  inventory: Item[];
  attacks: Attack[];
  spellcasting: CharacterSpellcasting | null;
  features: Feature[];
  source: "creator" | "ddb";
  issues: Issue[];
  pending_level_up?: LevelUpOffer | null;
  actions?: ClassAction[];
  // M3
  ruleset?: Ruleset;
  feats?: { name: string; description: string }[];
  masteries?: { weapon_key: string; name: string; mastery: string; description: string }[];
  exhaustion?: number;
  // M4
  portrait_url?: string | null;
  custom?: AttachedCustom[];
}

export type CustomKind = "feat" | "feature" | "spell" | "item" | "background" | "species_trait";

/** A custom entry attached to a character (homebrew or content from a book the player owns). */
export interface AttachedCustom {
  entry_id: string;
  kind: CustomKind;
  name: string;
  description: string;
  level?: number | null;
}

/** An entry in my private custom content library. */
export interface CustomEntry {
  id: string;
  kind: CustomKind;
  name: string;
  description: string;
  level: number | null;
  data: Record<string, unknown>;
  created_at?: string;
}

export interface CustomEntryInput {
  kind: CustomKind;
  name: string;
  description: string;
  level?: number | null;
  data?: Record<string, unknown>;
}

export interface CreateCharacter {
  name: string;
  race: string;
  subrace: string | null;
  class: string;
  background: string;
  ability_method: "standard" | "pointbuy" | "roll";
  roll_id: string | null;
  abilities: AbilityMap;
  skills: string[];
  equipment_option: string;
  cantrips: string[];
  spells: string[];
  alignment: string;
  backstory: string;
  color: string;
  // M2 optional choices
  subclass?: string;
  fighting_style?: string;
  expertise?: string[];
  bonus_abilities?: Ability[];
  ancestry?: string;
  // M3 (2024)
  ruleset?: Ruleset;
  background_asi?: Partial<AbilityMap>;
  masteries?: string[];
  magic_initiate?: null | { cantrips: string[]; spell: string };
}

export interface AbilityRoll {
  roll_id: string;
  sets: { rolls: number[]; dropped: number; total: number }[];
}

// ---------- Games ----------

export interface GameSettings {
  story_type: "dungeon_crawl" | "mystery" | "heist" | "war" | "horror" | "wilderness" | "intrigue" | "seafaring" | "sandbox";
  tone: "heroic" | "gritty" | "dark" | "lighthearted";
  length: "one_shot" | "short" | "open";
  difficulty: "story" | "normal" | "hard" | "deadly";
  death_rule: "heroic" | "standard" | "permadeath";
  rest_rule: "standard" | "gritty" | "epic";
  starting_level: number;
  max_players: number;
  leveling: "xp" | "milestone";
  magic_level: "low" | "standard" | "high";
  economy: "scarce" | "standard" | "rich";
  sell_rate: number;
  ruleset: Ruleset;
  rolls: "players" | "auto";
  combat_mode: "side" | "classic";
  narration_length: "short" | "medium" | "long";
  content_limits: string;
  round_timer_minutes: number;
  combat_timer_minutes: number | null;
  timeout_policy: "ai" | "skip" | "pause";
  input_mode: "individual" | "single";
  speaker_id: string | null;
  live: boolean;
  live_timer_minutes: number;
  dm_engine: "offline" | "claude_code" | "api_key";
  dm_model: string;
  discord_webhook: string | null;
}

/** Fields the host may PATCH on a running game. */
export type SettingsPatch = Partial<
  Pick<
    GameSettings,
    | "round_timer_minutes"
    | "combat_timer_minutes"
    | "live_timer_minutes"
    | "live"
    | "input_mode"
    | "speaker_id"
    | "timeout_policy"
    | "rolls"
    | "combat_mode"
    | "narration_length"
    | "dm_engine"
    | "dm_model"
    | "discord_webhook"
  >
>;

export const DEFAULT_SETTINGS: GameSettings = {
  story_type: "sandbox",
  tone: "heroic",
  length: "short",
  difficulty: "normal",
  death_rule: "standard",
  rest_rule: "standard",
  starting_level: 1,
  max_players: 4,
  leveling: "xp",
  magic_level: "standard",
  economy: "standard",
  sell_rate: 0.5,
  ruleset: "2014",
  rolls: "players",
  combat_mode: "classic",
  narration_length: "medium",
  content_limits: "",
  round_timer_minutes: 1440,
  combat_timer_minutes: null,
  timeout_policy: "ai",
  input_mode: "individual",
  speaker_id: null,
  live: false,
  live_timer_minutes: 5,
  dm_engine: "offline",
  dm_model: "claude-opus-5-5",
  discord_webhook: null,
};

export type GameStatus = "lobby" | "active" | "ended";
export type PhaseType = "lobby" | "exploration" | "roll" | "shop" | "combat" | "dm" | "ended";

export interface GameSummary {
  id: string;
  name: string;
  status: GameStatus;
  phase_type: PhaseType | null;
  deadline: string | null;
  my_turn: boolean;
  player_count: number;
  max_players: number;
  host_name: string;
  invite_code: string;
  role: "host" | "player" | "spectator" | null;
}

export type TravelTo = null | { settlement_id: string } | { q: number; r: number };
export type RestKind = null | "short" | "long";

export interface PendingRoll {
  id: string;
  user_id: string;
  character_id: string;
  label: string;
  dc: number | null;
  /** What the roll adds to the d20, and which check it is ("combat" for a typed attack or spell). */
  bonus?: number;
  check?: string;
  advantage: "normal" | "advantage" | "disadvantage";
  result: null | {
    total: number;
    rolls: number[];
    modifier: number;
    success: boolean | null;
    /** Typed combat: whether an attack roll hit, and the game's log lines for what the roll did. */
    hit?: boolean;
    lines?: string[];
  };
  /** Typed combat: an attack or spell the DM queued for this character; the roll resolves it. */
  combat?: Record<string, unknown> | null;
}

export interface Phase {
  id: string;
  type: PhaseType;
  prompt: string | null;
  opened_at: string | null;
  deadline: string | null;
  waiting_on: string[];
  my_submission: null | { text: string; travel_to: TravelTo; rest?: RestKind; edited?: boolean; updated_at?: string };
  submissions_visible: {
    user_id: string;
    text: string;
    travel_to: TravelTo;
    rest?: RestKind;
    edited?: boolean;
    updated_at?: string;
  }[];
  pending_rolls: PendingRoll[];
  error: string | null;
}

export interface Settlement {
  id: string;
  name: string;
  q: number;
  r: number;
  size: "village" | "town" | "city";
  shops: string[];
  description: string;
}

export interface Poi {
  id: string;
  name: string;
  kind: "ruins" | "cave" | "tower" | "camp" | "shrine";
  q: number;
  r: number;
  description?: string;
}

export interface World {
  w: number;
  h: number;
  hexes: string[];
  revealed: string[];
  settlements: Settlement[];
  pois: Poi[];
  roads: [number, number][];
  party: { q: number; r: number };
}

export interface Token {
  id: string;
  name: string;
  kind: "pc" | "monster";
  character_id: string | null;
  x: number;
  y: number;
  hp: number | null;
  hp_max: number | null;
  hp_state: "healthy" | "hurt" | "bloodied" | "down" | "dead";
  ac: number | null;
  conditions: string[];
  speed: number;
  size: number;
  color: string;
  done?: boolean;
  concentrating?: boolean;
  raging?: boolean;
  marked?: boolean;
  /** M4: a PC token may carry its character's portrait (the frontend also looks it up by character_id). */
  portrait_url?: string | null;
}

export type Terrain = "road" | "forest" | "tavern" | "cave" | "dungeon" | "ruins" | "camp" | "swamp" | "town";

export interface PointSpell {
  spell_index: string;
  range_ft: number;
  area: SpellArea | null;
}

export interface Encounter {
  round: number;
  /** Fights use individual initiative ("classic"); "side" only appears in fights started before typed combat. */
  mode: "side" | "classic";
  turn: { side: "party" | "monsters" | null; actor_id: string | null };
  grid: { w: number; h: number };
  cells: string[];
  terrain: Terrain;
  point_spells?: PointSpell[];
  /** What each 'T' obstacle square is (table, bar, barrel, tree, boulder, stalagmite, cart). */
  props?: { x: number; y: number; kind: string }[];
  /** What '~' squares are on this map, e.g. "brush". */
  difficult?: string;
  tokens: Token[];
  my_turn: boolean;
  my_token_id: string | null;
  budget: null | { move_ft: number; action: boolean; bonus: boolean; attacks_left?: number; reaction?: boolean };
  reachable: [number, number][];
  targets: { token_id: string; attack_ids: string[]; spell_indexes: string[] }[];
}

export interface ShopStockItem {
  key: string;
  name: string;
  category: string;
  price_cp: number;
  qty: number;
  description: string;
  weight: number;
  damage: string;
  ac: string;
  properties: string[];
  service?: boolean;
  rarity?: string | null;
}

export interface Shop {
  name: string;
  keeper: string;
  type: string;
  sell_rate: number;
  stock: ShopStockItem[];
  discounts?: Record<string, number>;
  haggled?: string[];
}

export interface LogEntry {
  id: string | number;
  ts: string;
  kind: "narration" | "action" | "roll" | "event" | "combat" | "system" | "npc";
  author: string | null;
  text: string;
  data: Record<string, unknown> | null;
}

export interface Member {
  user_id: string;
  display_name: string;
  character_id: string | null;
  role: "host" | "player" | "spectator";
  has_acted: boolean;
  ready: boolean;
  // M3
  away_until?: string | null;
}

export interface GameView {
  game: {
    id: string;
    name: string;
    status: GameStatus;
    invite_code: string;
    host_id: string;
    settings: GameSettings;
    created_at: string;
  };
  me: {
    user_id: string | null;
    character_id: string | null;
    is_host: boolean;
    is_speaker?: boolean;
    controls?: string[];
    // M3
    role?: "host" | "player" | "spectator";
    last_seen_id?: number | null;
    unseen_count?: number;
  };
  tv_url?: string | null;
  members: Member[];
  characters: Record<string, CharacterView>;
  phase: Phase;
  world: World | null;
  location: { name: string; settlement_id: string | null; description: string } | null;
  scene: { type: string; time_of_day: string; weather: string; day: number; hour: number } | null;
  encounter: Encounter | null;
  shop: Shop | null;
  npcs: { name: string; role: string; attitude: string; notes: string }[];
  quests: { title: string; status: "active" | "done" | "failed"; notes: string }[];
  log: LogEntry[];
  dm: { engine: string; model: string; busy: boolean };
}
