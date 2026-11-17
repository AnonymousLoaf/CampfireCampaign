import type {
  AbilityRoll,
  CharacterView,
  ChatMessage,
  CreateCharacter,
  CreatorOptions,
  CustomEntry,
  CustomEntryInput,
  GameSettings,
  GameSummary,
  GameView,
  Issue,
  LevelUpBody,
  LogEntry,
  Me,
  Meta,
  NotificationsPatch,
  RestKind,
  Ruleset,
  SettingsPatch,
  TravelTo,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  const res = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    // FormData sets its own multipart Content-Type (with boundary).
    headers: body !== undefined && !isForm ? { "Content-Type": "application/json" } : undefined,
    body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
  });
  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    if (data && typeof data === "object" && "detail" in data) {
      const d = (data as { detail: unknown }).detail;
      if (typeof d === "string") detail = d;
      else if (Array.isArray(d))
        detail = d
          .map((x) => (x && typeof x === "object" && "msg" in x ? String((x as { msg: unknown }).msg) : String(x)))
          .join("; ");
      else detail = JSON.stringify(d);
    } else if (typeof data === "string" && data) {
      detail = data.slice(0, 300);
    }
    throw new ApiError(detail, res.status);
  }
  return data as T;
}

const get = <T,>(p: string) => request<T>("GET", p);
const post = <T,>(p: string, b?: unknown) => request<T>("POST", p, b ?? {});
const put = <T,>(p: string, b?: unknown) => request<T>("PUT", p, b ?? {});
const patch = <T,>(p: string, b?: unknown) => request<T>("PATCH", p, b ?? {});
const del = <T,>(p: string, b?: unknown) => request<T>("DELETE", p, b);

type Ok = { ok: true };

/** Adds character_id to a body only when acting for someone other than myself. */
const withChar = <B extends object>(body: B, character_id?: string | null): B & { character_id?: string } =>
  character_id ? { ...body, character_id } : body;

export const api = {
  // auth
  register: (username: string, password: string, display_name: string) =>
    post<Me>("/auth/register", { username, password, display_name }),
  login: (username: string, password: string) => post<Me>("/auth/login", { username, password }),
  logout: () => post<Ok>("/auth/logout"),
  me: () => get<Me>("/me"),
  setApiKey: (key: string) => put<Me>("/me/api-key", { key }),
  removeApiKey: () => del<Me>("/me/api-key"),
  setXaiKey: (key: string) => put<Me>("/me/xai-key", { key }),
  removeXaiKey: () => del<Me>("/me/xai-key"),
  generatePortrait: (characterId: string, notes: string) =>
    post<CharacterView>(`/characters/${characterId}/portrait/generate`, { notes }),
  meta: () => get<Meta>("/meta"),
  setNotifications: (p: NotificationsPatch) => put<Me>("/me/notifications", p),
  pushKey: () => get<{ public_key: string }>("/push/key"),
  pushSubscribe: (subscription: unknown) => post<Ok>("/push/subscribe", { subscription }),
  pushUnsubscribe: (endpoint: string) => del<Ok>("/push/subscribe", { endpoint }),
  pushTest: () => post<Ok>("/push/test"),

  // rules / characters
  creatorOptions: (ruleset: Ruleset = "2014") =>
    get<CreatorOptions>(ruleset === "2014" ? "/rules/creator" : `/rules/creator?ruleset=${ruleset}`),
  characters: () => get<CharacterView[]>("/characters"),
  character: (id: string) => get<CharacterView>(`/characters/${id}`),
  rollAbilities: () => post<AbilityRoll>("/characters/roll-abilities"),
  createCharacter: (c: CreateCharacter) => post<CharacterView>("/characters", c),
  importCharacter: (source: string) =>
    post<{ character: CharacterView; issues: Issue[]; ruleset?: Ruleset }>("/characters/import", { source }),
  deleteCharacter: (id: string) => del<Ok>(`/characters/${id}`),

  // portraits (M4)
  uploadPortrait: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("image", file);
    return request<CharacterView>("POST", `/characters/${id}/portrait`, fd);
  },
  removePortrait: (id: string) => del<CharacterView>(`/characters/${id}/portrait`),

  // custom content library (M4)
  customList: () => get<CustomEntry[]>("/custom"),
  customCreate: (e: CustomEntryInput) => post<CustomEntry>("/custom", e),
  customUpdate: (id: string, e: CustomEntryInput) => put<CustomEntry>(`/custom/${id}`, e),
  customDelete: (id: string) => del<Ok>(`/custom/${id}`),
  attachCustom: (characterId: string, entry_id: string) => post<CharacterView>(`/characters/${characterId}/custom`, { entry_id }),
  detachCustom: (characterId: string, entry_id: string) => del<CharacterView>(`/characters/${characterId}/custom/${entry_id}`),

  // games
  games: () => get<GameSummary[]>("/games"),
  createGame: (name: string, settings: Partial<GameSettings>, character_id: string, plot_id?: string | null) =>
    post<{ id: string }>("/games", { name, settings, character_id, plot_id: plot_id || null }),
  setPlot: (id: string, entry_id: string | null) => put<Ok>(`/games/${id}/plot`, { entry_id }),
  joinGame: (invite_code: string, character_id: string) =>
    post<{ id: string }>("/games/join", { invite_code, character_id }),
  spectateGame: (invite_code: string) => post<{ id: string }>("/games/join", { invite_code, spectate: true }),
  away: (id: string, until: string | null) => post<Ok>(`/games/${id}/away`, { until }),
  log: (id: string, opts: { before_id?: number | string; limit?: number; kinds?: string } = {}) => {
    const q = new URLSearchParams();
    if (opts.before_id !== undefined) q.set("before_id", String(opts.before_id));
    q.set("limit", String(opts.limit ?? 50));
    if (opts.kinds) q.set("kinds", opts.kinds);
    return get<{ entries: LogEntry[]; has_more: boolean }>(`/games/${id}/log?${q.toString()}`);
  },
  seen: (id: string, log_id: number | string) => post<Ok>(`/games/${id}/seen`, { log_id }),
  // table chat
  chat: (id: string, before_id?: number) =>
    get<{ messages: ChatMessage[]; has_more: boolean }>(
      `/games/${id}/chat?limit=50` + (before_id !== undefined ? `&before_id=${before_id}` : ""),
    ),
  chatPost: (id: string, text: string) => post<ChatMessage>(`/games/${id}/chat`, { text }),
  chatEdit: (id: string, mid: number, text: string) => patch<ChatMessage>(`/games/${id}/chat/${mid}`, { text }),
  chatDelete: (id: string, mid: number) => del<ChatMessage>(`/games/${id}/chat/${mid}`),
  chatSeen: (id: string, message_id: number) => post<Ok>(`/games/${id}/chat/seen`, { message_id }),
  recap: (id: string) => post<{ text: string }>(`/games/${id}/recap`),
  storySummary: (id: string) => post<{ text: string; updated_at: string | null; upto_id: number }>(`/games/${id}/story`),
  view: (id: string, character_id?: string | null) =>
    get<GameView>(`/games/${id}/view` + (character_id ? `?character_id=${encodeURIComponent(character_id)}` : "")),
  start: (id: string) => post<Ok>(`/games/${id}/start`),
  leave: (id: string) => post<Ok>(`/games/${id}/leave`),
  deleteGame: (id: string) => del<Ok>(`/games/${id}`),
  removePlayer: (id: string, user_id: string) => post<Ok>(`/games/${id}/remove-player`, { user_id }),
  patchSettings: (id: string, s: SettingsPatch) => patch<Ok>(`/games/${id}/settings`, s),
  tvLink: (id: string) => post<{ tv_token: string; url: string }>(`/games/${id}/tv-link`),
  tvView: (token: string) => get<GameView>(`/tv/${encodeURIComponent(token)}/view`),

  // playing
  submitAction: (id: string, text: string, travel_to: TravelTo, rest: RestKind = null) =>
    post<Ok>(`/games/${id}/action`, { text, travel_to, rest }),
  levelUp: (id: string, body: LevelUpBody) =>
    post<Ok & { hp_gained?: number; level?: number }>(`/games/${id}/level-up`, body),
  levelUpCharacter: (characterId: string, body: LevelUpBody) =>
    post<Ok & { hp_gained?: number; level?: number }>(`/characters/${characterId}/level-up`, body),
  prepare: (id: string, spells: string[], character_id?: string | null) =>
    post<Ok>(`/games/${id}/prepare`, withChar({ spells }, character_id)),
  prepareCharacter: (characterId: string, spells: string[]) =>
    post<Ok>(`/characters/${characterId}/prepare`, { spells }),
  haggle: (id: string, character_id?: string | null) =>
    post<Ok & { discount?: number }>(`/games/${id}/shop/haggle`, withChar({}, character_id)),
  feature: (
    id: string,
    feature_id: string,
    opts: { target_id?: string; x?: number; y?: number } = {},
    character_id?: string | null,
  ) => post<Ok>(`/games/${id}/combat/feature`, withChar({ feature_id, ...opts }, character_id)),
  castAt: (id: string, spell_index: string, x: number, y: number, slot_level?: number, character_id?: string | null) =>
    post<Ok>(`/games/${id}/combat/cast`, withChar({ spell_index, x, y, slot_level }, character_id)),
  withdrawAction: (id: string) => del<Ok>(`/games/${id}/action`),
  roll: (id: string, roll_id: string) => post<Ok>(`/games/${id}/roll`, { roll_id }),
  ready: (id: string, ready: boolean) => post<Ok>(`/games/${id}/ready`, { ready }),
  buy: (id: string, key: string, qty: number, character_id?: string | null) =>
    post<Ok>(`/games/${id}/shop/buy`, withChar({ key, qty }, character_id)),
  sell: (id: string, item_id: string, qty: number, character_id?: string | null) =>
    post<Ok>(`/games/${id}/shop/sell`, withChar({ item_id, qty }, character_id)),
  equip: (id: string, item_id: string, equipped: boolean, character_id?: string | null) =>
    post<Ok>(`/games/${id}/inventory/equip`, withChar({ item_id, equipped }, character_id)),
  useItem: (id: string, item_id: string, target_character_id?: string, character_id?: string | null) =>
    post<Ok>(
      `/games/${id}/inventory/use`,
      withChar(target_character_id ? { item_id, target_character_id } : { item_id }, character_id),
    ),
  give: (id: string, item_id: string, qty: number, to_character_id: string, character_id?: string | null) =>
    post<Ok>(`/games/${id}/inventory/give`, withChar({ item_id, qty, to_character_id }, character_id)),
  move: (id: string, x: number, y: number, character_id?: string | null) =>
    post<Ok>(`/games/${id}/combat/move`, withChar({ x, y }, character_id)),
  attack: (id: string, attack_id: string, target_id: string, character_id?: string | null) =>
    post<Ok>(`/games/${id}/combat/attack`, withChar({ attack_id, target_id }, character_id)),
  cast: (id: string, spell_index: string, target_id?: string, slot_level?: number, character_id?: string | null) =>
    post<Ok>(`/games/${id}/combat/cast`, withChar({ spell_index, target_id, slot_level }, character_id)),
  act: (
    id: string,
    kind: "dodge" | "dash" | "disengage" | "second_wind" | "custom",
    text?: string,
    character_id?: string | null,
  ) => post<Ok>(`/games/${id}/combat/act`, withChar({ kind, text }, character_id)),
  endTurn: (id: string, character_id?: string | null) =>
    post<Ok>(`/games/${id}/combat/end-turn`, withChar({}, character_id)),
  forceResolve: (id: string) => post<Ok>(`/games/${id}/force-resolve`),
  nudge: (id: string, user_id: string) => post<Ok>(`/games/${id}/nudge`, { user_id }),
  inviteByEmail: (id: string, email: string) => post<Ok>(`/games/${id}/invite`, { email }),
  retryDm: (id: string) => post<Ok>(`/games/${id}/retry-dm`),
};
