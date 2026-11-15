# Async D&D — Game Design & Build Plan

*Working title. Draft 1 — 2026-11-14.*

A browser game where a party of friends plays a D&D 5e campaign run by an AI Dungeon Master, **on their own time**. Every round has a deadline (5 minutes to 5 days, picked by the host). If everyone is online together the game moves as fast as a live table; otherwise it keeps going through the week, one move at a time. The site shows the world map, the battle map, your character sheet, inventory and gold, and lets the party browse shops, buy and sell, and mark themselves ready before the story continues.

It is built from this repository's Claude Code skill: its DM standards, rules data and dice/combat logic, rebuilt as a standalone web app. It starts out hosted on your own PC and is designed so it can be put on the public internet later.

---

## 1. Decisions so far

| Question | Decision |
|---|---|
| Product shape | Standalone web app. The `/dm:dnd` skill is a source of parts, not something we keep in sync. |
| Who runs the AI DM | Two interchangeable **DM engines**: (1) **Local Claude Code**, using the host's Claude Code login, for games hosted on your PC; (2) **Account API key**, a Claude API key a player saves to their account (stored encrypted) that powers the games they host. |
| Missed deadlines | **Host decides per game**: AI plays the character, skip the turn, or pause the game. |
| First milestone | **Thin slice of everything**: a basic, working version of every major feature, rather than one feature polished. |
| Playing together in person | Same game, different pace: the host can **start a live session** (short timer) when the group sits down and end it afterwards — the story continues exactly where it was. **Input mode** per game: each player acts for themselves, or **one table speaker** types and acts for the whole party. A **TV view** (private link, no login) shows the map, party stats, story, shops and whose turn it is on a big screen. |

---

## 2. Core principle: rules in code, story from the AI

Shops, inventory, gold, HP and a battle map only work if the game state is exact. So:

- **The server owns all game state** in a database: characters, items, gold, HP, conditions, positions, map, quests, the log.
- **Code enforces the rules**: dice, attack rolls, damage, AC, prices, carrying, XP, rests, movement.
- **The AI DM decides and describes.** It reads a snapshot of the state, writes the narration, and changes the world only by calling **DM tools** (`roll_check`, `start_combat`, `grant_item`, `open_shop`, …). The server validates every call — the DM can't hand out an item that doesn't exist or spend gold the party doesn't have.
- **Purely mechanical actions need no AI call.** Buying a sword, moving a token, or a plain weapon attack is resolved by code instantly. The DM is called when something needs judgement or description. This keeps the game fast and keeps AI cost down.

---

## 3. Architecture

```
 Browser (React + TypeScript)
   ├─ World map · Battle map · Character sheet · Inventory · Shop · Story feed · Lobby
   │        ▲  live updates (WebSocket)        │ actions (HTTP)
   ▼        │                                  ▼
 Game server (Python · FastAPI)
   ├─ Auth & accounts ── invites, saved API keys (encrypted)
   ├─ Turn engine ────── phases, deadlines, ready checks, timeout policies
   ├─ Rules engine ───── dice, combat, characters, XP, shops   (ported from skills/dnd/scripts)
   ├─ World generator ── procedural hex map, settlements, battle-map templates
   ├─ DM orchestrator ── builds context, exposes DM tools, applies results
   │     ├─ LocalClaudeCodeEngine  (Claude Agent SDK on the host machine)
   │     └─ ApiKeyEngine           (Anthropic Python SDK, Messages API + tool use)
   ├─ Notifier ───────── in-site, Discord webhook (M1); email / web push (later)
   └─ Database ───────── SQLite locally → Postgres when hosted
```

**Stack**

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite (Postgres later). Python lets us port the skill's existing rules code directly.
- **Frontend:** React + TypeScript (Vite). Maps drawn on HTML canvas with PixiJS. Needs Node.js to build.
- **Realtime:** WebSockets push state changes to everyone viewing a game.
- **Deadlines:** a background task in the server checks for expired rounds every few seconds and resolves them.
- **Repo layout:** a new top-level `game/` folder (`game/server`, `game/web`). `skills/` stays untouched as reference.

**Playing with friends while hosted locally:** friends on your Wi-Fi open `http://<your-PC-IP>:<port>`. Friends elsewhere connect through Tailscale or a Cloudflare Tunnel. Because the game is async, **your PC must be on for rounds to resolve** — especially with the Local Claude Code engine. This is the main reason to move to a hosted server later.

---

## 4. The turn model

Everything in the game runs on one pattern: **a phase opens with a deadline → players act or mark ready → the phase resolves when everyone is done or time runs out.**

### 4.1 Phases

| Phase | What players do | Resolves when | AI call? |
|---|---|---|---|
| **Exploration / roleplay** | Each player writes what their character does (free text, plus optional quick-action chips: *talk, search, sneak, use item, cast*). Actions can be edited until the round resolves. | All submitted, or deadline | Yes — one DM response for the whole round |
| **Travel** | Party proposes a destination on the world map and votes. | Majority/all agree, or deadline | Yes — narrates the journey and any encounter |
| **Shop / downtime** | Browse shops, buy, sell, trade with party, level up, rest. Each player toggles **Ready**. | All ready, or deadline | One short call on entry (shopkeeper flavour); buying and selling are pure code |
| **Combat** | Move and act on the battle map (see 4.4). | Per combat turn | Monster turns + a round narration |
| **Roll request** | When the DM calls for a roll in "players roll" mode, the named player rolls on the site. | Rolled, or deadline (auto-roll on timeout) | No |

### 4.2 Deadlines

Host picks a **round timer** per game, with presets matching how the group plays:

- **Live** — 5 min (everyone at the table)
- **Quick** — 1 hour
- **Daily** — 24 hours
- **Relaxed** — 3 days
- **Custom** — anything from 5 minutes to 5 days

An optional, separate **combat timer** (combat turns are small, so groups often want them shorter). A round resolves early the moment everyone has acted, so a group online together never waits for the timer.

### 4.3 Missed deadlines (host's choice per game)

- **AI plays them** — the DM takes a cautious, in-character action (Dodge in combat, follow the party out of it).
- **Skip** — the character holds; nothing happens for them.
- **Pause** — the game waits for that player; the host can override with *skip now*.

The host can also **nudge** a player (sends a notification) or **force resolve** a round early. (Later: vacation mode, so a player can hand their character to the AI for a few days.)

### 4.4 Combat in an async game

Classic one-at-a-time initiative is painful when each turn might take a day. Host chooses:

- **Side initiative (default for async games)** — all players act during the party's window, in any order; then all monsters act; then the DM narrates the round. One wait per round instead of one per character.
- **Classic initiative** — individual turn order, each turn with the combat timer. Best for Live games.

On their turn a player uses the battle map: move (reachable squares highlighted), then attack, cast, use an item, or write a custom action. Standard attacks and moves resolve in code immediately; custom actions go to the DM. Monster tactics are chosen by the DM via tools; their rolls are made by the server.

### 4.5 Round resolution, step by step

1. Phase opens; deadline set; players notified.
2. Players submit actions (or mark ready).
3. Trigger: everyone done **or** deadline. Apply the timeout policy to anyone missing.
4. DM orchestrator builds the context and calls the DM engine with this round's actions.
5. The DM calls tools (rolls, damage, items, combat start, shop open…); the server validates and applies each one. If a tool needs a player's roll, the round pauses into a **roll request** with its own deadline.
6. DM returns narration (and optionally suggested next actions per player).
7. Server commits state + log entry in one transaction, pushes updates, notifies players, opens the next phase.

---

## 5. DM tools (the AI's only way to change the game)

| Tool | Effect |
|---|---|
| `roll_check(character, ability/skill/save, dc, advantage, hidden)` | Server rolls, or creates a roll request if players roll their own |
| `start_combat(monsters, map_template, placement)` | Creates encounter from SRD monsters, generates battle map, rolls initiative |
| `monster_action(monster, action, target)` | Server resolves the attack/spell with real rolls |
| `apply_damage / heal / add_condition / remove_condition` | Changes HP and conditions |
| `grant_items / remove_items / grant_gold` | Loot and costs; items must exist in the SRD data or be defined as custom items |
| `award_xp(encounter or amount)` | Uses the 5e XP tables |
| `open_shop(type, settlement)` | Starts a shop phase with generated stock |
| `travel(destination) / reveal_hexes / set_location` | World map changes |
| `create_npc / update_npc(attitude, notes)` | NPC roster and dispositions |
| `add_quest / update_quest` | Quest journal |
| `set_scene(type, time, weather)` | Drives backgrounds, sky, ambience |
| `end_round(narration, prompts)` | Finishes the DM's response |

Tools use `strict: true` schemas so arguments are always valid. The same tool definitions back both engines.

---

## 6. DM engines and cost

**One interface, two engines:** `run_turn(context, tools) → narration + applied tool calls`.

- **LocalClaudeCodeEngine** — runs Claude through the Claude Agent SDK (Claude Code as a library) on the host's PC, signed in with their own Claude Code login, with the DM tools exposed as custom tools. For you and friends on a game you host. *Must be verified early in M1: custom tools, latency per call, and that it runs unattended.*
- **ApiKeyEngine** — calls the Claude API with the Anthropic Python SDK (Messages API + tool use). The key comes from the hosting player's account. This is the engine a public site uses.

**Model:** Claude Opus 5.5 (`claude-opus-5-5`) by default. A per-game setting can switch to a cheaper model (Sonnet 5.5) — the host's choice.

**Keeping cost down**
- Mechanics resolved by code — no AI call for buying, moving or plain attacks.
- **Prompt caching:** the DM rules, tool definitions and campaign bible form a stable prefix that is cached; only the latest state and actions change per call.
- Rolling summaries instead of full history (the skill's session-log approach).
- One DM call per round, not per player.

**Rough estimate, to be measured in M1:** with caching, a DM response on Opus 5.5 should cost on the order of **$0.03–$0.10**. A busy evening of ~100 rounds would be roughly **$3–$10**. M1 will log real token usage per call so this can be replaced with real numbers.

**Saved API keys:** encrypted at rest with a server secret (Fernet via `cryptography`, already installed); never sent back to the browser after saving (only the last 4 characters shown); usable only for games that player hosts.

---

## 7. Data model (first pass)

- **User** — login, display name, encrypted API key (optional), notification settings
- **Game** — host, status, settings/modifiers (JSON), DM engine, timers, timeout policy, seed
- **Membership** — user ↔ game, role (host/player/spectator), character
- **Character** — ruleset, race, class(es), level, ability scores, HP, AC, proficiencies, features, spells & slots, conditions, XP, portrait
- **Item / InventoryEntry** — SRD item reference or custom item; quantity; equipped; owner (character or party stash); gold as currency fields
- **WorldMap** — seed, hex cells (biome, elevation, river, road), settlements, points of interest, fog of war per game
- **Location / NPC / Quest / Faction** — campaign entities the DM creates through tools
- **Encounter / BattleMap** — grid, walls, terrain, tokens (position, HP, conditions), initiative or side order, round
- **Shop** — settlement, type, stock with prices, restock time
- **Phase / Round** — type, opened_at, deadline, status, submissions
- **Submission** — player action text + structured action, timestamps
- **LogEntry** — narration, roll results, tool effects (the story feed and the audit trail)
- **Summary** — rolling campaign/arc summaries for DM context

---

## 8. Screens

- **Home / lobby** — your games (whose move it is, time left), create game, join by invite link
- **Game setup** — story type, difficulty and every modifier (section 12), timers, DM engine
- **Character creator** — step-by-step (section 11), or import from D&D Beyond
- **Game screen** (the main view)
  - Centre: **World map** or **Battle map** (tabs; switches automatically when combat starts)
  - Right: **Story feed** (narration, rolls, events) with the action box and countdown at the bottom
  - Left: **Party** (HP bars, conditions, who has acted / is ready)
  - Drawers: **Character sheet** · **Inventory & gold** · **Abilities & spells** · **Quests** · **NPCs met**
- **Shop screen** — shop stock and your inventory side by side, prices, buy/sell, party-trade, and the party's Ready status
- **Settings** — account, saved API key, notifications

Mobile layout follows in M3; M1 targets desktop/laptop browsers.

---

## 9. Procedural world map

- **Seeded hex map** (e.g. 40×30 hexes for M1). Elevation and moisture noise → biomes (plains, forest, hills, mountains, swamp, desert, coast, water); rivers flow downhill; settlements placed by suitability (water, flat land); roads connect them by cheapest path; points of interest (ruins, caves, camps, towers) scattered by biome.
- **Code makes the geography; the AI names and flavours it.** At game creation, one DM call writes a short gazetteer for the generated map (region names, settlement names and character, the main threat) shaped by the chosen story type. Places get fuller descriptions when discovered.
- **Fog of war** — the party sees only hexes they've visited or can see from where they are.
- **Travel** — click a destination; the server computes route, days and supplies; random encounter checks happen in code; the DM narrates what happens on the way.

---

## 10. Battle map

- **Square grid, 5 ft squares**, using the skill's `battlemap.py` rules: diagonal = 5 ft, difficult terrain ×2, walls/obstacles block, cheapest-path movement checks.
- **Generated from templates by scene type** (M1: road ambush, forest clearing, tavern, cave/dungeon room) with randomised obstacles and cover.
- Tokens with HP bars and condition icons; reachable squares highlighted on your turn; click a target to attack (range checked); area-of-effect templates in M2.

---

## 11. Characters

**On-site creator (M1: SRD 2014; 2024 opt-in later)**
1. Race/species → 2. Class → 3. Background → 4. Ability scores (standard array, point buy, or **4d6-drop-lowest rolled by the server and logged**, so no rerolling until you like it) → 5. Skills → 6. Equipment (class pack or starting gold) → 7. Spells (casters) → 8. Name, look, backstory.

Derived numbers (AC, HP, saves, attack bonuses, spell DCs) are calculated by code, reusing `character.py`.

**D&D Beyond import** — paste a character link; reuse `ddb_import.py`, which reads D&D Beyond's character JSON (works only for characters whose sharing is set to **Public**) and flags problems (armour not equipped, no spells prepared…). Imported features outside the SRD come in as text-only custom features. This uses an unofficial endpoint, so it can break without notice; the creator is always the fallback.

---

## 12. Game setup options

| Group | Options |
|---|---|
| **Story** | Type: dungeon crawl, mystery, heist, war, horror, wilderness survival, political intrigue, seafaring, open sandbox · Tone: heroic, gritty, dark, lighthearted · Length: one-shot, short campaign, open-ended |
| **Challenge** | Difficulty: Story, Normal, Hard, Deadly (encounter budgets, monster tactics, healing availability) · Death: standard death saves, permadeath, or heroic (knocked out, never killed) · Rest rules: standard, gritty, epic |
| **Party** | Players 1–6 · Starting level · Starting gold/gear · AI companions to fill empty seats · Leveling: XP or milestone |
| **World** | Magic level: low, standard, high (affects loot and shop stock) · Economy: scarce, standard, rich · Sell price (default 50%) · Ruleset: 2014 or 2024 |
| **Table** | Who rolls: players on site, or automatic · Combat: side or classic initiative · Narration length · Content limits (lines & veils) |
| **Pace** | Round timer · Combat timer · Timeout policy · DM engine and model |

M1 stores all of these and wires up a core set (story type, tone, difficulty, death rule, starting level, timers, timeout policy, who rolls, combat style); the rest become active in M2.

---

## 13. What we reuse from the skill

| From `skills/dnd/` | Becomes |
|---|---|
| `SKILL.md` DM standards, narrative-arc system | The DM system prompt and arc logic |
| `data/dnd5e_srd.json` (+ 2024 dataset) | Rules data for classes, items, spells, monsters, prices |
| `scripts/dice.py` | Dice engine |
| `scripts/combat.py` | Initiative, attack resolution, weapon mastery |
| `scripts/character.py` | AC/HP/derived stats, level up, rests |
| `scripts/xp.py` | Encounter difficulty and XP awards |
| `scripts/battlemap.py` | Grid movement, distance, pathing |
| `scripts/lookup.py` | Spell/feature/item lookups for tooltips |
| `scripts/ddb_import.py` | D&D Beyond import |
| `scripts/oracle.py`, `calendar.py`, `tracker.py` | Random events, world time, conditions/durations |
| Display companion: scene detection, sky canvas, SFX, TTS | Atmosphere features in M4 |

These scripts are written as command-line tools that read and write markdown campaign files, so we **port their logic** into a `rules` package with tests rather than calling them as-is. Not reused: markdown campaign files, the autorun/polling loop, and the Flask display app (replaced by the new server and frontend).

---

## 14. Milestones

### M1 — Thin slice of everything (playable with friends on your PC)

**Done when:** 2–4 friends can, from their browsers, make characters, start a game with chosen options, play async rounds with timers, travel on a hex map to a town, browse a shop and ready up, fight on a battle map, and see HP, inventory and gold update — with either your Claude Code login or a saved API key running the DM.

Scope:
- Accounts (username + password), invite links, saved encrypted API key
- Game setup with the core options from section 12
- Character creator: 2014 SRD, levels 1–3, four classes (Fighter, Rogue, Cleric, Wizard) and the SRD races; D&D Beyond import (basic)
- Turn engine: exploration, travel, shop, combat (side + classic initiative), roll requests; deadlines; all three timeout policies; nudge and force-resolve
- DM orchestrator with both engines, the section-5 tools, prompt caching, and per-call token logging
- World map: generated hex map, fog of war, travel
- Battle map: 4 templates, movement, melee/ranged attacks, monster turns
- Shops: general store and blacksmith, buy/sell, party ready check
- UI: lobby, game screen with map tabs, story feed, party panel, character sheet, inventory, shop
- Notifications: in-site + optional Discord webhook per game
- Tests for the rules engine and turn engine

### M2 — Depth ✅ built
All 12 SRD classes and races to level 5, player-confirmed level-ups, spell preparation and spellbooks, area spells with on-map aiming, concentration, reactions and opportunity attacks, class features in combat, four more battle maps, rests by vote with the rest-rules setting active, haggling, alchemist/magic/temple/inn shops, loot by CR.
*Moved to M3:* the 2024 ruleset (needs the SRD 5.2 dataset built and per-edition class tables) and levels above 5.

### M3 — Async polish ✅ built
Email and web-push notifications with deadline reminders, vacation mode, phone layout, story history with catch-up recaps, spectators, edited-action markers — plus the 2024 rules (SRD 5.2) and levels 6-10 for both rulesets.

### M4 — Atmosphere
Scene backgrounds and sky canvas from the display companion, sound effects, spoken narration (reuse `tts.py`), dice animations, character portraits.

### M5 — Going public
Hosted server (Postgres, cloud), Google/Discord login, bring-your-own-key and/or billing, open lobbies to play with strangers, moderation and reporting, rate limits, content audit (SRD only), published source (AGPL), terms of service and privacy policy.

---

## 15. Before going public

- **License:** the original is AGPL-3.0. A public site must offer its full source code to users. Fine if we're happy to be open source; it rules out a closed-source product.
- **Content:** only SRD content (CC-BY-4.0, with attribution) can ship publicly. The skill's supplemental data scraped from a fan wiki (Xanathar's, Tasha's, etc.) must be excluded.
- **D&D Beyond:** the import uses an unofficial endpoint; it may break, and D&D Beyond's terms should be reviewed before offering it publicly.
- **Competition:** the original authors run a paid hosted version (neuralinitiative.ai). Async multiplayer is a real point of difference.
- **AI provider terms:** a personal Claude Code login can't power a public service; public games use API keys.

---

## 16. Risks

- **AI cost** — measured from M1 onward; mechanics in code and caching are the main levers.
- **DM consistency** — the DM may describe something the state doesn't support; mitigated by tools being the only way to change state, and by giving the DM a fresh state snapshot every call.
- **Resolution time** — a DM response may take 20–60 seconds; fine for async, shown as "the DM is writing…".
- **Local hosting** — rounds only resolve while the host PC is on.
- **Scope** — this is a big game. The thin-slice plan keeps something playable at every step; each milestone ends with a play session.

---

## 17. Open questions (later)

- Game name and art direction
- One character per player per game, or allow a player to run several?
- PvP or party-vs-party ever?
- Max party size beyond 6?
- AI-generated character portraits and scene art?
