"""Treasure after a victory, scaled by monster CR, type and the game's magic level."""
from __future__ import annotations

import random

from . import srd
from .dice import roll

CARRIES_COIN = {"humanoid", "giant", "fiend", "dragon", "monstrosity", "undead"}
POTION_CHANCE = {"low": 0.08, "standard": 0.2, "high": 0.35}
MAGIC_CHANCE = {"low": 0.0, "standard": 0.05, "high": 0.15}


def roll_treasure(monsters: list[dict], magic_level: str = "standard", rng: random.Random | None = None) -> dict:
    """monsters: [{cr, ctype}] → {cp, items: [item keys]}"""
    rng = rng or random.Random()
    cp = 0
    for m in monsters:
        if m.get("ctype") not in CARRIES_COIN:
            continue
        cr = m.get("cr") or 0
        if cr < 1:
            cp += roll("3d6").total * 10          # silver
        elif cr <= 4:
            cp += roll("3d6").total * 100         # gold
        else:
            cp += roll("6d6").total * 100
    items: list[str] = []
    total_cr = sum(m.get("cr") or 0 for m in monsters)
    if monsters and rng.random() < POTION_CHANCE.get(magic_level, 0.2) + min(0.2, total_cr * 0.03):
        items.append("potion-of-healing")
    if total_cr >= 1 and rng.random() < MAGIC_CHANCE.get(magic_level, 0.05) + min(0.1, total_cr * 0.02):
        pool = [m for m in srd.equipment().values() if m.get("category") == "Magic Item"
                and m.get("rarity") in (("Common", "Uncommon") if total_cr >= 3 else ("Common",))]
        if pool:
            items.append(rng.choice(pool)["index"])
    return {"cp": cp, "items": items}
