"""Shops: stock generation, services, haggling, buying and selling. Pure code — no AI involved."""
from __future__ import annotations

import random

from . import srd
from .character import RulesError, add_item, find_inv, heal, item_view, remove_condition, remove_item, skill_bonus
from .dice import d20

SHOP_TYPES = ("general", "blacksmith", "alchemist", "magic", "temple", "inn")

GENERAL_GEAR = [
    "backpack", "bedroll", "rations-1-day", "torch", "rope-hempen-50-feet", "waterskin", "tinderbox",
    "lantern-hooded", "oil-flask", "crowbar", "grappling-hook", "healers-kit", "blanket", "candle",
    "chalk-1-piece", "climbers-kit", "hammer", "piton", "pouch", "sack", "shovel", "tent-two-person",
    "mess-kit", "clothes-travelers", "arrow", "crossbow-bolt", "sling-bullet", "holy-water-flask",
    "antitoxin-vial", "caltrops", "ball-bearings-bag-of-1000", "spellbook", "component-pouch",
]
ALCHEMIST_GOODS = ["antitoxin-vial", "acid-vial", "alchemists-fire-flask", "oil-flask", "healers-kit", "herbalism-kit",
                   "holy-water-flask", "poison-basic-vial", "perfume-vial", "vial", "component-pouch"]
LIGHT_MED_ARMOR = ["padded-armor", "leather-armor", "studded-leather-armor", "hide-armor", "chain-shirt",
                   "scale-mail", "breastplate"]
HEAVY_ARMOR = ["ring-mail", "chain-mail", "splint-armor"]
PRICE_MULT = {"scarce": 1.25, "standard": 1.0, "rich": 0.9}
POTIONS = {"low": 1, "standard": 3, "high": 6}

SERVICES = {
    "svc-heal": {"name": "Healing prayers (restore all HP)", "price_cp": 1000, "shops": ["temple"],
                 "description": "A priest tends your wounds until you are whole."},
    "svc-cure": {"name": "Cure poison and disease", "price_cp": 1500, "shops": ["temple"],
                 "description": "Removes the Poisoned condition and any disease."},
    "svc-blessing": {"name": "Blessing for the road", "price_cp": 500, "shops": ["temple"],
                     "description": "A blessing — Inspiration for your next roll."},
    "svc-room": {"name": "Room and board (long rest)", "price_cp": 50, "shops": ["inn"],
                 "description": "A warm bed and a meal: you finish a long rest when the party leaves."},
    "svc-meal": {"name": "Hot meal and the local gossip", "price_cp": 30, "shops": ["inn"],
                 "description": "Hear what the locals are talking about (the DM tells you)."},
    "svc-stable": {"name": "Stable and feed for a mount", "price_cp": 50, "shops": ["inn"],
                   "description": "Keep a horse fed and sheltered for a night."},
}


def generate(shop_type: str, size: str, magic_level: str = "standard", economy: str = "standard",
             seed: int | None = None) -> list[dict]:
    rng = random.Random(seed)
    mult = PRICE_MULT.get(economy, 1.0)
    keys: list[tuple[str, int]] = []
    if shop_type == "general":
        pool = GENERAL_GEAR[:]
        rng.shuffle(pool)
        n = {"village": 14, "town": 22, "city": len(pool)}.get(size, 18)
        for k in pool[:n]:
            qty = 20 if k in ("arrow", "crossbow-bolt", "sling-bullet", "torch", "rations-1-day") else rng.randint(1, 4)
            keys.append((k, qty))
        keys.append(("potion-of-healing", POTIONS.get(magic_level, 3) + (2 if size == "city" else 0)))
    elif shop_type == "blacksmith":
        weapons = [r["index"] for r in srd.equipment().values() if r.get("category") == "Weapon"]
        simple = [w for w in weapons if w in srd.SIMPLE_WEAPONS]
        martial = [w for w in weapons if w not in srd.SIMPLE_WEAPONS and w not in ("lance", "net", "blowgun")]
        rng.shuffle(martial)
        for k in simple + martial[: {"village": 5, "town": 12, "city": len(martial)}.get(size, 8)]:
            keys.append((k, rng.randint(1, 3)))
        armor = LIGHT_MED_ARMOR + (HEAVY_ARMOR if size != "village" else ["ring-mail", "chain-mail"])
        if size == "city":
            armor = armor + ["half-plate-armor", "plate-armor"]
        for k in armor:
            keys.append((k, rng.randint(1, 2)))
        keys.append(("shield", rng.randint(2, 4)))
        keys += [("arrow", 40), ("crossbow-bolt", 40), ("sling-bullet", 40)]
    elif shop_type == "alchemist":
        for k in ALCHEMIST_GOODS:
            keys.append((k, rng.randint(1, 5)))
        keys.append(("potion-of-healing", POTIONS.get(magic_level, 3) * 2))
        if magic_level != "low" or size == "city":
            keys.append(("potion-of-healing-greater", 1 + (2 if magic_level == "high" else 0)))
        potions = [m for m in srd.equipment().values() if m.get("category") == "Magic Item"
                   and m["name"].lower().startswith("potion") and m.get("rarity") in ("Common", "Uncommon")
                   and "healing" not in m["index"]]
        rng.shuffle(potions)
        for m in potions[: {"low": 1, "standard": 3, "high": 6}.get(magic_level, 3)]:
            keys.append((m["index"], 1))
    elif shop_type == "magic":
        items = [m for m in srd.equipment().values() if m.get("category") == "Magic Item"]
        common = [m for m in items if m["rarity"] == "Common"]
        uncommon = [m for m in items if m["rarity"] == "Uncommon"]
        rare = [m for m in items if m["rarity"] == "Rare"]
        rng.shuffle(uncommon)
        rng.shuffle(rare)
        n_unc = {"low": 1, "standard": 3, "high": 6}.get(magic_level, 3) + (2 if size == "city" else 0)
        picks = common + uncommon[:n_unc] + (rare[:1 if size == "city" else 0] if magic_level == "high" else [])
        for m in picks:
            keys.append((m["index"], 1))
        keys.append(("potion-of-healing", POTIONS.get(magic_level, 3)))
    elif shop_type == "temple":
        keys += [("holy-water-flask", rng.randint(2, 5)), ("healers-kit", 2), ("candle", 10), ("potion-of-healing", 2)]
    elif shop_type == "inn":
        keys += [("rations-1-day", 20), ("waterskin", 4), ("candle", 10), ("torch", 10), ("bedroll", 2)]
    else:
        raise RulesError(f"unknown shop type {shop_type!r}")
    stock = []
    for k, qty in keys:
        rec = srd.item(k)
        if not rec or not rec.get("cost_cp"):
            continue
        stock.append({"key": k, "qty": qty, "price_cp": max(1, int(round(rec["cost_cp"] * mult)))})
    for k, svc in SERVICES.items():
        if shop_type in svc["shops"]:
            stock.append({"key": k, "qty": 99, "price_cp": max(1, int(round(svc["price_cp"] * mult))), "service": True})
    return stock


def stock_view(shop: dict) -> dict:
    out = []
    for s in shop.get("stock", []):
        if s.get("service"):
            svc = SERVICES.get(s["key"], {})
            out.append({"key": s["key"], "name": svc.get("name", s["key"]), "category": "Service", "price_cp": s["price_cp"],
                        "qty": s["qty"], "description": svc.get("description", ""), "weight": 0, "damage": "", "ac": "",
                        "properties": [], "service": True, "rarity": None})
            continue
        rec = srd.item(s["key"]) or {}
        out.append({"key": s["key"], "name": rec.get("name", s["key"]), "category": rec.get("category", ""),
                    "price_cp": s["price_cp"], "qty": s["qty"], "description": rec.get("description", ""),
                    "weight": rec.get("weight") or 0, "damage": rec.get("damage") or "", "ac": rec.get("ac") or "",
                    "properties": [p for p in rec.get("properties") or [] if p.lower() != "monk"],
                    "service": False, "rarity": rec.get("rarity")})
    return {"name": shop.get("name"), "keeper": shop.get("keeper"), "type": shop.get("type"),
            "sell_rate": shop.get("sell_rate", 0.5), "stock": out,
            "discounts": shop.get("discounts", {}), "haggled": shop.get("haggled", [])}


def price_for(shop: dict, entry: dict, char_id: str | None) -> int:
    disc = float((shop.get("discounts") or {}).get(char_id or "", 0))
    return max(1, int(round(entry["price_cp"] * (1 + disc))))


def buy(sheet: dict, shop: dict, key: str, qty: int, char_id: str | None = None) -> dict:
    if qty < 1:
        raise RulesError("buy at least one")
    entry = next((s for s in shop.get("stock", []) if s["key"] == key), None)
    if not entry or entry["qty"] < 1:
        raise RulesError("the shop doesn't have that")
    if qty > entry["qty"]:
        raise RulesError(f"the shop only has {entry['qty']}")
    total = price_for(shop, entry, char_id) * qty
    if sheet.get("gold_cp", 0) < total:
        raise RulesError("not enough money")
    if entry.get("service"):
        effect = _service(sheet, shop, key, char_id)
        sheet["gold_cp"] -= total
        return {"name": SERVICES[key]["name"], "qty": 1, "cost_cp": total, "effect": effect}
    sheet["gold_cp"] -= total
    entry["qty"] -= qty
    rec = srd.item(key) or {}
    if rec.get("category") in ("Weapon", "Armor"):
        for _ in range(qty):
            add_item(sheet, key, 1)
    else:
        add_item(sheet, key, qty)
    return {"name": rec.get("name", key), "qty": qty, "cost_cp": total, "effect": None}


def _service(sheet: dict, shop: dict, key: str, char_id: str | None) -> str:
    if key == "svc-heal":
        if sheet["hp"] >= sheet["hp_max"]:
            raise RulesError("you're already at full health")
        n = heal(sheet, sheet["hp_max"])
        return f"healed {n} HP"
    if key == "svc-cure":
        if "Poisoned" not in sheet.get("conditions", []):
            raise RulesError("you aren't poisoned or diseased")
        remove_condition(sheet, "Poisoned")
        return "cured"
    if key == "svc-blessing":
        if sheet.get("inspiration"):
            raise RulesError("you already have Inspiration")
        sheet["inspiration"] = True
        return "gained Inspiration"
    if key == "svc-room":
        rooms = shop.setdefault("rooms", [])
        if char_id in rooms:
            raise RulesError("you've already paid for a room")
        rooms.append(char_id)
        return "will finish a long rest"
    if key == "svc-meal":
        return "hears the local gossip"
    if key == "svc-stable":
        return "stabled a mount"
    raise RulesError("unknown service")


def haggle(sheet: dict, shop: dict, char_id: str, size: str = "town") -> dict:
    """One Persuasion check per character per shop; sets that character's price adjustment."""
    haggled = shop.setdefault("haggled", [])
    if char_id in haggled:
        raise RulesError("you've already haggled here — the keeper won't budge again")
    dc = {"village": 12, "town": 14, "city": 16}.get(size, 14)
    bonus = skill_bonus(sheet, "Persuasion")
    r = d20(bonus)
    margin = r["total"] - dc
    disc = -0.2 if margin >= 5 else -0.1 if margin >= 0 else 0.0 if margin > -5 else 0.1
    shop.setdefault("discounts", {})[char_id] = disc
    haggled.append(char_id)
    return {"roll": r, "dc": dc, "discount": disc}


def sell(sheet: dict, shop: dict, item_id: str, qty: int) -> dict:
    it = find_inv(sheet, item_id)
    v = item_view(it)
    if v["value_cp"] <= 0:
        raise RulesError(f"no one here will pay for {it['name']}")
    rate = float(shop.get("sell_rate", 0.5))
    price = int(v["value_cp"] * rate) * qty
    remove_item(sheet, item_id, qty)
    sheet["gold_cp"] = sheet.get("gold_cp", 0) + price
    stock = next((s for s in shop.setdefault("stock", []) if s["key"] == it["key"]), None)
    if stock:
        stock["qty"] += qty
    elif srd.item(it["key"]):
        shop["stock"].append({"key": it["key"], "qty": qty, "price_cp": v["value_cp"]})
    return {"name": it["name"], "qty": qty, "price_cp": price}


def fmt_cp(cp: int) -> str:
    gp, rem = divmod(int(cp), 100)
    sp, c = divmod(rem, 10)
    parts = [f"{gp} gp" if gp else "", f"{sp} sp" if sp else "", f"{c} cp" if c else ""]
    return " ".join(p for p in parts if p) or "0 gp"
