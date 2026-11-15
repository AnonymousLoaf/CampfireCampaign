"""The bundled 5e SRD dataset (skills/dnd/data/dnd5e_srd.json), indexed for the game."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from ..config import SRD_PATH

SIMPLE_WEAPONS = {
    "club", "dagger", "greatclub", "handaxe", "javelin", "light-hammer", "mace", "quarterstaff",
    "sickle", "spear", "crossbow-light", "dart", "shortbow", "sling",
}

# Items the SRD lists without a usable shop price.
CUSTOM_ITEMS = {
    "potion-of-healing": {
        "index": "potion-of-healing", "name": "Potion of Healing", "category": "Potion",
        "cost_cp": 5000, "weight": 0.5, "usable": True, "heal": "2d4+2",
        "description": "Drink to regain 2d4 + 2 hit points.",
    },
    "potion-of-healing-greater": {
        "index": "potion-of-healing-greater", "name": "Potion of Greater Healing", "category": "Potion",
        "cost_cp": 15000, "weight": 0.5, "usable": True, "heal": "4d4+4",
        "description": "Drink to regain 4d4 + 4 hit points.",
    },
}

_COST = re.compile(r"^\s*([\d,]+)\s*(cp|sp|ep|gp|pp)\s*$", re.I)
_RATE = {"cp": 1, "sp": 10, "ep": 50, "gp": 100, "pp": 1000}
_RANGE = re.compile(r"(\d+)\s*/\s*(\d+|\?)")
_DMG = re.compile(r"^\s*(\d*d\d+(?:\s*[+-]\s*\d+)?|\d+)\s*([A-Za-z]+)?")
_ACTION = re.compile(
    r"Action\s*\W+\s*(?P<name>[^:\n]+):\s*(?P<kind>Melee|Ranged|Melee or Ranged)\s+(?:Weapon|Spell)\s+Attack:\s*"
    r"(?P<hit>[+-]\d+)\s*to hit,\s*(?:reach\s*(?P<reach>\d+)\s*ft\.?)?(?:\s*or\s*)?(?:range\s*(?P<r1>\d+)/(?P<r2>\d+)\s*ft\.?)?"
    r".*?Hit:\s*(?:(?P<avg>\d+)\s*)?\((?P<dice>[^)]+)\)\s*(?P<type>[a-z]+)\s+damage",
    re.I | re.S)


def cost_to_cp(cost: str | None) -> int:
    if not cost:
        return 0
    m = _COST.match(cost)
    if not m:
        return 0
    return int(m.group(1).replace(",", "")) * _RATE[m.group(2).lower()]


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(SRD_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def equipment() -> dict[str, dict]:
    out = {}
    for r in data()["equipment"]:
        rec = dict(r)
        rec["cost_cp"] = cost_to_cp(r.get("cost"))
        if r["category"] == "Weapon":
            rec["weapon_category"] = "simple" if r["index"] in SIMPLE_WEAPONS else "martial"
        out[r["index"]] = rec
    for k, v in CUSTOM_ITEMS.items():
        out[k] = dict(v)
    for m in data()["magic_items"]:
        if m["index"] in out or m.get("rarity") not in RARITY_PRICE_GP:
            continue
        out[m["index"]] = {"index": m["index"], "name": m["name"], "category": "Magic Item",
                           "rarity": m["rarity"], "cost_cp": RARITY_PRICE_GP[m["rarity"]] * 100, "weight": 0,
                           "description": m.get("description", ""), "attunement": m.get("attunement", False)}
    return out


RARITY_PRICE_GP = {"Common": 100, "Uncommon": 400, "Rare": 4000, "Very Rare": 40000}


def item(index: str) -> dict | None:
    return equipment().get(index)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def find_item(name: str) -> dict | None:
    """Look up an item by index or name (loose match)."""
    eq = equipment()
    key = _norm(name)
    if key in eq:
        return eq[key]
    for rec in eq.values():
        if _norm(rec["name"]) == key:
            return rec
    # "longsword +1" etc. are not supported in M1; try a prefix match on plain names.
    for rec in eq.values():
        if key and (_norm(rec["name"]).startswith(key) or key.startswith(_norm(rec["name"]))):
            return rec
    return None


def weapon_profile(rec: dict) -> dict:
    """Damage dice/type, range and properties for an SRD weapon record."""
    dmg = (rec.get("damage") or "1 Bludgeoning").strip()
    m = _DMG.match(dmg)
    dice = m.group(1).replace(" ", "") if m else "1"
    dtype = (m.group(2) or "bludgeoning").lower() if m else "bludgeoning"
    props = [p for p in rec.get("properties") or [] if p.lower() != "monk"]
    plow = [p.lower() for p in props]
    rng = _RANGE.search(rec.get("range") or "")
    ranged = bool(rng and rng.group(2) != "?" and "thrown" not in plow and int(rng.group(1)) > 5) \
        or "ammunition" in plow
    if ranged and rng:
        normal, long = int(rng.group(1)), (int(rng.group(2)) if rng.group(2) != "?" else None)
    else:
        normal = 10 if "reach" in plow else 5
        long = None
    thrown = _RANGE.search(rec.get("throw_range") or "") if "thrown" in plow else None
    return {"dice": dice, "type": dtype, "properties": props, "ranged": ranged,
            "finesse": "finesse" in plow, "range": normal, "long_range": long,
            "thrown_range": (int(thrown.group(1)), int(thrown.group(2))) if thrown else None,
            "two_handed": "two-handed" in plow, "versatile": rec.get("damage_2h") or None,
            "category": rec.get("weapon_category", "simple")}


# ── monsters ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _monsters_2014() -> dict[str, dict]:
    return {m["index"]: m for m in data()["monsters"]}


@lru_cache(maxsize=1)
def _monsters_2024() -> dict[str, dict]:
    return {m["index"]: _norm_monster_2024(m) for m in data_2024()["monsters"]}


def monsters(ruleset: str = "2014") -> dict[str, dict]:
    return _monsters_2024() if ruleset == "2024" and data_2024()["monsters"] else _monsters_2014()


def find_monster(name: str, ruleset: str = "2014") -> dict | None:
    ms = monsters(ruleset)
    if ruleset == "2024":  # 2024 renamed a few: goblin → goblin-warrior etc.; fall back to a 2014 name match
        alias = {"goblin": "goblin-warrior", "goblins": "goblin-warrior", "orc": "orc", "kobold": "kobold-warrior"}
        k = _norm(name)
        if k in alias and alias[k] in ms:
            return ms[alias[k]]
    key = _norm(name)
    if key in ms:
        return ms[key]
    for m in ms.values():
        if _norm(m["name"]) == key:
            return m
    # plural / loose: "goblins" → goblin
    if key.endswith("s") and key[:-1] in ms:
        return ms[key[:-1]]
    for m in ms.values():
        if key and key in _norm(m["name"]):
            return m
    return None


_ACTION_2024 = re.compile(r"Action\s*\W+\s*(?P<name>[^(\n:]+?)\s*\((?P<dice>\d*d\d+(?:\s*[+-]\s*\d+)?)\s+(?P<type>[a-z]+)\)", re.I)
_RANGED_2024 = {"shortbow": (80, 320), "light crossbow": (80, 320), "longbow": (150, 600), "heavy crossbow": (100, 400),
                "hand crossbow": (30, 120), "sling": (30, 120), "javelin": (30, 120), "dart": (20, 60),
                "spear": (20, 60), "dagger": (20, 60), "handaxe": (20, 60)}
_RANGED_WORDS = ("bow", "crossbow", "sling", "ray", "bolt", "spit", "blast", "rock", "spike", "dart")


def _actions_2024(m: dict) -> list[dict]:
    """2024 stat blocks give only 'Name (dice type)': derive the attack bonus and damage modifier."""
    pb = int(m.get("proficiency_bonus") or 2)
    smod, dmod = (m.get("str", 10) - 10) // 2, (m.get("dex", 10) - 10) // 2
    out = []
    for a in _ACTION_2024.finditer(m.get("description") or ""):
        name = a.group("name").strip()
        low = name.lower()
        rng = next((v for k, v in _RANGED_2024.items() if k == low), None)
        ranged = bool(rng and low not in ("spear", "dagger", "handaxe", "javelin")) or any(w in low for w in _RANGED_WORDS) \
            or low == "javelin"
        if low == "javelin":
            ranged = False  # javelins are thrown melee weapons; the engine treats them as melee
        use = dmod if ranged else max(smod, dmod if low in ("scimitar", "shortsword", "rapier", "dagger") else smod)
        dice = a.group("dice").replace(" ", "")
        if not re.search(r"[+-]\d+$", dice) and use:
            dice = f"{dice}{use:+d}"
        out.append({"name": name, "to_hit": pb + use, "dice": dice, "type": a.group("type").lower(),
                    "ranged": ranged, "range": (rng[0] if rng else 60) if ranged else 5,
                    "long_range": (rng[1] if rng else None) if ranged else None, "reach": 5})
    return out


def monster_actions(m: dict) -> list[dict]:
    """Parse attack actions out of the monster's description text (2014 or 2024 stat-block wording)."""
    out = []
    if m.get("_rules") == "2024" or (m.get("proficiency_bonus") and "to hit" not in (m.get("description") or "")):
        out = _actions_2024(m)
    for a in _ACTION.finditer(m.get("description") or "") if not out else []:
        kind = a.group("kind").lower()
        ranged = kind.startswith("ranged")
        out.append({
            "name": a.group("name").strip(),
            "to_hit": int(a.group("hit")),
            "dice": a.group("dice").replace(" ", ""),
            "type": a.group("type").lower(),
            "ranged": ranged,
            "range": int(a.group("r1")) if a.group("r1") else int(a.group("reach") or 5),
            "long_range": int(a.group("r2")) if a.group("r2") else None,
            "reach": int(a.group("reach") or 5),
        })
    if not out:
        str_mod = (m.get("str", 10) - 10) // 2
        out.append({"name": "Slam", "to_hit": 2 + str_mod, "dice": f"1d4{str_mod:+d}" if str_mod else "1d4",
                    "type": "bludgeoning", "ranged": False, "range": 5, "long_range": None, "reach": 5})
    return out


_NUM = {"two": 2, "three": 3, "four": 4, "five": 5}


def monster_multiattack(m: dict) -> int:
    """How many attacks the monster makes with its Multiattack action (1 if none)."""
    desc = m.get("description") or ""
    mm = re.search(r"Multiattack:[^.]*?makes (two|three|four|five)\b", desc, re.I)
    if mm:
        return _NUM.get(mm.group(1).lower(), 1)
    mm = re.search(r"Multiattack:([^.\n]*)", desc, re.I)
    if mm:  # 2024 wording: "makes one Bite attack and one Claw attack"
        n = len(re.findall(r"\bone\b", mm.group(1), re.I))
        return max(1, min(4, n))
    return 1


def monster_speed(m: dict) -> int:
    mm = re.search(r"walk\s*(\d+)", m.get("speed") or "")
    if mm:
        return int(mm.group(1))
    mm = re.search(r"(\d+)", m.get("speed") or "")
    return int(mm.group(1)) if mm else 30


# ── 2024 dataset ────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def data_2024() -> dict:
    from ..config import SRD_2024_PATH
    if not SRD_2024_PATH.exists():
        return {"spells": [], "monsters": [], "species": [], "subspecies": [], "backgrounds": [], "feats": [],
                "weapon_mastery_properties": [], "features": [], "equipment": [], "magic_items": []}
    return json.loads(SRD_2024_PATH.read_text(encoding="utf-8"))


def _norm_monster_2024(m: dict) -> dict:
    rec = dict(m)
    cr = m.get("cr_value", m.get("cr"))
    if isinstance(cr, str):
        from fractions import Fraction
        try:
            cr = float(Fraction(cr.strip()))  # "1/4" → 0.25
        except (ValueError, ZeroDivisionError):
            cr = 0.0
    rec["cr"] = cr
    rec["type"] = str(m.get("type") or "").split(" ")[0].lower()
    rec["_rules"] = "2024"
    for k in ("resistances", "immunities", "vulnerabilities", "condition_immunities"):
        rec.setdefault(k, "")
    return rec


# ── spells, races ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _spells_2014() -> dict[str, dict]:
    return {s["index"]: s for s in data()["spells"]}


@lru_cache(maxsize=1)
def _spells_2024() -> dict[str, dict]:
    old = _spells_2014()
    by_name = {s["name"].lower().replace("'", ""): s for s in old.values()}
    out = {}
    for s in data_2024()["spells"]:
        rec = dict(s)
        prev = old.get(s["index"]) or by_name.get(s["name"].lower().replace("'", ""))
        rec.setdefault("classes", list((prev or {}).get("classes") or []))
        out[s["index"]] = rec
    try:  # the rules-data module may supply 2024 class lists for spells missing from 2014
        from .classes_2024 import SPELL_CLASSES_2024  # type: ignore
        for idx, cls in SPELL_CLASSES_2024.items():
            if idx in out:
                out[idx]["classes"] = list(cls)
    except ImportError:
        pass
    return out


def spells(ruleset: str = "2014") -> dict[str, dict]:
    return _spells_2024() if ruleset == "2024" and data_2024()["spells"] else _spells_2014()


@lru_cache(maxsize=1)
def races() -> dict[str, dict]:
    return {r["index"]: r for r in data()["races"]}


@lru_cache(maxsize=1)
def subraces() -> dict[str, dict]:
    return {r["index"]: r for r in data()["subraces"]}


def monsters_by_cr(max_cr: float, types: set[str] | None = None, ruleset: str = "2014") -> list[dict]:
    out = []
    for m in monsters(ruleset).values():
        cr = m.get("cr")
        if cr is None or cr > max_cr:
            continue
        if types and m.get("type") not in types:
            continue
        out.append(m)
    return out
