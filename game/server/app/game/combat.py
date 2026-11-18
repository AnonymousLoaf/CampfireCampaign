"""Grid combat: initiative, movement, attacks, spells, class features, reactions, monster and auto-play turns.

An encounter is a plain dict stored on the game's state. PC hit points live on the
character sheets (`chars`: character_id → sheet); monster stats live on their tokens.
Every function returns log lines: dicts {kind, text, data}.
"""
from __future__ import annotations

import math
import random
import re

from ..rules import character as ch
from ..rules import dice, srd
from ..rules.character import RulesError, mod
from ..rules.classes import prof_bonus
from ..rules.rulesets import R


def FX(s: dict) -> dict:
    """Spell effects for this caster's ruleset."""
    return R(s).SPELL_EFFECTS


def spell_target_for(s: dict, index: str) -> str:
    return R(s).spell_target(index)
from ..world import battlemap as bm

MONSTER_COLORS = ["#b33a3a", "#8e3b8e", "#a35a1f", "#6b6b6b", "#3b6e8e", "#7a7a2e"]
INCAPACITATING = {"Unconscious", "Paralyzed", "Stunned", "Asleep", "Charmed"}


def line(text: str, kind: str = "combat", **data) -> dict:
    return {"kind": kind, "text": text, "data": data or None}


# ── setup ───────────────────────────────────────────────────────────────────

def _spots_near(m: dict, wanted: list, taken: set) -> list[tuple[int, int]]:
    """A free, passable square for each wanted spot: the spot itself, else the nearest free one (None = anywhere)."""
    w, h = m["grid"]["w"], m["grid"]["h"]
    free = [(x, y) for y in range(h) for x in range(w) if bm.passable(m, x, y)]
    out = []
    for want in wanted:
        opts = [p for p in free if p not in taken and p not in out]
        if not opts:
            break
        p = min(opts, key=lambda q: bm.distance_ft(q, tuple(want))) if want else opts[0]
        out.append(p)
    return out


def start(specs: list[tuple[str, int]], terrain: str, party: list[tuple[str, dict]], mode: str = "side",
          death_rule: str = "standard", seed: int | None = None, ruleset: str = "2014",
          distance: str = "far", premade: dict | None = None, pc_spots: dict | None = None,
          foe_spots: list | None = None, bystanders: list | None = None) -> tuple[dict, list[dict]]:
    """party: [(character_id, sheet)] — living characters only. `premade`: a map to fight on (the scene map) instead
    of a generated one; `pc_spots` {character_id: (x, y)} and `foe_spots` [(x, y)] say where each side starts."""
    rng = random.Random(seed)
    for _, s in party:
        s["prep_open"] = False  # prepared spells are locked in once a fight starts
    m = premade or bm.generate(terrain if terrain in bm.TERRAINS else "road", seed)
    enc = {**m, "round": 1, "mode": mode if mode in ("side", "classic") else "side", "death_rule": death_rule,
           "ruleset": ruleset,
           "tokens": {}, "order": [], "idx": 0, "turn": {"side": "party", "actor_id": None},
           "round_log": [], "custom_actions": [], "xp": 0, "outcome": None, "monsters_cr": []}
    taken: set = set()
    pcs = [(cid, s) for cid, s in party if not s.get("dead")]
    enc.pop("visible", None)
    if bystanders:  # friendly NPCs on a scene map: they stay put and take up their squares
        enc["bystanders"] = []
        for b in bystanders:
            xy = (int(b["x"]), int(b["y"]))
            if bm.passable(m, *xy) and xy not in taken:
                taken.add(xy)
                enc["bystanders"].append({"name": str(b["name"])[:40], "x": xy[0], "y": xy[1]})
    pc_xy = _spots_near(m, [tuple(pc_spots[c]) if pc_spots and c in pc_spots else None for c, _ in pcs], taken) \
        if pc_spots else bm.deploy(m, len(pcs), "left", taken, rng, distance)
    for (cid, s), (x, y) in zip(pcs, pc_xy):
        taken.add((x, y))
        tid = f"pc-{cid}"
        enc["tokens"][tid] = {"id": tid, "name": s["name"], "kind": "pc", "character_id": cid, "x": x, "y": y,
                              "color": s.get("color", "#c9a227"), "conditions": [], "budget": None, "done": False,
                              "reaction": True}
        s["concentration"] = None
    n = 0
    names = []
    for idx, count in specs:
        rec = srd.monsters(ruleset).get(idx) or srd.monsters().get(idx)
        if not rec:
            continue
        spots = _spots_near(m, [foe_spots[(n + i) % len(foe_spots)] for i in range(count)], taken) if foe_spots \
            else bm.deploy(m, count, "right", taken, rng, distance)
        for i, (x, y) in enumerate(spots):
            taken.add((x, y))
            n += 1
            name = rec["name"] if count == 1 else f"{rec['name']} {i + 1}"
            tid = f"m{n}"
            enc["tokens"][tid] = {
                "id": tid, "name": name, "kind": "monster", "character_id": None, "monster_index": idx,
                "x": x, "y": y, "hp": rec["hp"], "hp_max": rec["hp"], "ac": rec["ac"],
                "speed": srd.monster_speed(rec), "conditions": [], "actions": srd.monster_actions(rec),
                "multiattack": srd.monster_multiattack(rec),
                "abilities": {a: rec.get(a.lower(), 10) for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA")},
                "xp": rec.get("xp", 0), "cr": rec.get("cr", 0), "ctype": rec.get("type", ""),
                "color": MONSTER_COLORS[(n - 1) % len(MONSTER_COLORS)],
                "resist": rec.get("resistances", ""), "immune": rec.get("immunities", ""),
                "vulnerable": rec.get("vulnerabilities", ""),
                "pack_tactics": "Pack Tactics" in (rec.get("description") or ""),
                "budget": None, "done": False, "reaction": True, "save_ends": {},
            }
            enc["xp"] += rec.get("xp", 0)
            enc["monsters_cr"].append(rec.get("cr", 0))
        names.append(f"{count} × {rec['name']}" if count > 1 else rec["name"])
    lines = [line(f"Combat begins: {', '.join(names)}.", "event")]

    chars = dict(pcs)
    if enc["mode"] == "classic":
        rolls = []
        for t in enc["tokens"].values():
            if t["kind"] == "pc":
                ps = chars[t["character_id"]]
                dmod = ch.initiative(ps)
                adv = "advantage" if ch.has_feature(ps, "Feral Instinct") else "normal"
            else:
                dmod, adv = mod(t["abilities"]["DEX"]), "normal"
            r = dice.d20(dmod, adv)
            rolls.append((r["total"], dmod, rng.random(), t["id"]))
            t["initiative"] = r["total"]
        rolls.sort(reverse=True)
        enc["order"] = [r[3] for r in rolls]
        lines.append(line("Initiative: " + ", ".join(f"{enc['tokens'][r[3]]['name']} {r[0]}" for r in rolls) + ".", "roll"))
        enc["idx"] = 0
        enc["turn"] = {"side": None, "actor_id": None}
        lines += _begin_actor(enc, chars)
    else:
        pbest = max((ch.initiative(s) for _, s in pcs), default=0)
        mbest = max((mod(t["abilities"]["DEX"]) for t in enc["tokens"].values() if t["kind"] == "monster"), default=0)
        pr, mr = dice.d20(pbest), dice.d20(mbest)
        first = "party" if pr["total"] >= mr["total"] else "monsters"
        lines.append(line(f"Initiative: party {pr['total']} vs enemies {mr['total']} — "
                          f"{'the party acts first' if first == 'party' else 'the enemies act first'}.", "roll"))
        if first == "monsters":
            lines += run_monsters(enc, chars)
            lines += _new_round(enc, chars)
        else:
            lines += _begin_side(enc, chars, "party")
    return enc, lines


# ── helpers ─────────────────────────────────────────────────────────────────

def pos(t: dict) -> tuple[int, int]:
    return t["x"], t["y"]


def sheet_of(t: dict, chars: dict) -> dict | None:
    return chars.get(t["character_id"]) if t["kind"] == "pc" else None


def alive(t: dict, chars: dict) -> bool:
    if t["kind"] == "pc":
        s = chars.get(t["character_id"])
        return bool(s) and s["hp"] > 0 and not s.get("dead")
    return t["hp"] > 0


def present(t: dict, chars: dict) -> bool:
    if t["kind"] == "pc":
        s = chars.get(t["character_id"])
        return bool(s) and not s.get("dead")
    return t["hp"] > 0


def conds(t: dict, chars: dict) -> list[str]:
    if t["kind"] == "pc":
        s = chars.get(t["character_id"]) or {}
        return list(s.get("conditions", [])) + list(t.get("conditions", []))
    return list(t.get("conditions", []))


def has_cond(t: dict, chars: dict, c: str) -> bool:
    return c in conds(t, chars)


def add_cond(t: dict, chars: dict, c: str) -> None:
    if t["kind"] == "pc":
        ch.add_condition(chars[t["character_id"]], c)
    elif c not in t["conditions"]:
        t["conditions"].append(c)


def remove_cond(t: dict, chars: dict, c: str) -> None:
    if t["kind"] == "pc":
        ch.remove_condition(chars[t["character_id"]], c)
    t["conditions"] = [x for x in t.get("conditions", []) if x != c]
    t.get("save_ends", {}).pop(c, None)


def incapacitated(t: dict, chars: dict) -> bool:
    return bool(set(conds(t, chars)) & INCAPACITATING)


def occupied(enc: dict, chars: dict, exclude: str | None = None) -> set[tuple[int, int]]:
    return {pos(t) for t in enc["tokens"].values() if t["id"] != exclude and present(t, chars)}         | {(b["x"], b["y"]) for b in enc.get("bystanders") or []}  # NPCs standing around take up their squares


def enemies(enc: dict, t: dict, chars: dict) -> list[dict]:
    return [o for o in enc["tokens"].values() if o["kind"] != t["kind"] and alive(o, chars)]


def allies(enc: dict, t: dict, chars: dict) -> list[dict]:
    return [o for o in enc["tokens"].values() if o["kind"] == t["kind"] and o["id"] != t["id"] and alive(o, chars)]


def token_ac(t: dict, chars: dict) -> int:
    return ch.armor_class(chars[t["character_id"]]) if t["kind"] == "pc" else t["ac"]


def token_speed(t: dict, chars: dict) -> int:
    if has_cond(t, chars, "Restrained"):
        return 0
    if t["kind"] == "pc":
        return ch.speed(chars[t["character_id"]])
    sp = t["speed"]
    return max(0, sp - 10) if "Slowed" in t.get("conditions", []) else sp


def save_bonus(t: dict, chars: dict, ability: str) -> int:
    if t["kind"] == "pc":
        return ch.save_bonus(chars[t["character_id"]], ability)
    return mod(t["abilities"].get(ability, 10))


def melee_reach(t: dict, chars: dict) -> int:
    if t["kind"] == "monster":
        return max([a["reach"] for a in t["actions"] if not a["ranged"]] or [0])
    s = chars[t["character_id"]]
    return max([a["range_ft"] for a in ch.attacks(s) if a["kind"] == "melee"] or [5])


def _reset_budget(t: dict, chars: dict) -> None:
    t["budget"] = {"move_ft": token_speed(t, chars), "action": True, "bonus": True, "attacks_left": 0}
    t["done"] = False
    t["dodging"] = False
    t["disengaged"] = False
    t["sneak_used"] = False
    t["colossus_used"] = False
    t["savage_used"] = False
    t["divine_strike_used"] = False
    t["cleave_used"] = False
    t["attacked"] = False
    t["reckless"] = False
    t["exposed"] = False
    t["reaction"] = True
    for c in ("Slowed",):
        if c in t.get("conditions", []):
            t["conditions"].remove(c)
    if has_cond(t, chars, "Prone") and not incapacitated(t, chars):
        remove_cond(t, chars, "Prone")
        t["budget"]["move_ft"] //= 2  # standing up costs half your movement


def can_act(enc: dict, tid: str, chars: dict) -> bool:
    if enc.get("outcome"):
        return False
    t = enc["tokens"].get(tid)
    if not t or t["kind"] != "pc" or not alive(t, chars) or incapacitated(t, chars):
        return False
    if enc["mode"] == "classic":
        return enc["turn"]["actor_id"] == tid
    return enc["turn"]["side"] == "party" and not t.get("done")


def require(enc: dict, tid: str, chars: dict) -> dict:
    if not can_act(enc, tid, chars):
        raise RulesError("it isn't that character's turn")
    return enc["tokens"][tid]


def reachable_for(enc: dict, tid: str, chars: dict) -> dict:
    t = enc["tokens"][tid]
    if not t.get("budget"):
        return {}
    return bm.reachable(enc, pos(t), t["budget"]["move_ft"], occupied(enc, chars, exclude=tid))


def dist(a: dict, b: dict) -> int:
    return bm.distance_ft(pos(a), pos(b))


# ── concentration ───────────────────────────────────────────────────────────

def start_concentration(enc: dict, chars: dict, caster: dict, spell: str, effects: list[dict]) -> list[dict]:
    s = chars[caster["character_id"]]
    out = end_concentration(enc, chars, caster, quiet=True)
    s["concentration"] = {"spell": spell, "effects": effects}
    return out


def end_concentration(enc: dict | None, chars: dict, caster: dict, quiet: bool = False) -> list[dict]:
    s = chars.get(caster["character_id"]) if caster.get("character_id") else None
    if not s or not s.get("concentration"):
        return []
    conc = s["concentration"]
    s["concentration"] = None
    for e in conc.get("effects", []):
        if enc:
            t = enc["tokens"].get(e.get("token"))
            if t:
                if e.get("condition"):
                    remove_cond(t, chars, e["condition"])
                if e.get("mark"):
                    t.pop("mark", None)
        if e.get("character") and e.get("condition") and e["character"] in chars:
            ch.remove_condition(chars[e["character"]], e["condition"])
    name = srd.spells(ch.rs(s)).get(conc["spell"], {}).get("name") or srd.spells().get(conc["spell"], {}).get("name", conc["spell"])
    return [] if quiet else [line(f"{s['name']} loses concentration on {name}.", "combat")]


def aura_bonus(enc: dict | None, chars: dict, t: dict) -> int:
    """Aura of Protection: +CHA to saves for a paladin (6th+) and allies within 10 ft."""
    if not enc or t["kind"] != "pc":
        return 0
    best = 0
    for o in enc["tokens"].values():
        if o["kind"] != "pc" or not alive(o, chars) or incapacitated(o, chars):
            continue
        s = chars[o["character_id"]]
        if ch.has_feature(s, "Aura of Protection") and dist(o, t) <= 10:
            best = max(best, max(1, mod(s["abilities"]["CHA"])))
    return best


def pc_save(enc: dict | None, chars: dict, t: dict, ability: str, dc: int) -> tuple[dict, bool]:
    """A PC saving throw with Aura of Protection, Indomitable (reroll a failure) and Lucky."""
    s = chars[t["character_id"]]
    bonus = ch.save_bonus(s, ability) + aura_bonus(enc, chars, t)
    r = _lucky(t, chars, dice.d20(bonus), bonus, "normal")
    ok = r["total"] >= dc
    if not ok and ch.has_feature(s, "Indomitable") and ch.uses_left(s, "Indomitable") > 0:
        ch.use_feature(s, "Indomitable")
        r = dice.d20(bonus + (s["level"] if ch.rs(s) == "2024" else 0))
        r["indomitable"] = True
        ok = r["total"] >= dc
    return r, ok


def _concentration_check(enc: dict, chars: dict, t: dict, damage: int) -> list[dict]:
    s = chars[t["character_id"]]
    if not s.get("concentration") or damage <= 0:
        return []
    if s["hp"] <= 0:
        return end_concentration(enc, chars, t)
    dc = min(30, max(10, damage // 2)) if ch.rs(s) == "2024" else max(10, damage // 2)
    r, ok = pc_save(enc, chars, t, "CON", dc)
    tag = " (Indomitable)" if r.get("indomitable") else ""
    if ok:
        return [line(f"{s['name']} keeps concentration (CON {r['total']} vs DC {dc}){tag}.", "roll")]
    return [line(f"{s['name']} fails a concentration save (CON {r['total']} vs DC {dc}).", "roll")] + \
        end_concentration(enc, chars, t)


# ── damage ──────────────────────────────────────────────────────────────────

def _has(text: str, dtype: str) -> bool:
    return bool(dtype) and dtype.lower() in (text or "").lower()


def apply_damage(enc: dict, chars: dict, t: dict, amount: int, dtype: str = "", source: dict | None = None) -> tuple[int, str, list]:
    """Apply damage to a token; returns (damage dealt, status note, extra log lines)."""
    extra: list[dict] = []
    if t["kind"] == "monster":
        if _has(t.get("immune", ""), dtype):
            return 0, "immune", extra
        if _has(t.get("vulnerable", ""), dtype):
            amount *= 2
        elif _has(t.get("resist", ""), dtype):
            amount //= 2
        t["hp"] = max(0, t["hp"] - amount)
        for c in ("Asleep", "Unconscious", "Charmed"):
            if c in t["conditions"] and amount > 0:
                t["conditions"].remove(c)
        if t["hp"] == 0:
            if source and source["kind"] == "pc":
                extra += _on_kill(enc, chars, source)
            return amount, "dies", extra
        return amount, ("bloodied" if t["hp"] <= t["hp_max"] // 2 else ""), extra
    s = chars[t["character_id"]]
    rage = ["bludgeoning", "piercing", "slashing"] if t.get("raging") else []
    res = ch.take_damage(s, amount, dtype, rage)
    if enc.get("death_rule") == "heroic" and s.get("dead"):
        s["dead"] = False
        s["death_saves"]["fail"] = 2
    extra += _concentration_check(enc, chars, t, res["damage"])
    if res["endured"]:
        return res["damage"], "endures", extra
    if res["died"]:
        return res["damage"], "dies", extra
    if res["down"]:
        t["raging"] = False
        return res["damage"], "falls unconscious", extra
    return res["damage"], "", extra


def _on_kill(enc: dict, chars: dict, killer: dict) -> list[dict]:
    s = chars.get(killer["character_id"])
    if s and s["class"] == "warlock" and s.get("subclass") == "fiend":
        temp = max(1, mod(s["abilities"]["CHA"]) + s["level"])
        if temp > s.get("temp_hp", 0):
            s["temp_hp"] = temp
            return [line(f"Dark One's Blessing: {s['name']} gains {temp} temporary HP.", "combat")]
    return []


def _status_text(name: str, note: str) -> str:
    return {"dies": f" {name} falls.", "falls unconscious": f" {name} drops, unconscious!",
            "bloodied": f" {name} is bloodied.", "immune": f" {name} is unharmed.",
            "endures": f" {name} refuses to fall (Relentless Endurance)!"}.get(note, "")


# ── attacks ─────────────────────────────────────────────────────────────────

def _advantage(enc: dict, chars: dict, att: dict, tgt: dict, ranged: bool, d: int, normal: int | None) -> str:
    adv = dis = False
    tc = set(conds(tgt, chars))
    ac = set(conds(att, chars))
    if tc & {"Paralyzed", "Unconscious", "Asleep", "Restrained", "Stunned", "Blinded", "Outlined"}:
        adv = True
    if "Prone" in tc:
        if ranged:
            dis = True
        else:
            adv = True
    if tgt.get("dodging") and not incapacitated(tgt, chars):
        dis = True
    if tgt.get("exposed"):
        adv = True
    if ac & {"Poisoned", "Prone", "Blinded", "Frightened", "Restrained", "Mocked"}:
        dis = True
    if att.get("reckless") and not ranged:
        adv = True
    if att.get("hidden"):
        adv = True
    if ranged:
        if any(dist(att, e) <= 5 for e in enemies(enc, att, chars) if not incapacitated(e, chars)):
            dis = True
        if normal and d > normal:
            dis = True
    if att.get("pack_tactics") and any(dist(a, tgt) <= 5 for a in allies(enc, att, chars)):
        adv = True
    if att.get("vex") == tgt["id"]:  # Vex mastery
        adv = True
    if att.get("sapped"):  # Sap mastery
        dis = True
    if adv and not dis:
        return "advantage"
    if dis and not adv:
        return "disadvantage"
    return "normal"


def _lucky(att: dict, chars: dict, r: dict, bonus: int, adv: str) -> dict:
    s = sheet_of(att, chars)
    if s and ch.race_info(s)["mechanics"].get("lucky") and r["natural"] == 1:
        r2 = dice.d20(bonus, adv)
        r2["lucky"] = True
        return r2
    return r


def _sides(notation: str) -> int:
    m = re.search(r"d(\d+)", notation or "")
    return int(m.group(1)) if m else 0


def resolve_attack(enc: dict, chars: dict, att: dict, tgt: dict, *, name: str, to_hit: int, dmg: str, dtype: str,
                   ranged: bool, normal: int | None, crit_on: int = 20, weapon: bool = True, spell: bool = False,
                   finesse: bool = False, weapon_die: str | None = None, mastery: str | None = None,
                   ability_mod: int = 0, cleave: bool = False) -> list[dict]:
    d = dist(att, tgt)
    adv = _advantage(enc, chars, att, tgt, ranged, d, normal)
    if att.get("vex") == tgt["id"]:
        att.pop("vex", None)
    att.pop("sapped", None)
    bonus = 0
    notes = []
    s0 = sheet_of(att, chars)
    if s0 and ch.rs(s0) == "2024" and s0.get("exhaustion"):
        bonus -= 2 * int(s0["exhaustion"])
    if has_cond(att, chars, "Blessed"):
        b = dice.die(4)
        bonus += b
    if att.get("sacred") and weapon:
        bonus += att["sacred"]
    if has_cond(att, chars, "Inspired"):
        insp = dice.roll(att.get("inspire_die", "1d6")).total
        bonus += insp
        remove_cond(att, chars, "Inspired")
        notes.append(f"+{insp} inspiration")
    if has_cond(att, chars, "Baned"):
        bonus -= dice.die(4)
    r = dice.d20(to_hit + bonus, adv)
    r = _lucky(att, chars, r, to_hit + bonus, adv)
    if "Mocked" in conds(att, chars):
        remove_cond(att, chars, "Mocked")
    att.pop("hidden", None)
    if "Outlined" in tgt.get("conditions", []) and spell is False and tgt.get("outline_once"):
        remove_cond(tgt, chars, "Outlined")
    ac = token_ac(tgt, chars)
    auto_crit = d <= 5 and bool(set(conds(tgt, chars)) & {"Paralyzed", "Unconscious", "Asleep"})
    hit = r["natural"] == 20 or (r["natural"] != 1 and r["total"] >= ac)
    crit = hit and (r["natural"] >= crit_on or auto_crit)
    adv_txt = {"advantage": " (adv)", "disadvantage": " (dis)"}.get(adv, "")
    # Players don't see a monster's AC (the DM has it); a character's own AC is no secret.
    vs = f" vs AC {ac}" if tgt["kind"] == "pc" else ""
    head = f"{att['name']} attacks {tgt['name']} with {name}: {r['total']}{adv_txt}{vs}"
    data = {"attacker": att["id"], "target": tgt["id"], "roll": r, "ac": ac if tgt["kind"] == "pc" else None,
            "hit": hit, "crit": crit,
            "attack": name, "damage_type": dtype, "ranged": ranged, "spell": spell, "damage_notation": dmg}
    if not hit:
        out = [line(head + " — miss.", "combat", **data)]
        if mastery == "Graze" and ability_mod > 0 and weapon:
            dealt, note, extra = apply_damage(enc, chars, tgt, ability_mod, dtype, att)
            out.append(line(f"Graze: {tgt['name']} still takes {dealt} {dtype} damage." + _status_text(tgt["name"], note), "combat"))
            out += extra
        return out
    dmg_dice: list[dict] = []  # every damage die rolled, for the dice on the table

    def roll_dmg(notation: str) -> int:
        r_ = dice.damage(notation, crit)
        dmg_dice.extend({"sides": _sides(notation), "value": v} for v in r_.rolls)
        return r_.total

    total = roll_dmg(dmg)
    out_extra: list[dict] = []
    s = sheet_of(att, chars)
    melee_weapon = weapon and not ranged
    if s:
        if weapon and ch.has_feat(s, "Savage Attacker") and not att.get("savage_used"):
            second = dice.damage(dmg, crit).total  # roll the weapon's damage twice, keep the higher (once per turn)
            if second > total:
                notes.append(f"savage attacker {total}→{second}")
                total = second
            att["savage_used"] = True
        if att.get("raging") and melee_weapon:
            rb = 2 if s["level"] < 9 else 3
            total += rb
            notes.append(f"+{rb} rage")
        if crit and melee_weapon and weapon_die:
            extra_dice = (1 if ch.race_info(s)["mechanics"].get("savage") else 0) + \
                (1 if ch.has_feature(s, "Brutal Critical") else 0)
            if extra_dice:
                extra = sum(dice.roll(weapon_die).total for _ in range(extra_dice))
                total += extra
                notes.append(f"+{extra} brutal")
        if weapon and ch.has_feature(s, "Divine Strike") and not att.get("divine_strike_used"):
            ds = roll_dmg("1d8" if s["level"] < 14 else "2d8")
            total += ds
            att["divine_strike_used"] = True
            notes.append(f"+{ds} divine strike")
        mark = tgt.get("mark")
        if mark and mark.get("by") == att["id"] and (weapon or mark.get("any_attack")):
            m = roll_dmg(mark["dice"])
            total += m
            notes.append(f"+{m} mark")
        if weapon and s["class"] == "ranger" and s.get("subclass") == "hunter" and not att.get("colossus_used") \
                and _below_max(tgt, chars):
            c = roll_dmg("1d8")
            total += c
            att["colossus_used"] = True
            notes.append(f"+{c} colossus slayer")
        if weapon and s["class"] == "rogue" and not att.get("sneak_used") and (finesse or ranged) and adv != "disadvantage" and \
                (adv == "advantage" or any(dist(a, tgt) <= 5 for a in allies(enc, att, chars) if not incapacitated(a, chars))):
            sa = roll_dmg(f"{(s['level'] + 1) // 2}d6")
            total += sa
            att["sneak_used"] = True
            notes.append(f"+{sa} sneak attack")
        if melee_weapon and att.get("smite_armed"):
            slot = ch.lowest_free_slot(s)
            if slot:
                ch.use_slot(s, slot)
                n = min(5, 1 + slot + (1 if tgt.get("ctype") in ("undead", "fiend") else 0))
                sm = roll_dmg(f"{n}d8")
                total += sm
                notes.append(f"+{sm} radiant smite")
            att["smite_armed"] = False
        if melee_weapon and att.get("stun_armed") and tgt["kind"] == "monster" and ch.uses_left(s, "Ki") > 0:
            ch.use_feature(s, "Ki")
            att["stun_armed"] = False
            kdc = 8 + prof_bonus(s["level"]) + mod(s["abilities"]["WIS"])
            sv = dice.d20(save_bonus(tgt, chars, "CON"))
            if sv["total"] < kdc:
                add_cond(tgt, chars, "Stunned")
                out_extra.append(line(f"{tgt['name']} is stunned (CON {sv['total']} vs DC {kdc})!", "combat"))
            else:
                out_extra.append(line(f"{tgt['name']} shakes off the stunning strike (CON {sv['total']} vs DC {kdc}).", "combat"))
    # Uncanny Dodge
    ts = sheet_of(tgt, chars)
    if ts and ts["class"] == "rogue" and ch.has_feature(ts, "Uncanny Dodge") and tgt.get("reaction", True) \
            and not incapacitated(tgt, chars):
        total = total // 2
        tgt["reaction"] = False
        notes.append("halved by Uncanny Dodge")
    dealt, note, extra_lines = apply_damage(enc, chars, tgt, max(1, total), dtype, att)
    data["damage"] = dealt
    data["damage_dice"] = [d_ for d_ in dmg_dice if d_["sides"]][:20]
    note_txt = f" ({', '.join(notes)})" if notes else ""
    out = [line(f"{head} — {'critical hit' if crit else 'hit'}! {dealt} {dtype} damage{note_txt}."
                + _status_text(tgt["name"], note), "combat", **data)] + out_extra + extra_lines
    if mastery and weapon and s:
        out += _mastery_effect(enc, chars, att, tgt, s, mastery, dealt, ability_mod, ranged, dtype, cleave)
    return out


def _mastery_effect(enc: dict, chars: dict, att: dict, tgt: dict, s: dict, mastery: str, dealt: int, ability_mod: int,
                    ranged: bool, dtype: str, cleave: bool) -> list[dict]:
    """2024 weapon mastery properties, applied after a hit."""
    out: list[dict] = []
    alive_t = alive(tgt, chars)
    dc = 8 + ability_mod + prof_bonus(s["level"])
    if mastery == "Vex" and dealt > 0 and alive_t:
        att["vex"] = tgt["id"]
    elif mastery == "Sap" and alive_t:
        tgt["sapped"] = True
        out.append(line(f"Sap: {tgt['name']} is thrown off balance (disadvantage on its next attack).", "combat"))
    elif mastery == "Slow" and dealt > 0 and alive_t:
        add_cond(tgt, chars, "Slowed")
    elif mastery == "Topple" and alive_t and tgt["kind"] == "monster":
        sv = dice.d20(save_bonus(tgt, chars, "CON"))
        if sv["total"] < dc:
            add_cond(tgt, chars, "Prone")
            out.append(line(f"Topple: {tgt['name']} is knocked prone (CON {sv['total']} vs DC {dc}).", "combat"))
    elif mastery == "Push" and alive_t and tgt["kind"] == "monster":
        dx = (tgt["x"] > att["x"]) - (tgt["x"] < att["x"])
        dy = (tgt["y"] > att["y"]) - (tgt["y"] < att["y"])
        occ = occupied(enc, chars, tgt["id"])
        moved = 0
        for _ in range(2):
            nx, ny = tgt["x"] + dx, tgt["y"] + dy
            if not bm.passable(enc, nx, ny) or (nx, ny) in occ:
                break
            tgt["x"], tgt["y"] = nx, ny
            moved += 5
        if moved:
            out.append(line(f"Push: {tgt['name']} is shoved {moved} ft back.", "combat"))
    elif mastery == "Cleave" and not ranged and not cleave and not att.get("cleave_used"):
        other = next((e for e in enemies(enc, att, chars) if e["id"] != tgt["id"] and dist(att, e) <= 5 and dist(tgt, e) <= 5), None)
        if other:
            att["cleave_used"] = True
            a = next((x for x in ch.attacks(s) if x["kind"] == "melee" and x.get("mastery") == "Cleave"), None)
            if a:
                dmg = re.sub(r"[+-]\d+$", "", a["damage"]) if ability_mod > 0 else a["damage"]
                out.append(line(f"Cleave: the swing carries on into {other['name']}!", "combat"))
                out += resolve_attack(enc, chars, att, other, name=a["name"], to_hit=a["to_hit"], dmg=dmg,
                                      dtype=a["damage_type"], ranged=False, normal=None, cleave=True,
                                      finesse=a.get("finesse", False))
    return out


def _below_max(t: dict, chars: dict) -> bool:
    if t["kind"] == "monster":
        return t["hp"] < t["hp_max"]
    s = chars[t["character_id"]]
    return s["hp"] < s["hp_max"]


def _weapon_attack(enc: dict, chars: dict, t: dict, a: dict, tgt: dict) -> list[dict]:
    s = chars[t["character_id"]]
    d = dist(t, tgt)
    ranged = a["kind"] == "ranged"
    normal = a["range_ft"]
    if ranged:
        if d > (a["long_range_ft"] or a["range_ft"]):
            raise RulesError(f"{tgt['name']} is out of range ({d} ft)")
    elif d > a["range_ft"]:
        if a["long_range_ft"] and d <= a["long_range_ft"]:
            ranged, normal = True, a["long_range_ft"]  # thrown
        else:
            raise RulesError(f"{tgt['name']} is out of reach ({d} ft) — move closer first")
    if a.get("ammo"):
        ammo = ch.find_inv_key(s, a["ammo"])
        if not ammo:
            raise RulesError(f"out of ammunition for the {a['name']}")
        ch.remove_item(s, ammo["id"], 1)
    crit_on = 19 if ch.has_feature(s, "Improved Critical") else 20
    wdie = re.match(r"\d*d\d+", a["damage"])
    return resolve_attack(enc, chars, t, tgt, name=a["name"], to_hit=a["to_hit"], dmg=a["damage"],
                          dtype=a["damage_type"], ranged=ranged, normal=normal, crit_on=crit_on,
                          finesse=a.get("finesse", False), weapon_die=("1" + wdie.group(0)[wdie.group(0).index("d"):]) if wdie else None,
                          mastery=a.get("mastery"), ability_mod=a.get("ability_mod", 0))


def attack(enc: dict, chars: dict, tid: str, attack_id: str, target_id: str) -> list[dict]:
    t = require(enc, tid, chars)
    b = t["budget"]
    tgt = enc["tokens"].get(target_id)
    if not tgt or not alive(tgt, chars) or tgt["kind"] == "pc":
        raise RulesError("pick a living enemy to attack")
    s = chars[t["character_id"]]
    a = next((x for x in ch.attacks(s) if x["id"] == attack_id), None)
    if not a:
        raise RulesError("unknown attack")
    if b.get("attacks_left", 0) > 0:
        b["attacks_left"] -= 1
        out = _weapon_attack(enc, chars, t, a, tgt)
    else:
        if not b["action"]:
            raise RulesError("you've already used your action this turn")
        out = _weapon_attack(enc, chars, t, a, tgt)
        b["action"] = False
        b["attacks_left"] = ch.extra_attacks(s) - 1
        t["attacked"] = True
    _log(enc, out)
    return out


# ── areas ───────────────────────────────────────────────────────────────────

def area_cells(enc: dict, origin: tuple[int, int], point: tuple[int, int], area: dict, from_self: bool) -> set[tuple[int, int]]:
    w, h = enc["grid"]["w"], enc["grid"]["h"]
    size = area["size_ft"]
    shape = area["shape"]
    cells: set = set()
    ox, oy = origin
    px, py = point
    dx, dy = px - ox, py - oy
    norm = math.hypot(dx, dy) or 1.0
    ux, uy = dx / norm, dy / norm
    for y in range(h):
        for x in range(w):
            if shape == "sphere":
                c = origin if from_self else point
                if bm.distance_ft(c, (x, y)) <= size:
                    cells.add((x, y))
            elif shape == "cube" and not from_self:
                if bm.distance_ft(point, (x, y)) <= size // 2:
                    cells.add((x, y))
            elif shape in ("cone", "cube"):
                vx, vy = x - ox, y - oy
                d = math.hypot(vx, vy)
                if d == 0 or bm.distance_ft(origin, (x, y)) > size:
                    continue
                cosang = (vx * ux + vy * uy) / d
                limit = 0.87 if shape == "cone" else 0.5  # ~30° half-angle for cones, 60° for a cube pushed out from you
                if cosang >= limit:
                    cells.add((x, y))
            elif shape == "line":
                vx, vy = x - ox, y - oy
                along = vx * ux + vy * uy
                perp = abs(vx * uy - vy * ux)
                if 0 < along <= size / 5 + 0.01 and perp <= 0.55:
                    cells.add((x, y))
    if from_self:
        cells.discard(origin)
    return cells


def tokens_in(enc: dict, chars: dict, cells: set) -> list[dict]:
    return [t for t in enc["tokens"].values() if alive(t, chars) and pos(t) in cells]


# ── spells ──────────────────────────────────────────────────────────────────

def _upcast(dice_str: str, extra: str | None, levels: int) -> str:
    if not extra or levels <= 0:
        return dice_str
    m1 = re.match(r"(\d+)d(\d+)", dice_str)
    m2 = re.match(r"(\d+)d(\d+)", extra)
    if m1 and m2 and m1.group(2) == m2.group(2):
        return f"{int(m1.group(1)) + int(m2.group(1)) * levels}d{m1.group(2)}{dice_str[m1.end():]}"
    return dice_str


def _cantrip_dice(dice_str: str, level: int) -> str:
    if level < 5:
        return dice_str
    m = re.match(r"(\d+)d(\d+)", dice_str)
    return f"{int(m.group(1)) * 2}d{m.group(2)}{dice_str[m.end():]}" if m else dice_str


def cast(enc: dict, chars: dict, tid: str, spell_index: str, target_id: str | None, slot_level: int | None,
         x: int | None = None, y: int | None = None) -> list[dict]:
    t = require(enc, tid, chars)
    s = chars[t["character_id"]]
    if not ch.knows_spell(s, spell_index):
        raise RulesError(f"{s['name']} doesn't have that spell ready")
    eff = FX(s).get(spell_index)
    rec = srd.spells(ch.rs(s)).get(spell_index) or srd.spells().get(spell_index, {"name": spell_index, "level": 0})
    if not eff:
        raise RulesError(f"{rec['name']} isn't resolved automatically — describe it as a custom action")
    use_bonus = bool(eff.get("bonus"))
    b = t["budget"]
    if use_bonus and not b["bonus"]:
        raise RulesError("you've already used your bonus action")
    if not use_bonus and not b["action"]:
        raise RulesError("you've already used your action")
    lvl = rec.get("level", 0)
    ability = ch.spell_ability(s)
    smod = mod(s["abilities"][ability]) if ability else 0
    dc = ch.spell_save_dc(s) or 10
    atk = ch.spell_attack(s) or 0
    rng_ft = eff.get("range", 60)
    kind = eff["kind"]
    target_kind = spell_target_for(s, spell_index)
    tgt = enc["tokens"].get(target_id) if target_id else None
    point = (int(x), int(y)) if x is not None and y is not None else None

    # validate targets before spending anything
    if target_kind == "enemy":
        if not tgt or tgt["kind"] == "pc" or not alive(tgt, chars):
            raise RulesError("pick a living enemy as the target")
        if dist(t, tgt) > rng_ft:
            raise RulesError(f"{tgt['name']} is out of range ({rng_ft} ft)")
    elif target_kind == "ally":
        tgt = tgt or t
        if tgt["kind"] != "pc":
            raise RulesError("pick an ally")
        if dist(t, tgt) > max(rng_ft, 5):
            raise RulesError(f"{tgt['name']} is out of range ({rng_ft} ft)")
        if kind == "revive" and not chars[tgt["character_id"]].get("dead"):
            raise RulesError("Revivify only works on a character who has died")
    elif target_kind == "point":
        if not point:
            raise RulesError("pick a square on the map")
        if not eff.get("from_self") and bm.distance_ft(pos(t), point) > rng_ft:
            raise RulesError(f"that square is out of range ({rng_ft} ft)")
        if kind == "teleport" and (not bm.passable(enc, *point) or point in occupied(enc, chars, tid)):
            raise RulesError("you can't teleport there")
    slot = 0
    if lvl > 0:
        free_mi = spell_index in (s.get("spells") or {}).get("bonus_spells", []) and not s.get("mi_free_used") \
            and ch.lowest_free_slot(s, lvl) is None
        if free_mi:  # Magic Initiate: once per long rest without a slot
            s["mi_free_used"] = True
            slot = lvl
        else:
            slot = ch.use_slot(s, int(slot_level or lvl) if (slot_level or lvl) >= lvl else lvl)
    b["bonus" if use_bonus else "action"] = False
    if not use_bonus:
        b["attacks_left"] = 0
    up = max(0, slot - lvl) if slot else 0
    name = rec["name"]
    out: list[dict] = [line(f"{t['name']} casts {name}" + (f" (level {slot})" if slot and slot > lvl else "") + ".", "combat")]
    conc_effects: list[dict] = []
    evocation = str(rec.get("school", "")).lower() == "evocation"
    sculpt = s["class"] == "wizard" and str(s.get("subclass") or "") in ("evocation", "evoker") and evocation
    evo_bonus = 0
    if evocation and ch.has_feature(s, "Empowered Evocation"):
        evo_bonus += max(0, mod(s["abilities"]["INT"]))
    if ch.has_feature(s, "Elemental Affinity") and s.get("ancestry") and eff.get("type") == s["ancestry"]["damage_type"]:
        evo_bonus += max(0, mod(s["abilities"]["CHA"]))

    def victims_for(cells: set) -> list[dict]:
        vs = [v for v in tokens_in(enc, chars, cells) if v["id"] != t["id"]]
        if sculpt or eff.get("enemies_only"):
            vs = [v for v in vs if v["kind"] != "pc"]
        return vs

    if kind == "attack":
        n = 1
        if eff.get("rays"):
            n = eff["rays"] + up
        if eff.get("beams"):
            n = 2 if s["level"] >= 5 else 1
        dmg = _upcast(eff["dice"], eff.get("upcast"), up)
        if eff.get("cantrip") and not eff.get("beams"):
            dmg = _cantrip_dice(dmg, s["level"])
        if eff.get("beams") and ch.has_feature(s, "Agonizing Blast") and smod:
            dmg = f"{dmg}{smod:+d}"
        for i in range(n):
            if not alive(tgt, chars):
                break
            d_i = f"{dmg}{evo_bonus:+d}" if (i == 0 and evo_bonus) else dmg
            res = resolve_attack(enc, chars, t, tgt, name=name, to_hit=atk, dmg=d_i, dtype=eff["type"],
                                 ranged=rng_ft > 5, normal=rng_ft, weapon=False, spell=True)
            out += res
            hitd = res[0]["data"] or {}
            if hitd.get("hit"):
                if eff.get("condition") and tgt["kind"] == "monster":
                    add_cond(tgt, chars, eff["condition"])
                if eff.get("on_hit_condition"):
                    add_cond(tgt, chars, eff["on_hit_condition"])
                    tgt["outline_once"] = True
                if eff.get("drain") and hitd.get("damage"):
                    healed = ch.heal(s, hitd["damage"] // 2)
                    out.append(line(f"{t['name']} drains {healed} HP.", "combat"))
        if eff.get("concentration"):
            out += start_concentration(enc, chars, t, spell_index, [])
    elif kind == "auto":
        darts = eff["darts"] + up
        total = sum(dice.roll("1d4+1").total for _ in range(darts)) + evo_bonus
        dealt, note, extra = apply_damage(enc, chars, tgt, total, eff["type"], t)
        out.append(line(f"{darts} darts strike {tgt['name']} for {dealt} force damage." + _status_text(tgt["name"], note),
                        "combat", attacker=t["id"], target=tgt["id"], damage=dealt))
        out += extra
    elif kind in ("save", "save_condition", "sleep"):
        if eff.get("area"):
            origin = pos(t)
            cells = area_cells(enc, origin, point or pos(tgt or t), eff["area"], bool(eff.get("from_self")))
            vs = victims_for(cells)
        else:
            vs = [tgt]
        if eff.get("creature_type"):
            vs = [v for v in vs if v.get("ctype") == eff["creature_type"] or v["kind"] == "pc"]
        if not vs:
            out.append(line("No one is caught in it.", "combat"))
        if kind == "sleep":
            pool = dice.roll(_upcast(eff["dice"], eff.get("upcast"), up)).total
            slept = []
            for v in sorted([v for v in vs if v["kind"] == "monster" and v.get("ctype") != "undead"], key=lambda v: v["hp"]):
                if v["hp"] > pool:
                    break
                pool -= v["hp"]
                add_cond(v, chars, "Asleep")
                slept.append(v["name"])
            out.append(line((", ".join(slept) + " fall asleep.") if slept else "Nothing succumbs.", "combat"))
        elif kind == "save":
            dmg = _upcast(eff["dice"], eff.get("upcast"), up)
            if eff.get("cantrip"):
                dmg = _cantrip_dice(dmg, s["level"])
            rolled = dice.roll(dmg).total + evo_bonus
            potent = eff.get("cantrip") and ch.has_feature(s, "Potent Cantrip")
            for v in vs:
                if v["kind"] == "pc":
                    sv, ok = pc_save(enc, chars, v, eff["save"], dc)
                else:
                    sv = dice.d20(save_bonus(v, chars, eff["save"]))
                    ok = sv["total"] >= dc
                amount = (rolled // 2 if (eff.get("half") or potent) else 0) if ok else rolled
                dealt, note, extra = apply_damage(enc, chars, v, amount, eff["type"], t) if amount else (0, "", [])
                out.append(line(f"{v['name']}: {eff['save']} save {sv['total']} vs DC {dc} — {'saved' if ok else 'failed'}, "
                                f"{dealt} {eff['type']} damage." + _status_text(v["name"], note), "combat",
                                target=v["id"], damage=dealt, roll=sv))
                out += extra
                if not ok and eff.get("fail_condition") and alive(v, chars):
                    add_cond(v, chars, eff["fail_condition"])
            if eff.get("concentration"):
                out += start_concentration(enc, chars, t, spell_index, [])
        else:  # save_condition
            for v in vs:
                sv = dice.d20(save_bonus(v, chars, eff["save"]))
                if sv["total"] >= dc:
                    out.append(line(f"{v['name']} resists ({eff['save']} {sv['total']} vs DC {dc}).", "combat"))
                    continue
                add_cond(v, chars, eff["condition"])
                if eff.get("save_ends") and v["kind"] == "monster":
                    v.setdefault("save_ends", {})[eff["condition"]] = {"save": eff["save"], "dc": dc}
                if eff.get("one_turn"):
                    v.setdefault("one_turn", []).append(eff["condition"])
                conc_effects.append({"token": v["id"], "condition": eff["condition"]})
                out.append(line(f"{v['name']} is {eff['condition'].lower()} ({eff['save']} {sv['total']} vs DC {dc}).", "combat"))
            if eff.get("concentration"):
                out += start_concentration(enc, chars, t, spell_index, conc_effects)
    elif kind == "heal":
        targets = [tgt]
        if eff.get("multi"):
            pool = [a for a in [t] + allies(enc, t, chars) + [o for o in enc["tokens"].values() if o["kind"] == "pc"
                                                             and not alive(o, chars) and present(o, chars)]
                    if a["kind"] == "pc" and dist(t, a) <= rng_ft]
            pool = sorted({a["id"]: a for a in pool}.values(), key=lambda a: chars[a["character_id"]]["hp"])
            targets = [tgt] + [a for a in pool if a["id"] != tgt["id"]][: eff["multi"] - 1]
        for a in targets:
            hr = dice.roll(_upcast(eff["dice"], eff.get("upcast"), up))
            bonus = smod
            if s["class"] == "cleric" and str(s.get("subclass") or "") == "life":
                bonus += 2 + max(1, slot)
            amount = max(1, hr.total + bonus)
            healed = ch.heal(chars[a["character_id"]], amount)
            out.append(line(f"{a['name']} regains {healed} HP ({' + '.join(map(str, hr.rolls))}{bonus:+d} = {amount}).",
                            "combat", target=a["id"], heal=healed,
                            roll={"rolls": hr.rolls, "natural": None, "modifier": bonus, "total": amount,
                                  "notation": hr.notation}))
        if ch.has_feature(s, "Blessed Healer") and any(a["id"] != t["id"] for a in targets) and slot:
            bh = ch.heal(s, 2 + slot)
            if bh:
                out.append(line(f"Blessed Healer: {t['name']} regains {bh} HP.", "combat"))
    elif kind == "buff":
        targets = [tgt]
        if eff.get("multi"):
            near = sorted([a for a in allies(enc, t, chars) + [t] if a["id"] != tgt["id"] and dist(t, a) <= rng_ft],
                          key=lambda a: dist(t, a))
            targets += near[: eff["multi"] - 1]
        for a in targets:
            sa = chars[a["character_id"]]
            if eff.get("condition"):
                ch.add_condition(sa, eff["condition"])
                conc_effects.append({"character": a["character_id"], "condition": eff["condition"]})
            if eff.get("temp_hp"):
                th = smod if eff["temp_hp"] == "MOD" else dice.roll(eff["temp_hp"]).total + 5 * up
                sa["temp_hp"] = max(sa.get("temp_hp", 0), max(1, th))
            if eff.get("max_hp"):
                bonus = eff["max_hp"] + 5 * up
                sa["hp_max"] += bonus
                sa["hp"] += bonus
        out.append(line("Affects " + ", ".join(a["name"] for a in targets) + ".", "combat"))
        if eff.get("concentration"):
            out += start_concentration(enc, chars, t, spell_index, conc_effects)
    elif kind == "mark":
        tgt["mark"] = {"by": t["id"], "dice": eff["dice"], "any_attack": spell_index == "hex"}
        out += start_concentration(enc, chars, t, spell_index, [{"token": tgt["id"], "mark": True}])
        out.append(line(f"{tgt['name']} is marked by {t['name']}.", "combat"))
    elif kind == "teleport":
        t["x"], t["y"] = point
        out.append(line(f"{t['name']} vanishes and reappears {bm.distance_ft(pos(t), point) or 'nearby'}.", "combat"))
    elif kind == "summon_weapon":
        t["spiritual_weapon"] = {"dice": _upcast(eff["dice"], "1d8", up // 2), "mod": smod}
        if tgt and tgt["kind"] == "monster":
            out += resolve_attack(enc, chars, t, tgt, name="Spiritual Weapon", to_hit=atk, dmg=f"{t['spiritual_weapon']['dice']}{smod:+d}",
                                  dtype="force", ranged=False, normal=None, weapon=False, spell=True)
        out.append(line("A spectral weapon hovers nearby (bonus action to attack again on later turns).", "combat"))
    elif kind == "cleanse":
        sa = chars[tgt["character_id"]]
        removed = [c for c in sa["conditions"] if c in ("Poisoned", "Blinded", "Paralyzed", "Deafened")]
        for c in removed:
            ch.remove_condition(sa, c)
        out.append(line(f"{tgt['name']}: " + (", ".join(removed) + " removed." if removed else "nothing to cure."), "combat"))
    elif kind == "revive":
        sa = chars[tgt["character_id"]]
        sa["dead"] = False
        sa["hp"] = 1
        sa["death_saves"] = {"success": 0, "fail": 0}
        ch.remove_condition(sa, "Unconscious")
        out.append(line(f"{tgt['name']} gasps back to life with 1 HP!", "combat"))
    _log(enc, out)
    return out


# ── class features ──────────────────────────────────────────────────────────

def _need(b: dict, what: str) -> None:
    if not b[what]:
        raise RulesError(f"you've already used your {'bonus action' if what == 'bonus' else what}")


def _unarmed(enc: dict, chars: dict, t: dict, tgt: dict, label: str = "Unarmed Strike") -> list[dict]:
    s = chars[t["character_id"]]
    a = next(x for x in ch.attacks(s) if x["id"] == "unarmed")
    if dist(t, tgt) > 5:
        raise RulesError(f"{tgt['name']} is out of reach")
    return resolve_attack(enc, chars, t, tgt, name=label, to_hit=a["to_hit"], dmg=a["damage"], dtype="bludgeoning",
                          ranged=False, normal=None, finesse=True)


def feature(enc: dict, chars: dict, tid: str, fid: str, target_id: str | None = None,
            x: int | None = None, y: int | None = None) -> list[dict]:
    t = require(enc, tid, chars)
    s = chars[t["character_id"]]
    b = t["budget"]
    tgt = enc["tokens"].get(target_id) if target_id else None
    out: list[dict] = []
    if fid == "rage":
        _need(b, "bonus")
        if t.get("raging"):
            raise RulesError("you're already raging")
        ch.use_feature(s, "Rage")
        b["bonus"] = False
        t["raging"] = True
        out.append(line(f"{t['name']} flies into a rage!", "combat"))
    elif fid == "reckless":
        if not ch.has_feature(s, "Reckless Attack"):
            raise RulesError("you can't do that")
        t["reckless"] = True
        t["exposed"] = True
        out.append(line(f"{t['name']} attacks recklessly!", "combat"))
    elif fid == "frenzy":
        _need(b, "bonus")
        if not t.get("raging"):
            raise RulesError("Frenzy needs you to be raging")
        if not tgt or tgt["kind"] == "pc":
            raise RulesError("pick an enemy")
        a = next((x for x in ch.attacks(s) if x["kind"] == "melee"), None)
        b["bonus"] = False
        out += _weapon_attack(enc, chars, t, a, tgt)
    elif fid == "second_wind":
        _need(b, "bonus")
        ch.use_feature(s, "Second Wind")
        b["bonus"] = False
        healed = ch.heal(s, dice.roll(f"1d10+{s['level']}").total)
        out.append(line(f"{t['name']} uses Second Wind: +{healed} HP.", "combat"))
    elif fid == "action_surge":
        ch.use_feature(s, "Action Surge")
        b["action"] = True
        out.append(line(f"{t['name']} surges into action!", "combat"))
    elif fid in ("martial_arts", "flurry"):
        _need(b, "bonus")
        if not t.get("attacked"):
            raise RulesError("take the Attack action first")
        if not tgt or tgt["kind"] == "pc" or not alive(tgt, chars):
            raise RulesError("pick an enemy next to you")
        if fid == "flurry":
            ch.use_feature(s, "Ki")
        b["bonus"] = False
        for i in range(2 if fid == "flurry" else 1):
            if not alive(tgt, chars):
                break
            res = _unarmed(enc, chars, t, tgt, "Flurry of Blows" if fid == "flurry" else "Martial Arts")
            out += res
            if fid == "flurry" and s.get("subclass") == "open-hand" and (res[0]["data"] or {}).get("hit") and alive(tgt, chars):
                kdc = 8 + prof_bonus(s["level"]) + mod(s["abilities"]["WIS"])
                sv = dice.d20(save_bonus(tgt, chars, "DEX"))
                if sv["total"] < kdc:
                    add_cond(tgt, chars, "Prone")
                    out.append(line(f"{tgt['name']} is knocked prone (Open Hand).", "combat"))
    elif fid == "patient_defense":
        _need(b, "bonus")
        ch.use_feature(s, "Ki")
        b["bonus"] = False
        t["dodging"] = True
        out.append(line(f"{t['name']} takes a defensive stance (Dodge).", "combat"))
    elif fid == "step_of_wind":
        _need(b, "bonus")
        ch.use_feature(s, "Ki")
        b["bonus"] = False
        b["move_ft"] += token_speed(t, chars)
        t["disengaged"] = True
        out.append(line(f"{t['name']} moves like the wind.", "combat"))
    elif fid == "stunning_strike":
        if ch.uses_left(s, "Ki") < 1:
            raise RulesError("no ki left")
        t["stun_armed"] = True
        out.append(line(f"{t['name']} readies a stunning strike.", "combat"))
    elif fid in ("cunning_dash", "cunning_disengage", "cunning_hide"):
        if not ch.has_feature(s, "Cunning Action"):
            raise RulesError("you can't do that")
        _need(b, "bonus")
        b["bonus"] = False
        if fid == "cunning_dash":
            b["move_ft"] += token_speed(t, chars)
            out.append(line(f"{t['name']} dashes.", "combat"))
        elif fid == "cunning_disengage":
            t["disengaged"] = True
            out.append(line(f"{t['name']} disengages.", "combat"))
        else:
            r = dice.d20(ch.skill_bonus(s, "Stealth"))
            best = max((10 + mod(e["abilities"]["WIS"]) for e in enemies(enc, t, chars) if e["kind"] == "monster"), default=10)
            if r["total"] >= best:
                t["hidden"] = True
                out.append(line(f"{t['name']} slips out of sight (Stealth {r['total']}).", "roll"))
            else:
                out.append(line(f"{t['name']} tries to hide but is spotted (Stealth {r['total']} vs {best}).", "roll"))
    elif fid == "bardic_inspiration":
        _need(b, "bonus")
        if not tgt or tgt["kind"] != "pc" or tgt["id"] == t["id"] or dist(t, tgt) > 60:
            raise RulesError("pick another ally within 60 ft")
        ch.use_feature(s, "Bardic Inspiration")
        b["bonus"] = False
        add_cond(tgt, chars, "Inspired")
        tgt["inspire_die"] = "1d8" if s["level"] >= 5 else "1d6"
        out.append(line(f"{t['name']} inspires {tgt['name']}!", "combat"))
    elif fid == "lay_on_hands":
        _need(b, "action")
        if not tgt or tgt["kind"] != "pc" or dist(t, tgt) > 5:
            raise RulesError("pick an ally within reach (or yourself)")
        ts = chars[tgt["character_id"]]
        missing = ts["hp_max"] - ts["hp"]
        left = ch.uses_left(s, "Lay on Hands")
        amount = min(missing, left)
        if amount <= 0:
            raise RulesError("no healing needed" if missing <= 0 else "your Lay on Hands pool is empty")
        ch.use_feature(s, "Lay on Hands", amount)
        b["action"] = False
        b["attacks_left"] = 0
        ch.heal(ts, amount)
        out.append(line(f"{t['name']} lays hands on {tgt['name']}: +{amount} HP.", "combat"))
    elif fid == "divine_smite":
        if not ch.lowest_free_slot(s):
            raise RulesError("no spell slots left to smite with")
        t["smite_armed"] = True
        out.append(line(f"{t['name']}'s weapon glows with holy light.", "combat"))
    elif fid == "sacred_weapon":
        _need(b, "action")
        ch.use_feature(s, "Channel Divinity")
        b["action"] = False
        t["sacred"] = max(1, mod(s["abilities"]["CHA"]))
        out.append(line(f"{t['name']} channels divinity into their weapon (+{t['sacred']} to hit).", "combat"))
    elif fid == "turn_undead":
        _need(b, "action")
        ch.use_feature(s, "Channel Divinity")
        b["action"] = False
        dc = ch.spell_save_dc(s) or 10
        undead = [e for e in enemies(enc, t, chars) if e.get("ctype") == "undead" and dist(t, e) <= 30]
        if not undead:
            out.append(line(f"{t['name']} presents a holy symbol — no undead are close enough.", "combat"))
        for e in undead:
            sv = dice.d20(save_bonus(e, chars, "WIS"))
            if sv["total"] >= dc:
                out.append(line(f"{e['name']} resists the turning (WIS {sv['total']} vs DC {dc}).", "combat"))
            elif s["level"] >= 5 and (e.get("cr") or 0) <= (1 if s["level"] >= 8 else 0.5):
                e["hp"] = 0
                out.append(line(f"{e['name']} crumbles to dust (Destroy Undead)!", "combat"))
            else:
                add_cond(e, chars, "Turned")
                out.append(line(f"{e['name']} is turned and flees!", "combat"))
    elif fid == "preserve_life":
        _need(b, "action")
        ch.use_feature(s, "Channel Divinity")
        b["action"] = False
        pool = 5 * s["level"]
        healed = []
        for a in sorted([t] + allies(enc, t, chars) + [o for o in enc["tokens"].values() if o["kind"] == "pc" and not alive(o, chars)
                                                      and present(o, chars)], key=lambda a: chars[a["character_id"]]["hp"]):
            if a["kind"] != "pc" or dist(t, a) > 30 or pool <= 0:
                continue
            sa = chars[a["character_id"]]
            cap = sa["hp_max"] // 2 - sa["hp"]
            if cap > 0:
                n = min(cap, pool)
                pool -= n
                ch.heal(sa, n)
                healed.append(f"{a['name']} +{n}")
        out.append(line("Preserve Life: " + (", ".join(healed) if healed else "no one needed it") + ".", "combat"))
    elif fid == "breath_weapon":
        _need(b, "action")
        anc = s.get("ancestry")
        if not anc or x is None or y is None:
            raise RulesError("pick a direction on the map")
        ch.use_feature(s, "Breath Weapon")
        b["action"] = False
        b["attacks_left"] = 0
        area = {"shape": anc["shape"], "size_ft": 15 if anc["shape"] == "cone" else 30}
        cells = area_cells(enc, pos(t), (int(x), int(y)), area, True)
        save = "CON" if anc["damage_type"] in ("poison", "cold") else "DEX"
        dc = 8 + mod(s["abilities"]["CON"]) + prof_bonus(s["level"])
        if ch.rs(s) == "2024":
            bd = "1d10" if s["level"] < 5 else "2d10" if s["level"] < 11 else "3d10"
        else:
            bd = "2d6" if s["level"] < 6 else "3d6" if s["level"] < 11 else "4d6"
        rolled = dice.roll(bd).total
        out.append(line(f"{t['name']} breathes {anc['damage_type']}!", "combat"))
        for v in [v for v in tokens_in(enc, chars, cells) if v["id"] != t["id"]]:
            sv = dice.d20(save_bonus(v, chars, save))
            amount = rolled // 2 if sv["total"] >= dc else rolled
            dealt, note, extra = apply_damage(enc, chars, v, amount, anc["damage_type"], t)
            out.append(line(f"{v['name']}: {save} save {sv['total']} vs DC {dc} — {dealt} damage." + _status_text(v["name"], note), "combat"))
            out += extra
    elif fid == "spiritual_weapon":
        _need(b, "bonus")
        sw = t.get("spiritual_weapon")
        if not sw:
            raise RulesError("no spiritual weapon is active")
        if not tgt or tgt["kind"] == "pc" or not alive(tgt, chars):
            raise RulesError("pick an enemy")
        b["bonus"] = False
        out += resolve_attack(enc, chars, t, tgt, name="Spiritual Weapon", to_hit=ch.spell_attack(s) or 0,
                              dmg=f"{sw['dice']}{sw['mod']:+d}", dtype="force", ranged=False, normal=None, weapon=False, spell=True)
    else:
        raise RulesError("unknown feature")
    _log(enc, out)
    return out


# ── other actions ───────────────────────────────────────────────────────────

def _opportunity(enc: dict, chars: dict, mover: dict, old: tuple[int, int], new: tuple[int, int]) -> list[dict]:
    """Enemies whose reach the mover leaves get one reaction attack each."""
    if mover.get("disengaged"):
        return []
    out: list[dict] = []
    for e in enemies(enc, mover, chars):
        if not e.get("reaction", True) or incapacitated(e, chars) or has_cond(e, chars, "Turned"):
            continue
        r = melee_reach(e, chars)
        if not r:
            continue
        if bm.distance_ft(old, pos(e)) <= r < bm.distance_ft(new, pos(e)):
            e["reaction"] = False
            if e["kind"] == "monster":
                a = max([a for a in e["actions"] if not a["ranged"]], key=lambda a: a["to_hit"])
                saved = (mover["x"], mover["y"])
                mover["x"], mover["y"] = old
                out.append(line(f"{e['name']} takes an opportunity attack!", "combat"))
                out += resolve_attack(enc, chars, e, mover, name=a["name"], to_hit=a["to_hit"], dmg=a["dice"],
                                      dtype=a["type"], ranged=False, normal=None)
                mover["x"], mover["y"] = saved
            else:
                s = chars[e["character_id"]]
                a = next((x for x in ch.attacks(s) if x["kind"] == "melee"), None)
                if a:
                    saved = (mover["x"], mover["y"])
                    mover["x"], mover["y"] = old
                    out.append(line(f"{e['name']} takes an opportunity attack!", "combat"))
                    out += resolve_attack(enc, chars, e, mover, name=a["name"], to_hit=a["to_hit"], dmg=a["damage"],
                                          dtype=a["damage_type"], ranged=False, normal=None, finesse=a.get("finesse", False))
                    mover["x"], mover["y"] = saved
            if not alive(mover, chars):
                break
    return out


def move(enc: dict, chars: dict, tid: str, x: int, y: int) -> list[dict]:
    t = require(enc, tid, chars)
    opts = reachable_for(enc, tid, chars)
    if (x, y) not in opts or (x, y) == pos(t):
        raise RulesError("you can't move there")
    old = pos(t)
    t["budget"]["move_ft"] -= opts[(x, y)]
    out = _opportunity(enc, chars, t, old, (x, y))
    if alive(t, chars):
        t["x"], t["y"] = x, y
    _log(enc, out)
    return out


def act(enc: dict, chars: dict, tid: str, kind: str, text: str | None = None) -> list[dict]:
    if kind in ("second_wind", "action_surge"):
        return feature(enc, chars, tid, kind)
    t = require(enc, tid, chars)
    b = t["budget"]
    out: list[dict] = []
    if kind == "dodge":
        _need(b, "action")
        b["action"] = False
        b["attacks_left"] = 0
        t["dodging"] = True
        out.append(line(f"{t['name']} takes the Dodge action.", "combat"))
    elif kind in ("dash", "disengage"):
        _need(b, "action")
        b["action"] = False
        b["attacks_left"] = 0
        if kind == "dash":
            b["move_ft"] += token_speed(t, chars)
        else:
            t["disengaged"] = True
        out.append(line(f"{t['name']} {'dashes' if kind == 'dash' else 'disengages'}.", "combat"))
    elif kind == "custom":
        txt = (text or "").strip()
        if not txt:
            raise RulesError("describe what you do")
        _need(b, "action")
        b["action"] = False
        b["attacks_left"] = 0
        enc["custom_actions"].append({"token": t["id"], "name": t["name"], "text": txt[:500]})
        out.append(line(f"{t['name']}: {txt[:500]}", "action"))
    else:
        raise RulesError("unknown action")
    _log(enc, out)
    return out


def use_item_in_combat(enc: dict, chars: dict, tid: str) -> None:
    t = require(enc, tid, chars)
    _need(t["budget"], "action")
    t["budget"]["action"] = False
    t["budget"]["attacks_left"] = 0


# ── turn flow ───────────────────────────────────────────────────────────────

def end_turn(enc: dict, chars: dict, tid: str) -> list[dict]:
    t = require(enc, tid, chars)
    t["done"] = True
    return advance(enc, chars)


def advance(enc: dict, chars: dict) -> list[dict]:
    out: list[dict] = []
    if check_end(enc, chars):
        return out
    if enc["mode"] == "classic":
        enc["turn"]["actor_id"] = None
        out += _next_actor(enc, chars)
        return out
    pcs = [t for t in enc["tokens"].values() if t["kind"] == "pc" and alive(t, chars) and not incapacitated(t, chars)]
    if all(t.get("done") for t in pcs):
        out += run_monsters(enc, chars)
        if not check_end(enc, chars):
            out += _new_round(enc, chars)
    return out


def _new_round(enc: dict, chars: dict) -> list[dict]:
    enc["round"] += 1
    enc["round_complete"] = True
    return _begin_side(enc, chars, "party")


def _begin_side(enc: dict, chars: dict, side: str) -> list[dict]:
    enc["turn"] = {"side": side, "actor_id": None}
    out: list[dict] = []
    for t in enc["tokens"].values():
        if t["kind"] == ("pc" if side == "party" else "monster"):
            if t["kind"] == "pc":
                out += _death_save(enc, chars, t)
            _reset_budget(t, chars)
    return out


def _death_save(enc: dict, chars: dict, t: dict) -> list[dict]:
    s = chars[t["character_id"]]
    if s["hp"] > 0 or s.get("dead") or "Stable" in s["conditions"] or enc.get("death_rule") == "heroic":
        return []
    aura = aura_bonus(enc, chars, t)
    r = dice.d20(aura)
    r = _lucky(t, chars, r, aura, "normal")
    ds = s.setdefault("death_saves", {"success": 0, "fail": 0})
    if r["natural"] == 20:
        ch.heal(s, 1)
        return [line(f"{s['name']} rolls a natural 20 on a death save and regains 1 HP!", "roll", roll=r)]
    if r["natural"] == 1:
        ds["fail"] += 2
    elif r["total"] >= 10:
        ds["success"] += 1
    else:
        ds["fail"] += 1
    txt = f"{s['name']} makes a death save: {r['natural']} ({ds['success']} successes, {ds['fail']} failures)."
    if ds["fail"] >= 3:
        s["dead"] = True
        txt += f" {s['name']} dies."
    elif ds["success"] >= 3:
        ch.add_condition(s, "Stable")
        txt += f" {s['name']} is stable."
    return [line(txt, "roll", roll=r)]


def _begin_actor(enc: dict, chars: dict) -> list[dict]:
    out: list[dict] = []
    for _ in range(len(enc["order"]) * 2 + 2):
        if check_end(enc, chars):
            return out
        tid = enc["order"][enc["idx"]]
        t = enc["tokens"][tid]
        if not present(t, chars):
            _step_idx(enc)
            continue
        _reset_budget(t, chars)
        if t["kind"] == "monster":
            out += monster_turn(enc, chars, t)
            _step_idx(enc)
            continue
        out += _death_save(enc, chars, t)
        if not alive(t, chars) or incapacitated(t, chars):
            _step_idx(enc)
            continue
        enc["turn"] = {"side": "party", "actor_id": tid}
        return out
    return out


def _step_idx(enc: dict) -> None:
    enc["idx"] += 1
    if enc["idx"] >= len(enc["order"]):
        enc["idx"] = 0
        enc["round"] += 1
        enc["round_complete"] = True


def _next_actor(enc: dict, chars: dict) -> list[dict]:
    _step_idx(enc)
    return _begin_actor(enc, chars)


def run_monsters(enc: dict, chars: dict) -> list[dict]:
    enc["turn"] = {"side": "monsters", "actor_id": None}
    out: list[dict] = []
    for t in list(enc["tokens"].values()):
        if t["kind"] == "monster" and alive(t, chars):
            _reset_budget(t, chars)
            out += monster_turn(enc, chars, t)
            if check_end(enc, chars):
                break
    return out


def _start_of_turn_saves(enc: dict, chars: dict, t: dict) -> list[dict]:
    out = []
    for c in list(t.get("one_turn", [])):
        if c in t["conditions"]:
            t["conditions"].remove(c)
    t["one_turn"] = []
    for c, info in list(t.get("save_ends", {}).items()):
        if c not in t["conditions"]:
            t["save_ends"].pop(c, None)
            continue
        sv = dice.d20(save_bonus(t, chars, info["save"]))
        if sv["total"] >= info["dc"]:
            remove_cond(t, chars, c)
            out.append(line(f"{t['name']} shakes off being {c.lower()} ({info['save']} {sv['total']}).", "combat"))
    return out


def monster_turn(enc: dict, chars: dict, t: dict) -> list[dict]:
    out: list[dict] = _start_of_turn_saves(enc, chars, t)
    if "Stunned" in t["conditions"]:
        t["conditions"].remove("Stunned")
        out.append(line(f"{t['name']} reels, stunned, and loses its turn.", "combat"))
        _log(enc, out)
        return out
    if incapacitated(t, chars):
        _log(enc, out)
        return out
    foes = [e for e in enemies(enc, t, chars)]
    if not foes:
        return out
    conscious = [e for e in foes if not incapacitated(e, chars)] or foes
    foe = min(conscious, key=lambda e: (dist(t, e), e["id"]))
    occ = occupied(enc, chars, t["id"])
    if "Turned" in t["conditions"]:
        # flee: move to the reachable square farthest from the nearest PC
        opts = bm.reachable(enc, pos(t), t["budget"]["move_ft"], occ)
        dest = max(opts, key=lambda p: bm.distance_ft(p, pos(foe)))
        out += _opportunity(enc, chars, t, pos(t), dest)
        if alive(t, chars):
            t["x"], t["y"] = dest
            out.append(line(f"{t['name']} flees in terror.", "combat"))
        _log(enc, out)
        return out
    melee = [a for a in t["actions"] if not a["ranged"]]
    ranged = [a for a in t["actions"] if a["ranged"]]
    d = dist(t, foe)
    act_ = None
    if melee:
        reach = max(a["reach"] for a in melee)
        dest = bm.step_toward(enc, pos(t), pos(foe), t["budget"]["move_ft"], occ, reach)
        if bm.distance_ft(dest, pos(foe)) <= reach:
            if dest != pos(t):
                out += _opportunity(enc, chars, t, pos(t), dest)
            if alive(t, chars):
                t["x"], t["y"] = dest
                act_ = max(melee, key=lambda a: a["to_hit"])
        elif ranged and d <= (ranged[0]["long_range"] or ranged[0]["range"]):
            act_ = ranged[0]
        else:
            out += _opportunity(enc, chars, t, pos(t), dest)
            if alive(t, chars):
                t["x"], t["y"] = dest
    elif ranged:
        if d <= (ranged[0]["long_range"] or ranged[0]["range"]):
            act_ = ranged[0]
        else:
            dest = bm.step_toward(enc, pos(t), pos(foe), t["budget"]["move_ft"], occ, ranged[0]["range"])
            out += _opportunity(enc, chars, t, pos(t), dest)
            if alive(t, chars):
                t["x"], t["y"] = dest
    if act_ and alive(t, chars):
        n = t.get("multiattack", 1) if not act_["ranged"] or len(t["actions"]) == 1 else 1
        for _ in range(max(1, n)):
            if not alive(foe, chars):
                rest = [e for e in enemies(enc, t, chars) if dist(t, e) <= (act_["reach"] if not act_["ranged"] else act_["long_range"] or act_["range"])]
                if not rest:
                    break
                foe = rest[0]
            out += resolve_attack(enc, chars, t, foe, name=act_["name"], to_hit=act_["to_hit"], dmg=act_["dice"],
                                  dtype=act_["type"], ranged=act_["ranged"], normal=act_["range"] if act_["ranged"] else None)
    elif alive(t, chars) and not out:
        out.append(line(f"{t['name']} closes in on {foe['name']}.", "combat"))
    _log(enc, out)
    return out


def auto_turn(enc: dict, chars: dict, tid: str, policy: str) -> list[dict]:
    """Play a PC whose player missed the deadline (policy 'ai'), or have them Dodge ('skip')."""
    t = enc["tokens"][tid]
    out: list[dict] = []
    if not can_act(enc, tid, chars):
        return out
    s = chars[t["character_id"]]
    if policy == "ai":
        try:
            out += _ai_heal(enc, chars, t, s)
        except RulesError:
            pass
        foes = enemies(enc, t, chars)
        atks = ch.attacks(s)
        if foes and t["budget"]["action"]:
            foe = min(foes, key=lambda e: dist(t, e))
            melee = [a for a in atks if a["kind"] == "melee" and a["id"] != "unarmed"] or [a for a in atks if a["kind"] == "melee"]
            ranged = [a for a in atks if a["kind"] == "ranged" and (not a.get("ammo") or ch.find_inv_key(s, a["ammo"]))]
            fx = FX(s)
            cantrip = next((c for c in ch.all_cantrips(s)
                            if fx.get(c, {}).get("kind") in ("attack", "save") and not fx[c].get("area")), None)
            d = dist(t, foe)
            try:
                if ranged and 5 < d <= (ranged[0]["long_range_ft"] or ranged[0]["range_ft"]):
                    out += attack(enc, chars, tid, ranged[0]["id"], foe["id"])
                elif cantrip and 5 < d <= fx[cantrip].get("range", 60) and ch.spell_ability(s) and \
                        mod(s["abilities"][ch.spell_ability(s)]) >= mod(s["abilities"]["STR"]):
                    out += cast(enc, chars, tid, cantrip, foe["id"], None)
                elif melee:
                    dest = bm.step_toward(enc, pos(t), pos(foe), t["budget"]["move_ft"], occupied(enc, chars, tid), 5)
                    if dest != pos(t):
                        out += move(enc, chars, tid, *dest)
                    while alive(t, chars) and alive(foe, chars) and dist(t, foe) <= melee[0]["range_ft"] and \
                            (t["budget"]["action"] or t["budget"].get("attacks_left", 0) > 0):
                        out += attack(enc, chars, tid, melee[0]["id"], foe["id"])
            except RulesError:
                pass
        if alive(t, chars) and t["budget"]["action"]:
            t["budget"]["action"] = False
            t["dodging"] = True
            out.append(line(f"{t['name']} keeps their guard up (Dodge).", "combat"))
        if out:
            out.insert(0, line(f"(The DM plays {t['name']} this turn.)", "system"))
    else:
        if t["budget"]["action"]:
            t["budget"]["action"] = False
            t["dodging"] = True
        out.append(line(f"{t['name']} hesitates and takes the Dodge action.", "combat"))
    _log(enc, out)
    t["done"] = True
    return out


def _ai_heal(enc: dict, chars: dict, t: dict, s: dict) -> list[dict]:
    """If an ally is down or badly hurt and we can heal, do it."""
    fx = FX(s)
    heals = [i for i in ch.ready_spells(s) if fx.get(i, {}).get("kind") == "heal" and "multi" not in fx[i]]
    if not heals or not ch.lowest_free_slot(s):
        return []
    hurt = [a for a in [o for o in enc["tokens"].values() if o["kind"] == "pc" and present(o, chars)]
            if chars[a["character_id"]]["hp"] <= chars[a["character_id"]]["hp_max"] // 3]
    for sp in sorted(heals, key=lambda i: -fx[i].get("range", 5)):
        eff = fx[sp]
        for a in hurt:
            if dist(t, a) <= eff["range"]:
                bonus = bool(eff.get("bonus"))
                if (bonus and t["budget"]["bonus"]) or (not bonus and t["budget"]["action"]):
                    return cast(enc, chars, t["id"], sp, a["id"], None)
    return []


def check_end(enc: dict, chars: dict) -> str | None:
    if enc.get("outcome"):
        return enc["outcome"]
    mons = [t for t in enc["tokens"].values() if t["kind"] == "monster" and alive(t, chars)]
    pcs = [t for t in enc["tokens"].values() if t["kind"] == "pc" and alive(t, chars)]
    if not mons:
        enc["outcome"] = "victory"
    elif not pcs:
        enc["outcome"] = "defeat"
    return enc.get("outcome")


def finish(enc: dict, chars: dict) -> None:
    """Combat is over: end concentration and combat-only effects on every PC."""
    for t in enc["tokens"].values():
        if t["kind"] == "pc" and t["character_id"] in chars:
            end_concentration(None, chars, t, quiet=True)
            s = chars[t["character_id"]]
            for c in ("Inspired", "Mocked", "Outlined", "Restrained", "Prone", "Frightened", "Stunned", "Slowed"):
                ch.remove_condition(s, c)


def flee(enc: dict) -> None:
    enc["outcome"] = "fled"


def _log(enc: dict, lines: list[dict]) -> None:
    enc.setdefault("round_log", []).extend(l["text"] for l in lines)


# ── view ────────────────────────────────────────────────────────────────────

def hp_state(t: dict, chars: dict) -> str:
    if t["kind"] == "pc":
        s = chars[t["character_id"]]
        if s.get("dead"):
            return "dead"
        hp, mx = s["hp"], s["hp_max"]
    else:
        hp, mx = t["hp"], t["hp_max"]
    if hp <= 0:
        return "down" if t["kind"] == "pc" else "dead"
    if hp <= mx // 2:
        return "bloodied"
    return "hurt" if hp < mx else "healthy"


def view(enc: dict, chars: dict, controls: list[str], prefer: str | None = None) -> dict:
    tokens = []
    for t in enc["tokens"].values():
        if t["kind"] == "monster" and t["hp"] <= 0:
            continue
        flags = {"concentrating": False, "raging": bool(t.get("raging")), "marked": bool(t.get("mark")),
                 "dodging": bool(t.get("dodging")), "hidden": bool(t.get("hidden"))}
        if t["kind"] == "pc":
            s = chars.get(t["character_id"])
            if not s:
                continue
            flags["concentrating"] = bool(s.get("concentration"))
            tokens.append({"id": t["id"], "name": t["name"], "kind": "pc", "character_id": t["character_id"],
                           "x": t["x"], "y": t["y"], "hp": s["hp"], "hp_max": s["hp_max"], "hp_state": hp_state(t, chars),
                           "ac": ch.armor_class(s), "conditions": s.get("conditions", []) + t.get("conditions", []),
                           "speed": ch.speed(s), "size": 1, "color": t["color"], "done": bool(t.get("done")), **flags})
        else:
            tokens.append({"id": t["id"], "name": t["name"], "kind": "monster", "character_id": None,
                           "x": t["x"], "y": t["y"], "hp": None, "hp_max": None, "hp_state": hp_state(t, chars),
                           "ac": None, "conditions": t["conditions"], "speed": t["speed"], "size": 1, "color": t["color"],
                           "done": bool(t.get("done")),
                           "portrait_url": f"/api/files/art/{t['art']}" if t.get("art") else None, **flags})
    actable = [f"pc-{c}" for c in ([prefer] if prefer else []) + controls if can_act(enc, f"pc-{c}", chars)]
    mine = actable[0] if actable else None
    reach: list = []
    targets: list = []
    point_spells: list = []
    budget = None
    if mine:
        t = enc["tokens"][mine]
        budget = dict(t["budget"])
        budget["reaction"] = bool(t.get("reaction", True))
        reach = [[x, y] for (x, y) in reachable_for(enc, mine, chars) if (x, y) != pos(t)]
        s = chars[t["character_id"]]
        atks = ch.attacks(s)
        SPELL_EFFECTS = FX(s)  # noqa: N806 — this caster's ruleset

        def spell_target(i: str) -> str:
            return spell_target_for(s, i)
        known = [i for i in ch.all_cantrips(s) + ch.ready_spells(s) if i in SPELL_EFFECTS]
        can_attack = budget["action"] or budget.get("attacks_left", 0) > 0
        feats = [a for a in ch.actions(s)] + ([{"id": "spiritual_weapon", "target": "enemy", "range_ft": 60}]
                                              if t.get("spiritual_weapon") else [])
        for e in enc["tokens"].values():
            if not alive(e, chars) and not (e["kind"] == "pc" and present(e, chars)):
                continue
            d = dist(t, e)
            if e["kind"] == "monster":
                aids = [a["id"] for a in atks if d <= max(a["range_ft"], a["long_range_ft"] or 0)] if can_attack else []
                sids = [i for i in known if spell_target(i) == "enemy" and d <= SPELL_EFFECTS[i].get("range", 60)]
                fids = [f["id"] for f in feats if f.get("target") == "enemy" and d <= (f.get("range_ft") or 5)]
            else:
                aids = []
                sids = [i for i in known if spell_target(i) == "ally" and d <= max(5, SPELL_EFFECTS[i].get("range", 60))
                        and (alive(e, chars) or SPELL_EFFECTS[i]["kind"] in ("heal", "revive"))]
                fids = [f["id"] for f in feats if f.get("target") == "ally" and d <= (f.get("range_ft") or 5)]
            if aids or sids or fids:
                targets.append({"token_id": e["id"], "attack_ids": aids, "spell_indexes": sids, "feature_ids": fids})
        for i in known:
            if spell_target(i) == "point":
                eff = SPELL_EFFECTS[i]
                point_spells.append({"spell_index": i, "range_ft": eff.get("range", 60), "area": eff.get("area"),
                                     "from_self": bool(eff.get("from_self"))})
    return {
        "round": enc["round"], "mode": enc["mode"], "turn": enc["turn"], "grid": enc["grid"], "cells": enc["cells"],
        "terrain": enc["terrain"], "props": enc.get("props", []), "difficult": enc.get("difficult", "difficult terrain"),
        "tokens": tokens + [{"id": f"npc-{i}", "name": b["name"], "kind": "npc", "character_id": None, "x": b["x"],
                             "y": b["y"], "hp": None, "hp_max": None, "hp_state": "healthy", "ac": None, "conditions": [],
                             "speed": 30, "size": 1, "color": "#5a7d9a", "done": True}
                            for i, b in enumerate(enc.get("bystanders") or [])],
        "my_turn": bool(mine), "my_token_id": mine, "budget": budget,
        "reachable": reach, "targets": targets, "point_spells": point_spells, "outcome": enc.get("outcome"),
        "spiritual_weapon": bool(mine and enc["tokens"][mine].get("spiritual_weapon")),
    }
