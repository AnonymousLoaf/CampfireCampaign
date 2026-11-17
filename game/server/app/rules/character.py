"""Characters: creation, derived stats, inventory, HP, rests, spells and levelling (levels 1-10, 2014 or 2024 rules).

A character's stored `sheet` holds the facts (ruleset, scores, level, HP, inventory, spells…);
everything derived (AC, attacks, saves, skills, actions) is computed by `view()`.
Rules tables come from `rulesets.R(sheet)` so the same code runs both editions.
"""
from __future__ import annotations

import re
import uuid

from . import campfire_races as cf
from . import srd
from .classes import (ABILITIES, ALIGNMENTS, DRAGON_ANCESTRIES, FIGHTING_STYLES, MEDIUM_ARMOR, POINT_BUY_COSTS,
                      RACE_EXTRAS, RACE_RESISTANCES, SKILLS, STANDARD_ARRAY)
from .dice import roll
from .rulesets import R


class RulesError(ValueError):
    """A request that breaks the rules (shown to the player)."""


def mod(score: int) -> int:
    return (score - 10) // 2


def _id() -> str:
    return uuid.uuid4().hex[:10]


def rs(sheet: dict) -> str:
    return sheet.get("ruleset", "2014")


def cls_of(sheet: dict) -> dict:
    return R(sheet).CLASSES[sheet["class"]]


def prof_bonus_of(sheet: dict) -> int:
    return R(sheet).prof_bonus(sheet["level"])


def has_feature(sheet: dict, name: str) -> bool:
    return any(f["name"].lower() == name.lower() for f in sheet.get("features", []))


def has_feat(sheet: dict, name: str) -> bool:
    return any(f.lower() == name.lower() for f in sheet.get("feats", []))


# ── spells ──────────────────────────────────────────────────────────────────

def spell_card(index: str, ruleset: str = "2014") -> dict:
    rules = R(ruleset)
    s = srd.spells(ruleset).get(index) or srd.spells().get(index) or {
        "index": index, "name": index.replace("-", " ").title(), "level": 0, "school": "", "description": ""}
    eff = rules.SPELL_EFFECTS.get(index, {})
    rng = eff.get("range")
    if rng is None:
        m = re.match(r"(\d+)\s*(?:feet|ft)", s.get("range") or "")
        rng = int(m.group(1)) if m else (5 if (s.get("range") or "").lower() == "touch" else None)
    return {"index": index, "name": s["name"], "level": s.get("level", 0), "school": s.get("school", ""),
            "kind": rules.spell_kind(index), "range_ft": rng, "description": s.get("description", ""),
            "combat": index in rules.SPELL_EFFECTS, "concentration": bool(s.get("concentration") or eff.get("concentration")),
            "ritual": bool(s.get("ritual")), "casting_time": s.get("casting_time", ""),
            "target": rules.spell_target(index), "area": eff.get("area")}


def class_spell_list(cls_key: str, max_level: int, min_level: int = 0, ruleset: str = "2014") -> list[str]:
    sc = R(ruleset).CLASSES[cls_key].get("spellcasting")
    if not sc:
        return []
    return sorted(i for i, s in srd.spells(ruleset).items()
                  if sc["list"] in (s.get("classes") or []) and min_level <= s.get("level", 0) <= max_level)


def cantrips_known(cls_key: str, level: int, ruleset: str = "2014") -> int:
    sc = R(ruleset).CLASSES[cls_key].get("spellcasting")
    return (sc or {}).get("cantrips_known", {}).get(level, 0) if sc else 0


def spells_known(cls_key: str, level: int, ruleset: str = "2014") -> int:
    sc = R(ruleset).CLASSES[cls_key].get("spellcasting")
    return (sc or {}).get("spells_known", {}).get(level, 0) if sc else 0


def max_spell_level(sheet_or_cls, level: int | None = None, ruleset: str = "2014") -> int:
    if isinstance(sheet_or_cls, dict):
        return R(sheet_or_cls).max_spell_level(sheet_or_cls["class"], sheet_or_cls["level"])
    return R(ruleset).max_spell_level(sheet_or_cls, level or 1)


def prepared_max(sheet: dict) -> int | None:
    sc = cls_of(sheet).get("spellcasting")
    if not sc or not sc.get("prepares"):
        return None
    lvl = sheet["level"]
    if sc.get("prepared"):  # 2024: a fixed table
        return int(sc["prepared"].get(lvl, sc["prepared"].get(max(sc["prepared"]), 1)))
    ab = mod(sheet["abilities"][sc["ability"]])
    if sc["type"] == "half":
        return max(1, ab + lvl // 2) if lvl >= 2 else 0
    return max(1, ab + lvl)


def species_spells(sheet: dict) -> tuple[list[str], list[str]]:
    """(cantrips, leveled spells) a 2024 species grants: always-known cantrips (a tiefling's Thaumaturgy) and the
    chosen lineage's spells by character level (Wood Elf: Druidcraft, then Longstrider at 3, Pass without Trace at 5).
    Lineage spells are always prepared; the DM rules the once-per-long-rest free cast."""
    if rs(sheet) != "2024" or sheet.get("homebrew_race"):
        return [], []
    mech = race_info(sheet)["mechanics"]
    have = srd.spells("2024")
    cants = list(mech.get("always_cantrips") or [])
    spells: list[str] = []
    for lvl, idxs in ((mech.get("lineage_spells") or {}).get(sheet.get("subrace") or "") or {}).items():
        if sheet["level"] >= int(lvl):
            for i in idxs:
                (cants if (have.get(i) or {}).get("level", 0) == 0 else spells).append(i)
    return [i for i in dict.fromkeys(cants) if i in have], [i for i in dict.fromkeys(spells) if i in have]


def lineage_ability(sheet: dict) -> str:
    """The ability a species' spells use: the player's pick (INT, WIS or CHA), else the best of the three."""
    if sheet.get("lineage_ability") in ("INT", "WIS", "CHA"):
        return sheet["lineage_ability"]
    return max(("INT", "WIS", "CHA"), key=lambda a: sheet["abilities"].get(a, 10))


def always_prepared(sheet: dict) -> list[str]:
    sc = cls_of(sheet).get("spellcasting") or {}
    out = []
    for lvl, idxs in (sc.get("always") or {}).items():
        if sheet["level"] >= int(lvl):
            out += idxs
    out += (sheet.get("spells") or {}).get("bonus_spells", [])
    out += species_spells(sheet)[1]
    have = srd.spells(rs(sheet))
    return [i for i in dict.fromkeys(out) if i in have]


def prep_options(sheet: dict) -> list[str]:
    sc = cls_of(sheet).get("spellcasting")
    if not sc or not sc.get("prepares"):
        return []
    always = set(always_prepared(sheet))
    if sc.get("spellbook"):
        return [i for i in sheet["spells"].get("spellbook", []) if i not in always]
    msl = max_spell_level(sheet)
    return [i for i in class_spell_list(sheet["class"], msl, 1, rs(sheet)) if i not in always] if msl else []


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


def all_cantrips(sheet: dict) -> list[str]:
    sp = sheet.get("spells") or {}
    return list(dict.fromkeys(list(sp.get("cantrips", [])) + list(sp.get("bonus_cantrips", []))
                              + species_spells(sheet)[0]))


def knows_spell(sheet: dict, index: str) -> bool:
    return index in all_cantrips(sheet) or index in ready_spells(sheet)


def spell_slots(sheet: dict) -> dict:
    sc = cls_of(sheet).get("spellcasting") or {}
    t = sc.get("type")
    rules = R(sheet)
    table = rules.FULL_SLOTS if t == "full" else rules.HALF_SLOTS if t == "half" else None
    if not table:
        return {}
    used = sheet.get("slots_used") or {}
    return {lvl: {"max": n, "used": min(n, used.get(lvl, 0))} for lvl, n in table.get(sheet["level"], {}).items()}


def pact_slots(sheet: dict) -> dict | None:
    if (cls_of(sheet).get("spellcasting") or {}).get("type") != "pact":
        return None
    n, lvl = R(sheet).PACT_SLOTS[sheet["level"]]
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
        # a Magic Initiate spell can be cast once per long rest without a slot
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
    if sc:
        return sc["ability"]
    if sheet.get("mi_ability"):
        return sheet["mi_ability"]  # Magic Initiate on a non-caster
    if any(species_spells(sheet)):
        return lineage_ability(sheet)  # a non-caster with lineage magic (a wood elf rogue's Druidcraft)
    return None


def spell_save_dc(sheet: dict) -> int | None:
    a = spell_ability(sheet)
    return 8 + prof_bonus_of(sheet) + mod(sheet["abilities"][a]) if a else None


def spell_attack(sheet: dict) -> int | None:
    a = spell_ability(sheet)
    return prof_bonus_of(sheet) + mod(sheet["abilities"][a]) if a else None


# ── species / races ─────────────────────────────────────────────────────────

_SPECIES_CACHE: dict = {}


def _species_2024() -> dict:
    """Species with subspecies normalised to [{index, name}] (names from the dataset)."""
    if _SPECIES_CACHE:
        return _SPECIES_CACHE
    names = {s["index"]: s["name"] for s in srd.data_2024().get("subspecies", [])}
    for sp in srd.data_2024().get("species", []):
        for x in sp.get("subspecies", []) or []:
            if isinstance(x, dict):
                names.setdefault(x["index"], x.get("name", x["index"]))
    src = R("2024").SPECIES or {s["index"]: {"name": s["name"], "speed": s.get("speed", 30), "size": s.get("size", "Medium"),
                                             "traits": [t.get("name") for t in s.get("traits", [])],
                                             "subspecies": s.get("subspecies", [])}
                                for s in srd.data_2024().get("species", [])}
    for idx, sp in src.items():
        rec = dict(sp)
        subs = []
        for x in sp.get("subspecies", []) or []:
            if isinstance(x, dict):
                subs.append({"index": x["index"], "name": x.get("name") or names.get(x["index"], x["index"])})
            else:
                subs.append({"index": x, "name": names.get(x, x.replace("-", " ").title())})
        rec["subspecies"] = subs
        _SPECIES_CACHE[idx] = rec
    return _SPECIES_CACHE


def nonsrd_race(sheet: dict) -> dict | None:
    """The record for a Campfire race (looked up live) or a homebrew race (snapshot on the sheet); None for SRD races."""
    if sheet.get("homebrew_race") and isinstance(sheet.get("race_data"), dict):
        return sheet["race_data"]
    return cf.CAMPFIRE_RACES.get(sheet.get("race") or "")


def race_source(sheet: dict) -> str:
    if sheet.get("homebrew_race"):
        return "homebrew"
    return "campfire" if sheet.get("race") in cf.CAMPFIRE_RACES else "srd"


def race_traits(sheet: dict) -> list[dict]:
    """[{name, description}] for Campfire and homebrew races (SRD races' traits live in the rules data)."""
    rec = nonsrd_race(sheet)
    return cf.trait_list(rec, rs(sheet)) if rec else []


def race_info(sheet: dict) -> dict:
    """{name, speed, resistances, mechanics} for the character's race (2014) or species (2024)."""
    rec = nonsrd_race(sheet)
    if rec:
        return {"name": rec.get("name") or "Unknown", "speed": int(rec.get("speed") or 30),
                "resistances": list(rec.get("resistances") or []), "mechanics": dict(rec.get("mechanics") or {})}
    if rs(sheet) == "2024":
        sp = _species_2024().get(sheet["race"], {})
        mech = dict(sp.get("mechanics") or {})
        res = list(sp.get("resistances") or [])
        by_sub = mech.get("resist_by_subspecies") or sp.get("resist_by_subspecies") or {}
        if sheet.get("subrace") and sheet["subrace"] in by_sub:
            v = by_sub[sheet["subrace"]]
            res += v if isinstance(v, list) else [v]
        spd = (mech.get("speed_by_subspecies") or {}).get(sheet.get("subrace") or "", sp.get("speed", 30))
        return {"name": sp.get("name", sheet["race"].title()), "speed": spd, "resistances": res, "mechanics": mech}
    race = srd.races().get(sheet["race"]) or {"name": sheet["race"], "speed": 30}
    mech = {"tough_per_level": 1 if sheet.get("subrace") == "hill-dwarf" else 0,
            "lucky": sheet["race"] == "halfling", "relentless": sheet["race"] == "half-orc",
            "savage": sheet["race"] == "half-orc"}
    res = list(RACE_RESISTANCES.get(sheet["race"], []))
    return {"name": race["name"], "speed": race.get("speed", 30), "resistances": res, "mechanics": mech}


def subrace_name(sheet: dict) -> str | None:
    if not sheet.get("subrace"):
        return None
    if rs(sheet) == "2024":
        for s in _species_2024().get(sheet["race"], {}).get("subspecies", []):
            if s["index"] == sheet["subrace"]:
                return s["name"]
        return sheet["subrace"]
    sub = srd.subraces().get(sheet["subrace"])
    return sub["name"] if sub else None


# ── creator options ─────────────────────────────────────────────────────────

def _mastery_options(cls: dict, ruleset: str) -> list[dict]:
    rules = R(ruleset)
    out = []
    for key, prop in sorted(rules.MASTERY.items()):
        rec = srd.item(key)
        if not rec or rec.get("category") != "Weapon":
            continue
        cat = rec.get("weapon_category", "simple")
        if cat in cls["weapon_cats"] or key in cls["weapon_extra"]:
            out.append({"weapon_key": key, "name": rec["name"], "mastery": prop})
    starting = {k for o in cls["equipment_options"] for k, _, _ in o["items"]}
    out.sort(key=lambda o: (o["weapon_key"] not in starting, o["name"]))  # the class's own starting weapons first
    return out


def creator_options(ruleset: str = "2014") -> dict:
    rules = R(ruleset)
    races = []
    if ruleset == "2024":
        for idx, sp in _species_2024().items():
            races.append({"index": idx, "name": sp.get("name", idx), "speed": sp.get("speed", 30), "size": sp.get("size", "Medium"),
                          "ability_bonuses": {}, "traits": sp.get("traits", []), "languages": [],
                          "subraces": [{"index": s["index"], "name": s["name"], "ability_bonuses": {}, "traits": []}
                                       for s in sp.get("subspecies", [])],
                          "ability_choices": None, "ancestries": None, "group": "srd", "source": "SRD 5.2"})
    else:
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
                "group": "srd", "source": "SRD 5.1",
            })
    races += cf.campfire_options(ruleset)  # original Campfire Campaign races, after the SRD ones
    classes = []
    for c in rules.CLASSES.values():
        sc = c["spellcasting"]
        spell_block = None
        if sc:
            msl = rules.max_spell_level(c["index"], 1)
            lst = class_spell_list(c["index"], max(msl, 0), 0, ruleset)
            always = set((sc.get("always") or {}).get(1, []))
            if sc.get("spellbook"):
                n_spells = 6
            elif sc.get("prepared"):
                n_spells = int(sc["prepared"].get(1, 0))
            elif sc.get("known"):
                n_spells = spells_known(c["index"], 1, ruleset)
            else:
                n_spells = 3 if msl else 0
            spells_all = srd.spells(ruleset)
            spell_block = {"ability": sc["ability"], "cantrips_known": cantrips_known(c["index"], 1, ruleset),
                           "spells_at_l1": n_spells if msl else 0, "prepares": sc["prepares"], "known": sc.get("known", False),
                           "pact": sc["type"] == "pact",
                           "cantrips": [spell_card(i, ruleset) for i in lst if spells_all[i]["level"] == 0],
                           "spells": [spell_card(i, ruleset) for i in lst if spells_all[i]["level"] == 1 and i not in always] if msl else []}
        fs_level = c.get("fighting_style_level")
        wm = (c.get("weapon_mastery") or {}).get(1, 0) if ruleset == "2024" else 0
        classes.append({
            "index": c["index"], "name": c["name"], "hit_die": c["hit_die"], "saves": c["saves"],
            "description": c["description"], "skill_choices": c["skill_choices"],
            "armor": c["armor"], "weapons": c["weapons"],
            "equipment_options": [{"id": o["id"], "label": o["label"],
                                   "items": [_item_label(k, q) for k, q, _ in o["items"]] +
                                            [_item_label(k, q) for k, q in c.get("gear", [])]}
                                  for o in c["equipment_options"]],
            "features": [{"name": f.get("label") or f["name"], "description": f["description"]} for f in c["features"].get(1, [])
                         if f["name"] != "Ability Score Improvement"],
            "spellcasting": spell_block,
            "subclass_level": c["subclass_level"], "subclasses": c["subclasses"],
            "fighting_styles": [{"name": k, "description": v} for k, v in FIGHTING_STYLES.items()] if fs_level == 1 else None,
            "expertise_at_l1": c.get("expertise_at_l1", 0),
            "weapon_mastery": wm, "mastery_options": _mastery_options(c, ruleset) if wm else [],
        })
    backgrounds = []
    for b in rules.BACKGROUNDS.values():
        entry = {"index": b["index"], "name": b["name"], "skills": b["skills"], "description": b.get("description", ""),
                 "gold_cp": b.get("gold_cp", 1000)}
        if ruleset == "2024":
            feat = rules.FEATS.get(b.get("origin_feat") or "", {})
            entry.update({"ability_options": b.get("ability_options", []), "tool": b.get("tool"),
                          "origin_feat": {"name": b.get("origin_feat"), "description": _plain(feat.get("description", "")),
                                          "list": _mi_list(b)}})
        backgrounds.append(entry)
    out = {
        "ruleset": ruleset, "races": races, "classes": classes, "backgrounds": backgrounds,
        "skills": SKILLS, "standard_array": STANDARD_ARRAY,
        "point_buy": {"budget": 27, "min": 8, "max": 15, "costs": {str(k): v for k, v in POINT_BUY_COSTS.items()}},
        "alignments": ALIGNMENTS,
    }
    if ruleset == "2024":
        out["feats"] = [{"name": f["name"], "description": _plain(f.get("description", "")), "category": f.get("category", "general")}
                        for f in rules.FEATS.values()]
    return out


def _plain(text: str) -> str:
    """Strip the dataset's markdown emphasis (**bold**, *italic*) for plain-text display."""
    return re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text or "")


def _mi_list(bg: dict) -> str | None:
    """Which class list a background's Magic Initiate feat draws from."""
    feat = (bg.get("origin_feat") or "")
    if not feat.lower().startswith("magic initiate"):
        return None
    m = re.search(r"\((\w+)\)", feat)
    if m:
        return m.group(1).title()
    return bg.get("magic_initiate_list") or {"acolyte": "Cleric", "sage": "Wizard"}.get(bg["index"], "Wizard")


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
        "properties": list(dict.fromkeys([p for p in (rec.get("properties") or []) if p.lower() != "monk"]
                                         + [x for x in it.get("extra_properties") or [] if x in HOMEBREW_PROPERTIES])),
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


def _ancestry_from_subspecies(sub_name: str | None) -> dict | None:
    if not sub_name:
        return None
    for a in DRAGON_ANCESTRIES:
        if a["name"].lower() in sub_name.lower():
            return a
    return None


def _custom_race_choice(payload: dict, homebrew: dict | None) -> tuple[str, dict, dict | None] | None:
    """(race index, record, homebrew snapshot) for a Campfire or homebrew race choice; None for SRD races.

    `homebrew` is the user's own custom entry ({id, name, description, data}), already ownership-checked by the API.
    """
    req = str(payload.get("race") or "")
    if req == "homebrew" or req.startswith("homebrew:"):
        if not homebrew:
            raise RulesError("choose one of your homebrew races")
        try:
            data = cf.clean_homebrew_race(homebrew.get("data") or {})
        except ValueError as e:
            raise RulesError(f"homebrew race {homebrew.get('name', '')}: {e}")
        snap = {"name": str(homebrew.get("name") or "Homebrew race")[:80], **data,
                "description": str(homebrew.get("description") or "")[:2000]}
        rec = snap
    elif req in cf.CAMPFIRE_RACES:
        rec, snap = cf.CAMPFIRE_RACES[req], None
    else:
        return None
    if payload.get("subrace"):
        raise RulesError(f"{rec['name']} has no subraces")
    return ("homebrew" if snap else req), rec, snap


def create(payload: dict, roll_sets: list | None = None, starting_level: int = 1, homebrew: dict | None = None) -> dict:
    """Build a level-1 sheet (then level it to `starting_level`). `homebrew`: the player's own homebrew race entry."""
    ruleset = payload.get("ruleset") or "2014"
    if ruleset not in ("2014", "2024"):
        raise RulesError("unknown ruleset")
    rules = R(ruleset)
    if ruleset == "2024" and rules.key != "2024":
        raise RulesError("the 2024 rules aren't installed on this server")
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 40:
        raise RulesError("give your character a name (up to 40 characters)")
    cls = rules.CLASSES.get(payload.get("class") or "")
    if not cls:
        raise RulesError("choose a class")
    bg = rules.BACKGROUNDS.get(payload.get("background") or "")
    if not bg:
        raise RulesError("choose a background")
    abilities = payload.get("abilities") or {}
    _validate_scores(payload.get("ability_method") or "", abilities, roll_sets)
    scores = {a: int(abilities[a]) for a in ABILITIES}
    bonus: list[str] = []
    ancestry = None
    sub_index = None
    feats: list[str] = []
    custom = _custom_race_choice(payload, homebrew)
    custom_race = custom[1] if custom else None
    homebrew_snap = custom[2] if custom else None

    if ruleset == "2024":
        species = _species_2024()
        sp = species.get(payload.get("race") or "")
        if custom:  # Campfire / homebrew race: no lineage; 2024 ignores racial ability bonuses
            race_index = custom[0]
        elif not sp:
            raise RulesError("choose a species")
        else:
            race_index = payload["race"]
        if custom:
            pass  # no lineage to check
        elif payload.get("subrace"):
            sub = next((s for s in sp.get("subspecies", []) if s["index"] == payload["subrace"]), None)
            if not sub:
                raise RulesError("that lineage doesn't belong to the species")
            sub_index = sub["index"]
            ancestry = _ancestry_from_subspecies(sub["name"])
        elif sp.get("subspecies"):
            raise RulesError(f"choose your {sp.get('name', 'species').lower()} lineage")
        asi = payload.get("background_asi") or {}
        opts = bg.get("ability_options") or []
        vals = sorted(int(v) for v in asi.values())
        if any(k not in opts for k in asi) or vals not in ([1, 2], [1, 1, 1]):
            raise RulesError(f"split +3 among {', '.join(opts)}: +2/+1 or +1/+1/+1")
        for k, v in asi.items():
            scores[k] += int(v)
        if any(v > 20 for v in scores.values()):
            raise RulesError("ability scores can't go above 20")
        if bg.get("origin_feat"):
            feats.append(bg["origin_feat"])
    elif custom:
        race_index = custom[0]
        for a, v in (custom_race.get("ability_bonuses") or {}).items():
            scores[a] += int(v)
    else:
        race = srd.races().get(payload.get("race") or "")
        if not race:
            raise RulesError("choose a race")
        race_index = race["index"]
        sub = None
        if payload.get("subrace"):
            sub = srd.subraces().get(payload["subrace"])
            if not sub or sub.get("race") != race["name"]:
                raise RulesError("that subrace doesn't belong to the race")
            sub_index = sub["index"]
        extra = RACE_EXTRAS.get(race["index"], {})
        if extra.get("ability_choices"):
            ac = extra["ability_choices"]
            bonus = list(dict.fromkeys(payload.get("bonus_abilities") or []))
            if len(bonus) != ac["count"] or any(b not in ABILITIES or b in ac["exclude"] for b in bonus):
                raise RulesError(f"choose {ac['count']} different abilities (not {', '.join(ac['exclude'])}) for your racial +1s")
        if extra.get("ancestries"):
            ancestry = next((a for a in DRAGON_ANCESTRIES if a["name"].lower() == str(payload.get("ancestry") or "").lower()), None)
            if not ancestry:
                raise RulesError("choose your draconic ancestry")
        for src in (race.get("ability_bonuses") or {}, (sub or {}).get("ability_bonuses") or {}):
            for a, v in src.items():
                scores[a] += int(v)
        for a in bonus:
            scores[a] += 1

    picks = list(dict.fromkeys(payload.get("skills") or []))
    sc = cls["skill_choices"]
    bad = [s for s in picks if s not in sc["options"]]
    if bad:
        raise RulesError(f"{cls['name']} can't choose {', '.join(bad)}")
    overlap = [s for s in picks if s in bg["skills"]]
    picks = [s for s in picks if s not in bg["skills"]]
    if len(picks) + len(overlap) != sc["count"] or (not picks and sc["count"]):
        raise RulesError(f"choose {sc['count']} class skills")
    skill_profs = sorted(set(picks) | set(bg["skills"]) | {s for s in (custom_race or {}).get("skills") or [] if s in SKILLS})
    if "Skilled" in feats:
        extra_sk = [s for s in SKILLS if s not in skill_profs][:3]
        skill_profs = sorted(set(skill_profs) | set(extra_sk))
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

    masteries: list[str] = []
    if ruleset == "2024":
        n_m = (cls.get("weapon_mastery") or {}).get(1, 0)
        if n_m:
            allowed = {o["weapon_key"] for o in _mastery_options(cls, ruleset)}
            masteries = [w for w in dict.fromkeys(payload.get("masteries") or []) if w in allowed][:n_m]
            if len(masteries) < n_m:  # fill from the starting weapons
                for k, _, _ in opt["items"]:
                    if k in allowed and k not in masteries and len(masteries) < n_m:
                        masteries.append(k)

    sheet: dict = {
        "ruleset": ruleset, "name": name, "race": race_index, "subrace": sub_index,
        "class": cls["index"], "subclass": None, "background": bg["index"],
        "alignment": payload.get("alignment") or "True Neutral",
        "backstory": (payload.get("backstory") or "")[:4000],
        "color": payload.get("color") or "#c9a227",
        "level": 1, "xp": 0, "level_target": 1, "abilities": scores, "base_abilities": {a: int(abilities[a]) for a in ABILITIES},
        "bonus_abilities": bonus, "background_asi": payload.get("background_asi") if ruleset == "2024" else None,
        "ancestry": ancestry, "feats": feats, "masteries": masteries, "exhaustion": 0,
        "skill_profs": skill_profs, "expertise": expertise, "save_profs": list(cls["saves"]),
        "fighting_style": style,
        "conditions": [], "death_saves": {"success": 0, "fail": 0}, "dead": False, "inspiration": False,
        "gold_cp": bg.get("gold_cp", 1000), "inventory": [], "features": [], "spells": {"cantrips": [], "spells": []},
        "slots_used": {}, "pact_used": 0, "hit_dice_used": 0, "temp_hp": 0, "concentration": None,
        "source": "creator", "issues": [],
    }
    if homebrew_snap:  # snapshot: later edits or deletion of the library entry don't touch the character
        sheet["homebrew_race"] = {"entry_id": homebrew.get("id"), "name": homebrew_snap["name"]}
        sheet["race_data"] = homebrew_snap
    for key, qty, equipped in opt["items"]:
        if srd.item(key):
            sheet["inventory"].append(make_item(key, qty, equipped))
    if opt["items"] or ruleset == "2014":
        for key, qty in cls.get("gear", []):
            if srd.item(key):
                add_item(sheet, key, qty)
    sheet["gold_cp"] += int(opt.get("gold_cp") or 0)
    for entry in bg.get("items") or []:  # 2024 backgrounds come with gear
        key, qty = (entry[0], entry[1]) if isinstance(entry, (list, tuple)) else (entry, 1)
        if srd.item(key):
            add_item(sheet, key, int(qty))

    spc = cls["spellcasting"]
    if spc:
        msl1 = rules.max_spell_level(cls["index"], 1)
        allowed = set(class_spell_list(cls["index"], max(1, msl1), 0, ruleset))
        spells_all = srd.spells(ruleset)
        cantrips = [c for c in dict.fromkeys(payload.get("cantrips") or []) if c in allowed and spells_all[c]["level"] == 0]
        spells = [s for s in dict.fromkeys(payload.get("spells") or []) if s in allowed and spells_all[s]["level"] == 1]
        need_c = cantrips_known(cls["index"], 1, ruleset)
        if len(cantrips) != need_c:
            raise RulesError(f"choose {need_c} cantrips")
        if spc.get("spellbook"):
            if len(spells) != 6:
                raise RulesError("choose 6 level-1 spells for your spellbook")
            n_prep = int(spc["prepared"][1]) if spc.get("prepared") else max(1, mod(scores["INT"]) + 1)
            sheet["spells"] = {"cantrips": cantrips, "spellbook": spells, "spells": spells[:n_prep]}
        elif spc.get("prepared"):
            n = int(spc["prepared"].get(1, 0)) if msl1 else 0
            if n and (not spells or len(spells) > n):
                raise RulesError(f"choose up to {n} level-1 spells to prepare")
            sheet["spells"] = {"cantrips": cantrips, "spells": spells[:n] if n else []}
        elif spc.get("known"):
            need = spells_known(cls["index"], 1, ruleset)
            if len(spells) != need:
                raise RulesError(f"choose {need} level-1 spells")
            sheet["spells"] = {"cantrips": cantrips, "spells": spells}
        else:
            mx = max(3, mod(scores[spc["ability"]]) + 1) if msl1 else 0
            if mx and (not spells or len(spells) > mx):
                raise RulesError(f"choose up to {mx} level-1 spells to prepare")
            sheet["spells"] = {"cantrips": cantrips, "spells": spells}

    if any(f.lower().startswith("magic initiate") for f in feats):
        mi = payload.get("magic_initiate") or {}
        lst = _mi_list(bg) or "Wizard"
        pool_c = [i for i, s in srd.spells(ruleset).items() if lst in (s.get("classes") or []) and s.get("level") == 0]
        pool_s = [i for i, s in srd.spells(ruleset).items() if lst in (s.get("classes") or []) and s.get("level") == 1]
        mc = [c for c in dict.fromkeys(mi.get("cantrips") or []) if c in pool_c][:2]
        ms = mi.get("spell") if mi.get("spell") in pool_s else None
        if len(mc) < 2:
            mc = (mc + [c for c in sorted(pool_c) if c not in mc])[:2]
        if not ms and pool_s:
            ms = sorted(pool_s)[0]
        sheet["spells"]["bonus_cantrips"] = mc
        sheet["spells"]["bonus_spells"] = [ms] if ms else []
        sheet["mi_ability"] = {"Cleric": "WIS", "Druid": "WIS", "Wizard": "INT"}.get(lst, "INT")
        sheet["mi_free_used"] = False

    sheet["hp_max"] = cls["hit_die"] + mod(scores["CON"]) + _hp_bonus_per_level(sheet)
    sheet["hp"] = sheet["hp_max"]
    _grant_features(sheet, 1)
    if ancestry:
        uses = ({"max_spec": "PROF", "max": prof_bonus_of(sheet), "used": 0, "per": "long"} if ruleset == "2024"
                else {"max": 1, "used": 0, "per": "short"})
        sheet["features"].append({"name": "Breath Weapon", "description": f"Exhale {ancestry['damage_type']} in a "
                                  f"{'15 ft cone' if ancestry['shape'] == 'cone' else '5 by 30 ft line'}; save for half.",
                                  "uses": uses})
    if cls["subclass_level"] == 1:
        sheet["subclass"] = cls["subclasses"][0]["index"]
    target = max(1, min(int(starting_level), rules.MAX_LEVEL))
    while sheet["level"] < target:
        level_up(sheet, auto_choices(sheet))
    sheet["xp"] = rules.XP_THRESHOLDS[sheet["level"]]
    sheet["level_target"] = sheet["level"]
    return sheet


def _hp_bonus_per_level(sheet: dict) -> int:
    b = int(race_info(sheet)["mechanics"].get("tough_per_level") or 0)
    if sheet["class"] == "sorcerer" and (rs(sheet) == "2014" or "draconic" in str(sheet.get("subclass") or "")):
        b += 1  # Draconic Resilience
    if has_feat(sheet, "Tough"):
        b += 2
    return b


def _resolve_uses(sheet: dict, spec) -> int:
    if isinstance(spec, int):
        return spec
    if isinstance(spec, dict):  # {level: n} tables (e.g. 2024 Second Wind)
        best = 1
        for lv, n in sorted(((int(k), v) for k, v in spec.items())):
            if sheet["level"] >= lv:
                best = n
        return int(best)
    if spec == "CHA":
        return max(1, mod(sheet["abilities"]["CHA"]))
    if spec == "WIS":
        return max(1, mod(sheet["abilities"]["WIS"]))
    if spec == "CHA+1":
        return 1 + max(0, mod(sheet["abilities"]["CHA"]))
    if spec == "LEVEL":
        return sheet["level"]
    if spec == "LOH":
        return 5 * sheet["level"]
    if spec == "PROF":
        return prof_bonus_of(sheet)
    return 1


def _grant_features(sheet: dict, level: int) -> None:
    cls = cls_of(sheet)
    feats = list(cls["features"].get(level, []))
    sub = sheet.get("subclass")
    for s in cls.get("subclasses", []):  # subclass-specific features, if the data provides them per subclass
        if s["index"] == sub:
            feats += (s.get("features") or {}).get(level, [])
    for f in feats:
        if f["name"] == "Ability Score Improvement":
            continue
        existing = next((x for x in sheet["features"] if x["name"] == f["name"]), None)
        if existing:
            if f.get("uses") and existing.get("uses"):
                existing["uses"]["max_spec"] = f["uses"]["max"]
            continue
        entry = {"name": f["name"], "description": f["description"], "uses": None}
        if f.get("label"):
            entry["label"] = f["label"]
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
        if u and f["name"] == "Rage" and not isinstance(u.get("max_spec"), dict):
            lvl = sheet["level"]
            u["max"] = 2 if lvl < 3 else 3 if lvl < 6 else 4 if lvl < 12 else 5
        if u and f["name"] == "Bardic Inspiration" and sheet["level"] >= 5:
            u["per"] = "short"
        if u and f["name"] == "Channel Divinity" and sheet["class"] == "cleric" and not isinstance(u.get("max_spec"), dict):
            u["max"] = 1 if sheet["level"] < 6 else 2


# ── levelling ───────────────────────────────────────────────────────────────

def level_for_xp(xp: int, ruleset: str = "2014") -> int:
    rules = R(ruleset)
    lvl = 1
    for L, need in rules.XP_THRESHOLDS.items():
        if xp >= need and L <= rules.MAX_LEVEL:
            lvl = max(lvl, L)
    return lvl


def award_xp(sheet: dict, amount: int) -> bool:
    """Add XP; returns True if a new level became available (the player confirms it)."""
    sheet["xp"] = sheet.get("xp", 0) + max(0, int(amount))
    before = sheet.get("level_target", sheet["level"])
    sheet["level_target"] = max(before, level_for_xp(sheet["xp"], rs(sheet)))
    return sheet["level_target"] > before


def grant_milestone(sheet: dict) -> bool:
    if sheet.get("level_target", sheet["level"]) >= R(sheet).MAX_LEVEL:
        return False
    sheet["level_target"] = sheet.get("level_target", sheet["level"]) + 1
    return True


def _feat_options(sheet: dict) -> list[dict]:
    rules = R(sheet)
    out = []
    for f in rules.FEATS.values():
        cat = f.get("category", "general")
        if cat not in ("general", "fighting_style"):
            continue
        if f["name"] == "Ability Score Improvement" or has_feat(sheet, f["name"]):
            continue
        if cat == "fighting_style" and not cls_of(sheet).get("fighting_style_level"):
            continue
        out.append({"name": f["name"], "description": _plain(f.get("description", ""))})
    return out


def level_offer(sheet: dict) -> dict | None:
    rules = R(sheet)
    if sheet.get("level_target", sheet["level"]) <= sheet["level"] or sheet["level"] >= rules.MAX_LEVEL or sheet.get("dead"):
        return None
    cls = cls_of(sheet)
    to = sheet["level"] + 1
    ruleset = rs(sheet)
    sc = cls.get("spellcasting")
    asi = rules.is_asi_level(sheet["class"], to)
    offer = {"to_level": to, "hit_die": cls["hit_die"], "hp_average": cls["hit_die"] // 2 + 1,
             "con_mod": mod(sheet["abilities"]["CON"]), "asi": asi, "feat_options": None, "subclass_options": None,
             "fighting_style_options": None, "expertise": 0, "expertise_options": [], "cantrips": 0,
             "cantrip_options": [], "spells": 0, "spell_options": [], "max_spell_level": 0,
             "masteries": 0, "mastery_options": [],
             "features": [{"name": f.get("label") or f["name"], "description": f["description"]}
                          for f in cls["features"].get(to, []) if f["name"] != "Ability Score Improvement"]}
    if asi:
        fo = _feat_options(sheet)
        offer["feat_options"] = fo or None
    if cls["subclass_level"] == to and not sheet.get("subclass"):
        offer["subclass_options"] = cls["subclasses"]
    if cls.get("fighting_style_level") == to and not sheet.get("fighting_style"):
        offer["fighting_style_options"] = [{"name": k, "description": v} for k, v in FIGHTING_STYLES.items()]
    exp_levels = cls.get("expertise_levels") or ({3: 2, 10: 2} if sheet["class"] == "bard" and ruleset == "2014" else
                                                  {6: 2} if sheet["class"] == "rogue" and ruleset == "2014" else {})
    n_exp = exp_levels.get(to, 0) if isinstance(exp_levels, dict) else 0
    if n_exp:
        offer["expertise"] = n_exp
        offer["expertise_options"] = [s for s in sheet["skill_profs"] if s not in sheet.get("expertise", [])]
    wm = cls.get("weapon_mastery") or {}
    if ruleset == "2024" and wm:
        def wm_at(lv):
            best = 0
            for k, v in wm.items():
                if lv >= int(k):
                    best = max(best, int(v))
            return best
        more = wm_at(to) - wm_at(sheet["level"])
        if more > 0:
            offer["masteries"] = more
            offer["mastery_options"] = [o for o in _mastery_options(cls, ruleset) if o["weapon_key"] not in sheet.get("masteries", [])]
    if sc:
        msl = rules.max_spell_level(sheet["class"], to)
        offer["max_spell_level"] = msl
        have_c = set(sheet["spells"].get("cantrips", []))
        offer["cantrips"] = max(0, cantrips_known(sheet["class"], to, ruleset) - len(have_c))
        if offer["cantrips"]:
            offer["cantrip_options"] = [spell_card(i, ruleset) for i in class_spell_list(sheet["class"], 0, 0, ruleset) if i not in have_c]
        if sc.get("spellbook"):
            offer["spells"] = 2
            have = set(sheet["spells"].get("spellbook", []))
            offer["spell_options"] = [spell_card(i, ruleset) for i in class_spell_list(sheet["class"], msl, 1, ruleset) if i not in have]
        elif sc.get("known") and not sc.get("prepared"):
            have = set(sheet["spells"].get("spells", []))
            offer["spells"] = max(0, spells_known(sheet["class"], to, ruleset) - len(have))
            if offer["spells"] and msl:
                offer["spell_options"] = [spell_card(i, ruleset) for i in class_spell_list(sheet["class"], msl, 1, ruleset) if i not in have]
    return offer


def auto_choices(sheet: dict) -> dict:
    """Sensible picks for automatic levelling (starting levels above 1, AI defaults)."""
    offer = level_offer({**sheet, "level_target": sheet["level"] + 1}) or {}
    cls = cls_of(sheet)
    ch: dict = {"hp_method": "average"}
    if offer.get("asi"):
        prim = cls["primary"][0]
        sec = cls["primary"][1] if len(cls["primary"]) > 1 else "CON"
        room = 20 - sheet["abilities"][prim]
        if room >= 2:
            ch["asi"] = {prim: 2}
        elif room == 1:
            ch["asi"] = {prim: 1, sec: 1} if sheet["abilities"][sec] < 20 else {prim: 1, "CON": 1}
        else:
            ch["asi"] = {sec: 2} if sheet["abilities"][sec] <= 18 else {"CON": 2}
    if offer.get("subclass_options"):
        ch["subclass"] = offer["subclass_options"][0]["index"]
    if offer.get("fighting_style_options"):
        ch["fighting_style"] = "Defense"
    if offer.get("expertise"):
        ch["expertise"] = offer["expertise_options"][: offer["expertise"]]
    if offer.get("masteries"):
        ch["masteries"] = [o["weapon_key"] for o in offer["mastery_options"]][: offer["masteries"]]

    def pick(opts, n):
        combat_first = sorted(opts, key=lambda o: (not o["combat"], o["level"] * -1, o["name"]))
        return [o["index"] for o in combat_first[:n]]
    if offer.get("cantrips"):
        ch["cantrips"] = pick(offer["cantrip_options"], offer["cantrips"])
    if offer.get("spells"):
        ch["spells"] = pick(offer["spell_options"], offer["spells"])
    return ch


def _apply_feat(sheet: dict, name: str) -> None:
    rules = R(sheet)
    f = rules.FEATS.get(name) or {}
    if f.get("category") == "fighting_style" or name in FIGHTING_STYLES:
        sheet["fighting_style"] = name.replace(" Fighting Style", "")
    sheet.setdefault("feats", []).append(name)
    if name == "Tough":
        sheet["hp_max"] += 2 * sheet["level"]
        sheet["hp"] += 2 * sheet["level"]


def level_up(sheet: dict, choices: dict | None = None) -> dict:
    rules = R(sheet)
    if sheet["level"] >= rules.MAX_LEVEL:
        raise RulesError(f"level {rules.MAX_LEVEL} is the cap for now")
    sheet["level_target"] = max(sheet.get("level_target", sheet["level"]), sheet["level"] + 1)
    offer = level_offer(sheet)
    choices = choices or {}
    cls = cls_of(sheet)
    asi = choices.get("asi") or None
    feat = choices.get("feat") or None
    if offer["asi"]:
        if feat:
            if feat not in {f["name"] for f in (offer["feat_options"] or [])}:
                raise RulesError("you can't take that feat")
            asi = None
        else:
            if not asi:
                raise RulesError("choose your ability score improvement (or a feat)")
            if sum(int(v) for v in asi.values()) != 2 or any(k not in ABILITIES or int(v) < 1 for k, v in asi.items()):
                raise RulesError("an ability score improvement is +2 to one ability or +1 to two")
            if any(sheet["abilities"][k] + int(v) > 20 for k, v in asi.items()):
                raise RulesError("ability scores can't go above 20")
    else:
        asi = None
        feat = None
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
    masts = []
    if offer["masteries"]:
        allowed = {o["weapon_key"] for o in offer["mastery_options"]}
        masts = [m for m in dict.fromkeys(choices.get("masteries") or []) if m in allowed][: offer["masteries"]]
        if len(masts) < min(offer["masteries"], len(allowed)):
            masts = (masts + [m for m in sorted(allowed) if m not in masts])[: offer["masteries"]]
    new_c = [c for c in dict.fromkeys(choices.get("cantrips") or []) if c in {o["index"] for o in offer["cantrip_options"]}]
    if len(new_c) != min(offer["cantrips"], len(offer["cantrip_options"])):
        raise RulesError(f"choose {offer['cantrips']} new cantrips")
    new_s = [s for s in dict.fromkeys(choices.get("spells") or []) if s in {o["index"] for o in offer["spell_options"]}]
    if offer["spell_options"] and len(new_s) != min(offer["spells"], len(offer["spell_options"])):
        raise RulesError(f"choose {offer['spells']} new spells")

    sheet["level"] += 1
    if asi:
        for k, v in asi.items():
            sheet["abilities"][k] += int(v)
    con = mod(sheet["abilities"]["CON"])
    hp_roll = roll(f"1d{cls['hit_die']}").total if choices.get("hp_method") == "roll" else cls["hit_die"] // 2 + 1
    gain = max(1, hp_roll + con) + _hp_bonus_per_level(sheet)
    if asi and "CON" in asi and mod(sheet["abilities"]["CON"] - int(asi["CON"])) != con:
        gain += sheet["level"] - 1  # retroactive HP from a higher CON modifier
    sheet["hp_max"] += gain
    sheet["hp"] += gain
    if feat:
        _apply_feat(sheet, feat)
    if sub:
        sheet["subclass"] = sub
        if rs(sheet) == "2024" and sheet["class"] == "sorcerer" and "draconic" in sub:
            sheet["hp_max"] += sheet["level"]  # Draconic Resilience, retroactive
            sheet["hp"] += sheet["level"]
    if style:
        sheet["fighting_style"] = style
    if exp:
        sheet["expertise"] = sorted(set(sheet.get("expertise", [])) | set(exp))
    if masts:
        sheet["masteries"] = list(dict.fromkeys(sheet.get("masteries", []) + masts))
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
        if sheet["class"] == "sorcerer" and rs(sheet) == "2014":
            options.append(13 + dex)
        if sheet["class"] == "sorcerer" and rs(sheet) == "2024" and "draconic" in str(sheet.get("subclass") or ""):
            options.append(10 + dex + mod(ab["CHA"]))
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
    lvl = sheet["level"]
    if rs(sheet) == "2024":
        return "1d6" if lvl < 5 else "1d8" if lvl < 11 else "1d10"
    return "1d4" if lvl < 5 else "1d6" if lvl < 11 else "1d8"


def _is_monk_weapon(rec: dict) -> bool:
    props = [p.lower() for p in rec.get("properties") or []]
    return rec["index"] == "shortsword" or (rec.get("weapon_category") == "simple" and "two-handed" not in props
                                             and "heavy" not in props)


def _die_size(d: str) -> int:
    m = re.match(r"\d*d(\d+)", d)
    return int(m.group(1)) if m else 0


_AMMO = {"longbow": "arrow", "shortbow": "arrow", "crossbow-light": "crossbow-bolt", "crossbow-heavy": "crossbow-bolt",
         "crossbow-hand": "crossbow-bolt", "sling": "sling-bullet", "blowgun": "blowgun-needle"}


def mastery_of(sheet: dict, weapon_key: str | None) -> str | None:
    if rs(sheet) != "2024" or not weapon_key or weapon_key not in (sheet.get("masteries") or []):
        return None
    return R(sheet).MASTERY.get(weapon_key)


HOMEBREW_PROPERTIES = ("Finesse", "Light", "Thrown")  # properties a host may add to a single weapon


def attacks(sheet: dict) -> list[dict]:
    ab = sheet["abilities"]
    pb = prof_bonus_of(sheet)
    out = []
    monk = sheet["class"] == "monk" and not wearing_armor(sheet) and not has_shield(sheet)
    weapons = _equipped(sheet, "Weapon")
    one_weapon = len([1 for _, r in weapons if not srd.weapon_profile(r)["ranged"]]) == 1
    for it, rec in weapons:
        wp = srd.weapon_profile(rec)
        extra = [p for p in it.get("extra_properties") or [] if p in HOMEBREW_PROPERTIES]  # a homebrew tweak to one item
        if extra:
            wp = {**wp, "properties": list(dict.fromkeys(list(wp["properties"]) + extra)),
                  "finesse": wp["finesse"] or "Finesse" in extra}
        s, d = mod(ab["STR"]), mod(ab["DEX"])
        finesse = wp["finesse"] or (monk and _is_monk_weapon(rec))
        use = d if wp["ranged"] or (finesse and d > s) else s
        shillelagh = "Shillelagh" in (sheet.get("conditions") or []) and rec["index"] in ("club", "quarterstaff")
        if shillelagh:
            use = max(use, mod(ab["WIS"]))
        to_hit = use + (pb if weapon_proficient(sheet, rec) else 0)
        if wp["ranged"] and sheet.get("fighting_style") == "Archery":
            to_hit += 2
        dice = wp["dice"]
        if monk and _is_monk_weapon(rec) and _die_size(martial_arts_die(sheet)) > _die_size(dice):
            dice = martial_arts_die(sheet)
        if shillelagh:
            dice = "1d8" if sheet["level"] < 5 else "1d10"
        bonus_dmg = use
        if not wp["ranged"] and sheet.get("fighting_style") == "Dueling" and one_weapon and not wp["two_handed"]:
            bonus_dmg += 2
        dmg = f"{dice}{bonus_dmg:+d}" if bonus_dmg else dice
        long = wp["long_range"] if wp["ranged"] else (wp["thrown_range"][0] if wp["thrown_range"] else None)
        out.append({"id": it["id"], "name": it.get("name") or rec["name"], "to_hit": to_hit, "damage": dmg,
                    "damage_type": wp["type"], "range_ft": wp["range"], "long_range_ft": long,
                    "kind": "ranged" if wp["ranged"] else "melee", "properties": wp["properties"],
                    "finesse": finesse, "ammo": _AMMO.get(rec["index"]) if "Ammunition" in wp["properties"] else None,
                    "two_handed": wp["two_handed"], "weapon_key": rec["index"], "mastery": mastery_of(sheet, rec["index"]),
                    "ability_mod": use})
    if monk or not out:
        s = mod(ab["STR"])
        use = max(s, mod(ab["DEX"])) if monk else s
        dmg = f"{martial_arts_die(sheet)}{use:+d}" if monk else str(max(1, 1 + s))
        out.append({"id": "unarmed", "name": "Unarmed Strike", "to_hit": use + pb, "damage": dmg,
                    "damage_type": "bludgeoning", "range_ft": 5, "long_range_ft": None, "kind": "melee",
                    "properties": [], "finesse": monk, "ammo": None, "two_handed": False, "weapon_key": None,
                    "mastery": None, "ability_mod": use})
    return out


def extra_attacks(sheet: dict) -> int:
    n = 1
    if has_feature(sheet, "Extra Attack"):
        n = 2
    if has_feature(sheet, "Two Extra Attacks") or (sheet["class"] == "fighter" and sheet["level"] >= 11):
        n = 3
    return n


def skill_bonus(sheet: dict, skill: str) -> int:
    ab = SKILLS[skill]
    b = mod(sheet["abilities"][ab])
    pb = prof_bonus_of(sheet)
    if skill in (sheet.get("expertise") or []):
        b += 2 * pb
    elif skill in (sheet.get("skill_profs") or []):
        b += pb
    elif has_feature(sheet, "Jack of All Trades"):
        b += pb // 2
    return b - 2 * int(sheet.get("exhaustion", 0) if rs(sheet) == "2024" else 0)


def save_bonus(sheet: dict, ability: str) -> int:
    b = mod(sheet["abilities"][ability])
    if ability in (sheet.get("save_profs") or []):
        b += prof_bonus_of(sheet)
    return b - 2 * int(sheet.get("exhaustion", 0) if rs(sheet) == "2024" else 0)


def initiative(sheet: dict) -> int:
    b = mod(sheet["abilities"]["DEX"])
    if has_feat(sheet, "Alert"):
        b += prof_bonus_of(sheet)
    return b


def speed(sheet: dict) -> int:
    sp = race_info(sheet)["speed"]
    heavy = any(rec["index"] in ("ring-mail", "chain-mail", "splint-armor", "plate-armor") for _, rec in _equipped(sheet, "Armor"))
    if has_feature(sheet, "Fast Movement") and not heavy:
        sp += 10
    if has_feature(sheet, "Unarmored Movement") and not wearing_armor(sheet) and not has_shield(sheet):
        sp += 10 if sheet["level"] < 6 else 15 if sheet["level"] < 10 else 20
    conds = sheet.get("conditions") or []
    if "Hasted" in conds:
        sp *= 2
    if "Slowed" in conds:
        sp = max(0, sp - 10)
    if rs(sheet) == "2024" and sheet.get("exhaustion"):
        sp = max(0, sp - 5 * int(sheet["exhaustion"]))
    for it, rec in _equipped(sheet, "Armor"):
        if rec.get("str_minimum") and sheet["abilities"]["STR"] < rec["str_minimum"]:
            sp -= 10
    return max(0, sp)


def resistances(sheet: dict) -> list[str]:
    out = list(race_info(sheet)["resistances"])
    if sheet.get("ancestry"):
        out.append(sheet["ancestry"]["damage_type"])
    return list(dict.fromkeys(out))


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
            raise RulesError(f"{f.get('label') or name} is used up until you rest")
        f["uses"]["used"] += amount
    return f


def uses_left(sheet: dict, name: str) -> int:
    f = feature(sheet, name)
    if not f or not f.get("uses"):
        return 0
    return f["uses"]["max"] - f["uses"]["used"]


def actions(sheet: dict) -> list[dict]:
    out: list[dict] = []
    cls = sheet["class"]
    lvl = sheet["level"]
    sub = str(sheet.get("subclass") or "")

    def add(fid, name, kind, target="none", rng=None, uses_of=None, desc=""):
        f = feature(sheet, uses_of) if uses_of else None
        u = f["uses"] if f and f.get("uses") else None
        uv = {k: u[k] for k in ("max", "used", "per")} if u else None
        out.append({"id": fid, "name": name, "kind": kind, "description": desc or (f["description"] if f else ""),
                    "target": target, "range_ft": rng, "uses": uv,
                    "available": not u or u["used"] < u["max"]})
    if cls == "barbarian":
        add("rage", "Rage", "bonus", uses_of="Rage")
        if has_feature(sheet, "Reckless Attack"):
            add("reckless", "Reckless Attack", "free", desc="Advantage on your melee attacks this turn; enemies have advantage against you until your next turn.")
        if "berserker" in sub:
            add("frenzy", "Frenzied Strike", "bonus", "enemy", 5, desc="While raging: one melee weapon attack as a bonus action.")
    if cls == "fighter":
        add("second_wind", "Second Wind", "bonus", uses_of="Second Wind")
        if has_feature(sheet, "Action Surge"):
            add("action_surge", "Action Surge", "free", uses_of="Action Surge")
    if cls == "monk":
        add("martial_arts", "Martial Arts strike", "bonus", "enemy", 5, desc="After taking the Attack action, make one unarmed strike.")
        if feature(sheet, "Ki"):
            pts = "focus" if rs(sheet) == "2024" else "ki"
            add("flurry", f"Flurry of Blows (1 {pts})", "bonus", "enemy", 5, uses_of="Ki", desc="Make two unarmed strikes as a bonus action.")
            add("patient_defense", f"Patient Defense (1 {pts})", "bonus", uses_of="Ki", desc="Take the Dodge action as a bonus action.")
            add("step_of_wind", f"Step of the Wind (1 {pts})", "bonus", uses_of="Ki", desc="Dash or Disengage as a bonus action.")
        if has_feature(sheet, "Stunning Strike"):
            add("stunning_strike", "Stunning Strike", "free", uses_of="Ki", desc="Your next melee hit forces a CON save or the target is stunned.")
    if cls == "rogue" and has_feature(sheet, "Cunning Action"):
        add("cunning_dash", "Cunning Action: Dash", "bonus")
        add("cunning_disengage", "Cunning Action: Disengage", "bonus")
        add("cunning_hide", "Cunning Action: Hide", "bonus", desc="Hide (Stealth): your next attack has advantage.")
    if cls == "bard":
        add("bardic_inspiration", "Bardic Inspiration", "bonus", "ally", 60, uses_of="Bardic Inspiration")
    if cls == "paladin":
        add("lay_on_hands", "Lay on Hands", "action" if rs(sheet) == "2014" else "bonus", "ally", 5, uses_of="Lay on Hands")
        if has_feature(sheet, "Divine Smite"):
            add("divine_smite", ("Paladin's Smite" if rs(sheet) == "2024" else "Divine Smite") + " (next hit)", "free",
                desc="Spend a spell slot on your next melee hit: +2d8 radiant (+1d8 per slot level above 1st).")
        if "devotion" in sub and feature(sheet, "Channel Divinity"):
            add("sacred_weapon", "Channel Divinity: Sacred Weapon", "action", uses_of="Channel Divinity")
    if cls == "cleric" and feature(sheet, "Channel Divinity"):
        add("turn_undead", "Channel Divinity: Turn Undead", "action", uses_of="Channel Divinity",
            desc="Undead within 30 ft make a WIS save or are turned (frightened, fleeing).")
        if "life" in sub:
            add("preserve_life", "Channel Divinity: Preserve Life", "action", uses_of="Channel Divinity",
                desc="Heal 5 × your level HP split among wounded allies within 30 ft (up to half their max).")
    if sheet.get("ancestry") and feature(sheet, "Breath Weapon"):
        add("breath_weapon", f"Breath Weapon ({sheet['ancestry']['damage_type']})", "action", "point",
            15 if sheet["ancestry"]["shape"] == "cone" else 30, uses_of="Breath Weapon")
    return out


def view(char_id: str, owner_id: str, game_id: str | None, sheet: dict) -> dict:
    ab = sheet["abilities"]
    lvl = sheet["level"]
    ruleset = rs(sheet)
    rules = R(sheet)
    sp_ab = spell_ability(sheet)
    spellcasting = None
    acts = actions(sheet)
    sc = cls_of(sheet).get("spellcasting")
    if sp_ab:
        conc = sheet.get("concentration")
        spellcasting = {
            "ability": sp_ab, "save_dc": spell_save_dc(sheet), "attack_bonus": spell_attack(sheet),
            "slots": spell_slots(sheet), "pact": pact_slots(sheet),
            "cantrips": [spell_card(i, ruleset) for i in all_cantrips(sheet)],
            "spells": [spell_card(i, ruleset) for i in ready_spells(sheet)],
            "prepares": bool(sc and sc.get("prepares")), "prepared_max": prepared_max(sheet) if sc else None,
            "known": bool(sc and sc.get("known")),
            "spellbook": [spell_card(i, ruleset) for i in sheet["spells"].get("spellbook", [])] if sc and sc.get("spellbook") else None,
            "options": [spell_card(i, ruleset) for i in prep_options(sheet)] if sc else [],
            "always": always_prepared(sheet),
            "max_spell_level": max_spell_level(sheet) if sc else 0,
            "concentrating_on": (srd.spells(ruleset).get(conc["spell"], {}).get("name") if conc else None),
        }
    cls = cls_of(sheet)
    subclass = next((s["name"] for s in cls["subclasses"] if s["index"] == sheet.get("subclass")), sheet.get("subclass"))
    ri = race_info(sheet)
    feats = [{"name": f, "description": _plain(rules.FEATS.get(f, {}).get("description", ""))} for f in sheet.get("feats", [])]
    masteries = [{"weapon_key": k, "name": (srd.item(k) or {}).get("name", k), "mastery": rules.MASTERY.get(k),
                  "description": rules.MASTERY_DESCRIPTIONS.get(rules.MASTERY.get(k) or "", "")} for k in sheet.get("masteries", [])]
    return {
        "id": char_id, "name": sheet["name"], "owner_id": owner_id, "game_id": game_id, "ruleset": ruleset,
        "race": ri["name"], "subrace": subrace_name(sheet),
        "race_source": race_source(sheet), "race_traits": race_traits(sheet),
        "class": cls["name"], "subclass": subclass,
        "background": rules.BACKGROUNDS.get(sheet.get("background") or "", {}).get("name", sheet.get("background")),
        "alignment": sheet.get("alignment"), "backstory": sheet.get("backstory", ""), "color": sheet.get("color"),
        "level": lvl, "xp": sheet.get("xp", 0), "xp_next": rules.XP_THRESHOLDS.get(lvl + 1) if lvl < rules.MAX_LEVEL else None,
        "prof_bonus": prof_bonus_of(sheet),
        "hp": sheet["hp"], "hp_max": sheet["hp_max"], "temp_hp": sheet.get("temp_hp", 0),
        "ac": armor_class(sheet), "speed": speed(sheet), "initiative": initiative(sheet),
        "abilities": ab, "mods": {a: mod(v) for a, v in ab.items()},
        "saves": {a: save_bonus(sheet, a) for a in ABILITIES}, "save_profs": sheet.get("save_profs", []),
        "skills": {s: skill_bonus(sheet, s) for s in SKILLS}, "skill_profs": sheet.get("skill_profs", []),
        "expertise": sheet.get("expertise", []),
        "passive_perception": 10 + skill_bonus(sheet, "Perception"),
        "conditions": sheet.get("conditions", []), "death_saves": sheet.get("death_saves", {"success": 0, "fail": 0}),
        "down": sheet["hp"] <= 0 and not sheet.get("dead"), "dead": bool(sheet.get("dead")),
        "inspiration": bool(sheet.get("inspiration")), "exhaustion": int(sheet.get("exhaustion", 0)),
        "gold_cp": sheet.get("gold_cp", 0),
        "inventory": [item_view(it) for it in sheet.get("inventory", [])],
        "attacks": [{k: v for k, v in a.items() if k in ("id", "name", "to_hit", "damage", "damage_type", "range_ft",
                                                         "long_range_ft", "kind", "properties", "mastery")} for a in attacks(sheet)],
        "spellcasting": spellcasting,
        "features": [{"name": f.get("label") or f["name"], "description": f["description"],
                      "uses": ({k: f["uses"][k] for k in ("max", "used", "per")} if f.get("uses") else None)}
                     for f in sheet.get("features", [])],
        "feats": feats, "masteries": masteries,
        "custom": [{"entry_id": c.get("entry_id"), "kind": c.get("kind"), "name": c.get("name"),
                    "description": c.get("description", ""), "level": c.get("level"), "source": c.get("source", "library")}
                   for c in sheet.get("custom", [])],
        "portrait_url": f"/api/files/portraits/{sheet['portrait']}" if sheet.get("portrait") else None,
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
    if sheet["hp"] == 0 and not was_down and race_info(sheet)["mechanics"].get("relentless") \
            and not sheet.get("endurance_used") and amount > 0:
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
        elif f.get("uses") and f["name"] == "Second Wind" and rs(sheet) == "2024":
            f["uses"]["used"] = max(0, f["uses"]["used"] - 1)  # 2024: regain one use on a short rest
    sheet["pact_used"] = 0
    return {"healed": healed}


def long_rest(sheet: dict) -> dict:
    if sheet.get("dead"):
        return {"healed": 0}
    healed = heal(sheet, sheet["hp_max"])
    sheet["hit_dice_used"] = 0 if rs(sheet) == "2024" else max(0, sheet.get("hit_dice_used", 0) - max(1, sheet["level"] // 2))
    sheet["slots_used"] = {}
    sheet["pact_used"] = 0
    sheet["endurance_used"] = False
    sheet["mi_free_used"] = False
    if sheet.get("exhaustion"):
        sheet["exhaustion"] = max(0, int(sheet["exhaustion"]) - 1)
    for f in sheet.get("features", []):
        if f.get("uses"):
            f["uses"]["used"] = 0
    sheet["conditions"] = [c for c in sheet["conditions"] if c not in TEMP_CONDITIONS]
    sheet["temp_hp"] = 0
    sheet["concentration"] = None
    return {"healed": healed}
