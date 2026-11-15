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
def monsters() -> dict[str, dict]:
    return {m["index"]: m for m in data()["monsters"]}


def find_monster(name: str) -> dict | None:
    ms = monsters()
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


def monster_actions(m: dict) -> list[dict]:
    """Parse attack actions out of the monster's description text."""
    out = []
    for a in _ACTION.finditer(m.get("description") or ""):
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
    mm = re.search(r"Multiattack:[^.]*?makes (two|three|four|five)\b", m.get("description") or "", re.I)
    return _NUM.get(mm.group(1).lower(), 1) if mm else 1


def monster_speed(m: dict) -> int:
    mm = re.search(r"walk\s*(\d+)", m.get("speed") or "")
    if mm:
        return int(mm.group(1))
    mm = re.search(r"(\d+)", m.get("speed") or "")
    return int(mm.group(1)) if mm else 30


# ── spells, races ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def spells() -> dict[str, dict]:
    return {s["index"]: s for s in data()["spells"]}


@lru_cache(maxsize=1)
def races() -> dict[str, dict]:
    return {r["index"]: r for r in data()["races"]}


@lru_cache(maxsize=1)
def subraces() -> dict[str, dict]:
    return {r["index"]: r for r in data()["subraces"]}


def monsters_by_cr(max_cr: float, types: set[str] | None = None) -> list[dict]:
    out = []
    for m in monsters().values():
        cr = m.get("cr")
        if cr is None or cr > max_cr:
            continue
        if types and m.get("type") not in types:
            continue
        out.append(m)
    return out
