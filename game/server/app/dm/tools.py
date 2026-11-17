"""DM tools — the AI DM's only way to change the game. Every call is validated here."""
from __future__ import annotations

import random
import uuid

from ..game import combat, turns
from ..game.state import Ctx
from ..rules.rulesets import R
from ..rules import character as ch
from ..rules import dice, srd
from ..rules import shop as shop_rules
from ..rules import xp as xp_rules
from ..rules.character import RulesError
from ..rules.classes import ABILITIES, SKILLS
from ..world import battlemap as bm
from ..world import hexmap

TOOLS: list[dict] = [
    {"name": "roll_check",
     "description": "Call for an ability check, skill check or saving throw from one player character. If players roll "
                    "their own dice, this requests the roll and you must stop and wait — the result comes in your next "
                    "turn. Hidden checks (Perception, Insight, Stealth you don't want to reveal) are rolled immediately.",
     "input_schema": {"type": "object", "properties": {
         "character": {"type": "string", "description": "Player character name"},
         "check": {"type": "string", "description": "A skill (e.g. 'Stealth'), an ability ('STR'..'CHA'), or '<ABILITY> save'"},
         "dc": {"type": "integer", "minimum": 1, "maximum": 30},
         "advantage": {"type": "string", "enum": ["normal", "advantage", "disadvantage"]},
         "hidden": {"type": "boolean", "description": "Roll secretly now instead of asking the player"}},
         "required": ["character", "check", "dc"]}},
    {"name": "start_combat",
     "description": "Start a fight on the battle map with SRD monsters. Combat is then played turn by turn on the grid; "
                    "you narrate rounds afterwards. Keep encounters fair for the party's level and the game difficulty.",
     "input_schema": {"type": "object", "properties": {
         "monsters": {"type": "array", "items": {"type": "object", "properties": {
             "name": {"type": "string", "description": "SRD monster name, e.g. 'Goblin', 'Wolf', 'Bandit', 'Skeleton'"},
             "count": {"type": "integer", "minimum": 1, "maximum": 8}}, "required": ["name", "count"]}},
         "terrain": {"type": "string", "enum": ["road", "forest", "tavern", "cave", "dungeon", "ruins", "camp", "swamp", "town"],
                     "description": "The battle map; 'town' is a street or market square"},
         "distance": {"type": "string", "enum": ["close", "near", "far"],
                      "description": "How far apart the sides start: close = 10-20 ft (a standoff), near = 30-40 ft, "
                                     "far = opposite ends of the map (default)"}},
         "required": ["monsters", "terrain"]}},
    {"name": "end_combat",
     "description": "End the current fight without a victory (the enemies flee or surrender, or the party escapes).",
     "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}},
    # Typed combat: these act only on the player character whose turn it is, in the order you call them.
    {"name": "combat_move",
     "description": "Move the character whose turn it is. Give a square (x, y), or `toward` a creature (stops within "
                    "stop_within_ft, default 5 = adjacent), or `away_from` a creature (as far as their movement allows). "
                    "Uses their remaining movement; difficult terrain costs double; leaving an enemy's reach provokes an "
                    "opportunity attack unless they Disengaged. Fails if the square is out of reach.",
     "input_schema": {"type": "object", "properties": {
         "x": {"type": "integer"}, "y": {"type": "integer"},
         "toward": {"type": "string", "description": "creature name"},
         "away_from": {"type": "string", "description": "creature name"},
         "stop_within_ft": {"type": "integer", "minimum": 5, "maximum": 120}}}},
    {"name": "combat_attack",
     "description": "One weapon attack by the character whose turn it is (call it once per attack; Extra Attack allows "
                    "more). The player rolls the attack (and damage on a hit) unless the game auto-rolls; until then the "
                    "result is unknown, so end your narration by asking for the roll. Fails if out of range or no "
                    "attacks are left.",
     "input_schema": {"type": "object", "properties": {
         "target": {"type": "string"}, "weapon": {"type": "string", "description": "attack id or name from the brief"}},
         "required": ["target", "weapon"]}},
    {"name": "combat_cast",
     "description": "Cast one of the acting character's spells that the game resolves (see the brief). Give `target` "
                    "for a creature, or x/y for an area's point. Spell attacks and damage are rolled by the player.",
     "input_schema": {"type": "object", "properties": {
         "spell": {"type": "string"}, "target": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"},
         "slot_level": {"type": "integer", "minimum": 1, "maximum": 9}}, "required": ["spell"]}},
    {"name": "combat_feature",
     "description": "Use one of the acting character's combat features (Second Wind, Action Surge, Rage, Flurry of "
                    "Blows, Cunning Action, Lay on Hands, Bardic Inspiration…) by id or name, with a target if it needs one.",
     "input_schema": {"type": "object", "properties": {
         "feature": {"type": "string"}, "target": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}},
         "required": ["feature"]}},
    {"name": "combat_action",
     "description": "A standard action by the acting character: dodge, dash, disengage, or (spending the action, resolved "
                    "by you with roll_check/apply_damage/add_condition) hide, help, ready, use_item, other.",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["dodge", "dash", "disengage", "hide", "help", "ready", "use_item", "other"]},
         "note": {"type": "string", "description": "what exactly they do, for hide/help/ready/use_item/other"}},
         "required": ["action"]}},
    {"name": "combat_end_turn",
     "description": "End the acting character's turn once everything they did is resolved (call it after the player's "
                    "rolls came back, not while rolls are pending). The enemies then take their turns; the result tells "
                    "you what they did and whose turn is next, so narrate it all and end by turning to that character.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "apply_damage",
     "description": "Deal damage to a player character or a monster on the battle map (traps, falls, environmental harm).",
     "input_schema": {"type": "object", "properties": {
         "target": {"type": "string"}, "amount": {"type": "integer", "minimum": 0, "maximum": 200},
         "damage_type": {"type": "string"}}, "required": ["target", "amount"]}},
    {"name": "heal",
     "description": "Restore hit points to a player character.",
     "input_schema": {"type": "object", "properties": {
         "target": {"type": "string"}, "amount": {"type": "integer", "minimum": 1, "maximum": 200}},
         "required": ["target", "amount"]}},
    {"name": "add_condition",
     "description": "Give a condition (Poisoned, Frightened, Prone, Restrained, Blinded, Charmed, Exhaustion…) to a character or monster.",
     "input_schema": {"type": "object", "properties": {"target": {"type": "string"}, "condition": {"type": "string"}},
                      "required": ["target", "condition"]}},
    {"name": "remove_condition",
     "description": "Remove a condition from a character or monster.",
     "input_schema": {"type": "object", "properties": {"target": {"type": "string"}, "condition": {"type": "string"}},
                      "required": ["target", "condition"]}},
    {"name": "grant_item",
     "description": "Give an item to a player character (loot, rewards, gifts). Use an SRD item name when one fits "
                    "(e.g. 'Potion of Healing', 'Longsword', 'Rope, hempen (50 feet)'); otherwise describe a custom item "
                    "(trinkets, keys, letters, gems) with a value.",
     "input_schema": {"type": "object", "properties": {
         "character": {"type": "string"}, "item": {"type": "string"}, "quantity": {"type": "integer", "minimum": 1, "maximum": 100},
         "custom_description": {"type": "string", "description": "Only for items not in the SRD"},
         "custom_value_gp": {"type": "number", "minimum": 0, "maximum": 10000}},
         "required": ["character", "item"]}},
    {"name": "remove_item",
     "description": "Take an item from a player character (used up, stolen, handed over).",
     "input_schema": {"type": "object", "properties": {
         "character": {"type": "string"}, "item": {"type": "string"}, "quantity": {"type": "integer", "minimum": 1}},
         "required": ["character", "item"]}},
    {"name": "grant_gold",
     "description": "Give (positive) or charge (negative) gold. character may be 'party' to split evenly among living characters.",
     "input_schema": {"type": "object", "properties": {
         "character": {"type": "string"}, "gp": {"type": "number", "minimum": -10000, "maximum": 10000}},
         "required": ["character", "gp"]}},
    {"name": "award_xp",
     "description": "Award experience to every living party member for overcoming a non-combat challenge (combat XP is "
                    "awarded automatically). In milestone games set milestone=true to level everyone up instead.",
     "input_schema": {"type": "object", "properties": {
         "xp_each": {"type": "integer", "minimum": 0, "maximum": 5000}, "milestone": {"type": "boolean"},
         "reason": {"type": "string"}}, "required": ["reason"]}},
    {"name": "open_shop",
     "description": "Let the party browse a shop. The game shows a shop screen where players buy and sell themselves; "
                    "the story continues when everyone is ready. Use when they visit a market, smith or trader.",
     "input_schema": {"type": "object", "properties": {
         "shop_type": {"type": "string", "enum": ["general", "blacksmith", "alchemist", "magic", "temple", "inn"]},
         "name": {"type": "string", "description": "Shop name"}, "keeper": {"type": "string", "description": "Shopkeeper name and one-line description"}},
         "required": ["shop_type", "name", "keeper"]}},
    {"name": "travel",
     "description": "Move the party on the world map once they've agreed where to go. Give a settlement or place of "
                    "interest by name, or, for open country, a compass direction and how far (in days; a day is about "
                    "4 hexes, 24 miles on easy ground). Returns the days taken and the terrain.",
     "input_schema": {"type": "object", "properties": {
         "destination": {"type": "string", "description": "A place name from the world map"},
         "direction": {"type": "string", "enum": ["north", "northeast", "east", "southeast", "south", "southwest",
                                                  "west", "northwest"]},
         "days": {"type": "number", "minimum": 0.25, "maximum": 10, "description": "With direction: how far to go"}},
         "required": []}},
    {"name": "set_scene",
     "description": "Update the current location, its description, time of day and weather; optionally advance the clock.",
     "input_schema": {"type": "object", "properties": {
         "location_name": {"type": "string"}, "description": {"type": "string"},
         "scene_type": {"type": "string", "enum": ["town", "tavern", "wilderness", "forest", "dungeon", "cave", "ruins",
                                                    "road", "castle", "temple", "swamp", "mountain", "coast"]},
         "time_of_day": {"type": "string", "enum": ["dawn", "morning", "midday", "afternoon", "evening", "night"]},
         "weather": {"type": "string"}, "advance_hours": {"type": "integer", "minimum": 0, "maximum": 240}},
         "required": []}},
    {"name": "rest",
     "description": "The party takes a short (1 hour) or long (8 hours) rest: hit points, spell slots and features recover.",
     "input_schema": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["short", "long"]}},
                      "required": ["kind"]}},
    {"name": "upsert_npc",
     "description": "Record or update an NPC the party has met (shown in the party's NPC list).",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}, "role": {"type": "string"}, "attitude": {"type": "string",
                                                                           "enum": ["friendly", "neutral", "wary", "hostile"]},
         "notes": {"type": "string"}}, "required": ["name"]}},
    {"name": "upsert_quest",
     "description": "Record or update a quest in the party's journal.",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"}, "status": {"type": "string", "enum": ["active", "done", "failed"]},
         "notes": {"type": "string"}}, "required": ["title"]}},
    {"name": "name_place",
     "description": "Rename or describe a generated settlement or place of interest on the world map (by its id or current name).",
     "input_schema": {"type": "object", "properties": {
         "place": {"type": "string"}, "new_name": {"type": "string"}, "description": {"type": "string"}},
         "required": ["place"]}},
    {"name": "update_summary",
     "description": "Replace the running story summary you'll be given in future turns. Keep it under 300 words: key "
                    "events, open threads, secrets, NPC attitudes. Update it whenever something important changes.",
     "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
]

TOOL_NAMES = [t["name"] for t in TOOLS]


class ToolBox:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.started_combat = False
        self.ended_combat = False
        self.opened_shop = False
        self.pending_rolls: list[dict] = []
        self.calls: list[str] = []
        self.ended_turn = False
        self.combat_steps = 0

    # ── dispatch ──
    def call(self, name: str, args: dict) -> str:
        fn = getattr(self, f"t_{name}", None)
        if not fn:
            return f"Error: unknown tool {name}"
        try:
            result = fn(**(args or {}))
            self.calls.append(name)
            return result
        except RulesError as e:
            return f"Error: {e}"
        except TypeError as e:
            return f"Error: bad arguments — {e}"

    # ── targets ──
    def _char(self, name: str) -> tuple[str, dict]:
        cid = self.ctx.find_char_by_name(name)
        if not cid:
            names = ", ".join(s["name"] for _, s in self.ctx.party())
            raise RulesError(f"no player character called {name!r} (party: {names})")
        return cid, self.ctx.chars[cid]

    def _target(self, name: str):
        cid = self.ctx.find_char_by_name(name)
        if cid:
            return "pc", cid, self.ctx.chars[cid]
        enc = self.ctx.encounter
        if enc:
            key = name.strip().lower()
            for t in enc["tokens"].values():
                if t["kind"] == "monster" and t["hp"] > 0 and t["name"].lower() == key:
                    return "monster", t["id"], t
            for t in enc["tokens"].values():
                if t["kind"] == "monster" and t["hp"] > 0 and t["name"].lower().startswith(key):
                    return "monster", t["id"], t
        raise RulesError(f"no character or monster called {name!r}")

    # ── tools ──
    def t_roll_check(self, character: str, check: str, dc: int, advantage: str = "normal", hidden: bool = False) -> str:
        cid, s = self._char(character)
        label, bonus = _check_bonus(s, check)
        adv = advantage if advantage in ("normal", "advantage", "disadvantage") else "normal"
        if hidden or self.ctx.settings.get("rolls") == "auto":
            r = dice.d20(bonus, adv)
            ok = r["total"] >= dc
            if not hidden:
                self.ctx.log("roll", f"{s['name']} — {label}{two_dice(r)}: {r['total']} vs DC {dc} — {'success' if ok else 'failure'}.",
                             None, {"roll": r, "dc": dc, "character_id": cid})
            if r["natural"] == 20 and not s.get("inspiration"):
                s["inspiration"] = True
            return f"{s['name']} rolled {label}: {r['total']} (d20 {r['natural']}{bonus:+d}) vs DC {dc} — {'SUCCESS' if ok else 'FAILURE'}."
        m = self.ctx.member_for_char(cid)
        roll = {"id": uuid.uuid4().hex[:8], "user_id": m.user_id if m else None, "character_id": cid,
                "label": f"{s['name']}: {label}", "check": label, "bonus": bonus, "dc": dc, "advantage": adv,
                "result": None}
        self.pending_rolls.append(roll)
        return (f"Roll requested: {s['name']} {label} (DC {dc}). Players roll their own dice — end your narration now by "
                f"asking for this roll; you'll get the result next turn.")

    def t_start_combat(self, monsters: list, terrain: str = "road", distance: str = "far") -> str:
        if self.ctx.encounter:
            return "Error: a fight is already in progress."
        specs = []
        ruleset = self.ctx.settings.get("ruleset", "2014")
        for m in monsters or []:
            rec = srd.find_monster(str(m.get("name", "")), ruleset) or srd.find_monster(str(m.get("name", "")))
            if not rec:
                raise RulesError(f"no SRD monster called {m.get('name')!r}")
            specs.append((rec["index"], max(1, min(8, int(m.get("count", 1))))))
        if not specs:
            raise RulesError("name at least one monster")
        party = self.ctx.living_party()
        if not party:
            raise RulesError("no living party members")
        # Typed combat is always individual initiative: one character at a time, each move affects the next.
        enc, lines = combat.start(specs, terrain, party, "classic",
                                  self.ctx.settings.get("death_rule", "standard"), seed=random.randrange(1 << 30),
                                  ruleset=ruleset, distance=distance if distance in bm.DISTANCES else "far")
        self.ctx.state["encounter"] = enc
        self.ctx.log_lines(lines)
        self.started_combat = True
        return self._combat_opening(enc, lines)

    @staticmethod
    def _combat_opening(enc: dict, lines: list[dict]) -> str:
        """What the DM needs to narrate the opening of a fight truthfully: foes and their weapons, where everyone
        stands, initiative, and every attack already resolved before the players' first move."""
        foes = []
        for t in enc["tokens"].values():
            if t["kind"] != "monster":
                continue
            weapons = ", ".join(a["name"] for a in (t.get("actions") or [])[:3]) or "no listed attacks"
            foes.append(f"{t['name']} (AC {t['ac']}, {t['hp']} HP; attacks: {weapons})")
        pcs = [t for t in enc["tokens"].values() if t["kind"] == "pc"]
        mons = [t for t in enc["tokens"].values() if t["kind"] == "monster"]
        gap = min((bm.distance_ft((p["x"], p["y"]), (m["x"], m["y"])) for p in pcs for m in mons), default=0)
        happened = [ln["text"] for ln in lines[1:]]
        enc.pop("round_complete", None)
        nxt = enc["tokens"].get(enc["turn"].get("actor_id") or "", {})
        turn = (f"It is now {nxt['name']}'s turn (round {enc['round']}). End your narration by turning to {nxt['name']} "
                f"and asking what they do." if nxt.get("kind") == "pc" else "")
        return (f"Combat started on a {enc['terrain']} map; the nearest enemy is {gap} ft from the party. "
                f"Foes: {'; '.join(foes)}.\nWhat has happened so far, exactly as resolved by the game:\n- "
                + "\n- ".join(happened)
                + f"\nNarrate the fight's opening to match these results exactly (same weapons, hits, misses and damage). "
                  f"{turn} Don't resolve any player's action yet: each player types their own turn.")

    # ── typed combat ──
    def _turn(self) -> tuple[dict, dict, dict]:
        enc = self.ctx.encounter
        if not enc:
            raise RulesError("no fight is in progress")
        t = turns.actor(enc, self.ctx.chars)
        if not t:
            raise RulesError("it isn't a player character's turn right now")
        return enc, t, self.ctx.chars[t["character_id"]]

    def _step(self, op: dict, roll_label: str | None = None, bonus: int = 0) -> str:
        """Run a step of the acting character's turn now, or queue it behind a player roll."""
        enc, t, s = self._turn()
        self.combat_steps += 1
        q = enc.setdefault("queue", [])
        if roll_label and self.ctx.settings.get("rolls") != "auto":
            turns.validate(enc, self.ctx.chars, op)
            rid = uuid.uuid4().hex[:8]
            op["roll_id"] = rid
            q.append(op)
            m = self.ctx.member_for_char(t["character_id"])
            self.pending_rolls.append({"id": rid, "user_id": m.user_id if m else None, "character_id": t["character_id"],
                                       "label": roll_label, "check": "combat", "bonus": bonus, "dc": None,
                                       "advantage": "normal", "result": None, "combat": {"op": op["kind"]}})
            return (f"Roll requested: {roll_label}. The outcome is unknown until the player rolls — narrate the build-up, "
                    f"end by asking for the roll, and don't end the turn yet. One Roll covers the attack and, on a hit, "
                    f"its damage: don't ask for a separate damage roll.")
        if q:
            turns.validate(enc, self.ctx.chars, op)
            q.append(op)
            return "Queued: it happens right after the pending roll(s), in order."
        lines = turns.run_op(enc, self.ctx.chars, op)
        self.ctx.log_lines(lines)
        return "Resolved: " + (" ".join(ln["text"] for ln in lines) or "done.")

    def t_combat_move(self, x: int | None = None, y: int | None = None, toward: str | None = None,
                      away_from: str | None = None, stop_within_ft: int = 5) -> str:
        enc, t, _ = self._turn()
        op: dict = {"kind": "move", "tid": t["id"]}
        if toward:
            op.update(toward=turns.find_token(enc, self.ctx.chars, toward)["id"], stop=max(5, int(stop_within_ft or 5)))
        elif away_from:
            op["away_from"] = turns.find_token(enc, self.ctx.chars, away_from)["id"]
        elif x is not None and y is not None:
            op.update(x=int(x), y=int(y))
        else:
            raise RulesError("give x and y, or toward/away_from a creature")
        return self._step(op)

    def t_combat_attack(self, target: str, weapon: str) -> str:
        enc, t, s = self._turn()
        tgt = turns.find_token(enc, self.ctx.chars, target, kind="monster")
        a = turns.find_attack(s, weapon)
        op = {"kind": "attack", "tid": t["id"], "attack_id": a["id"], "target_id": tgt["id"]}
        return self._step(op, f"{s['name']}: attack roll — {a['name']} vs {tgt['name']} (d20{a['to_hit']:+d})", a["to_hit"])

    def t_combat_cast(self, spell: str, target: str | None = None, x: int | None = None, y: int | None = None,
                      slot_level: int | None = None) -> str:
        enc, t, s = self._turn()
        idx = turns.find_spell(s, spell)
        if idx not in combat.FX(s):
            raise RulesError(f"the game doesn't resolve {spell} automatically — resolve it yourself with roll_check, "
                             f"apply_damage, heal or add_condition, and use combat_action 'other' for the action")
        tgt = turns.find_token(enc, self.ctx.chars, target) if target else None
        op = {"kind": "cast", "tid": t["id"], "spell": idx, "target_id": tgt["id"] if tgt else None,
              "slot_level": slot_level, "x": x, "y": y}
        rules = R(s)
        name = srd.spells(ch.rs(s)).get(idx, {}).get("name", idx)
        kind = rules.spell_kind(idx)
        needs_dice = kind in ("attack", "save", "heal")
        sab = ch.spell_attack(s) or 0
        label = (f"{s['name']}: spell attack — {name}" + (f" vs {tgt['name']}" if tgt else "") + (f" (d20{sab:+d})" if sab else "")
                 if kind == "attack" else f"{s['name']}: roll for {name}")
        return self._step(op, label if needs_dice else None, sab if kind == "attack" else 0)

    def t_combat_feature(self, feature: str, target: str | None = None, x: int | None = None, y: int | None = None) -> str:
        enc, t, s = self._turn()
        f = turns.find_feature(s, feature)
        tgt = turns.find_token(enc, self.ctx.chars, target) if target else None
        op = {"kind": "feature", "tid": t["id"], "feature": f["id"], "target_id": tgt["id"] if tgt else None, "x": x, "y": y}
        rolls = f.get("target") == "enemy"
        return self._step(op, f"{s['name']}: {f['name']}" + (f" vs {tgt['name']}" if tgt else "") if rolls else None)

    def t_combat_action(self, action: str, note: str | None = None) -> str:
        enc, t, _ = self._turn()
        if action not in turns.ACTS:
            raise RulesError(f"action must be one of {', '.join(sorted(turns.ACTS))}")
        return self._step({"kind": "act", "tid": t["id"], "act": action, "note": (note or "")[:300]})

    def t_combat_end_turn(self) -> str:
        enc = self.ctx.encounter
        if not enc:
            raise RulesError("no fight is in progress")
        if enc.get("queue"):
            raise RulesError("the player still has rolls to make — end the turn after you've narrated their results")
        tid = (enc.get("turn") or {}).get("actor_id")
        t = enc["tokens"].get(tid or "")
        if not t or t["kind"] != "pc":
            raise RulesError("it isn't a player character's turn")
        if combat.can_act(enc, tid, self.ctx.chars):
            lines = combat.end_turn(enc, self.ctx.chars, tid)
        else:  # they went down mid-turn
            lines = combat.advance(enc, self.ctx.chars)
        enc.pop("round_complete", None)
        enc.pop("declared", None)
        self.ctx.log_lines(lines)
        self.ended_turn = True
        happened = "\n".join(f"- {ln['text']}" for ln in lines) or "- (nothing else happened)"
        outcome = combat.check_end(enc, self.ctx.chars)
        if outcome:
            return (f"{t['name']}'s turn is over. Then:\n{happened}\nThe fight is over ({outcome}). Narrate how it ends; "
                    f"the game hands out XP and loot right after.")
        nxt = turns.actor(enc, self.ctx.chars) or enc["tokens"].get(enc["turn"].get("actor_id") or "", {})
        name = nxt.get("name", "the next character")
        return (f"{t['name']}'s turn is over. What happened next, exactly as resolved by the game:\n{happened}\n"
                f"Now it is {name}'s turn (round {enc['round']}). Narrate these results (same weapons, hits, misses "
                f"and damage) and end by turning to {name}: what do they do?")

    def t_end_combat(self, reason: str) -> str:
        if not self.ctx.encounter:
            return "No fight is in progress."
        self.ctx.state["encounter"] = None
        self.ended_combat = True
        self.ctx.log("event", f"The fight ends: {reason}.")
        return "Combat ended."

    def t_apply_damage(self, target: str, amount: int, damage_type: str = "") -> str:
        kind, tid, obj = self._target(target)
        if kind == "pc":
            res = ch.take_damage(obj, amount)
            self.ctx.log("event", f"{obj['name']} takes {res['damage']} {damage_type} damage.".replace("  ", " "))
            return f"{obj['name']} now has {obj['hp']}/{obj['hp_max']} HP" + (" and is down." if res["down"] else ".")
        dealt, note, extra = combat.apply_damage(self.ctx.encounter, self.ctx.chars, obj, amount, damage_type)
        self.ctx.log("combat", f"{obj['name']} takes {dealt} {damage_type} damage.".replace("  ", " "))
        self.ctx.log_lines(extra)
        return f"{obj['name']} takes {dealt}. {note}".strip()

    def t_heal(self, target: str, amount: int) -> str:
        cid, s = self._char(target)
        n = ch.heal(s, amount)
        self.ctx.log("event", f"{s['name']} regains {n} HP.")
        return f"{s['name']} now has {s['hp']}/{s['hp_max']} HP."

    def t_add_condition(self, target: str, condition: str) -> str:
        kind, tid, obj = self._target(target)
        cond = condition.strip().title()[:30]
        if kind == "pc":
            ch.add_condition(obj, cond)
        elif cond not in obj["conditions"]:
            obj["conditions"].append(cond)
        self.ctx.log("event", f"{obj['name']} is {cond.lower()}.")
        return "ok"

    def t_remove_condition(self, target: str, condition: str) -> str:
        kind, tid, obj = self._target(target)
        if kind == "pc":
            ch.remove_condition(obj, condition)
        else:
            obj["conditions"] = [c for c in obj["conditions"] if c.lower() != condition.lower()]
        return "ok"

    def t_grant_item(self, character: str, item: str, quantity: int = 1, custom_description: str | None = None,
                     custom_value_gp: float | None = None) -> str:
        cid, s = self._char(character)
        qty = max(1, min(100, int(quantity or 1)))
        rec = srd.find_item(item) if not custom_description else None
        if rec:
            if rec.get("category") in ("Weapon", "Armor"):
                for _ in range(qty):
                    ch.add_item(s, rec["index"], 1)
            else:
                ch.add_item(s, rec["index"], qty)
            name = rec["name"]
        else:
            custom = {"name": item.strip()[:60], "description": (custom_description or "")[:500],
                      "value_cp": int((custom_value_gp or 0) * 100), "category": "Treasure"}
            ch.add_item(s, "custom-" + uuid.uuid4().hex[:6], qty, custom=custom)
            name = custom["name"]
        self.ctx.log("event", f"{s['name']} receives {name}" + (f" ×{qty}" if qty > 1 else "") + ".")
        return f"Gave {name} ×{qty} to {s['name']}."

    def t_remove_item(self, character: str, item: str, quantity: int = 1) -> str:
        cid, s = self._char(character)
        key = item.strip().lower()
        it = next((i for i in s["inventory"] if i["name"].lower() == key), None) or \
            next((i for i in s["inventory"] if key in i["name"].lower()), None)
        if not it:
            raise RulesError(f"{s['name']} has no {item}")
        q = min(it["qty"], max(1, int(quantity or 1)))
        ch.remove_item(s, it["id"], q)
        self.ctx.log("event", f"{s['name']} loses {it['name']}" + (f" ×{q}" if q > 1 else "") + ".")
        return "ok"

    def t_grant_gold(self, character: str, gp: float) -> str:
        cp = int(round(float(gp) * 100))
        if character.strip().lower() in ("party", "everyone", "all"):
            party = self.ctx.living_party()
            if not party:
                raise RulesError("no living party members")
            each = cp // len(party)
            for _, s in party:
                if s["gold_cp"] + each < 0:
                    raise RulesError(f"{s['name']} can't pay that much")
            for _, s in party:
                s["gold_cp"] += each
            self.ctx.log("event", f"The party {'gains' if cp >= 0 else 'pays'} {shop_rules.fmt_cp(abs(cp))}"
                         f" ({shop_rules.fmt_cp(abs(each))} each).")
            return "ok"
        cid, s = self._char(character)
        if s["gold_cp"] + cp < 0:
            raise RulesError(f"{s['name']} only has {shop_rules.fmt_cp(s['gold_cp'])}")
        s["gold_cp"] += cp
        self.ctx.log("event", f"{s['name']} {'gains' if cp >= 0 else 'pays'} {shop_rules.fmt_cp(abs(cp))}.")
        return f"{s['name']} now has {shop_rules.fmt_cp(s['gold_cp'])}."

    def t_award_xp(self, reason: str, xp_each: int = 0, milestone: bool = False) -> str:
        out = []
        for _, s in self.ctx.living_party():
            if milestone or self.ctx.settings.get("leveling") == "milestone":
                if milestone and ch.grant_milestone(s):
                    out.append(f"{s['name']} can level up")
            elif ch.award_xp(s, xp_each):
                out.append(f"{s['name']} can level up")
        self.ctx.log("event", f"Experience: {reason}" + (f" (+{xp_each} XP each)" if xp_each and not milestone else "") +
                     ("" if not out else ". " + "; ".join(out) + "!"))
        return "; ".join(out) or "XP recorded."

    def t_open_shop(self, shop_type: str, name: str, keeper: str) -> str:
        loc = self.ctx.state.get("location") or {}
        size = "village"
        if loc.get("settlement_id") and self.ctx.world:
            st = next((s for s in self.ctx.world["settlements"] if s["id"] == loc["settlement_id"]), None)
            if st:
                size = st["size"]
        stock = shop_rules.generate(shop_type, size, self.ctx.settings.get("magic_level", "standard"),
                                    self.ctx.settings.get("economy", "standard"), seed=random.randrange(1 << 30))
        self.ctx.state["shop"] = {"name": name[:60], "keeper": keeper[:120], "type": shop_type,
                                  "sell_rate": float(self.ctx.settings.get("sell_rate", 0.5)), "stock": stock,
                                  "transactions": []}
        self.opened_shop = True
        return (f"The shop screen opens for the players after your narration ({len(stock)} kinds of goods). "
                f"Describe the shop and keeper briefly; don't list prices — players browse themselves.")

    def t_travel(self, destination: str | None = None, direction: str | None = None, days: float = 1) -> str:
        w = self.ctx.world
        if not w:
            raise RulesError("there is no world map yet")
        if not destination:
            if not direction:
                raise RulesError("give a destination by name, or a direction and how many days")
            dest = hexmap.hex_toward(w, direction, max(1, round(float(days) * hexmap.HEXES_PER_DAY)))
            if not dest:
                raise RulesError(f"the party can't head {direction} from here (water or the edge of the map)")
            return do_travel(self.ctx, dest)
        key = destination.strip().lower()
        place = next((s for s in w["settlements"] + w["pois"] if s["name"].lower() == key or s["id"] == key), None) or \
            next((s for s in w["settlements"] + w["pois"] if key in s["name"].lower()), None)
        if not place:
            names = ", ".join(s["name"] for s in w["settlements"])
            raise RulesError(f"no place called {destination!r} on the map (settlements: {names})")
        return do_travel(self.ctx, (place["q"], place["r"]))

    def t_set_scene(self, location_name: str | None = None, description: str | None = None, scene_type: str | None = None,
                    time_of_day: str | None = None, weather: str | None = None, advance_hours: int = 0) -> str:
        loc = self.ctx.state.setdefault("location", {"name": "", "settlement_id": None, "description": ""})
        if location_name:
            loc["name"] = location_name[:80]
        if description:
            loc["description"] = description[:600]
        sc = self.ctx.state.setdefault("scene", {"type": "town", "time_of_day": "morning", "weather": "clear", "day": 1, "hour": 8})
        if scene_type:
            sc["type"] = scene_type
        if weather:
            sc["weather"] = weather[:40]
        if advance_hours:
            advance_clock(self.ctx, int(advance_hours))
        if time_of_day:
            sc["time_of_day"] = time_of_day
        return "ok"

    def t_rest(self, kind: str) -> str:
        return rest_party(self.ctx, kind)

    def t_upsert_npc(self, name: str, role: str | None = None, attitude: str | None = None, notes: str | None = None) -> str:
        npcs = self.ctx.state.setdefault("npcs", [])
        n = next((x for x in npcs if x["name"].lower() == name.strip().lower()), None)
        if not n:
            n = {"name": name.strip()[:60], "role": "", "attitude": "neutral", "notes": ""}
            npcs.append(n)
        if role:
            n["role"] = role[:80]
        if attitude:
            n["attitude"] = attitude
        if notes:
            n["notes"] = notes[:400]
        return "ok"

    def t_upsert_quest(self, title: str, status: str | None = None, notes: str | None = None) -> str:
        qs = self.ctx.state.setdefault("quests", [])
        q = next((x for x in qs if x["title"].lower() == title.strip().lower()), None)
        if not q:
            q = {"title": title.strip()[:80], "status": "active", "notes": ""}
            qs.append(q)
            self.ctx.log("event", f"New quest: {q['title']}.")
        if status:
            if status != q["status"] and status in ("done", "failed"):
                self.ctx.log("event", f"Quest {'completed' if status == 'done' else 'failed'}: {q['title']}.")
            q["status"] = status
        if notes:
            q["notes"] = notes[:600]
        return "ok"

    def t_name_place(self, place: str, new_name: str | None = None, description: str | None = None) -> str:
        w = self.ctx.world
        if not w:
            raise RulesError("no world map")
        key = place.strip().lower()
        p = next((s for s in w["settlements"] + w["pois"] if s["id"] == key or s["name"].lower() == key), None)
        if not p:
            raise RulesError(f"no place {place!r}")
        old = p["name"]
        if new_name:
            p["name"] = new_name.strip()[:60]
            loc = self.ctx.state.get("location") or {}
            if loc.get("name") == old:
                loc["name"] = p["name"]
        if description:
            p["description"] = description[:400]
        return "ok"

    def t_update_summary(self, summary: str) -> str:
        self.ctx.summary = summary[:4000]
        return "Summary saved."


def _check_bonus(s: dict, check: str) -> tuple[str, int]:
    c = check.strip()
    for sk in SKILLS:
        if sk.lower() == c.lower():
            return f"{sk} check", ch.skill_bonus(s, sk)
    up = c.upper()
    for ab in ABILITIES:
        names = {ab, {"STR": "STRENGTH", "DEX": "DEXTERITY", "CON": "CONSTITUTION", "INT": "INTELLIGENCE",
                      "WIS": "WISDOM", "CHA": "CHARISMA"}[ab]}
        first = up.split()[0] if up else ""
        if first in names:
            if "SAVE" in up or "SAVING" in up:
                return f"{ab} save", ch.save_bonus(s, ab)
            return f"{ab} check", ch.mod(s["abilities"][ab])
    raise RulesError(f"unknown check {check!r} — use a skill name, an ability, or '<ABILITY> save'")


def roll_pending(ctx: Ctx, roll: dict) -> dict:
    if roll.get("combat"):
        return _roll_combat(ctx, roll)
    s = ctx.chars.get(roll["character_id"])
    bonus = roll.get("bonus", 0)
    r = dice.d20(bonus, roll.get("advantage", "normal"))
    ok = r["total"] >= roll["dc"] if roll.get("dc") else None
    roll["result"] = {"total": r["total"], "rolls": r["rolls"], "modifier": bonus, "natural": r["natural"], "success": ok}
    if s and r["natural"] == 20 and not s.get("inspiration"):
        s["inspiration"] = True
    ctx.log("roll", f"{roll['label']}{two_dice(r)}: {r['total']}" + (f" vs DC {roll['dc']} — {'success' if ok else 'failure'}" if roll.get("dc") else "") + ".",
            None, {"roll": r, "dc": roll.get("dc"), "character_id": roll["character_id"]})
    return roll


def two_dice(r: dict) -> str:
    """' (advantage: rolled 3 and 2, kept 3)' for a roll with advantage or disadvantage, else ''."""
    rolls = r.get("rolls") or []
    if len(rolls) != 2 or r.get("advantage") not in ("advantage", "disadvantage"):
        return ""
    return f" ({r['advantage']}: rolled {rolls[0]} and {rolls[1]}, kept {r['natural']})"


def _roll_combat(ctx: Ctx, roll: dict) -> dict:
    """A player rolls for a queued step of their combat turn: run the turn's steps up to this one (and any roll-free
    steps after it) with the real engine, and record what the dice did."""
    enc = ctx.encounter
    if not enc:
        roll["result"] = {"total": 0, "natural": 0, "modifier": 0, "success": None, "lines": ["The fight is already over."],
                          "skipped": True}
        return roll
    earlier = [r for r in ctx.phase.get("pending_rolls", []) if r.get("combat") and r.get("result") is None]
    if earlier and earlier[0]["id"] != roll["id"]:
        raise RulesError("make the earlier roll first — this turn's steps happen in order")
    mine, everything = turns.execute_through(enc, ctx.chars, roll["id"])
    ctx.log_lines(everything)
    first = next((ln for ln in mine if (ln.get("data") or {}).get("roll")), None)
    d = (first or {}).get("data") or {}
    r = d.get("roll") or {}
    roll["result"] = {"total": r.get("total", 0), "natural": r.get("natural", 0), "rolls": r.get("rolls", []),
                      "modifier": roll.get("bonus", 0), "success": d.get("hit"), "hit": d.get("hit"),
                      "damage": d.get("damage"),
                      "lines": [ln["text"] for ln in mine] or ["Nothing happened."], "skipped": not mine}
    return roll


REST_HOURS = {"standard": {"short": 1, "long": 8}, "gritty": {"short": 8, "long": 168}, "epic": {"short": 0, "long": 1}}


def rest_party(ctx: Ctx, kind: str, who: list[str] | None = None) -> str:
    """Short or long rest for the living party (or just `who`), honouring the game's rest rules."""
    if kind not in ("short", "long"):
        raise RulesError("rest must be short or long")
    if ctx.encounter:
        raise RulesError("you can't rest in the middle of a fight")
    res = []
    for cid, s in ctx.living_party():
        if who is not None and cid not in who:
            continue
        r = ch.long_rest(s) if kind == "long" else ch.short_rest(s)
        res.append(f"{s['name']} +{r['healed']} HP")
    hours = REST_HOURS.get(ctx.settings.get("rest_rule", "standard"), REST_HOURS["standard"])[kind]
    advance_clock(ctx, hours)
    span = {0: "a few minutes", 1: "an hour", 8: "the night", 168: "a full week"}.get(hours, f"{hours} hours")
    if res:
        ctx.log("event", f"{'The party' if who is None else ', '.join(ctx.chars[c]['name'] for c in who)} "
                         f"{'takes a' if who is None else 'take a'} {kind} rest ({span}). " + ", ".join(res) + ".")
    return "; ".join(res) or "no one rested"


def advance_clock(ctx: Ctx, hours: int) -> None:
    sc = ctx.state.setdefault("scene", {"type": "town", "time_of_day": "morning", "weather": "clear", "day": 1, "hour": 8})
    total = sc.get("hour", 8) + hours
    sc["day"] = sc.get("day", 1) + total // 24
    sc["hour"] = total % 24
    h = sc["hour"]
    sc["time_of_day"] = ("night" if h < 5 or h >= 21 else "dawn" if h < 7 else "morning" if h < 11 else
                         "midday" if h < 14 else "afternoon" if h < 18 else "evening")


def do_travel(ctx: Ctx, dest: tuple[int, int]) -> str:
    w = ctx.world
    plan = hexmap.plan_travel(w, dest)
    if not plan["ok"]:
        raise RulesError(plan["reason"])
    hexmap.apply_travel(w, plan)
    days = plan["days"]
    advance_clock(ctx, int(days * 24) if days >= 1 else int(days * 24) or 2)
    st = hexmap.settlement_at(w, *dest)
    poi = hexmap.poi_at(w, *dest)
    name = st["name"] if st else poi["name"] if poi else f"the {hexmap.BIOME_NAMES[hexmap.biome_at(w, *dest)]}"
    ctx.state["location"] = {"name": name, "settlement_id": st["id"] if st else None,
                             "description": (st or poi or {}).get("description", "")}
    sc = ctx.state.setdefault("scene", {})
    sc["type"] = "town" if st else ("ruins" if poi and poi["kind"] in ("ruins", "tower") else
                                    "cave" if poi and poi["kind"] == "cave" else "wilderness")
    ctx.log("event", f"The party travels to {name} ({days:g} day{'s' if days != 1 else ''} through "
                     f"{hexmap.BIOME_NAMES[plan['main_biome']]}).")
    # random encounter check: about one in three per day of travel, more on harder settings
    chance = min(0.85, (0.3 + {"story": -0.1, "normal": 0, "hard": 0.05, "deadly": 0.1}[ctx.settings.get("difficulty", "normal")]) * max(0.5, days))
    enc_note = ""
    if random.random() < chance and ctx.living_party():
        levels = [s["level"] for _, s in ctx.living_party()]
        rsk = ctx.settings.get("ruleset", "2014")
        specs = xp_rules.random_encounter(levels, ctx.settings.get("difficulty", "normal"), plan["main_biome"], ruleset=rsk)
        names = ", ".join(f"{c} × {(srd.monsters(rsk).get(i) or srd.monsters()[i])['name']}" for i, c in specs)
        enc_note = (f" A random encounter is due on the way: {names}. Stage it (ambush, standoff, or something they can talk "
                    f"their way past) and call start_combat if it comes to blows.")
    return f"The party arrives at {name} after {days:g} days through {hexmap.BIOME_NAMES[plan['main_biome']]}.{enc_note}"
