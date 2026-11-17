"""D&D Beyond import: reuse skills/dnd/scripts/ddb_import.py to read the character JSON, then map it to a sheet.

2024 ("5.5") characters are detected from D&D Beyond's legacy flags and import with the 2024 rules.
Features the game's own (SRD) tables don't cover — subclass features, feats, species traits from books
the player owns — are kept as custom entries on the character with their D&D Beyond descriptions,
so the DM can use them.
"""
from __future__ import annotations

import html
import importlib.util
import json
import re
import uuid
from functools import lru_cache

from .config import SKILL_SCRIPTS
from .rules import character as ch
from .rules import srd
from .rules.character import RulesError
from .rules.classes import SKILLS
from .rules.rulesets import SRD_SUBCLASS_FEATURES, R


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


def _text(raw: str | None) -> str:
    """D&D Beyond descriptions are HTML: turn them into plain text."""
    t = re.sub(r"<\s*br\s*/?>|</p>|</li>", "\n", raw or "", flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def detect_ruleset(d: dict) -> str:
    """2024 if the species or background is a current (non-legacy) 2024 option."""
    race = d.get("race") or {}
    bg = ((d.get("background") or {}).get("definition")) or {}
    if race.get("isLegacy") is False or bg.get("isLegacy") is False:
        return "2024"
    return "2014"


def _ddb_features(d: dict, main_class: dict | None) -> list[dict]:
    """Every named feature on the D&D Beyond sheet: class/subclass features, feats, species traits, background feature."""
    out: list[dict] = []
    level = sum((c.get("level") or 0) for c in d.get("classes") or [])
    for c in d.get("classes") or []:
        for f in c.get("classFeatures") or []:
            df = f.get("definition") or {}
            req = df.get("requiredLevel") or 0
            if df.get("name") and req <= (c.get("level") or level):
                out.append({"kind": "feature", "name": df["name"], "description": _text(df.get("description")),
                            "level": req or None})
    for f in d.get("feats") or []:
        df = f.get("definition") or {}
        if df.get("name"):
            out.append({"kind": "feat", "name": df["name"], "description": _text(df.get("description")), "level": None})
    for t in (d.get("race") or {}).get("racialTraits") or []:
        df = t.get("definition") or {}
        if df.get("name") and not df.get("hideInSheet"):
            out.append({"kind": "species_trait", "name": df["name"], "description": _text(df.get("description")),
                        "level": None})
    bgd = ((d.get("background") or {}).get("definition")) or {}
    if bgd.get("featureName"):
        out.append({"kind": "feature", "name": bgd["featureName"], "description": _text(bgd.get("featureDescription")),
                    "level": None})
    seen, uniq = set(), []
    for f in out:
        k = f["name"].lower()
        if k not in seen and f["description"]:
            seen.add(k)
            uniq.append(f)
    return uniq


def to_sheet(d: dict) -> dict:
    m = _mod()
    ruleset = detect_ruleset(d)
    rules = R(ruleset)
    rep = m.check(d, ruleset)
    classes = rep["classes"]
    if not classes:
        raise RulesError("the D&D Beyond character has no class yet — finish it in the builder")
    main = max(classes, key=lambda c: c["level"])
    cls_key = (main["name"] or "").lower()
    if cls_key not in rules.CLASSES:
        raise RulesError(f"{main['name']} isn't a class this game supports")
    cls = rules.CLASSES[cls_key]
    issues = list(rep["issues"])
    level = rep["level"] or 1
    if level > rules.MAX_LEVEL:
        issues.append({"issue": f"level {level} is capped at {rules.MAX_LEVEL} for now", "fix": f"play at level {rules.MAX_LEVEL}"})
    if len(classes) > 1:
        issues.append({"issue": "multiclassing isn't supported yet; imported as " + main["name"], "fix": ""})
    scores = rep["abilities"] or {a: 10 for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA")}

    species = (rep.get("species") or "Human")
    race_key, sub_key = "human", None
    lineage_ability = None
    if ruleset == "2024":
        sp_all = ch._species_2024()
        # 2024 lineages aren't in the species name ("Elf"): D&D Beyond keeps them as species options ("Wood Elf
        # Lineage", "Wood Elf - Charisma") and lists the lineage's spells under spells.race ("Druidcraft").
        picked = [str((o.get("definition") or {}).get("name") or "") for o in (d.get("options") or {}).get("race") or []]
        race_spells = {_slug((s.get("definition") or {}).get("name") or "")
                       for s in ((d.get("spells") or {}).get("race") or []) if isinstance(s, dict)}
        hay = " | ".join([species] + picked).lower()
        for idx, sp in sp_all.items():
            if sp.get("name", "").lower() in species.lower():
                race_key = idx
                lineage = (R("2024").SPECIES.get(idx) or {}).get("mechanics", {}).get("lineage_spells") or {}
                for sub in sp.get("subspecies", []):
                    tail = sub["name"].split(":")[-1].strip().lower()
                    if tail and tail in hay:
                        sub_key = sub["index"]
                        break
                if not sub_key and race_spells:  # fall back to the lineage's level-1 spell
                    sub_key = next((s for s, by_lvl in lineage.items()
                                    if set(by_lvl.get(1) or by_lvl.get("1") or []) & race_spells), None)
                break
        else:
            issues.append({"issue": f"species {species} isn't in the free 2024 rules; its traits are kept as custom entries",
                           "fix": ""})
        for name in picked:  # "Wood Elf - Charisma": the ability the lineage's spells use
            ab = re.search(r"\b(intelligence|wisdom|charisma)\b", name.lower())
            if ab and " - " in name:
                lineage_ability = ab.group(1)[:3].upper()
                break
        if sub_key is None and sp_all.get(race_key, {}).get("subspecies"):
            issues.append({"issue": f"couldn't tell which {species} lineage was chosen on D&D Beyond, so its lineage "
                                    f"spells and traits are missing", "fix": "tell the host which lineage it is"})
    else:
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
                issues.append({"issue": f"species {species} isn't in the free 2014 rules; its traits are kept as custom entries",
                               "fix": ""})

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
    bg_key = _slug(bg_name) if _slug(bg_name) in rules.BACKGROUNDS else (bg_name or next(iter(rules.BACKGROUNDS)))

    sub_name = main.get("subclass")
    sub_index = None
    for s in cls["subclasses"]:
        if sub_name and (s["name"].lower() in sub_name.lower() or sub_name.lower() in s["name"].lower()):
            sub_index = s["index"]

    sheet: dict = {
        "ruleset": ruleset, "name": rep["name"][:40], "race": race_key, "subrace": sub_key, "class": cls_key,
        "subclass": sub_index or sub_name, "background": bg_key, "alignment": "True Neutral", "backstory": "",
        "color": "#5b8fd1", "level": 1, "xp": 0, "level_target": 1, "abilities": scores, "base_abilities": dict(scores),
        "bonus_abilities": [], "ancestry": None, "feats": [], "masteries": [], "exhaustion": 0,
        "skill_profs": sorted(profs), "expertise": sorted(expertise), "save_profs": list(cls["saves"]),
        "fighting_style": None, "conditions": [], "death_saves": {"success": 0, "fail": 0}, "dead": False,
        "inspiration": bool(d.get("inspiration")), "gold_cp": 0, "inventory": [], "features": [],
        "spells": {"cantrips": [], "spells": []}, "slots_used": {}, "pact_used": 0, "hit_dice_used": 0, "temp_hp": 0,
        "concentration": None, "custom": [], "source": "ddb", "issues": issues, "ddb_id": d.get("id"),
    }
    if lineage_ability:
        sheet["lineage_ability"] = lineage_ability
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

    # spells: SRD ones become real spells; the rest are kept as custom spells
    spells = srd.spells(ruleset)
    by_name = {s["name"].lower().replace("'", ""): k for k, s in spells.items()}
    extra_spells: list[dict] = []
    for cs in d.get("classSpells") or []:
        for sp in (cs or {}).get("spells") or []:
            df = sp.get("definition") or {}
            nm = (df.get("name") or "")
            k = by_name.get(nm.lower().replace("'", ""))
            if not k:
                if nm:
                    extra_spells.append({"kind": "spell", "name": nm, "description": _text(df.get("description")),
                                         "level": df.get("level"), "data": {"level": df.get("level")}})
                continue
            if (df.get("level") or 0) == 0:
                sheet["spells"]["cantrips"].append(k)
            elif sp.get("prepared") or sp.get("alwaysPrepared") or cls_key == "wizard":
                sheet["spells"]["spells"].append(k)

    # feats the game knows by name ("Magic Initiate (Wizard)" is the game's "Magic Initiate")
    mi_list = None
    for f in d.get("feats") or []:
        nm = ((f.get("definition") or {}).get("name") or "")
        base = re.sub(r"\s*\(.*\)$", "", nm)
        if nm in rules.FEATS:
            sheet["feats"].append(nm)
        elif base in rules.FEATS:
            sheet["feats"].append(base)
            if base == "Magic Initiate":
                mi_list = re.search(r"\((\w+)\)", nm).group(1).title() if "(" in nm else None

    # spells granted by feats (Magic Initiate's two cantrips and 1st-level spell) and by items
    granted = [((s.get("definition") or {}).get("name") or "", (s.get("definition") or {}).get("level") or 0)
               for k in ("feat", "item", "background") for s in ((d.get("spells") or {}).get(k) or [])
               if isinstance(s, dict)]
    for nm, lvl in granted:
        k = by_name.get(nm.lower().replace("'", ""))
        if not k:
            if nm:
                extra_spells.append({"kind": "spell", "name": nm, "description": "Granted by a feat or item on D&D "
                                     "Beyond.", "level": lvl, "data": {"level": lvl}})
            continue
        bucket = "bonus_cantrips" if lvl == 0 else "bonus_spells"
        if k not in sheet["spells"]["cantrips"] + sheet["spells"]["spells"]:
            sheet["spells"].setdefault(bucket, []).append(k)
    if mi_list or any(f.startswith("Magic Initiate") for f in sheet["feats"]):
        picked_ab = next((ab.upper()[:3] for o in (d.get("options") or {}).get("feat") or []
                          for ab in [((o.get("definition") or {}).get("name") or "")]
                          if ab.lower() in ("intelligence", "wisdom", "charisma")), None)
        sheet["mi_ability"] = picked_ab or {"Cleric": "WIS", "Druid": "WIS", "Wizard": "INT"}.get(mi_list or "", "INT")
        sheet["mi_free_used"] = False

    hd = cls["hit_die"]
    sheet["hp_max"] = hd + ch.mod(scores["CON"])
    sheet["hp"] = sheet["hp_max"]
    if cls["subclass_level"] == 1 and not sub_index:
        sheet["subclass"] = cls["subclasses"][0]["index"]
    ch._grant_features(sheet, 1)
    sheet["spells"]["cantrips"] = list(dict.fromkeys(sheet["spells"]["cantrips"]))
    sheet["spells"]["spells"] = list(dict.fromkeys(sheet["spells"]["spells"]))
    if (cls.get("spellcasting") or {}).get("spellbook"):
        sheet["spells"]["spellbook"] = list(sheet["spells"]["spells"])
    for _ in range(2, min(level, rules.MAX_LEVEL) + 1):
        auto = ch.auto_choices(sheet)
        auto.pop("cantrips", None)
        auto.pop("spells", None)
        if sub_index and auto.get("subclass"):
            auto["subclass"] = sub_index
        try:
            ch.level_up(sheet, auto)
        except RulesError:
            ch.level_up(sheet, ch.auto_choices(sheet))
    wm = cls.get("weapon_mastery") or {}
    if ruleset == "2024" and wm:
        # Weapon masteries: the weapons the character carries first, then whatever the level-ups picked.
        n_m = max((int(v) for k, v in wm.items() if sheet["level"] >= int(k)), default=0)
        allowed = {o["weapon_key"] for o in ch._mastery_options(cls, ruleset)}
        carried = [it.get("key") for it in sheet["inventory"] if it.get("key") in allowed]
        sheet["masteries"] = list(dict.fromkeys(carried + list(sheet.get("masteries") or []) + sorted(allowed)))[:n_m]
    if sub_name and not sub_index and sheet["level"] >= cls["subclass_level"]:
        sheet["subclass"] = sub_name  # keep the player's own subclass name; its features come in as custom entries
        sheet["features"] = [f for f in sheet["features"] if f["name"] not in SRD_SUBCLASS_FEATURES
                             and not re.match(r"(Martial Archetype|Roguish Archetype|Arcane Tradition)", f["name"])]
        issues.append({"issue": f"{sub_name} isn't in the free rules — its features are kept as text for the DM, and the "
                                f"game's automatic subclass bonuses don't apply to it", "fix": ""})
    if rep.get("hp_max") and level <= rules.MAX_LEVEL:
        sheet["hp_max"] = sheet["hp"] = int(rep["hp_max"])
    sheet["xp"] = rules.XP_THRESHOLDS[sheet["level"]]
    sheet["level_target"] = sheet["level"]

    # keep everything the game's tables don't cover as custom entries the DM can read
    have = {f["name"].lower() for f in sheet["features"]} | {f.lower() for f in sheet["feats"]}
    kept = []
    for f in _ddb_features(d, main) + extra_spells:
        if f["name"].lower() in have:
            continue
        entry = {"entry_id": "ddb-" + uuid.uuid4().hex[:8], "kind": f["kind"], "name": f["name"][:80],
                 "description": f["description"][:3000], "level": f.get("level"), "data": f.get("data") or {},
                 "source": "ddb"}
        sheet["custom"].append(entry)
        kept.append(f["name"])
    sheet["imported_custom"] = kept
    return sheet
