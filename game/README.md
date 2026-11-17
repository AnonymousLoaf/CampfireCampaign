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

## Host it on an always-on machine with your own domain

1. **Clone and set up** as in "Run it on your PC" above (Python 3.11+, Node 20+). `web/dist` and `server/data` aren't in git, so build the web app there.
2. **Bring your games along (optional):** stop the old server and copy its whole `server/data` folder (the database, `secret.key` that unlocks saved API keys, and the push keys) into `server/data` on the new machine. Without it the new server starts empty.
3. **Claude Code as the DM:** install Claude Code on that machine, run `claude` once and sign in. Games set to "Claude Code (this PC)" use that login.
4. **Your domain, through a Cloudflare named tunnel** (the domain's DNS must be on Cloudflare):

   ```powershell
   cloudflared tunnel login
   cloudflared tunnel create campfire
   cloudflared tunnel route dns campfire yourdomain.com
   ```

   Then create `%USERPROFILE%\.cloudflared\config.yml` (`~/.cloudflared/config.yml` on Linux/macOS) and run the tunnel as a service so it survives reboots:

   ```yaml
   tunnel: campfire
   credentials-file: C:\Users\<you>\.cloudflared\<tunnel-id>.json
   ingress:
     - hostname: yourdomain.com
       service: http://localhost:8787
     - service: http_status:404
   ```

   ```powershell
   cloudflared service install
   ```

5. **Keep the server running:** set `GAME_PUBLIC_URL=https://yourdomain.com` and start `run.py` at boot (Task Scheduler "at startup" on Windows, a systemd unit on Linux). No `--lan` needed; the tunnel connects to localhost.
6. **Updating:** `git pull`, `npm run build` in `web`, re-run `pip install -r requirements.txt` if it changed, and restart the server (wait until no DM response is in progress).

A Claude subscription is meant for personal use: fine for you and friends, but for a public site switch games to the API-key DM.

## Choosing the Dungeon Master

Pick per game (and change any time in the ⚙ game settings):

- **Claude Code (this PC)** — uses the Claude Code login on the computer running the server. Sign in once: open a terminal, run `claude`, and complete the login.
- **My API key** — save a Claude API key in Settings; games you host use it. Each DM response costs a few cents (see `dm_calls` table for real token usage).
- **Offline test DM** — no AI; scripted narration that still exercises shops, combat, rolls and travel. Free, for trying things out.

## Playing together in person

- **Start live session** (header) switches the game to a short timer while everyone's together; **End live session** goes back to the normal pace. The story continues where it was.
- **Who acts** (game settings): each player, or **one table speaker** who types and acts for the whole party — shops and combat included.
- **📺 TV view** gives a private link (no login) for a TV or laptop across the room: map, party stats, story, shop stock and whose turn it is.

## Fights

Combat is played the tabletop way: theatre of the mind, with the battle map as the table.

- Everyone rolls initiative and acts **one at a time, in order** — each move changes the next. (Deciding what to do between fights stays asynchronous for the whole party.)
- On your turn you **type what your character does** ("I duck behind the cart and throw a dagger at the orc's head"). The DM resolves it by the rules: moves your token, spends your action and bonus action, and asks for your rolls.
- **You roll your own dice**: an attack or spell becomes a Roll button (one roll covers the attack and, on a hit, its damage). With the game's "rolls: auto" setting the game rolls for you.
- Clicking a creature only shows what your character could know: allies' HP and AC; enemies as Unhurt, Wounded or Bloodied, their conditions and how far away they are.
- Your combat panel is a read-only reference card: movement left, action / bonus action / reaction, weapons, spells and slots, features and their uses.
- The enemies act on their own turns (the DM rolls behind the screen), and the DM narrates exactly what the dice did.
- Miss your turn's deadline and the timeout policy applies (the AI plays you cautiously, or you Dodge); players on vacation are played by the AI.

## Travel and the world map

- Travel is typed like any other action: "we take the east road to the next town", "we head north into the hills". When the party agrees, the DM moves you (to a named place, or a direction and distance); if you disagree, the DM lets you settle it first.
- Clicking the map only shows what your party knows: a town's size, description and shops, a ruin or cave, the terrain, and how far away it is. Unexplored land stays a mystery.

## Your games and characters

- On the Home page the host can **Delete game** (gone for everyone; characters are kept), and players can **Leave game** (their character keeps everything it earned and is free for another game). Spectators can **Stop watching**.
- In a game, the host can **remove** a player from the party panel. Nobody can leave in the middle of a fight their character is in.
- A character can be deleted once it isn't in a game.

## Dice

Every d20 a player rolls tumbles across a felt table in the middle of everyone's screen, lands on the real result, then shows the total and Success/Failure (Hit/Miss for attacks). Turn the dice off in Settings.

## Notifications

Each player sets their own in Settings: push on this device, email, and a reminder before their deadline.

- **Push** works out of the box on `http://localhost`. Phones need the game served over **HTTPS** (a Cloudflare Tunnel or Tailscale HTTPS gives you that) — browsers only allow push on secure pages. The server makes its own VAPID keys in `server/data/`.
- **Email** needs an SMTP account. Set these before starting the server:

```powershell
$env:GAME_SMTP_HOST = "smtp.example.com"   # your mail provider's SMTP server
$env:GAME_SMTP_PORT = "587"
$env:GAME_SMTP_USER = "you@example.com"
$env:GAME_SMTP_PASSWORD = "app-password"
$env:GAME_SMTP_FROM = "Async D&D <you@example.com>"
$env:GAME_PUBLIC_URL = "https://your-game-address"   # so emails can link back to the game
```

Nothing is sent during a live session.

## Tests

```powershell
cd server
.venv\Scripts\python.exe -m pytest -q
```

`tests/test_m3.py` covers every class to level 10 in both rulesets, 2024 creation, masteries, feats, 2024 monsters and fights, and the notification/vacation/spectator/history API; `tests/test_data_m3.py` validates the rules tables against both datasets. `tests/test_rules.py` covers dice, characters, shops and full auto-played fights; `tests/test_m2.py` covers every class to level 5, level-ups, preparation, area shapes, Fireball, Extra Attack, features, concentration, shops and loot; `tests/test_flow.py` plays two-player games end to end with the offline DM (M1 loop, and an M2 loop with rests, haggling, Rage and an area spell).

## What's in (M1 + M2)

**M1:** accounts and invites; character creator and D&D Beyond import (public characters); game setup options; exploration rounds with deadlines and three timeout policies; procedural hex world map with fog and travel votes; browsable shops with a party ready check; grid combat (side or classic initiative); NPC and quest journals; live sessions, single-speaker mode, TV view; Discord webhook notifications.

**M2:**
- **All 12 SRD classes, levels 1–5**, one SRD subclass each; Half-Elf and Dragonborn choices; racial traits (Relentless Endurance, Lucky, Savage Attacks, resistances, Breath Weapon).
- **Levelling the player confirms**: HP average or roll, ability score improvement at 4, subclass, fighting style, expertise, new cantrips/spells.
- **Spellcasting**: full, half and pact casters; spell preparation (cleric, druid, paladin, wizard spellbook); ~60 combat-resolved spells including area spells with on-map aiming (sphere, cube, cone, line), concentration with CON saves, upcasting, cantrip scaling.
- **Combat depth**: Extra Attack, opportunity attacks and reactions, Uncanny Dodge, monster multiattack, ammunition, conditions with real effects (restrained, frightened, stunned, prone…), class features as buttons (Rage, Reckless Attack, Flurry of Blows, Stunning Strike, Divine Smite, Lay on Hands, Bardic Inspiration, Cunning Action, Channel Divinity…), smarter AI turns (heals, cantrips).
- **Shops**: general, blacksmith, alchemist, magic (priced by rarity), temple and inn services; haggling (one Persuasion check per character per shop).
- **Rests** by party vote (rest rules: standard, gritty, epic), with wilderness interruptions; **loot** by CR after victories; four more battle maps (dungeon, ruins, camp, swamp).

**M3:**
- **2024 rules (SRD 5.2)** alongside 2014: species and lineages, background ability scores (+2/+1 or +1/+1/+1), origin feats (Alert, Magic Initiate, Savage Attacker, Skilled), weapon masteries applied in combat (Vex, Topple, Sap, Slow, Push, Graze, Cleave), feats instead of an ability increase, 2024 class tables and spells, 2024 monster stat blocks, exhaustion. Pick the ruleset per game; characters belong to one ruleset. The 2024 data is built with `skills/dnd/scripts/build_srd.py --ruleset 2024` and lives in `server/rulesdata/`.
- **Levels 1–10** for both rulesets, with 4th/5th-level slots and spells and the tier-2 features (Aura of Protection, Brutal Critical, Indomitable, Divine Strike, Empowered Evocation, Potent Cantrip, and more).
- **Notifications:** browser push, email, and deadline reminders.
- **Vacation mode:** "I'm away" — the AI plays your character cautiously until you're back.
- **Spectators** can follow a game without a character.
- **History:** a Story tab with the whole campaign, a "Since you were last here" card, and "Catch me up" (the DM summarises what you missed).
- **Phone layout:** bottom tabs (Story / Map / Party / Sheet), touch pan and pinch-zoom on maps, full-screen dialogs.

**M4:**
- **Atmosphere:** scene backgrounds that follow the location, time of day and battle map; an animated sky (sun and moon arc, stars, clouds, rain, snow, fog); synthesized ambience and sound effects (no audio files); spoken narration through the browser's own voices; animated dice rolls.
- **Portraits:** upload your own (cropped to 256×256), or get a generated crest; shown everywhere, including battle-map tokens.
- **Custom content library:** private homebrew or content from books you own — feats, features, spells, items, backgrounds, species traits — attached to characters; the DM reads them.
- **D&D Beyond import, fixed:** 2024 ("5.5") characters import with the 2024 rules; features, feats and traits the free rules don't cover are kept as custom entries the DM can use; non-SRD subclasses keep their own name and features.
- **The DM is told which ruleset the game uses** (it said "SRD 5.1, levels 1-5" before).

Not yet: levels above 10, monster spellcasting, opportunity attacks along the path (they check start and end squares), Great Weapon Fighting rerolls, ammunition recovery, Evasion (no monster area attacks yet), public hosting.
