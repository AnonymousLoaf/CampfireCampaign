"""Characters: creation, derived stats, inventory, HP, rests, spells and levelling (levels 1-5).

A character's stored `sheet` holds the facts (scores, level, HP, inventory, spells…);
everything derived (AC, attacks, saves, skills, actions) is computed by `view()`.
"""
from __future__ import annotations

import re
import uuid

from . import srd
from .classes import (ABILITIES, ALIGNMENTS, BACKGROUNDS, CLASSES, DRAGON_ANCESTRIES, FIGHTING_STYLES,
                      FULL_CASTER_SLOTS, HALF_CASTER_SLOTS, MAX_LEVEL, MEDIUM_ARMOR, PACT_SLOTS, POINT_BUY_COSTS,
                      RACE_EXTRAS, RACE_RESISTANCES, SKILLS, SPELL_EFFECTS, STANDARD_ARRAY, XP_THRESHOLDS,
                      max_spell_level, prof_bonus, spell_kind, spell_target)
from .dice import roll


class RulesError(ValueError):
    """A request that breaks the rules (shown to the player)."""


def mod(score: int) -> int:
    return (score - 10) // 2


def _id() -> str:
    return uuid.uuid4().hex[:10]


def cls_of(sheet: dict) -> dict:
    return CLASSES[sheet["class"]]


def has_feature(sheet: dict, name: str) -> bool:
    return any(f["name"].lower() == name.lower() for f in sheet.get("features", []))


# ── spells ──────────────────────────────────────────────────────────────────

def spell_card(index: str) -> dict:
    s = srd.spells().get(index) or {"index": index, "name": index.replace("-", " ").title(), "level": 0,
                                     "school": "", "description": ""}
    eff = SPELL_EFFECTS.get(index, {})
    rng = eff.get("range")
    if rng is None:
        m = re.match(r"(\d+)\s*feet", s.get("range") or "")
        rng = int(m.group(1)) if m else (5 if (s.get("range") or "").lower() == "touch" else None)
    return {"index": index, "name": s["name"], "level": s.get("level", 0), "school": s.get("school", ""),
            "kind": spell_kind(index), "range_ft": rng, "description": s.get("description", ""),
            "combat": index in SPELL_EFFECTS, "concentration": bool(s.get("concentration") or eff.get("concentration")),
            "ritual": bool(s.get("ritual")), "casting_time": s.get("casting_time", ""),
            "target": spell_target(index), "area": eff.get("area")}


def class_spell_list(cls_key: str, max_level: int, min_level: int = 0) -> list[str]:
    sc = CLASSES[cls_key].get("spellcasting")
    if not sc:
        return []
    return sorted(i for i, s in srd.spells().items()
                  if sc["list"] in (s.get("classes") or []) and min_level <= s.get("level", 0) <= max_level)


def cantrips_known(cls_key: str, level: int) -> int:
    sc = CLASSES[cls_key].get("spellcasting")
    return (sc or {}).get("cantrips_known", {}).get(level, 0) if sc else 0


def spells_known(cls_key: str, level: int) -> int:
    sc = CLASSES[cls_key].get("spellcasting")
    return (sc or {}).get("spells_known", {}).get(level, 0) if sc else 0


def prepared_max(sheet: dict) -> int | None:
    sc = cls_of(sheet).get("spellcasting")
    if not sc or not sc.get("prepares"):
        return None
    ab = mod(sheet["abilities"][sc["ability"]])
    lvl = sheet["level"]
    if sc["type"] == "half":
        return max(1, ab + lvl // 2) if lvl >= 2 else 0
    return max(1, ab + lvl)


def always_prepared(sheet: dict) -> list[str]:
    sc = cls_of(sheet).get("spellcasting") or {}
    out = []
    for lvl, idxs in (sc.get("always") or {}).items():
        if sheet["level"] >= lvl:
            out += idxs
    return [i for i in out if i in srd.spells()]


def prep_options(sheet: dict) -> list[str]:
    sc = cls_of(sheet).get("spellcasting")
    if not sc or not sc.get("prepares"):
        return []
    always = set(always_prepared(sheet))
    if sc.get("spellbook"):
        return [i for i in sheet["spells"].get("spellbook", []) if i not in always]
    msl = max_spell_level(sheet["class"], sheet["level"])
    return [i for i in class_spell_list(sheet["class"], msl, 1) if i not in always] if msl else []


def prepare(sheet: dict, spells: list[str]) -> None:
    mx = prepared_max(sheet)
    if mx is None:
        raise RulesError(f"{cls_of(sheet)['name']}s don't prepare spells — they know a fixed list")
    allowed = set(prep_options(sheet))
    always = set(always_prepared(sheet))
    picks = [s for s in dict.fromkeys(spells) if s not in always]
    bad = [s for s in picks if s not in allowed]
    if bad:
        raise RulesError(f"can't prepare {', '.join(bad)}")
    if len(picks) > mx:
        raise RulesError(f"you can prepare up to {mx} spells")
    sheet["spells"]["spells"] = picks


def ready_spells(sheet: dict) -> list[str]:
    sp = sheet.get("spells") or {}
    out = list(sp.get("spells", []))
    for i in always_prepared(sheet):
        if i not in out:
            out.append(i)
    return out


def knows_spell(sheet: dict, index: str) -> bool:
    return index in (sheet.get("spells") or {}).get("cantrips", []) or index in ready_spells(sheet)


def spell_slots(sheet: dict) -> dict:
    t = (cls_of(sheet).get("spellcasting") or {}).get("type")
    table = FULL_CASTER_SLOTS if t == "full" else HALF_CASTER_SLOTS if t == "half" else None
    if not table:
        return {}
    used = sheet.get("slots_used") or {}
    return {lvl: {"max": n, "used": min(n, used.get(lvl, 0))} for lvl, n in table.get(sheet["level"], {}).items()}


def pact_slots(sheet: dict) -> dict | None:
    if (cls_of(sheet).get("spellcasting") or {}).get("type") != "pact":
        return None
    n, lvl = PACT_SLOTS[sheet["level"]]
    return {"level": lvl, "max": n, "used": min(n, sheet.get("pact_used", 0))}


def use_slot(sheet: dict, level: int) -> int:
    """Spend a slot of at least `level`; returns the level actually used (warlocks always cast at pact level)."""
    pact = pact_slots(sheet)
    if pact:
        if level > pact["level"]:
            raise RulesError(f"your pact slots are level {pact['level']}")
        if pact["used"] >= pact["max"]:
            raise RulesError("no pact slots left — they return on a short rest")
        sheet["pact_used"] = pact["used"] + 1
        return pact["level"]
    slots = spell_slots(sheet)
    s = slots.get(str(level))
    if not s:
        raise RulesError(f"no level-{level} spell slots")
    if s["used"] >= s["max"]:
        raise RulesError(f"no level-{level} spell slots left")
    sheet.setdefault("slots_used", {})[str(level)] = s["used"] + 1
    return level


def lowest_free_slot(sheet: dict, min_level: int = 1) -> int | None:
    pact = pact_slots(sheet)
    if pact:
        return pact["level"] if pact["used"] < pact["max"] and pact["level"] >= min_level else None
    for lvl, s in sorted(spell_slots(sheet).items(), key=lambda kv: int(kv[0])):
        if int(lvl) >= min_level and s["used"] < s["max"]:
            return int(lvl)
    return None


def spell_ability(sheet: dict) -> str | None:
    sc = cls_of(sheet).get("spellcasting")
    return sc["ability"] if sc else None


def spell_save_dc(sheet: dict) -> int | None:
    a = spell_ability(sheet)
    return 8 + prof_bonus(sheet["level"]) + mod(sheet["abilities"][a]) if a else None


def spell_attack(sheet: dict) -> int | None:
    a = spell_ability(sheet)
    return prof_bonus(sheet["level"]) + mod(sheet["abilities"][a]) if a else None


# ── creator options ─────────────────────────────────────────────────────────

def creator_options() -> dict:
    races = []
    subs = srd.subraces()
    for r in srd.races().values():
        extra = RACE_EXTRAS.get(r["index"], {})
        races.append({
            "index": r["index"], "name": r["name"], "speed": r.get("speed", 30), "size": r.get("size", "Medium"),
            "ability_bonuses": r.get("ability_bonuses") or {}, "traits": r.get("traits") or [],
            "languages": r.get("languages") or [],
            "subraces": [{"index": s["index"], "name": s["name"], "ability_bonuses": s.get("ability_bonuses") or {},
                          "traits": s.get("traits") or []} for s in subs.values() if s.get("race") == r["name"]],
            "ability_choices": extra.get("ability_choices"),
            "ancestries": [{"name": a["name"], "damage_type": a["damage_type"]} for a in extra.get("ancestries", [])] or None,
        })
    classes = []
    for c in CLASSES.values():
        sc = c["spellcasting"]
        spell_block = None
        if sc:
            msl = max_spell_level(c["index"], 1)
            lst = class_spell_list(c["index"], max(msl, 0))
            always = set((sc.get("always") or {}).get(1, []))
            n_spells = 6 if sc.get("spellbook") else (spells_known(c["index"], 1) if sc.get("known") else (3 if msl else 0))
            spell_block = {"ability": sc["ability"], "cantrips_known": cantrips_known(c["index"], 1),
                           "spells_at_l1": n_spells, "prepares": sc["prepares"], "known": sc.get("known", False),
                           "pact": sc["type"] == "pact",
                           "cantrips": [spell_card(i) for i in lst if srd.spells()[i]["level"] == 0],
                           "spells": [spell_card(i) for i in lst if srd.spells()[i]["level"] == 1 and i not in always] if msl else []}
        fs_level = c.get("fighting_style_level")
        classes.append({
            "index": c["index"], "name": c["name"], "hit_die": c["hit_die"], "saves": c["saves"],
            "description": c["description"], "skill_choices": c["skill_choices"],
            "armor": c["armor"], "weapons": c["weapons"],
            "equipment_options": [{"id": o["id"], "label": o["label"],
                                   "items": [_item_label(k, q) for k, q, _ in o["items"]] +
                                            [_item_label(k, q) for k, q in c["gear"]]}
                                  for o in c["equipment_options"]],
            "features": [{"name": f["name"], "description": f["description"]} for f in c["features"][1]],
            "spellcasting": spell_block,
            "subclass_level": c["subclass_level"], "subclasses": c["subclasses"],
            "fighting_styles": [{"name": k, "description": v} for k, v in FIGHTING_STYLES.items()] if fs_level == 1 else None,
            "expertise_at_l1": c.get("expertise_at_l1", 0),
        })
    return {
        "races": races, "classes": classes,
        "backgrounds": [{"index": b["index"], "name": b["name"], "skills": b["skills"],
                         "description": b["description"], "gold_cp": b["gold_cp"]} for b in BACKGROUNDS.values()],
        "skills": SKILLS, "standard_array": STANDARD_ARRAY,
        "point_buy": {"budget": 27, "min": 8, "max": 15, "costs": {str(k): v for k, v in POINT_BUY_COSTS.items()}},
        "alignments": ALIGNMENTS,
    }


def _item_label(key: str, qty: int) -> str:
    rec = srd.item(key)
    name = rec["name"] if rec else key
    return f"{name} ×{qty}" if qty > 1 else name


# ── inventory ───────────────────────────────────────────────────────────────

def make_item(key: str, qty: int = 1, equipped: bool = False, custom: dict | None = None) -> dict:
    rec = srd.item(key)
    if not rec and not custom:
        raise RulesError(f"unknown item {key!r}")
    name = (custom or {}).get("name") or rec["name"]
    entry = {"id": _id(), "key": key, "name": name, "qty": qty, "equipped": equipped}
    if custom:
        entry["custom"] = custom
    return entry


def add_item(sheet: dict, key: str, qty: int = 1, equipped: bool = False, custom: dict | None = None) -> dict:
    inv = sheet.setdefault("inventory", [])
    stackable = not equipped and not _is_equippable(key, custom)
    if stackable:
        for it in inv:
            if it["key"] == key and not it.get("custom") and not custom:
                it["qty"] += qty
                return it
    entry = make_item(key, qty, equipped, custom)
    inv.append(entry)
    return entry


def find_inv(sheet: dict, item_id: str) -> dict:
    for it in sheet.get("inventory", []):
        if it["id"] == item_id:
            return it
    raise RulesError("that item isn't in this inventory")


def find_inv_key(sheet: dict, key: str) -> dict | None:
    return next((it for it in sheet.get("inventory", []) if it["key"] == key and it["qty"] > 0), None)


def remove_item(sheet: dict, item_id: str, qty: int = 1) -> dict:
    it = find_inv(sheet, item_id)
    if qty < 1 or qty > it["qty"]:
        raise RulesError(f"only {it['qty']} × {it['name']} to remove")
    it["qty"] -= qty
    if it["qty"] == 0:
        sheet["inventory"].remove(it)
    return it


def _is_equippable(key: str, custom: dict | None = None) -> bool:
    if custom:
        return bool(custom.get("equippable"))
    rec = srd.item(key)
    return bool(rec and rec["category"] in ("Weapon", "Armor"))


def item_view(it: dict) -> dict:
    rec = srd.item(it["key"]) or {}
    custom = it.get("custom") or {}
    cat = custom.get("category") or rec.get("category") or "Treasure"
    return {
        "id": it["id"], "key": it["key"], "name": it["name"], "qty": it["qty"],
        "equipped": bool(it.get("equipped")), "equippable": _is_equippable(it["key"], custom or None),
        "usable": bool(rec.get("usable") or custom.get("heal")), "category": cat,
        "weight": rec.get("weight") or custom.get("weight") or 0,
        "value_cp": custom.get("value_cp", rec.get("cost_cp", 0)),
        "damage": rec.get("damage") or "", "ac": rec.get("ac") or "",
        "properties": [p for p in (rec.get("properties") or []) if p.lower() != "monk"],
        "description": custom.get("description") or rec.get("description") or "",
        "rarity": rec.get("rarity"),
    }


def equip(sheet: dict, item_id: str, equipped: bool) -> None:
    it = find_inv(sheet, item_id)
    if not _is_equippable(it["key"], it.get("custom")):
        raise RulesError(f"{it['name']} can't be equipped")
    if equipped:
        rec = srd.item(it["key"]) or {}
        if rec.get("category") == "Armor":
            is_shield = it["key"] == "shield"
            for other in sheet["inventory"]:
                orec = srd.item(other["key"]) or {}
                if other is not it and orec.get("category") == "Armor" and (other["key"] == "shield") == is_shield:
                    other["equipped"] = False
        if it["qty"] > 1 and rec.get("category") != "Armor":
            it["qty"] -= 1
            sheet["inventory"].append(make_item(it["key"], 1, True, it.get("custom")))
            return
    it["equipped"] = equipped


# ── creation ────────────────────────────────────────────────────────────────

def _final_abilities(base: dict, race: dict, sub: dict | None, bonus: list[str]) -> dict:
    out = {a: int(base[a]) for a in ABILITIES}
    for src in (race.get("ability_bonuses") or {}, (sub or {}).get("ability_bonuses") or {}):
        for a, v in src.items():
            out[a] = out.get(a, 10) + int(v)
    for a in bonus:
        out[a] += 1
    return out


def _validate_scores(method: str, abilities: dict, roll_sets: list | None) -> None:
    vals = [int(abilities.get(a, 0)) for a in ABILITIES]
    if method == "standard":
        if sorted(vals) != sorted(STANDARD_ARRAY):
            raise RulesError("standard array must use 15, 14, 13, 12, 10, 8 once each")
    elif method == "pointbuy":
        if any(v < 8 or v > 15 for v in vals):
            raise RulesError("point buy scores must be between 8 and 15")
        if sum(POINT_BUY_COSTS[v] for v in vals) > 27:
            raise RulesError("point buy is over the 27-point budget")
    elif method == "roll":
        if not roll_sets:
            raise RulesError("roll your ability scores first")
        if sorted(vals) != sorted(s["total"] for s in roll_sets):
            raise RulesError("assigned scores must match your rolled totals")
    else:
        raise RulesError("unknown ability score method")


def create(payload: dict, roll_sets: list | None = None, starting_level: int = 1) -> dict:
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 40:
        raise RulesError("give your character a name (up to 40 characters)")
    race = srd.races().get(payload.get("race") or "")
    if not race:
        raise RulesError("choose a race")
    sub = None
    if payload.get("subrace"):
        sub = srd.subraces().get(payload["subrace"])
        if not sub or sub.get("race") != race["name"]:
            raise RulesError("that subrace doesn't belong to the race")
    cls = CLASSES.get(payload.get("class") or "")
    if not cls:
        raise RulesError("choose a class")
    bg = BACKGROUNDS.get(payload.get("background") or "")
    if not bg:
        raise RulesError("choose a background")
    abilities = payload.get("abilities") or {}
    _validate_scores(payload.get("ability_method") or "", abilities, roll_sets)

    extra = RACE_EXTRAS.get(race["index"], {})
    bonus: list[str] = []
    if extra.get("ability_choices"):
        ac = extra["ability_choices"]
        bonus = list(dict.fromkeys(payload.get("bonus_abilities") or []))
        if len(bonus) != ac["count"] or any(b not in ABILITIES or b in ac["exclude"] for b in bonus):
            raise RulesError(f"choose {ac['count']} different abilities (not {', '.join(ac['exclude'])}) for your racial +1s")
    ancestry = None
    if extra.get("ancestries"):
        ancestry = next((a for a in DRAGON_ANCESTRIES if a["name"].lower() == str(payload.get("ancestry") or "").lower()), None)
        if not ancestry:
            raise RulesError("choose your draconic ancestry")
    scores = _final_abilities(abilities, race, sub, bonus)

    picks = list(dict.fromkeys(payload.get("skills") or []))
    sc = cls["skill_choices"]
    bad = [s for s in picks if s not in sc["options"]]
    if bad:
        raise RulesError(f"{cls['name']} can't choose {', '.join(bad)}")
    overlap = [s for s in picks if s in bg["skills"]]
    picks = [s for s in picks if s not in bg["skills"]]
    if len(picks) + len(overlap) != sc["count"] or (not picks and sc["count"]):
        raise RulesError(f"choose {sc['count']} class skills")
    skill_profs = sorted(set(picks) | set(bg["skills"]))
    n_exp = cls.get("expertise_at_l1", 0)
    expertise: list[str] = []
    if n_exp:
        expertise = [s for s in dict.fromkeys(payload.get("expertise") or []) if s in skill_profs][:n_exp]
        if len(expertise) < n_exp:
            expertise = (expertise + [s for s in picks if s not in expertise])[:n_exp]

    opt = next((o for o in cls["equipment_options"] if o["id"] == payload.get("equipment_option")), None)
    if not opt:
        raise RulesError("choose a starting equipment option")
    style = None
    if cls.get("fighting_style_level") == 1:
        style = payload.get("fighting_style") or opt.get("fighting_style")
        if style not in FIGHTING_STYLES:
            raise RulesError("choose a fighting style")

    sheet: dict = {
        "name": name, "race": race["index"], "subrace": sub["index"] if sub else None,
        "class": cls["index"], "subclass": None, "background": bg["index"],
        "alignment": payload.get("alignment") or "True Neutral",
        "backstory": (payload.get("backstory") or "")[:4000],
        "color": payload.get("color") or "#c9a227",
        "level": 1, "xp": 0, "level_target": 1, "abilities": scores, "base_abilities": {a: int(abilities[a]) for a in ABILITIES},
        "bonus_abilities": bonus, "ancestry": ancestry,
        "skill_profs": skill_profs, "expertise": expertise, "save_profs": list(cls["saves"]),
        "fighting_style": style,
        "conditions": [], "death_saves": {"success": 0, "fail": 0}, "dead": False, "inspiration": False,
        "gold_cp": bg["gold_cp"], "inventory": [], "features": [], "spells": {"cantrips": [], "spells": []},
        "slots_used": {}, "pact_used": 0, "hit_dice_used": 0, "temp_hp": 0, "concentration": None,
        "source": "creator", "issues": [],
    }
    for key, qty, equipped in opt["items"]:
        if srd.item(key):
            sheet["inventory"].append(make_item(key, qty, equipped))
    for key, qty in cls["gear"]:
        if srd.item(key):
            add_item(sheet, key, qty)

    spc = cls["spellcasting"]
    if spc:
        allowed = set(class_spell_list(cls["index"], max(1, max_spell_level(cls["index"], 1))))
        cantrips = [c for c in dict.fromkeys(payload.get("cantrips") or []) if c in allowed and srd.spells()[c]["level"] == 0]
        spells = [s for s in dict.fromkeys(payload.get("spells") or []) if s in allowed and srd.spells()[s]["level"] == 1]
        need_c = cantrips_known(cls["index"], 1)
        if len(cantrips) != need_c:
            raise RulesError(f"choose {need_c} cantrips")
        if spc.get("spellbook"):
            if len(spells) != 6:
                raise RulesError("choose 6 level-1 spells for your spellbook")
            sheet["spells"] = {"cantrips": cantrips, "spellbook": spells, "spells": spells[:max(1, mod(scores["INT"]) + 1)]}
        elif spc.get("known"):
            need = spells_known(cls["index"], 1)
            if len(spells) != need:
                raise RulesError(f"choose {need} level-1 spells")
            sheet["spells"] = {"cantrips": cantrips, "spells": spells}
        else:
            mx = max(3, mod(scores[spc["ability"]]) + 1) if max_spell_level(cls["index"], 1) else 0
            if mx and (not spells or len(spells) > mx):
                raise RulesError(f"choose up to {mx} level-1 spells to prepare")
            sheet["spells"] = {"cantrips": cantrips, "spells": spells}

    sheet["hp_max"] = cls["hit_die"] + mod(scores["CON"]) + _hp_bonus_per_level(sheet)
    sheet["hp"] = sheet["hp_max"]
    _grant_features(sheet, 1)
    if ancestry:
        sheet["features"].append({"name": "Breath Weapon", "description": f"Exhale {ancestry['damage_type']} (2d6) in a "
                                  f"{'15 ft cone' if ancestry['shape'] == 'cone' else '5 by 30 ft line'}; save for half.",
                                  "uses": {"max": 1, "used": 0, "per": "short"}})
    if cls["subclass_level"] == 1:
        sheet["subclass"] = cls["subclasses"][0]["index"]
    target = max(1, min(int(starting_level), MAX_LEVEL))
    while sheet["level"] < target:
        level_up(sheet, auto_choices(sheet))
    sheet["xp"] = XP_THRESHOLDS[sheet["level"]]
    sheet["level_target"] = sheet["level"]
    return sheet


def _hp_bonus_per_level(sheet: dict) -> int:
    b = 0
    if sheet.get("subrace") == "hill-dwarf":
        b += 1
    if sheet["class"] == "sorcerer":
        b += 1  # Draconic Resilience
    return b


def _resolve_uses(sheet: dict, spec) -> int:
    if isinstance(spec, int):
        return spec
    if spec == "CHA":
        return max(1, mod(sheet["abilities"]["CHA"]))
    if spec == "CHA+1":
        return 1 + max(0, mod(sheet["abilities"]["CHA"]))
    if spec == "LEVEL":
        return sheet["level"]
    if spec == "LOH":
        return 5 * sheet["level"]
    return 1


def _grant_features(sheet: dict, level: int) -> None:
    cls = cls_of(sheet)
    for f in cls["features"].get(level, []):
        if f["name"] == "Ability Score Improvement":
            continue
        if has_feature(sheet, f["name"]):
            continue
        entry = {"name": f["name"], "description": f["description"], "uses": None}
        if f.get("uses"):
            entry["uses"] = {"max_spec": f["uses"]["max"], "max": _resolve_uses(sheet, f["uses"]["max"]), "used": 0,
                             "per": f["uses"]["per"]}
        sheet["features"].append(entry)
    _refresh_uses(sheet)


def _refresh_uses(sheet: dict) -> None:
    for f in sheet.get("features", []):
        u = f.get("uses")
        if u and u.get("max_spec") is not None:
            u["max"] = _resolve_uses(sheet, u["max_spec"])
        if u and f["name"] == "Rage":
            u["max"] = 3 if sheet["level"] >= 3 else 2
        if u and f["name"] == "Bardic Inspiration" and sheet["level"] >= 5:
            u["per"] = "short"


# ── levelling ───────────────────────────────────────────────────────────────

def level_for_xp(xp: int) -> int:
    lvl = 1
    for L, need in XP_THRESHOLDS.items():
        if xp >= need and L <= MAX_LEVEL:
            lvl = L
    return lvl


def award_xp(sheet: dict, amount: int) -> bool:
    """Add XP; returns True if a new level became available (the player confirms it)."""
    sheet["xp"] = sheet.get("xp", 0) + max(0, int(amount))
    before = sheet.get("level_target", sheet["level"])
    sheet["level_target"] = max(before, level_for_xp(sheet["xp"]))
    return sheet["level_target"] > before


def grant_milestone(sheet: dict) -> bool:
    if sheet.get("level_target", sheet["level"]) >= MAX_LEVEL:
        return False
    sheet["level_target"] = sheet.get("level_target", sheet["level"]) + 1
    return True


def level_offer(sheet: dict) -> dict | None:
    if sheet.get("level_target", sheet["level"]) <= sheet["level"] or sheet["level"] >= MAX_LEVEL or sheet.get("dead"):
        return None
    cls = cls_of(sheet)
    to = sheet["level"] + 1
    sc = cls.get("spellcasting")
    offer = {"to_level": to, "hit_die": cls["hit_die"], "hp_average": cls["hit_die"] // 2 + 1,
             "con_mod": mod(sheet["abilities"]["CON"]), "asi": to == 4, "subclass_options": None,
             "fighting_style_options": None, "expertise": 0, "expertise_options": [], "cantrips": 0,
             "cantrip_options": [], "spells": 0, "spell_options": [], "max_spell_level": 0,
             "features": [{"name": f["name"], "description": f["description"]} for f in cls["features"].get(to, [])]}
    if cls["subclass_level"] == to and not sheet.get("subclass"):
        offer["subclass_options"] = cls["subclasses"]
    if cls.get("fighting_style_level") == to and not sheet.get("fighting_style"):
        offer["fighting_style_options"] = [{"name": k, "description": v} for k, v in FIGHTING_STYLES.items()]
    if sheet["class"] == "bard" and to == 3:
        offer["expertise"] = 2
        offer["expertise_options"] = [s for s in sheet["skill_profs"] if s not in sheet.get("expertise", [])]
    if sc:
        msl = max_spell_level(sheet["class"], to)
        offer["max_spell_level"] = msl
        have_c = set(sheet["spells"].get("cantrips", []))
        offer["cantrips"] = max(0, cantrips_known(sheet["class"], to) - len(have_c))
        if offer["cantrips"]:
            offer["cantrip_options"] = [spell_card(i) for i in class_spell_list(sheet["class"], 0) if i not in have_c]
        if sc.get("spellbook"):
            offer["spells"] = 2
            have = set(sheet["spells"].get("spellbook", []))
            offer["spell_options"] = [spell_card(i) for i in class_spell_list(sheet["class"], msl, 1) if i not in have]
        elif sc.get("known"):
            have = set(sheet["spells"].get("spells", []))
            offer["spells"] = max(0, spells_known(sheet["class"], to) - len(have))
            if offer["spells"] and msl:
                offer["spell_options"] = [spell_card(i) for i in class_spell_list(sheet["class"], msl, 1) if i not in have]
    return offer


def auto_choices(sheet: dict) -> dict:
    """Sensible picks for automatic levelling (starting levels above 1, AI defaults)."""
    offer = level_offer({**sheet, "level_target": sheet["level"] + 1}) or {}
    cls = cls_of(sheet)
    ch: dict = {"hp_method": "average"}
    if offer.get("asi"):
        prim = cls["primary"][0]
        if sheet["abilities"][prim] <= 18:
            ch["asi"] = {prim: 2}
        else:
            ch["asi"] = {prim: 20 - sheet["abilities"][prim], cls["primary"][1]: 2 - (20 - sheet["abilities"][prim])} \
                if sheet["abilities"][prim] < 20 else {cls["primary"][1]: 2}
    if offer.get("subclass_options"):
        ch["subclass"] = offer["subclass_options"][0]["index"]
    if offer.get("fighting_style_options"):
        ch["fighting_style"] = "Defense"
    if offer.get("expertise"):
        ch["expertise"] = offer["expertise_options"][: offer["expertise"]]

    def pick(opts, n):
        combat_first = sorted(opts, key=lambda o: (not o["combat"], o["level"] * -1, o["name"]))
        return [o["index"] for o in combat_first[:n]]
    if offer.get("cantrips"):
        ch["cantrips"] = pick(offer["cantrip_options"], offer["cantrips"])
    if offer.get("spells"):
        ch["spells"] = pick(offer["spell_options"], offer["spells"])
    return ch


def level_up(sheet: dict, choices: dict | None = None) -> dict:
    if sheet["level"] >= MAX_LEVEL:
        raise RulesError(f"level {MAX_LEVEL} is the cap for now")
    sheet["level_target"] = max(sheet.get("level_target", sheet["level"]), sheet["level"] + 1)
    offer = level_offer(sheet)
    choices = choices or {}
    cls = cls_of(sheet)
    # validate everything before changing anything
    asi = choices.get("asi") or None
    if offer["asi"]:
        if not asi:
            raise RulesError("choose your ability score improvement")
        if sum(int(v) for v in asi.values()) != 2 or any(k not in ABILITIES or int(v) < 1 for k, v in asi.items()):
            raise RulesError("an ability score improvement is +2 to one ability or +1 to two")
        if any(sheet["abilities"][k] + int(v) > 20 for k, v in asi.items()):
            raise RulesError("ability scores can't go above 20")
    sub = None
    if offer["subclass_options"]:
        sub = choices.get("subclass") or offer["subclass_options"][0]["index"]
        if sub not in [s["index"] for s in offer["subclass_options"]]:
            raise RulesError("choose a subclass")
    style = None
    if offer["fighting_style_options"]:
        style = choices.get("fighting_style")
        if style not in FIGHTING_STYLES:
            raise RulesError("choose a fighting style")
    exp = []
    if offer["expertise"]:
        exp = [s for s in dict.fromkeys(choices.get("expertise") or []) if s in offer["expertise_options"]]
        if len(exp) != offer["expertise"]:
            raise RulesError(f"choose {offer['expertise']} skills for expertise")
    new_c = [c for c in dict.fromkeys(choices.get("cantrips") or []) if c in {o["index"] for o in offer["cantrip_options"]}]
    if len(new_c) != offer["cantrips"]:
        raise RulesError(f"choose {offer['cantrips']} new cantrips")
    new_s = [s for s in dict.fromkeys(choices.get("spells") or []) if s in {o["index"] for o in offer["spell_options"]}]
    if len(new_s) != offer["spells"] and offer["spell_options"]:
        raise RulesError(f"choose {offer['spells']} new spells")

    # apply
    sheet["level"] += 1
    if asi:
        for k, v in asi.items():
            sheet["abilities"][k] += int(v)
    con = mod(sheet["abilities"]["CON"])
    if choices.get("hp_method") == "roll":
        hp_roll = roll(f"1d{cls['hit_die']}").total
    else:
        hp_roll = cls["hit_die"] // 2 + 1
    gain = max(1, hp_roll + con) + _hp_bonus_per_level(sheet)
    if asi and "CON" in asi and mod(sheet["abilities"]["CON"] - int(asi["CON"])) != con:
        gain += sheet["level"] - 1  # retroactive HP from a higher CON modifier
    sheet["hp_max"] += gain
    sheet["hp"] += gain
    if sub:
        sheet["subclass"] = sub
    if style:
        sheet["fighting_style"] = style
    if exp:
        sheet["expertise"] = sorted(set(sheet.get("expertise", [])) | set(exp))
    sheet["spells"].setdefault("cantrips", []).extend(new_c)
    sc = cls.get("spellcasting")
    if sc and sc.get("spellbook"):
        sheet["spells"].setdefault("spellbook", []).extend(new_s)
    elif new_s:
        sheet["spells"].setdefault("spells", []).extend(new_s)
    _grant_features(sheet, sheet["level"])
    return {"level": sheet["level"], "hp_gained": gain}


# ── derived stats ───────────────────────────────────────────────────────────

def _equipped(sheet: dict, category: str) -> list[tuple[dict, dict]]:
    out = []
    for it in sheet.get("inventory", []):
        rec = srd.item(it["key"])
        if it.get("equipped") and rec and rec["category"] == category:
            out.append((it, rec))
    return out


_AC = re.compile(r"AC\s*(\d+)(\s*\+\s*DEX)?(?:\s*\(max\s*(\d+)\))?", re.I)


def wearing_armor(sheet: dict) -> bool:
    return any(it["key"] != "shield" for it, _ in _equipped(sheet, "Armor"))


def has_shield(sheet: dict) -> bool:
    return any(it["key"] == "shield" for it, _ in _equipped(sheet, "Armor"))


def armor_class(sheet: dict) -> int:
    ab = sheet["abilities"]
    dex = mod(ab["DEX"])
    armor = [(it, rec) for it, rec in _equipped(sheet, "Armor") if it["key"] != "shield"]
    shield = has_shield(sheet)
    conds = set(sheet.get("conditions") or [])
    if armor:
        rec = armor[0][1]
        m = _AC.search(rec.get("ac") or "")
        base = int(m.group(1)) if m else 10
        if m and m.group(2):
            cap = 2 if rec["index"] in MEDIUM_ARMOR else None
            base += min(dex, cap) if cap is not None else dex
        ac = base
        if sheet.get("fighting_style") == "Defense":
            ac += 1
    else:
        options = [10 + dex]
        if "Mage Armor" in conds:
            options.append(13 + dex)
        if sheet["class"] == "barbarian":
            options.append(10 + dex + mod(ab["CON"]))
        if sheet["class"] == "monk" and not shield:
            options.append(10 + dex + mod(ab["WIS"]))
        if sheet["class"] == "sorcerer":
            options.append(13 + dex)
        ac = max(options)
    if shield:
        ac += 2
    if "Shield of Faith" in conds:
        ac += 2
    if "Hasted" in conds:
        ac += 2
    return ac


def weapon_proficient(sheet: dict, rec: dict) -> bool:
    cls = cls_of(sheet)
    cat = rec.get("weapon_category", "simple")
    return cat in cls["weapon_cats"] or rec["index"] in cls["weapon_extra"]


def martial_arts_die(sheet: dict) -> str:
    return "1d6" if sheet["level"] >= 5 else "1d4"


def _is_monk_weapon(rec: dict) -> bool:
    props = [p.lower() for p in rec.get("properties") or []]
    return rec["index"] == "shortsword" or (rec.get("weapon_category") == "simple" and "two-handed" not in props
                                             and "heavy" not in props)


def _die_size(d: str) -> int:
    m = re.match(r"\d*d(\d+)", d)
    return int(m.group(1)) if m else 0


def attacks(sheet: dict) -> list[dict]:
    ab = sheet["abilities"]
    pb = prof_bonus(sheet["level"])
    out = []
    monk = sheet["class"] == "monk" and not wearing_armor(sheet) and not has_shield(sheet)
    weapons = _equipped(sheet, "Weapon")
    one_weapon = len([1 for _, r in weapons if not srd.weapon_profile(r)["ranged"]]) == 1
    for it, rec in weapons:
        wp = srd.weapon_profile(rec)
        s, d = mod(ab["STR"]), mod(ab["DEX"])
        finesse = wp["finesse"] or (monk and _is_monk_weapon(rec))
        use = d if wp["ranged"] or (finesse and d > s) else s
        if "Shillelagh" in (sheet.get("conditions") or []) and rec["index"] in ("club", "quarterstaff"):
            use = max(use, mod(ab["WIS"]))
        to_hit = use + (pb if weapon_proficient(sheet, rec) else 0)
        if wp["ranged"] and sheet.get("fighting_style") == "Archery":
            to_hit += 2
        dice = wp["dice"]
        if monk and _is_monk_weapon(rec) and _die_size(martial_arts_die(sheet)) > _die_size(dice):
            dice = martial_arts_die(sheet)
        if "Shillelagh" in (sheet.get("conditions") or []) and rec["index"] in ("club", "quarterstaff"):
            dice = "1d8"
        bonus_dmg = use
        if not wp["ranged"] and sheet.get("fighting_style") == "Dueling" and one_weapon and not wp["two_handed"]:
            bonus_dmg += 2
        dmg = f"{dice}{bonus_dmg:+d}" if bonus_dmg else dice
        long = wp["long_range"] if wp["ranged"] else (wp["thrown_range"][0] if wp["thrown_range"] else None)
        out.append({"id": it["id"], "name": rec["name"], "to_hit": to_hit, "damage": dmg,
                    "damage_type": wp["type"], "range_ft": wp["range"], "long_range_ft": long,
                    "kind": "ranged" if wp["ranged"] else "melee", "properties": wp["properties"],
                    "finesse": finesse, "ammo": _ammo_for(rec["index"]) if "Ammunition" in wp["properties"] else None,
                    "two_handed": wp["two_handed"], "weapon_key": rec["index"]})
    if monk or not out:
        s = mod(ab["STR"])
        use = max(s, mod(ab["DEX"])) if monk else s
        dmg = f"{martial_arts_die(sheet)}{use:+d}" if monk else str(max(1, 1 + s))
        out.append({"id": "unarmed", "name": "Unarmed Strike", "to_hit": use + pb, "damage": dmg,
                    "damage_type": "bludgeoning", "range_ft": 5, "long_range_ft": None, "kind": "melee",
                    "properties": [], "finesse": monk, "ammo": None, "two_handed": False, "weapon_key": None})
    return out


_AMMO = {"longbow": "arrow", "shortbow": "arrow", "crossbow-light": "crossbow-bolt", "crossbow-heavy": "crossbow-bolt",
         "crossbow-hand": "crossbow-bolt", "sling": "sling-bullet", "blowgun": "blowgun-needle"}


def _ammo_for(weapon_key: str) -> str | None:
    return _AMMO.get(weapon_key)


def extra_attacks(sheet: dict) -> int:
    return 2 if has_feature(sheet, "Extra Attack") else 1


def skill_bonus(sheet: dict, skill: str) -> int:
    ab = SKILLS[skill]
    b = mod(sheet["abilities"][ab])
    pb = prof_bonus(sheet["level"])
    if skill in (sheet.get("expertise") or []):
        b += 2 * pb
    elif skill in (sheet.get("skill_profs") or []):
        b += pb
    elif has_feature(sheet, "Jack of All Trades"):
        b += pb // 2
    return b


def save_bonus(sheet: dict, ability: str) -> int:
    b = mod(sheet["abilities"][ability])
    if ability in (sheet.get("save_profs") or []):
        b += prof_bonus(sheet["level"])
    return b


def speed(sheet: dict) -> int:
    race = srd.races().get(sheet["race"]) or {}
    sp = race.get("speed", 30)
    heavy = any(rec["index"] in ("ring-mail", "chain-mail", "splint-armor", "plate-armor") for _, rec in _equipped(sheet, "Armor"))
    if has_feature(sheet, "Fast Movement") and not heavy:
        sp += 10
    if has_feature(sheet, "Unarmored Movement") and not wearing_armor(sheet) and not has_shield(sheet):
        sp += 10
    conds = sheet.get("conditions") or []
    if "Hasted" in conds:
        sp *= 2
    if "Slowed" in conds:
        sp = max(0, sp - 10)
    for it, rec in _equipped(sheet, "Armor"):
        if rec.get("str_minimum") and sheet["abilities"]["STR"] < rec["str_minimum"]:
            sp -= 10
    return max(0, sp)


def resistances(sheet: dict) -> list[str]:
    out = list(RACE_RESISTANCES.get(sheet["race"], []))
    if sheet["race"] == "dragonborn" and sheet.get("ancestry"):
        out.append(sheet["ancestry"]["damage_type"])
    return out


def feature(sheet: dict, name: str) -> dict | None:
    for f in sheet.get("features", []):
        if f["name"].lower().startswith(name.lower()):
            return f
    return None


def use_feature(sheet: dict, name: str, amount: int = 1) -> dict:
    f = feature(sheet, name)
    if not f:
        raise RulesError(f"{sheet['name']} doesn't have {name}")
    if f.get("uses"):
        if f["uses"]["used"] + amount > f["uses"]["max"]:
            raise RulesError(f"{name} is used up until you rest")
        f["uses"]["used"] += amount
    return f


def uses_left(sheet: dict, name: str) -> int:
    f = feature(sheet, name)
    if not f or not f.get("uses"):
        return 0
    return f["uses"]["max"] - f["uses"]["used"]


# combat feature buttons: (id, name, kind, target, range, requirement)
def actions(sheet: dict) -> list[dict]:
    out: list[dict] = []
    cls = sheet["class"]
    lvl = sheet["level"]

    def add(fid, name, kind, target="none", rng=None, uses_of=None, desc=""):
        f = feature(sheet, uses_of) if uses_of else None
        u = f["uses"] if f and f.get("uses") else None
        out.append({"id": fid, "name": name, "kind": kind, "description": desc or (f["description"] if f else ""),
                    "target": target, "range_ft": rng, "uses": u,
                    "available": not u or u["used"] < u["max"]})
    if cls == "barbarian":
        add("rage", "Rage", "bonus", uses_of="Rage")
        if lvl >= 2:
            add("reckless", "Reckless Attack", "free", desc="Advantage on your melee attacks this turn; enemies have advantage against you until your next turn.")
        if sheet.get("subclass") == "berserker":
            add("frenzy", "Frenzied Strike", "bonus", "enemy", 5, desc="While raging: one melee weapon attack as a bonus action.")
    if cls == "fighter":
        add("second_wind", "Second Wind", "bonus", uses_of="Second Wind")
        if lvl >= 2:
            add("action_surge", "Action Surge", "free", uses_of="Action Surge")
    if cls == "monk":
        add("martial_arts", "Martial Arts strike", "bonus", "enemy", 5, desc="After taking the Attack action, make one unarmed strike.")
        if lvl >= 2:
            add("flurry", "Flurry of Blows (1 ki)", "bonus", "enemy", 5, uses_of="Ki", desc="After taking the Attack action, make two unarmed strikes.")
            add("patient_defense", "Patient Defense (1 ki)", "bonus", uses_of="Ki", desc="Take the Dodge action as a bonus action.")
            add("step_of_wind", "Step of the Wind (1 ki)", "bonus", uses_of="Ki", desc="Dash or Disengage as a bonus action; jump distance doubles.")
        if lvl >= 5:
            add("stunning_strike", "Stunning Strike (1 ki)", "free", uses_of="Ki", desc="Your next melee hit this turn forces a CON save or the target is stunned.")
    if cls == "rogue" and lvl >= 2:
        add("cunning_dash", "Cunning Action: Dash", "bonus")
        add("cunning_disengage", "Cunning Action: Disengage", "bonus")
        add("cunning_hide", "Cunning Action: Hide", "bonus", desc="Hide (Stealth): your next attack has advantage.")
    if cls == "bard":
        add("bardic_inspiration", "Bardic Inspiration", "bonus", "ally", 60, uses_of="Bardic Inspiration")
    if cls == "paladin":
        add("lay_on_hands", "Lay on Hands", "action", "ally", 5, uses_of="Lay on Hands")
        if lvl >= 2:
            add("divine_smite", "Divine Smite (next hit)", "free", desc="Spend a spell slot on your next melee hit: +2d8 radiant (+1d8 per slot level above 1st).")
        if lvl >= 3:
            add("sacred_weapon", "Channel Divinity: Sacred Weapon", "action", uses_of="Channel Divinity")
    if cls == "cleric" and lvl >= 2:
        add("turn_undead", "Channel Divinity: Turn Undead", "action", uses_of="Channel Divinity",
            desc="Undead within 30 ft make a WIS save or are turned (frightened, fleeing).")
        add("preserve_life", "Channel Divinity: Preserve Life", "action", uses_of="Channel Divinity",
            desc="Heal 5 × your level HP split among wounded allies within 30 ft (up to half their max).")
    if sheet["race"] == "dragonborn" and sheet.get("ancestry") and feature(sheet, "Breath Weapon"):
        add("breath_weapon", f"Breath Weapon ({sheet['ancestry']['damage_type']})", "action", "point",
            15 if sheet["ancestry"]["shape"] == "cone" else 30, uses_of="Breath Weapon")
    return out


def view(char_id: str, owner_id: str, game_id: str | None, sheet: dict) -> dict:
    ab = sheet["abilities"]
    lvl = sheet["level"]
    sp_ab = spell_ability(sheet)
    spellcasting = None
    acts = actions(sheet)
    if sp_ab:
        sc = cls_of(sheet)["spellcasting"]
        conc = sheet.get("concentration")
        spellcasting = {
            "ability": sp_ab, "save_dc": spell_save_dc(sheet), "attack_bonus": spell_attack(sheet),
            "slots": spell_slots(sheet), "pact": pact_slots(sheet),
            "cantrips": [spell_card(i) for i in sheet["spells"].get("cantrips", [])],
            "spells": [spell_card(i) for i in ready_spells(sheet)],
            "prepares": bool(sc.get("prepares")), "prepared_max": prepared_max(sheet), "known": bool(sc.get("known")),
            "spellbook": [spell_card(i) for i in sheet["spells"].get("spellbook", [])] if sc.get("spellbook") else None,
            "options": [spell_card(i) for i in prep_options(sheet)],
            "always": always_prepared(sheet),
            "max_spell_level": max_spell_level(sheet["class"], lvl),
            "concentrating_on": (srd.spells().get(conc["spell"], {}).get("name") if conc else None),
        }
    race = srd.races().get(sheet["race"]) or {"name": sheet["race"]}
    sub = srd.subraces().get(sheet.get("subrace") or "") if sheet.get("subrace") else None
    cls = cls_of(sheet)
    subclass = next((s["name"] for s in cls["subclasses"] if s["index"] == sheet.get("subclass")), sheet.get("subclass"))
    return {
        "id": char_id, "name": sheet["name"], "owner_id": owner_id, "game_id": game_id,
        "race": race["name"], "subrace": sub["name"] if sub else None,
        "class": cls["name"], "subclass": subclass, "background": BACKGROUNDS.get(sheet.get("background") or "", {}).get("name", sheet.get("background")),
        "alignment": sheet.get("alignment"), "backstory": sheet.get("backstory", ""), "color": sheet.get("color"),
        "level": lvl, "xp": sheet.get("xp", 0), "xp_next": XP_THRESHOLDS.get(lvl + 1) if lvl < MAX_LEVEL else None,
        "prof_bonus": prof_bonus(lvl),
        "hp": sheet["hp"], "hp_max": sheet["hp_max"], "temp_hp": sheet.get("temp_hp", 0),
        "ac": armor_class(sheet), "speed": speed(sheet), "initiative": mod(ab["DEX"]),
        "abilities": ab, "mods": {a: mod(v) for a, v in ab.items()},
        "saves": {a: save_bonus(sheet, a) for a in ABILITIES}, "save_profs": sheet.get("save_profs", []),
        "skills": {s: skill_bonus(sheet, s) for s in SKILLS}, "skill_profs": sheet.get("skill_profs", []),
        "expertise": sheet.get("expertise", []),
        "passive_perception": 10 + skill_bonus(sheet, "Perception"),
        "conditions": sheet.get("conditions", []), "death_saves": sheet.get("death_saves", {"success": 0, "fail": 0}),
        "down": sheet["hp"] <= 0 and not sheet.get("dead"), "dead": bool(sheet.get("dead")),
        "inspiration": bool(sheet.get("inspiration")),
        "gold_cp": sheet.get("gold_cp", 0),
        "inventory": [item_view(it) for it in sheet.get("inventory", [])],
        "attacks": [{k: v for k, v in a.items() if k in ("id", "name", "to_hit", "damage", "damage_type", "range_ft",
                                                         "long_range_ft", "kind", "properties")} for a in attacks(sheet)],
        "spellcasting": spellcasting,
        "features": [{"name": f["name"], "description": f["description"],
                      "uses": ({k: f["uses"][k] for k in ("max", "used", "per")} if f.get("uses") else None)}
                     for f in sheet.get("features", [])],
        "actions": acts,
        "resistances": resistances(sheet),
        "fighting_style": sheet.get("fighting_style"),
        "pending_level_up": level_offer(sheet),
        "source": sheet.get("source", "creator"), "issues": sheet.get("issues", []),
    }


# ── HP, conditions, rests ───────────────────────────────────────────────────

def take_damage(sheet: dict, amount: int, dtype: str = "", resist_extra: list[str] | None = None) -> dict:
    amount = max(0, int(amount))
    dt = (dtype or "").lower()
    if dt and (dt in resistances(sheet) or dt in (resist_extra or [])):
        amount //= 2
    absorbed = min(sheet.get("temp_hp", 0), amount)
    sheet["temp_hp"] = sheet.get("temp_hp", 0) - absorbed
    amount -= absorbed
    was_down = sheet["hp"] <= 0
    sheet["hp"] = max(0, sheet["hp"] - amount)
    result = {"damage": amount, "absorbed": absorbed, "down": sheet["hp"] == 0, "died": False, "endured": False}
    if sheet["hp"] == 0 and not was_down and sheet["race"] == "half-orc" and not sheet.get("endurance_used") and amount > 0:
        sheet["hp"] = 1
        sheet["endurance_used"] = True
        result.update(down=False, endured=True)
        return result
    if sheet["hp"] == 0:
        if was_down and amount > 0 and not sheet.get("dead"):
            sheet.setdefault("death_saves", {"success": 0, "fail": 0})["fail"] += 1
            if sheet["death_saves"]["fail"] >= 3:
                sheet["dead"] = True
                result["died"] = True
        if "Unconscious" not in sheet["conditions"]:
            sheet["conditions"].append("Unconscious")
    return result


def heal(sheet: dict, amount: int) -> int:
    if sheet.get("dead"):
        return 0
    before = sheet["hp"]
    sheet["hp"] = min(sheet["hp_max"], sheet["hp"] + max(0, int(amount)))
    if sheet["hp"] > 0:
        sheet["death_saves"] = {"success": 0, "fail": 0}
        for c in ("Unconscious", "Stable"):
            if c in sheet["conditions"]:
                sheet["conditions"].remove(c)
    return sheet["hp"] - before


def add_condition(sheet: dict, name: str) -> None:
    if name not in sheet["conditions"]:
        sheet["conditions"].append(name)


def remove_condition(sheet: dict, name: str) -> None:
    sheet["conditions"] = [c for c in sheet["conditions"] if c.lower() != name.lower()]


TEMP_CONDITIONS = ("Mage Armor", "Shield of Faith", "Blessed", "Hasted", "Heroism", "Hopeful", "Shillelagh", "Inspired")


def short_rest(sheet: dict) -> dict:
    cls = cls_of(sheet)
    healed = 0
    avail = sheet["level"] - sheet.get("hit_dice_used", 0)
    while sheet["hp"] < sheet["hp_max"] and avail > 0 and not sheet.get("dead"):
        r = roll(f"1d{cls['hit_die']}").total + mod(sheet["abilities"]["CON"])
        healed += heal(sheet, max(1, r))
        sheet["hit_dice_used"] = sheet.get("hit_dice_used", 0) + 1
        avail -= 1
    for f in sheet.get("features", []):
        if f.get("uses") and f["uses"]["per"] == "short":
            f["uses"]["used"] = 0
    sheet["pact_used"] = 0
    return {"healed": healed}


def long_rest(sheet: dict) -> dict:
    if sheet.get("dead"):
        return {"healed": 0}
    healed = heal(sheet, sheet["hp_max"])
    sheet["hit_dice_used"] = max(0, sheet.get("hit_dice_used", 0) - max(1, sheet["level"] // 2))
    sheet["slots_used"] = {}
    sheet["pact_used"] = 0
    sheet["endurance_used"] = False
    for f in sheet.get("features", []):
        if f.get("uses"):
            f["uses"]["used"] = 0
    sheet["conditions"] = [c for c in sheet["conditions"] if c not in TEMP_CONDITIONS]
    sheet["temp_hp"] = 0
    sheet["concentration"] = None
    return {"healed": healed}
