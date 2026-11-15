# Async D&D — the web game (M1)

A browser D&D 5e game with an AI Dungeon Master that a party plays **on their own time** (each round has a deadline from 5 minutes to 5 days) or **live around one screen**. Design: [docs/game/DESIGN.md](../docs/game/DESIGN.md). API: [docs/game/API.md](../docs/game/API.md).

## Run it on your PC

One-time setup (Windows PowerShell, from this `game` folder):

```powershell
cd server
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\web
npm install
npm run build
```

Start the server (serves the game at http://localhost:8787):

```powershell
cd server
.venv\Scripts\python.exe run.py
```

Let friends on your Wi-Fi join with `run.py --lan`, then they open `http://<your PC's IP>:8787`. Friends elsewhere can reach it through Tailscale or a Cloudflare Tunnel. Rounds only resolve while the server is running.

Frontend development with hot reload: run the server as above, then `npm run dev` in `web` and open http://localhost:5173.

## Choosing the Dungeon Master

Pick per game (and change any time in the ⚙ game settings):

- **Claude Code (this PC)** — uses the Claude Code login on the computer running the server. Sign in once: open a terminal, run `claude`, and complete the login.
- **My API key** — save a Claude API key in Settings; games you host use it. Each DM response costs a few cents (see `dm_calls` table for real token usage).
- **Offline test DM** — no AI; scripted narration that still exercises shops, combat, rolls and travel. Free, for trying things out.

## Playing together in person

- **Start live session** (header) switches the game to a short timer while everyone's together; **End live session** goes back to the normal pace. The story continues where it was.
- **Who acts** (game settings): each player, or **one table speaker** who types and acts for the whole party — shops and combat included.
- **📺 TV view** gives a private link (no login) for a TV or laptop across the room: map, party stats, story, shop stock and whose turn it is.

## Tests

```powershell
cd server
.venv\Scripts\python.exe -m pytest -q
```

`tests/test_rules.py` covers dice, characters, shops and full auto-played fights; `tests/test_m2.py` covers every class to level 5, level-ups, preparation, area shapes, Fireball, Extra Attack, features, concentration, shops and loot; `tests/test_flow.py` plays two-player games end to end with the offline DM (M1 loop, and an M2 loop with rests, haggling, Rage and an area spell).

## What's in (M1 + M2)

**M1:** accounts and invites; character creator and D&D Beyond import (public characters); game setup options; exploration rounds with deadlines and three timeout policies; procedural hex world map with fog and travel votes; browsable shops with a party ready check; grid combat (side or classic initiative); NPC and quest journals; live sessions, single-speaker mode, TV view; Discord webhook notifications.

**M2:**
- **All 12 SRD classes, levels 1–5**, one SRD subclass each; Half-Elf and Dragonborn choices; racial traits (Relentless Endurance, Lucky, Savage Attacks, resistances, Breath Weapon).
- **Levelling the player confirms**: HP average or roll, ability score improvement at 4, subclass, fighting style, expertise, new cantrips/spells.
- **Spellcasting**: full, half and pact casters; spell preparation (cleric, druid, paladin, wizard spellbook); ~60 combat-resolved spells including area spells with on-map aiming (sphere, cube, cone, line), concentration with CON saves, upcasting, cantrip scaling.
- **Combat depth**: Extra Attack, opportunity attacks and reactions, Uncanny Dodge, monster multiattack, ammunition, conditions with real effects (restrained, frightened, stunned, prone…), class features as buttons (Rage, Reckless Attack, Flurry of Blows, Stunning Strike, Divine Smite, Lay on Hands, Bardic Inspiration, Cunning Action, Channel Divinity…), smarter AI turns (heals, cantrips).
- **Shops**: general, blacksmith, alchemist, magic (priced by rarity), temple and inn services; haggling (one Persuasion check per character per shop).
- **Rests** by party vote (rest rules: standard, gritty, epic), with wilderness interruptions; **loot** by CR after victories; four more battle maps (dungeon, ruins, camp, swamp).

Not yet (M3+): levels above 5, 2024 rules, monster spellcasting, opportunity attacks along the path (they check start and end squares), Great Weapon Fighting rerolls, ammunition recovery, email/push notifications, mobile layout polish, public hosting.
