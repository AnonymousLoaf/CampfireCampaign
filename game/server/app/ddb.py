"""D&D Beyond import: reuse skills/dnd/scripts/ddb_import.py to read the character JSON, then map it to a sheet."""
from __future__ import annotations

import importlib.util
import json
import re
from functools import lru_cache

from .config import SKILL_SCRIPTS
from .rules import character as ch
from .rules import srd
from .rules.character import RulesError
from .rules.classes import BACKGROUNDS, CLASSES, MAX_LEVEL, SKILLS, XP_THRESHOLDS


@lru_cache(maxsize=1)
def _mod():
    spec = importlib.util.spec_from_file_location("ddb_import", SKILL_SCRIPTS / "ddb_import.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def load_source(source: str) -> dict:
    """A D&D Beyond URL/id (fetched; character must be Public) or pasted JSON text."""
    m = _mod()
    s = (source or "").strip()
    if not s:
        raise RulesError("paste a D&D Beyond character link or its JSON")
    if s.startswith("{"):
        try:
            return m.unwrap(json.loads(s))
        except (ValueError, m.ImportFailed) as e:
            raise RulesError(f"that isn't D&D Beyond character JSON: {e}")
    cid = m.character_id(s)
    if not cid:
        raise RulesError("that isn't a D&D Beyond character link")
    try:
        return m.fetch(cid)
    except m.ImportFailed as e:
        raise RulesError(str(e))


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def to_sheet(d: dict) -> dict:
    m = _mod()
    rep = m.check(d, "2014")
    classes = rep["classes"]
    if not classes:
        raise RulesError("the D&D Beyond character has no class yet — finish it in the builder")
    main = max(classes, key=lambda c: c["level"])
    cls_key = (main["name"] or "").lower()
    if cls_key not in CLASSES:
        raise RulesError(f"{main['name']} isn't an SRD class this game supports")
    issues = list(rep["issues"])
    level = rep["level"] or 1
    if level > MAX_LEVEL:
        issues.append({"issue": f"level {level} is capped at {MAX_LEVEL} in this version", "fix": "play at level 3 for now"})
    if len(classes) > 1:
        issues.append({"issue": "multiclassing isn't supported yet; imported as " + main["name"], "fix": "—"})
    scores = rep["abilities"] or {a: 10 for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA")}

    species = (rep.get("species") or "Human")
    race_key, sub_key = "human", None
    for sr in srd.subraces().values():
        if sr["name"].lower() == species.lower():
            sub_key = sr["index"]
            race_key = _slug(sr["race"])
    if not sub_key:
        for r in srd.races().values():
            if r["name"].lower() in species.lower():
                race_key = r["index"]
                break
        else:
            issues.append({"issue": f"species {species} isn't in the SRD; speed and traits use Human", "fix": "—"})

    profs, expertise = set(), set()
    skill_by_slug = {_slug(s): s for s in SKILLS}
    for mo in m._all_modifiers(d):
        sk = skill_by_slug.get(str(mo.get("subType", "")))
        if not sk:
            continue
        if mo.get("type") == "proficiency":
            profs.add(sk)
        elif mo.get("type") == "expertise":
            expertise.add(sk)

    bg_name = rep.get("background") or ""
    bg_key = _slug(bg_name) if _slug(bg_name) in BACKGROUNDS else (bg_name or "acolyte")

    sheet: dict = {
        "name": rep["name"][:40], "race": race_key, "subrace": sub_key, "class": cls_key, "subclass": main.get("subclass"),
        "background": bg_key, "alignment": "True Neutral", "backstory": "", "color": "#5b8fd1",
        "level": 1, "xp": 0, "abilities": scores, "base_abilities": dict(scores),
        "skill_profs": sorted(profs), "expertise": sorted(expertise), "save_profs": list(CLASSES[cls_key]["saves"]),
        "fighting_style": None, "conditions": [], "death_saves": {"success": 0, "fail": 0}, "dead": False,
        "inspiration": bool(d.get("inspiration")), "gold_cp": 0, "inventory": [], "features": [],
        "spells": {"cantrips": [], "spells": []}, "slots_used": {}, "hit_dice_used": 0, "temp_hp": 0,
        "source": "ddb", "issues": issues, "ddb_id": d.get("id"),
    }
    cur = d.get("currencies") or {}
    sheet["gold_cp"] = int(cur.get("cp", 0) or 0) + 10 * int(cur.get("sp", 0) or 0) + 50 * int(cur.get("ep", 0) or 0) \
        + 100 * int(cur.get("gp", 0) or 0) + 1000 * int(cur.get("pp", 0) or 0)

    for it in m.inventory(d):
        rec = srd.find_item(it["name"])
        qty = max(1, int(it.get("qty") or 1))
        if rec:
            if rec["category"] in ("Weapon", "Armor"):
                for i in range(qty):
                    sheet["inventory"].append(ch.make_item(rec["index"], 1, bool(it["equipped"]) and i == 0))
            else:
                ch.add_item(sheet, rec["index"], qty)
        else:
            ch.add_item(sheet, "custom-" + _slug(it["name"])[:20], qty,
                        custom={"name": it["name"][:60], "description": "Imported from D&D Beyond.", "value_cp": 0,
                                "category": "Treasure"})

    spells = srd.spells()
    by_name = {s["name"].lower(): k for k, s in spells.items()}
    for cs in d.get("classSpells") or []:
        for sp in (cs or {}).get("spells") or []:
            df = sp.get("definition") or {}
            k = by_name.get((df.get("name") or "").lower())
            if not k:
                continue
            if (df.get("level") or 0) == 0:
                sheet["spells"]["cantrips"].append(k)
            elif sp.get("prepared") or sp.get("alwaysPrepared") or cls_key == "wizard":
                sheet["spells"]["spells"].append(k)

    hd = CLASSES[cls_key]["hit_die"]
    sheet["hp_max"] = hd + ch.mod(scores["CON"])
    sheet["hp"] = sheet["hp_max"]
    sheet["level_target"] = 1
    sheet["pact_used"] = 0
    sheet["concentration"] = None
    if CLASSES[cls_key]["subclass_level"] == 1:
        sheet["subclass"] = CLASSES[cls_key]["subclasses"][0]["index"]
    ch._grant_features(sheet, 1)
    sheet["spells"]["cantrips"] = list(dict.fromkeys(sheet["spells"]["cantrips"]))
    sheet["spells"]["spells"] = list(dict.fromkeys(sheet["spells"]["spells"]))
    if (CLASSES[cls_key].get("spellcasting") or {}).get("spellbook"):
        sheet["spells"]["spellbook"] = list(sheet["spells"]["spells"])
    # Level up with the imported picks kept: auto choices only fill what the import lacked.
    for _ in range(2, min(level, MAX_LEVEL) + 1):
        auto = ch.auto_choices(sheet)
        auto.pop("cantrips", None)
        auto.pop("spells", None)
        try:
            ch.level_up(sheet, auto)
        except RulesError:
            ch.level_up(sheet, ch.auto_choices(sheet))
    if rep.get("hp_max") and level <= MAX_LEVEL:
        sheet["hp_max"] = sheet["hp"] = int(rep["hp_max"])
    sheet["xp"] = XP_THRESHOLDS[sheet["level"]]
    sheet["level_target"] = sheet["level"]
    return sheet
