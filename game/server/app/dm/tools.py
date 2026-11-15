"""DM tools — the AI DM's only way to change the game. Every call is validated here."""
from __future__ import annotations

import random
import uuid

from ..game import combat
from ..game.state import Ctx
from ..rules import character as ch
from ..rules import dice, srd
from ..rules import shop as shop_rules
from ..rules import xp as xp_rules
from ..rules.character import RulesError
from ..rules.classes import ABILITIES, SKILLS
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
         "terrain": {"type": "string", "enum": ["road", "forest", "tavern", "cave", "dungeon", "ruins", "camp", "swamp"]}},
         "required": ["monsters", "terrain"]}},
    {"name": "end_combat",
     "description": "End the current fight without a victory (the enemies flee or surrender, or the party escapes).",
     "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}},
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
     "description": "Move the party on the world map to a settlement or place of interest by name. Returns the days taken and the terrain.",
     "input_schema": {"type": "object", "properties": {"destination": {"type": "string"}}, "required": ["destination"]}},
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
                self.ctx.log("roll", f"{s['name']} — {label}: {r['total']} vs DC {dc} — {'success' if ok else 'failure'}.",
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

    def t_start_combat(self, monsters: list, terrain: str = "road") -> str:
        if self.ctx.encounter:
            return "Error: a fight is already in progress."
        specs = []
        for m in monsters or []:
            rec = srd.find_monster(str(m.get("name", "")))
            if not rec:
                raise RulesError(f"no SRD monster called {m.get('name')!r}")
            specs.append((rec["index"], max(1, min(8, int(m.get("count", 1))))))
        if not specs:
            raise RulesError("name at least one monster")
        party = self.ctx.living_party()
        if not party:
            raise RulesError("no living party members")
        enc, lines = combat.start(specs, terrain, party, self.ctx.settings.get("combat_mode", "side"),
                                  self.ctx.settings.get("death_rule", "standard"), seed=random.randrange(1 << 30))
        self.ctx.state["encounter"] = enc
        self.ctx.log_lines(lines)
        self.started_combat = True
        foes = ", ".join(f"{t['name']} (AC {t['ac']}, {t['hp']} HP)" for t in enc["tokens"].values() if t["kind"] == "monster")
        return (f"Combat started on a {enc['terrain']} map: {foes}. Who acts first: {enc['turn']}. Finish your narration "
                f"setting the scene of the fight; the players will now act on the battle map.")

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
        dealt, note = combat.apply_damage(self.ctx.encounter, self.ctx.chars, obj, amount, damage_type)
        self.ctx.log("combat", f"{obj['name']} takes {dealt} {damage_type} damage.".replace("  ", " "))
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

    def t_travel(self, destination: str) -> str:
        w = self.ctx.world
        if not w:
            raise RulesError("there is no world map yet")
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
    s = ctx.chars.get(roll["character_id"])
    bonus = roll.get("bonus", 0)
    r = dice.d20(bonus, roll.get("advantage", "normal"))
    ok = r["total"] >= roll["dc"] if roll.get("dc") else None
    roll["result"] = {"total": r["total"], "rolls": r["rolls"], "modifier": bonus, "natural": r["natural"], "success": ok}
    if s and r["natural"] == 20 and not s.get("inspiration"):
        s["inspiration"] = True
    ctx.log("roll", f"{roll['label']}: {r['total']}" + (f" vs DC {roll['dc']} — {'success' if ok else 'failure'}" if roll.get("dc") else "") + ".",
            None, {"roll": r, "dc": roll.get("dc"), "character_id": roll["character_id"]})
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
        specs = xp_rules.random_encounter(levels, ctx.settings.get("difficulty", "normal"), plan["main_biome"])
        names = ", ".join(f"{c} × {srd.monsters()[i]['name']}" for i, c in specs)
        enc_note = (f" A random encounter is due on the way: {names}. Stage it (ambush, standoff, or something they can talk "
                    f"their way past) and call start_combat if it comes to blows.")
    return f"The party arrives at {name} after {days:g} days through {hexmap.BIOME_NAMES[plan['main_biome']]}.{enc_note}"
