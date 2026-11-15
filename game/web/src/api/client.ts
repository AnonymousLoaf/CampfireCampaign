import type {
  AbilityRoll,
  CharacterView,
  CreateCharacter,
  CreatorOptions,
  GameSettings,
  GameSummary,
  GameView,
  Issue,
  LevelUpBody,
  Me,
  Meta,
  RestKind,
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
  const res = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
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
const del = <T,>(p: string) => request<T>("DELETE", p);

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
  meta: () => get<Meta>("/meta"),

  // rules / characters
  creatorOptions: () => get<CreatorOptions>("/rules/creator"),
  characters: () => get<CharacterView[]>("/characters"),
  character: (id: string) => get<CharacterView>(`/characters/${id}`),
  rollAbilities: () => post<AbilityRoll>("/characters/roll-abilities"),
  createCharacter: (c: CreateCharacter) => post<CharacterView>("/characters", c),
  importCharacter: (source: string) =>
    post<{ character: CharacterView; issues: Issue[] }>("/characters/import", { source }),
  deleteCharacter: (id: string) => del<Ok>(`/characters/${id}`),

  // games
  games: () => get<GameSummary[]>("/games"),
  createGame: (name: string, settings: Partial<GameSettings>, character_id: string) =>
    post<{ id: string }>("/games", { name, settings, character_id }),
  joinGame: (invite_code: string, character_id: string) =>
    post<{ id: string }>("/games/join", { invite_code, character_id }),
  view: (id: string, character_id?: string | null) =>
    get<GameView>(`/games/${id}/view` + (character_id ? `?character_id=${encodeURIComponent(character_id)}` : "")),
  start: (id: string) => post<Ok>(`/games/${id}/start`),
  leave: (id: string) => post<Ok>(`/games/${id}/leave`),
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
  retryDm: (id: string) => post<Ok>(`/games/${id}/retry-dm`),
};
