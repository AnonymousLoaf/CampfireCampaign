# Game server API (M1)

Base URL: `/api`. JSON in and out. The server runs on `http://localhost:8787`; in development the Vite dev server proxies `/api` (including the WebSocket) to it. In production the server also serves the built frontend from `game/web/dist` at `/`.

Errors: HTTP 4xx with `{"detail": "human-readable message"}`. Successful mutations return `{"ok": true}` unless stated otherwise; clients then refetch the view (and also get a WebSocket `update`).

Times are ISO-8601 UTC strings. Money is stored in copper pieces (`*_cp`); 1 gp = 100 cp, 1 sp = 10 cp.

## Auth

Session cookie `session` (httpOnly), set by register/login.

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/register` | `{username, password, display_name}` | `Me` |
| POST | `/auth/login` | `{username, password}` | `Me` |
| POST | `/auth/logout` | – | ok |
| GET | `/me` | – | `Me` (401 if signed out) |
| PUT | `/me/api-key` | `{key}` | `Me` |
| DELETE | `/me/api-key` | – | `Me` |
| GET | `/meta` | – | `{engines: {offline: true, claude_code: bool, api_key: bool}, models: [{id, label}]}` — `claude_code` is true when the `claude` CLI is found on the host; `api_key` is true when the signed-in user has saved a key |

`Me = {id, username, display_name, has_api_key: bool, api_key_last4: string|null}`

## Rules data

`GET /rules/creator` →
```
{
  races: [{index, name, speed, size, ability_bonuses: {STR?: n,...}, traits: [str], languages: [str],
           subraces: [{index, name, ability_bonuses, traits: [str]}]}],
  classes: [{index, name, hit_die, saves: [ab], description,
             skill_choices: {count, options: [skill]},
             armor: [str], weapons: [str],
             equipment_options: [{id, label, items: [str]}],
             features: [{name, description}],          // level 1 features
             spellcasting: null | {ability, cantrips_known, spells_at_l1, prepares: bool,
                                   cantrips: [Spell], spells: [Spell]}}],   // level-1 spell options
  backgrounds: [{index, name, skills: [skill], description, gold_cp}],
  skills: {skillName: ability},
  standard_array: [15,14,13,12,10,8],
  point_buy: {budget: 27, min: 8, max: 15, costs: {"8":0,"9":1,...,"15":9}},
  alignments: [str]
}
Spell = {index, name, level, school, kind: "attack"|"save"|"auto"|"heal"|"utility",
         range_ft: n|null, description, combat: bool}
```

## Characters

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/characters` | – | `[CharacterView]` (mine) |
| GET | `/characters/{id}` | – | `CharacterView` |
| POST | `/characters/roll-abilities` | – | `{roll_id, sets: [{rolls: [n,n,n,n], dropped: n, total: n}] (6 sets)}` — server rolls 4d6-drop-lowest, recorded |
| POST | `/characters` | `CreateCharacter` | `CharacterView` |
| POST | `/characters/import` | `{source}` — a D&D Beyond character URL/id, or the raw character JSON text | `{character: CharacterView, issues: [{issue, fix}]}` |
| DELETE | `/characters/{id}` | – | ok (not allowed while in an active game) |

```
CreateCharacter = {
  name, race, subrace: str|null, class, background,
  ability_method: "standard"|"pointbuy"|"roll", roll_id: str|null,
  abilities: {STR,DEX,CON,INT,WIS,CHA},     // BEFORE racial bonuses
  skills: [skill],                         // class picks; background skills are added automatically
  equipment_option: id,
  cantrips: [spellIndex], spells: [spellIndex],
  alignment, backstory, color: "#rrggbb"
}

CharacterView = {
  id, name, owner_id, game_id: str|null,
  race, subrace, class, subclass: null, background, alignment, backstory, color,
  level, xp, xp_next, prof_bonus,
  hp, hp_max, temp_hp, ac, speed, initiative,
  abilities: {STR..CHA}, mods: {STR..CHA},
  saves: {STR..CHA: n}, save_profs: [ab],
  skills: {skillName: n}, skill_profs: [skill],
  passive_perception,
  conditions: [str], death_saves: {success, fail}, down: bool, dead: bool, inspiration: bool,
  gold_cp,
  inventory: [Item],
  attacks: [{id, name, to_hit, damage, damage_type, range_ft, long_range_ft|null, kind: "melee"|"ranged"|"spell", properties: [str]}],
  spellcasting: null | {ability, save_dc, attack_bonus,
                        slots: {"1": {max, used}, "2": {max, used}},
                        cantrips: [Spell], spells: [Spell]},
  features: [{name, description, uses: null | {max, used, per: "short"|"long"}}],
  source: "creator"|"ddb", issues: [{issue, fix}]
}

Item = {id, key, name, qty, equipped, equippable: bool, usable: bool, category,
        weight, value_cp, damage, ac, properties: [str], description}
```

## Games

`GameSettings` (all fields optional on create; defaults shown):
```
{
  story_type: "dungeon_crawl"|"mystery"|"heist"|"war"|"horror"|"wilderness"|"intrigue"|"seafaring"|"sandbox"  ("sandbox"),
  tone: "heroic"|"gritty"|"dark"|"lighthearted" ("heroic"),
  length: "one_shot"|"short"|"open" ("short"),
  difficulty: "story"|"normal"|"hard"|"deadly" ("normal"),
  death_rule: "heroic"|"standard"|"permadeath" ("standard"),
  rest_rule: "standard"|"gritty"|"epic" ("standard"),
  starting_level: 1..3 (1), max_players: 1..6 (4),
  leveling: "xp"|"milestone" ("xp"),
  magic_level: "low"|"standard"|"high" ("standard"),
  economy: "scarce"|"standard"|"rich" ("standard"),
  sell_rate: 0.1..1.0 (0.5),
  ruleset: "2014" ("2014"),
  rolls: "players"|"auto" ("players"),
  combat_mode: "side"|"classic" ("side"),
  narration_length: "short"|"medium"|"long" ("medium"),
  content_limits: str (""),
  round_timer_minutes: 5..7200 (1440),
  combat_timer_minutes: 5..7200 | null (null = same as round timer),
  timeout_policy: "ai"|"skip"|"pause" ("ai"),
  input_mode: "individual"|"single" ("individual"),   // single = one table speaker acts for the whole party
  speaker_id: user_id|null (null = host),              // who types in single mode
  live: bool (false),                                  // live session on: everyone's together; uses live_timer_minutes
  live_timer_minutes: 1..60 (5),
  dm_engine: "offline"|"claude_code"|"api_key" ("offline"),
  dm_model: "claude-opus-5-5"|"claude-sonnet-5-5" ("claude-opus-5-5"),
  discord_webhook: str|null (null)
}
```

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/games` | – | `[GameSummary]` |
| POST | `/games` | `{name, settings, character_id}` | `{id}` — creator becomes host and joins with that character |
| POST | `/games/join` | `{invite_code, character_id}` | `{id}` |
| GET | `/games/{id}/view` | – | `GameView` |
| POST | `/games/{id}/start` | – | ok (host; status lobby → active; world generated; DM opens the story) |
| POST | `/games/{id}/leave` | – | ok — any time except during a fight your character is in; the host can't leave (delete instead). The character keeps its progress and is freed. |
| POST | `/games/{id}/remove-player` | `{user_id}` | ok — host only; same rules as leave |
| DELETE | `/games/{id}` | – | ok — host only; deletes the game, its log and DM calls; characters are freed |

`GameSummary = {id, name, status: "lobby"|"active"|"ended", phase_type, deadline, my_turn: bool, player_count, max_players, host_name, invite_code}`

### Playing

All require membership. Each returns ok or 400 with a reason (wrong phase, not your turn, can't afford, out of range…).

| Method | Path | Body | When |
|---|---|---|---|
| POST | `/games/{id}/action` | `{text, travel_to: null \| {settlement_id} \| {q, r}}` | exploration — submit or replace my action |
| DELETE | `/games/{id}/action` | – | exploration — withdraw it |
| POST | `/games/{id}/roll` | `{roll_id}` | roll — make one of my pending rolls |
| POST | `/games/{id}/ready` | `{ready: bool}` | shop |
| POST | `/games/{id}/shop/buy` | `{key, qty}` | shop |
| POST | `/games/{id}/shop/sell` | `{item_id, qty}` | shop |
| POST | `/games/{id}/inventory/equip` | `{item_id, equipped}` | any phase except combat |
| POST | `/games/{id}/inventory/use` | `{item_id, target_character_id?}` | potions etc.; in combat uses my action |
| POST | `/games/{id}/inventory/give` | `{item_id, qty, to_character_id}` | outside combat |
| POST | `/games/{id}/combat/move` | `{x, y}` | combat, my turn — must be in `reachable` |
| POST | `/games/{id}/combat/attack` | `{attack_id, target_id}` | combat, my turn, action unused |
| POST | `/games/{id}/combat/cast` | `{spell_index, target_id?, slot_level?}` | combat, my turn |
| POST | `/games/{id}/combat/act` | `{kind: "dodge"\|"dash"\|"disengage"\|"second_wind"\|"custom", text?}` | combat, my turn |
| POST | `/games/{id}/combat/end-turn` | – | combat, my turn |
| POST | `/games/{id}/force-resolve` | – | host — resolve the current phase now (timeout policy applied to anyone missing) |
| POST | `/games/{id}/nudge` | `{user_id}` | host — notify a player |
| POST | `/games/{id}/retry-dm` | – | host — retry after a DM error |
| PATCH | `/games/{id}/settings` | partial `GameSettings` (pace + table fields: round/combat/live timers, live, input_mode, speaker_id, timeout_policy, rolls, combat_mode, narration_length, dm_engine, dm_model, discord_webhook) | host — change any time; "Start live session" = `{live: true, input_mode?: "single"}`, "End live session" = `{live: false}` |
| POST | `/games/{id}/tv-link` | – | host — `{tv_token, url}`; creates or rotates the TV link |

**Single input mode.** When `input_mode` is `"single"`, the speaker (settings.speaker_id, or the host) can act for every party character: their exploration action is the party's action, they make everyone's pending rolls, buy/sell/equip for any character (pass `character_id` in shop/inventory bodies), and move/attack/cast with any PC token whose turn it is (pass `character_id` in combat bodies). `phase.waiting_on` then contains only the speaker. Other players can still view everything. All shop/inventory/combat bodies accept an optional `character_id` (defaults to my own character); the server checks I'm allowed to control it.

### TV view

`GET /api/tv/{tv_token}/view` → `GameView` with `me = {user_id: null, character_id: null, is_host: false}` (no login needed; read-only). WebSocket: send `{"subscribe_tv": tv_token}`. The frontend route `#/tv/{tv_token}` shows a big-screen layout: large map (battle map during combat, world map otherwise), party stat cards (HP, AC, conditions, key abilities/spell slots), the latest narration in large text, the open shop's stock when a shop phase is on, the phase/whose turn/countdown, and pending rolls with results.

### GameView

```
{
  game: {id, name, status, invite_code, host_id, settings: GameSettings, created_at},
  me: {user_id, character_id, is_host, is_speaker: bool, controls: [characterId]},   // controls = characters I may act for
  tv_url: str|null,                    // host only, once a TV link exists
  members: [{user_id, display_name, character_id, role: "host"|"player", has_acted: bool, ready: bool}],
  characters: {characterId: CharacterView},          // every party member
  phase: {
    id, type: "lobby"|"exploration"|"roll"|"shop"|"combat"|"dm"|"ended",
    prompt: str|null,                  // what the DM asked the party, shown above the action box
    opened_at, deadline: str|null,
    waiting_on: [user_id],
    my_submission: null | {text, travel_to},
    submissions_visible: [{user_id, text, travel_to}],   // others' submitted actions (visible to party)
    pending_rolls: [{id, user_id, character_id, label, dc: n|null, advantage: "normal"|"advantage"|"disadvantage", result: null | {total, rolls: [n], modifier, success: bool|null}}],
    error: str|null                    // last DM error, if the DM call failed
  },
  world: null | {
    w, h,
    hexes: [str],          // h strings of w chars: biome code per hex (see below), offset coords (odd rows shifted right), pointy-top
    revealed: [str],       // h strings of w chars '0'/'1'
    settlements: [{id, name, q, r, size: "village"|"town"|"city", shops: ["general"|"blacksmith"], description}],
    pois: [{id, name, kind: "ruins"|"cave"|"tower"|"camp"|"shrine", q, r}],   // only revealed ones
    roads: [[q, r]],
    party: {q, r}
  },
  location: {name, settlement_id: str|null, description},
  scene: {type, time_of_day, weather, day, hour},
  encounter: null | {
    round, mode: "side"|"classic",
    turn: {side: "party"|"monsters", actor_id: str|null},
    grid: {w, h},
    cells: [str],          // '#' wall, '.' floor, 'T' obstacle, '~' difficult, ' ' void
    terrain: "road"|"forest"|"tavern"|"cave",
    props: [{x, y, kind: "table"|"bar"|"barrel"|"tree"|"boulder"|"stalagmite"|"cart"}],   // what each 'T' obstacle is
    difficult: str,        // what '~' squares are on this map ("brush", "undergrowth", "broken furniture", "rubble")
    tokens: [{id, name, kind: "pc"|"monster", character_id: str|null, x, y, hp: n|null, hp_max: n|null,
              hp_state: "healthy"|"bloodied"|"down"|"dead", ac: n|null, conditions: [str], speed, size: 1, color}],
    my_turn: bool, my_token_id: str|null,
    budget: null | {move_ft, action: bool, bonus: bool},
    reachable: [[x, y]],                  // squares my token can move to now
    targets: [{token_id, attack_ids: [id], spell_indexes: [index]}]   // what I can hit from here
  },
  shop: null | {name, keeper, type, sell_rate, stock: [{key, name, category, price_cp, qty, description, weight, damage, ac, properties}]},
  npcs: [{name, role, attitude, notes}],
  quests: [{title, status: "active"|"done"|"failed", notes}],
  log: [{id, ts, kind: "narration"|"action"|"roll"|"event"|"combat"|"system"|"npc", author: str|null, text, data: {}|null}],   // oldest → newest, last 150
  dm: {engine, model, busy: bool}
}
```

Biome codes: `~` deep water, `-` shallow/coast, `.` plains, `"` grassland, `f` forest, `F` dense forest, `h` hills, `M` mountains, `s` swamp, `d` desert, `n` snow/tundra.

## WebSocket

`GET /api/ws` (cookie auth). Client sends `{"subscribe": gameId}` to follow a game (or `{"subscribe": "lobby"}`). Server pushes `{"type": "update", "game_id"}` whenever that game changes, and `{"type": "lobby"}` when the user's game list changes. Clients refetch on receipt; there is no delta protocol in M1.

---

# M2 additions

Everything above still holds. These fields and endpoints are new or changed in M2.

## Classes, races and character creation

- All 12 SRD classes are playable: barbarian, bard, cleric, druid, fighter, monk, paladin, ranger, rogue, sorcerer, warlock, wizard. Levels **1-5** (MAX_LEVEL 5). One SRD subclass each: Berserker, Lore, Life, Land, Champion, Open Hand, Devotion, Hunter, Thief, Draconic Bloodline, Fiend, Evocation.
- `GET /rules/creator` class entries gain:
  - `subclass_level: n`, `subclasses: [{index, name, description}]`
  - `fighting_styles: null | [{name, description}]` (fighter at 1; paladin and ranger get theirs at level 2 via level-up)
  - `expertise_at_l1: n` (rogue 2, others 0)
  - `spellcasting` gains `known: bool` (bard/sorcerer/warlock/ranger learn a fixed list), `pact: bool` (warlock), `spells_at_l1` may be 0 (paladin/ranger cast from level 2)
- race entries gain `ability_choices: null | {count, amount, exclude: [ab]}` (Half-Elf: 2 × +1, not CHA) and `ancestries: null | [{name, damage_type}]` (Dragonborn).
- `CreateCharacter` gains optional `fighting_style`, `expertise: [skill]`, `bonus_abilities: [ab]`, `ancestry` (Dragonborn damage type name). Fighter's style is no longer tied to the equipment option.
- `GameSettings.starting_level` range is now 1..5. Characters below the game's starting level are levelled automatically at game start (average HP, sensible auto picks).

## Levelling up

`CharacterView` gains:
```
pending_level_up: null | {
  to_level, hit_die, hp_average, con_mod,
  asi: bool,                                   // level 4: +2 to one ability or +1 to two (max 20)
  subclass_options: null | [{index, name, description}],
  fighting_style_options: null | [{name, description}],
  expertise: n, expertise_options: [skill],
  cantrips: n, cantrip_options: [Spell],
  spells: n, spell_options: [Spell],           // new spells to learn (known casters) or add to the spellbook (wizard)
  max_spell_level: n,
  features: [{name, description}]               // what this level grants
}
```
XP (or a milestone) only *offers* a level; the player confirms it:

| Method | Path | Body |
|---|---|---|
| POST | `/games/{id}/level-up` | `{character_id?, hp_method: "average"\|"roll", asi: null \| {STR?: n,...} (sum 2), subclass?, fighting_style?, expertise?: [skill], cantrips?: [index], spells?: [index]}` — any phase except combat/dm |
| POST | `/characters/{id}/level-up` | same body, for a character not in an active game |

Returns `{ok, hp_gained, level}`. If a character earns several levels, `pending_level_up` offers the next one after each confirm.

## Spellcasting

`CharacterView.spellcasting` gains:
```
{ ..., prepares: bool, prepared_max: n|null, known: bool,
  spellbook: null | [Spell],         // wizard: every spell in the book; `spells` = the prepared ones
  options: [Spell],                  // what can be prepared now (cleric/druid/paladin: class list up to max_spell_level; wizard: spellbook)
  max_spell_level: n,
  pact: null | {level, max, used},   // warlock pact slots (recover on a short rest); `slots` is empty for warlocks
  concentrating_on: str|null }
Spell gains: concentration: bool, target: "enemy"|"ally"|"self"|"point"|"none",
             area: null | {shape: "sphere"|"cube"|"cone"|"line", size_ft}, ritual: bool, casting_time: str
```
| Method | Path | Body |
|---|---|---|
| POST | `/games/{id}/prepare` | `{character_id?, spells: [index]}` — prepared casters, outside combat/dm |
| POST | `/characters/{id}/prepare` | same, outside a game |

Combat casting: `/combat/cast` accepts `{spell_index, target_id?, slot_level?, x?, y?}`. Spells with `target: "point"` (Fireball, Shatter, Sleep, Thunderwave-from-self etc.) take a square `x, y`; "self" area spells (Burning Hands, Thunderwave) need nothing. Encounter `targets[]` keep listing per-token options; new `encounter.point_spells: [{spell_index, range_ft, area}]` lists AoE spells castable now (for the map's template preview). Casting a concentration spell drops the previous one; taking damage while concentrating forces a CON save (logged).

## Class features in combat

`CharacterView.actions: [{id, name, kind: "action"|"bonus"|"reaction"|"free", description, target: "enemy"|"ally"|"self"|"point"|"none", range_ft: n|null, uses: null|{max, used, per}, available: bool}]` — Rage, Reckless Attack, Flurry of Blows, Patient Defense, Step of the Wind, Bardic Inspiration, Lay on Hands, Divine Smite (toggle: next melee hit), Channel Divinity, Breath Weapon, Wild Shape (narrative), Second Wind, Action Surge, Cunning Action (Dash/Disengage/Hide), Hunter's Mark, Hex, etc.

| Method | Path | Body |
|---|---|---|
| POST | `/games/{id}/combat/feature` | `{character_id?, feature_id, target_id?, x?, y?}` |

`encounter.tokens[]` gain `concentrating: bool`, `raging: bool`, `marked: bool`. Opportunity attacks happen automatically when a creature leaves an enemy's reach without Disengaging (one reaction per round; logged). Extra Attack (level 5 martials) means `/combat/attack` can be used twice per action — `budget` gains `attacks_left: n`.

## Exploration: rests

`/games/{id}/action` body gains `rest: null | "short" | "long"`. A majority (or the table speaker) voting the same rest makes the party rest before the DM narrates; a long rest in the wilderness may be interrupted. `phase.submissions_visible[]` carry `rest`.

Rest rules setting is active: standard (short 1 h, long 8 h), gritty (short 8 h, long 7 days), epic (short 5 min, long 1 h — clock only).

## Shops

- Shop types: `general`, `blacksmith`, `alchemist`, `magic`, `temple`, `inn`. Stock entries gain `service: bool` and `rarity: str|null`. Services (temple healing, curing poison, an inn room) apply when bought; an inn room gives the buyer a long rest when the shop closes.
- Haggling: `POST /games/{id}/shop/haggle {character_id?}` — one Persuasion check per character per shop (rolled by the server, shown in the log). `shop` view gains `discounts: {characterId: fraction}` (e.g. `-0.15` = 15% off, `0.1` = 10% dearer) and `haggled: [characterId]`. Buy prices for that character are `price_cp * (1 + discount)`, rounded; sell prices unaffected.

## Battle maps

New terrains `dungeon`, `ruins`, `camp`, `swamp` (plus road/forest/tavern/cave). New prop kinds: `pillar`, `statue`, `chest`, `altar`, `tent`, `campfire`, `crate`, `log`, `dead_tree`.

## Loot

Victories roll treasure by monster CR (coins, sometimes a potion or a common/uncommon magic item depending on magic level). It goes to the party's characters automatically and is logged; the DM narrates it.

---

# M3 additions

## Rulesets (2014 and 2024) and levels 1-10

- `GameSettings.ruleset`: `"2014"` | `"2024"` (default "2014"). `starting_level` range is now 1..10. `MAX_LEVEL` = 10.
- Characters carry a ruleset fixed at creation (`CharacterView.ruleset`); a character can only join a game with the same ruleset.
- `GET /rules/creator?ruleset=2024` returns the same shape as 2014, with these differences:
  - `races` = the 2024 **species** (no `ability_bonuses`; `subraces` hold lineages/legacies where the SRD has them; `ancestries` for Dragonborn as before).
  - `backgrounds[]` gain `ability_options: [ab, ab, ab]` (the background's three abilities), `origin_feat: {name, description}`, `tool: str|null`.
  - `classes[]` gain `weapon_mastery: n` (weapons you master at level 1) and `mastery_options: [{weapon_key, name, mastery}]`; `subclass_level` is 3 for every class; `spellcasting.prepares` is true for every caster (2024 casters all prepare from a table: `spells_at_l1` is the number prepared at level 1).
  - `feats: [{name, description, category: "origin"|"general"|"fighting_style"}]` (SRD 5.2 feats).
- `CreateCharacter` gains (2024 only): `ruleset: "2024"`, `background_asi: {AB: 2, AB: 1}` or `{AB: 1, AB: 1, AB: 1}` (only the background's abilities), `masteries: [weapon_key]`, `magic_initiate: null | {cantrips: [index, index], spell: index}` (when the background's origin feat is Magic Initiate). 2014 characters ignore these.
- `CharacterView` gains `ruleset`, `feats: [{name, description}]`, `masteries: [{weapon_key, name, mastery, description}]`, `exhaustion: n` (2024: −2 to d20 tests per level).
- `attacks[]` gain `mastery: str|null` — the weapon's mastery property if the character has mastered it. Combat applies it automatically: **Vex** (advantage on your next attack against that target), **Topple** (CON save or prone), **Sap** (target has disadvantage on its next attack), **Slow** (−10 ft speed), **Push** (pushed 10 ft away), **Graze** (miss still deals your ability modifier), **Cleave** (one extra attack against a different adjacent enemy, once per turn), **Nick** (noted; no extra effect yet).
- `pending_level_up` gains `feat_options: null | [{name, description}]` (at ASI levels: choose an ASI **or** a feat) and `masteries: n` + `mastery_options` (new weapon masteries to pick). Level-up body gains `feat?: name`, `masteries?: [weapon_key]`.

## Notifications

`Me` gains `email: str|null`, `notify: {email: bool, push: bool, remind_minutes: n}`.

| Method | Path | Body | Returns |
|---|---|---|---|
| PUT | `/me/notifications` | `{email?, notify_email?, notify_push?, remind_minutes?}` | `Me` |
| GET | `/push/key` | – | `{public_key}` (VAPID, base64url) |
| POST | `/push/subscribe` | `{subscription}` (the browser PushSubscription JSON) | ok |
| DELETE | `/push/subscribe` | `{endpoint}` | ok |
| POST | `/push/test` | – | ok — sends a test notification to my devices |

`GET /meta` gains `email_available: bool` (SMTP configured on the server), `push_available: bool`.

The server notifies a player (push and/or email, per their settings) when: a phase opens that waits on them ("Your move in …"), the DM narrates while they're waiting, the host nudges them, and `remind_minutes` before their deadline if they still haven't acted. Nothing is sent during a live session. Payload: `{title, body, url}` where `url` is `/#/game/{id}`. The frontend registers a service worker at `/sw.js` (shows the notification; clicking focuses or opens `url`).

## Vacation mode

`POST /games/{id}/away {until: iso|null}` — while away, the game doesn't wait for that player: their character is played cautiously by the AI each round, whatever the timeout policy. `members[]` gain `away_until: str|null`.

## Spectators

`POST /games/join {invite_code, spectate: true}` (no `character_id`) joins as a spectator (up to 10, not counted in max players). `members[].role` can be `"spectator"`. `me.role` is added. Spectators get the full view but can't act.

## History and catch-up

- `GET /games/{id}/log?before_id=&limit=50&kinds=narration,event` → `{entries: [LogEntry], has_more}` (newest first) for the Story tab / infinite scroll.
- `GameView.me` gains `last_seen_id: n|null` and `unseen_count: n`; `POST /games/{id}/seen {log_id}` records how far I've read.
- `POST /games/{id}/recap` → `{text}`: the DM summarises what happened since my `last_seen_id` in a few sentences (uses the game's DM engine; the offline DM returns a bullet list). Not added to the log.
- Submissions gain `edited: bool` and `updated_at`; `submissions_visible[]` include them.

---

# M4 additions

## Atmosphere (frontend; driven by existing fields)

- **Scene backgrounds + sky:** `GameView.scene` = `{type, time_of_day, weather, day, hour}` drives a scene-reactive background behind the story and an animated sky strip (sun/moon arc by `hour`, stars at night, clouds/rain/snow/fog by `weather`). `scene.type` is one of town, tavern, wilderness, forest, dungeon, cave, ruins, road, castle, temple, swamp, mountain, coast. New: when the battle map is up, the background follows `encounter.terrain`.
- **Sound:** synthesized in the browser (Web Audio, no audio files): ambience per scene (wind, rain, fire crackle, tavern murmur, cave drips, water) and effects keyed off new log entries — `combat` lines with `data.hit` (sword/arrow/magic by the attack name or damage type), `data.crit`, `heal`, a death (`falls`), `roll` entries (dice rattle), loot/coin events, doors. Per-device volume and mute in Settings (localStorage).
- **Spoken narration:** browser speech synthesis (free, no key): a speaker button on each narration and an "auto-read new narration" toggle (per device; on by default in the TV view when switched on there). Voice/rate picker in Settings.
- **Dice:** an animated dice roll (d20 tumbling, landing on the natural roll, crit/fumble flourishes) whenever a `roll` log entry or a pending-roll result arrives — in the feed, on the TV and when I press Roll.

## Portraits

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/characters/{id}/portrait` | multipart file `image` (PNG/JPEG/WebP, ≤ 3 MB; the server re-encodes to 256×256 WebP) | `CharacterView` |
| DELETE | `/characters/{id}/portrait` | – | `CharacterView` |
| GET | `/files/portraits/{file}` | – | the image (public URL, unguessable name) |

`CharacterView.portrait_url: str|null`. Without one, the frontend draws a generated crest (class emblem + colour + initials). Portraits show in the party panel, sheet, battle-map tokens (clipped to the circle), TV cards and character cards. Allowed while in a game.

## Custom content library (homebrew and content from books you own)

Per user, private. Lets players add backgrounds, feats, subclass features, species traits, spells and items from their own books or homebrew; the DM reads them. Never shared outside the user's own games.

`CustomEntry = {id, kind: "feat"|"feature"|"spell"|"item"|"background"|"species_trait", name, description, level: n|null, data: {}, created_at}`
- spell `data`: `{level, school, casting_time, range, concentration}` (adjudicated by the DM; castable as a custom action)
- item `data`: `{value_gp, weight, category}`
- background `data`: `{skills: [skill], tool}`

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/custom` | – | `[CustomEntry]` (mine) |
| POST | `/custom` | `{kind, name, description, level?, data?}` | `CustomEntry` |
| PUT | `/custom/{id}` | same | `CustomEntry` |
| DELETE | `/custom/{id}` | – | ok |
| POST | `/characters/{id}/custom` | `{entry_id}` — attach to my character (items go into the inventory; others become features/feats/spells on the sheet) | `CharacterView` |
| DELETE | `/characters/{id}/custom/{entry_id}` | – | `CharacterView` |

`CharacterView` gains `custom: [{entry_id, kind, name, description, level}]` (also shown in Features/Feats/Spells with a "custom" tag). The DM's context includes every attached custom entry's description.

## D&D Beyond import (fixed)

- 2024 characters are detected (non-legacy species/background) and import as `ruleset: "2024"`; others as 2014. The import result gains `ruleset`.
- Features, feats, species traits and subclass features from the D&D Beyond sheet that the game's tables don't cover are kept as custom entries attached to the character (their descriptions come from the character JSON), so the DM can use them.

## Typed combat

Fights are played in words, in individual initiative order (`encounter.mode` is always `"classic"`; the old side-initiative mode and the click-to-act combat endpoints remain only for tests and AI play).

- **Your turn:** when `encounter.my_turn` is true (phase `combat`), the acting player (or the table speaker) sends `POST /games/{gid}/action {text}` — the same endpoint as exploration. Anyone else gets 400 "it's X's turn". The phase becomes `dm` while the DM resolves it.
- **Your dice:** the DM's attacks and damaging spells open phase `roll` with pending rolls that carry `combat: {op}`. `POST /games/{gid}/roll {roll_id}` runs that step (and any roll-free steps queued after it) and returns `result: {total, natural, rolls, modifier, hit, success, damage, lines: [...], skipped}`. Rolls of one turn must be made in order. With the setting `rolls: "auto"` the game rolls at once.
- **What players see:** monster tokens have no `hp`/`ac` (`hp_state` healthy/bloodied/dead). Attack log lines against monsters omit "vs AC" and carry `data.ac = null`; a player's attack line has `data.attacker = "pc-<character id>"`, `data.roll`, `data.hit`, `data.damage`, `data.attack` (the frontend shows the dice from it).
- **DM tools** (act only on the character whose turn it is): `combat_move` (x/y, `toward`, or `away_from` a creature), `combat_attack` (target, weapon), `combat_cast` (spell, target or x/y, slot_level), `combat_feature` (feature, target), `combat_action` (dodge, dash, disengage, hide, help, ready, use_item, other), `combat_end_turn` (runs the monsters' turns up to the next player and reports them). Each turn's DM message includes a text brief: a coordinate grid of the map, every creature's square, distance, HP and AC, and the actor's movement, action economy, weapons, spells, slots and features.
- **After the DM's reply:** if it resolved something but didn't end the turn, the game ends it and asks the DM to narrate what followed; if it changed nothing (asked the player to clarify), the same player's turn stays open. Timeouts and away players: the AI (or a Dodge) takes the turn and the DM narrates it.
- `start_combat` takes `terrain` (now including `town`) and `distance` (`close` 10-20 ft, `near` 30-40 ft, `far`); its result reports initiative and any enemy attacks before the first player's turn.
