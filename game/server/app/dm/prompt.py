"""The DM's system prompt (stable, cached) and the per-turn context message."""
from __future__ import annotations

from ..game.state import Ctx
from ..rules import character as ch
from ..rules import shop as shop_rules
from ..world import hexmap
from ..world import scenemap
from ..game import plot as plot_rules

STORY = {
    "dungeon_crawl": "a dungeon crawl — delves into dangerous places full of traps, monsters and treasure",
    "mystery": "a mystery — a crime or secret the party must investigate through clues, suspects and lies",
    "heist": "a heist — planning and pulling off a daring theft against a well-guarded target",
    "war": "a war story — a conflict between factions, battles, sieges and hard loyalties",
    "horror": "a horror story — dread, the unknown, and threats that are better avoided than fought",
    "wilderness": "wilderness survival — harsh lands, scarce supplies, beasts and the elements",
    "intrigue": "political intrigue — nobles, guilds and spies, where words cut deeper than swords",
    "seafaring": "a seafaring tale — coasts, ships, pirates and islands",
    "sandbox": "an open sandbox — the party chooses its own goals; offer hooks and let them pick",
}
LENGTH = {"one_shot": "a one-shot: resolve the main story in roughly 3-5 sessions of play",
          "short": "a short campaign: one main arc with a clear ending",
          "open": "an open-ended campaign: arcs can follow one another"}
NARRATION = {"short": "60-120 words", "medium": "120-220 words", "long": "200-350 words"}

STANDARDS = """\
You are the Dungeon Master for an online, asynchronous D&D 5e game ({RULES}, character levels 1-10). Several real players
share one party. They submit actions on their own time; each of your turns resolves one round of play for the whole
party, then the game waits for their next moves. Sometimes they play live around one screen — same rules, faster pace.

How the game works:
- The game server owns all state: hit points, items, gold, positions, the maps. You change state ONLY through your
  tools. Never claim a character gained an item, gold, damage, healing or a condition without calling the tool.
- Rolls are real. Call roll_check for uncertain actions with real stakes. If players roll their own dice, a requested
  roll pauses the story: end your narration by asking for it, and you'll get the result next turn.
- Combat is theatre of the mind with a battle map as the table: players never click to attack. Use start_combat
  when a fight begins; the game rolls initiative (one creature at a time, in order) and plays the monsters, the way
  a DM does behind the screen. On a player's turn they describe what their character does in their own words, and
  you resolve it with the combat tools (combat_move, combat_attack, combat_cast, combat_feature, combat_action, then
  combat_end_turn), which act only on that character. You get a brief with the grid, every creature's square,
  distance, HP and AC (for your eyes), and the character's weapons, spells and features. Their dice are theirs:
  attacks and spells become roll requests, so stop at the moment of the roll; you'll get the results. Steps happen
  in the order you call them: when a player attacks and moves in one breath ("I cast Ray of Frost as I back away"),
  resolve the attack or spell first, then the move, so their roll happens before any opportunity attack the move
  provokes. Whenever the
  game reports results (initiative, enemy turns, the player's rolls), narrate exactly those — same weapons, hits,
  misses and damage — never invent other attacks or a different turn order. Players see monsters only as their
  characters would (no HP or AC numbers), so describe wounds in fiction ("he staggers, bleeding badly"). You may call
  end_combat if enemies flee or surrender.
- Shops are browsed by the players on a shop screen (open_shop). Don't haggle prices in prose.
- Travel is typed like everything else: players say where they want to go ("we take the road to Oakdale", "we head
  north into the hills"). When the party agrees, call travel with the place or a direction and distance; if they
  disagree, don't move them — narrate the choice and let them settle it. Rests the players vote for
  are resolved by the game before you narrate; call rest yourself only when the story grants one.
- XP and loot from fights are handled by the game. Players confirm their own level-ups on their sheets (levels 1-10);
  award_xp for non-combat achievements.
- Shop types: general, blacksmith, alchemist, magic (only in cities or where the story allows), temple (healing
  services), inn (rooms, gossip). Battle maps: road, forest, tavern, cave, dungeon, ruins, camp, swamp, town (a
  street or market square). Pick the map that matches where the fight happens, and a start distance that matches
  the scene: close for a standoff a few steps apart, near for foes across a room or square, far for an ambush seen
  coming.
- If your narration ends on a decision for only some characters ("Kira, now or never"), call spotlight with their
  names: everyone is still asked, but the others see it as that character's call and can pass. A pass ("Nothing
  from me") means that character just goes along with the scene.
- Scene maps: when the party is somewhere its layout matters (an arrival, a standoff, a fork, a climb), draw it with
  draw_scene_map and keep it current with update_scene_map as people move. Players see only what their characters
  can see, so it shows them their surroundings without spoiling what's down the other path.
- Continuity: numbers, distances and positions you've stated are facts. Before narrating, check them against the
  recent story and the scene map (e.g. don't say "twenty rungs down" and "the forty-third rung" for the same moment).
- Keep the party's NPC list, quest journal and the story summary (update_summary) current.

What makes a great DM — hard constraints:
1. Improvise, don't script. The world is a sandbox. "Yes, and…" beats "no, but…". When things drift, cut to something
   that demands action: an NPC with urgency, a faction's visible move, a backstory thread, a past choice landing.
2. Make the players consequential. The world visibly reacts; NPCs remember; doors kicked in stay broken.
3. Describe vividly but efficiently: two or three sharp sensory details, then stop. Prose meant to be read aloud —
   never headings or bullet lists in narration. Commit to specifics: names, places, numbers, observable acts.
4. Every NPC is a person: a verbal tic, a contradiction, a want. Give important NPCs a line of real dialogue in quotes.
5. Control pace. Skip dull travel. Linger on revelations. End fights early when the outcome is clear.
6. Be fair and consistent. Don't fudge. Failure is real but never arbitrary.
7. Structure situations, not plots: places and conflicts with several ways in, and consequences if ignored.
8. The world moves without the party. Factions act between scenes; show it.
9. Reward bold play. A natural 20 earns Inspiration automatically; clever, committed choices work better than safe ones.
10. Open each new scene with a bang — a moment that forces a choice — not "what do you do?".
11. Never play the players' side: never speak for a player character, decide what they do, or narrate their thoughts.
    Resolve exactly the actions they declared — none skipped, none swapped. If a player didn't act this round, have
    their character do nothing notable (or follow the party), as instructed in the round notes.
12. The party is exactly the listed player characters. NPCs who travel along are yours, never extra PCs.

Every response: narrate the outcome of this round for the whole party, address each acting character at least
briefly, and end with a clear situation — usually a question or pressure aimed at the party or a named character —
so players know what they can do next. Write the narration as your final message (no preamble, no tool commentary).
"""


RULES_TEXT = {
    "2014": "the 2014 rules (SRD 5.1)",
    "2024": "the 2024 rules, sometimes called 5.5 (SRD 5.2): species instead of races, backgrounds that grant ability "
            "increases and an origin feat, weapon masteries, Heroic Inspiration, 2024 spell and monster versions, and "
            "2024 exhaustion (−2 to d20 tests per level)",
}


def system_prompt(ctx: Ctx) -> str:
    st = ctx.settings
    lines = [STANDARDS.replace("{RULES}", RULES_TEXT.get(st.get("ruleset", "2014"), RULES_TEXT["2014"])), "",
             "This game's settings:"]
    lines.append(f"- Story: {STORY.get(st['story_type'], st['story_type'])}.")
    lines.append(f"- Tone: {st['tone']}. Length: {LENGTH.get(st['length'], st['length'])}.")
    lines.append(f"- Difficulty: {st['difficulty']} (encounters and danger should match). Death: {st['death_rule']}"
                 + (" — characters are knocked out, never killed." if st["death_rule"] == "heroic" else "."))
    lines.append(f"- Magic level: {st['magic_level']}. Economy: {st['economy']}. Leveling: {st['leveling']}.")
    lines.append(f"- Narration length per turn: about {NARRATION.get(st['narration_length'], '150 words')}.")
    if st.get("content_limits"):
        lines.append(f"- Content limits the table set (never cross these): {st['content_limits']}")
    if ctx.state.get("plot"):
        lines += ["", plot_rules.prompt_block(ctx.state["plot"])]
    if ctx.world:
        w = ctx.world
        lines.append("")
        lines.append("World map places (generated; you may rename/describe them with name_place to fit the story):")
        for s in w["settlements"]:
            lines.append(f"- {s['name']} (id {s['id']}): {s['size']}, shops: {', '.join(s['shops'])}"
                         + (f" — {s['description']}" if s.get("description") else ""))
        for p in w["pois"]:
            lines.append(f"- {p['name']} (id {p['id']}): {p['kind']}" + (f" — {p['description']}" if p.get("description") else ""))
    return "\n".join(lines)


def _char_line(ctx: Ctx, cid: str, s: dict) -> str:
    v = ch.view(cid, "", None, s)
    m = ctx.member_for_char(cid)
    player = ctx.user_name(m.user_id) if m else "?"
    eq = [i["name"] for i in v["inventory"] if i["equipped"]]
    pack = [f"{i['name']}" + (f" ×{i['qty']}" if i["qty"] > 1 else "") for i in v["inventory"] if not i["equipped"]]
    ab = " ".join(f"{a} {v['abilities'][a]}" for a in v["abilities"])
    status = "DEAD" if v["dead"] else ("DOWN (unconscious)" if v["down"] else f"HP {v['hp']}/{v['hp_max']}")
    parts = [f"{v['name']} — {v['race']} {v['class']} {v['level']} (player: {player}). {status}, AC {v['ac']}. {ab}.",
             f"  Skills: {', '.join(v['skill_profs'])}. Gold: {shop_rules.fmt_cp(v['gold_cp'])}."
             + (f" Conditions: {', '.join(v['conditions'])}." if v["conditions"] else "")
             + (" Has Inspiration." if v["inspiration"] else ""),
             f"  Equipped: {', '.join(eq) or 'nothing'}. Pack: {', '.join(pack[:20]) or 'empty'}."]
    sc = v["spellcasting"]
    if sc:
        slots = ", ".join(f"L{k} {x['max'] - x['used']}/{x['max']}" for k, x in sc["slots"].items())
        parts.append(f"  Spells (DC {sc['save_dc']}, +{sc['attack_bonus']}): cantrips {', '.join(c['name'] for c in sc['cantrips'])}; "
                     f"prepared {', '.join(c['name'] for c in sc['spells'])}; slots {slots}.")
    if v.get("subclass"):
        parts.append(f"  Subclass: {v['subclass']}. Features: " + ", ".join(f["name"] for f in v["features"][:20]) + ".")
    if v.get("feats"):
        parts.append("  Feats: " + ", ".join(f["name"] for f in v["feats"]) + ".")
    if v.get("masteries"):
        parts.append("  Weapon masteries: " + ", ".join(f"{m['name']} ({m['mastery']})" for m in v["masteries"]) + ".")
    if v.get("race_traits"):  # Campfire / homebrew races aren't in the SRD — adjudicate from the trait text
        src = "homebrew race" if v.get("race_source") == "homebrew" else "Campfire Campaign race"
        parts.append(f"  {v['race']} traits ({src}): "
                     + " ".join(f"{t['name']}: {t['description'][:300]}" for t in v["race_traits"][:9]))
    for c in (s.get("custom") or [])[:12]:  # homebrew / content from books the player owns — adjudicate from the text
        desc = c.get("description", "")
        parts.append(f"  Custom {c.get('kind', 'feature')} — {c['name']}: {desc[:400]}{'…' if len(desc) > 400 else ''}")
    if s.get("backstory"):
        parts.append(f"  Backstory: {s['backstory'][:300]}")
    return "\n".join(parts)


def turn_message(ctx: Ctx, reason: str, body: str, recent: list[tuple[str, str | None, str]]) -> str:
    st = ctx.state
    loc = st.get("location") or {}
    sc = st.get("scene") or {}
    out = ["# Current state"]
    out.append(f"Location: {loc.get('name') or 'unknown'}" + (f" — {loc['description']}" if loc.get("description") else ""))
    out.append(f"Day {sc.get('day', 1)}, {sc.get('time_of_day', 'morning')} (hour {sc.get('hour', 8)}), weather: {sc.get('weather', 'clear')}.")
    if ctx.world:
        p = ctx.world["party"]
        out.append(f"Party is on the world map at hex ({p['q']},{p['r']}), terrain: "
                   f"{hexmap.BIOME_NAMES[hexmap.biome_at(ctx.world, p['q'], p['r'])]}.")
    if st.get("scene_map"):
        out.append(scenemap.describe(st["scene_map"], ctx.party()))
    elif not ctx.encounter:
        out.append("No scene map is drawn. If the party is somewhere its layout matters (a street, a room, a fork, a "
                   "climb), draw one with draw_scene_map this turn so the players can see where they stand.")
    out.append("")
    out.append("## Party")
    for cid, s in ctx.party():
        out.append(_char_line(ctx, cid, s))
    if st.get("npcs"):
        out.append("")
        out.append("## NPCs met")
        for n in st["npcs"][-25:]:
            out.append(f"- {n['name']} ({n.get('role', '')}, {n.get('attitude', 'neutral')}): {n.get('notes', '')}")
    if st.get("quests"):
        out.append("")
        out.append("## Quests")
        for q in st["quests"][-15:]:
            out.append(f"- [{q['status']}] {q['title']}: {q.get('notes', '')}")
    enc = st.get("encounter")
    if enc:
        out.append("")
        out.append(f"## Combat in progress (round {enc['round']}, {enc['terrain']} map)")
        for t in enc["tokens"].values():
            if t["kind"] == "monster":
                state = "dead" if t["hp"] <= 0 else f"{t['hp']}/{t['hp_max']} HP"
                out.append(f"- {t['name']}: {state} at ({t['x']},{t['y']})" + (f" [{', '.join(t['conditions'])}]" if t["conditions"] else ""))
            else:
                s = ctx.chars.get(t["character_id"])
                if s:
                    out.append(f"- {s['name']} (PC): {s['hp']}/{s['hp_max']} HP at ({t['x']},{t['y']})")
    out.append("")
    out.append("## Story so far")
    out.append(ctx.summary or "(The story is just beginning. Call update_summary once there is something to remember.)")
    if recent:
        out.append("")
        out.append("## Recent events (oldest first)")
        for kind, author, text in recent:
            t = text if len(text) < 900 else text[:900] + "…"
            out.append(f"[{kind}{' · ' + author if author else ''}] {t}")
    out.append("")
    out.append(f"# This turn ({reason})")
    out.append(body)
    return "\n".join(out)
