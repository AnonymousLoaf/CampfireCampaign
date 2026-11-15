"""Encounter difficulty and XP (5e DMG tables, levels 1-5)."""
from __future__ import annotations

import random

from . import srd

THRESHOLDS = {  # per character: easy, medium, hard, deadly
    1: (25, 50, 75, 100), 2: (50, 100, 150, 200), 3: (75, 150, 225, 400),
    4: (125, 250, 375, 500), 5: (250, 500, 750, 1100),
}
DIFFICULTY_TARGET = {"story": 0, "normal": 1, "hard": 2, "deadly": 3}  # index into THRESHOLDS

BIOME_TYPES = {
    "f": {"beast", "humanoid", "fey"}, "F": {"beast", "fey", "monstrosity"},
    ".": {"beast", "humanoid"}, '"': {"beast", "humanoid"}, "h": {"humanoid", "beast", "giant"},
    "M": {"monstrosity", "giant", "beast"}, "s": {"beast", "undead", "monstrosity"},
    "d": {"beast", "monstrosity", "elemental"}, "n": {"beast", "giant"}, "-": {"beast", "humanoid"},
    "road": {"humanoid", "beast"}, "cave": {"humanoid", "monstrosity", "beast", "undead"},
    "tavern": {"humanoid"}, "ruins": {"undead", "humanoid", "construct"},
}


def multiplier(count: int) -> float:
    if count <= 1:
        return 1
    if count == 2:
        return 1.5
    if count <= 6:
        return 2
    if count <= 10:
        return 2.5
    return 3


def encounter_xp(monsters: list[dict]) -> int:
    return sum(int(m.get("xp") or 0) for m in monsters)


def budget(levels: list[int], difficulty: str) -> int:
    idx = DIFFICULTY_TARGET.get(difficulty, 1)
    return sum(THRESHOLDS.get(max(1, min(5, lv)), THRESHOLDS[1])[idx] for lv in levels)


def random_encounter(levels: list[int], difficulty: str, biome: str, seed: int | None = None) -> list[tuple[str, int]]:
    """Pick (monster index, count) pairs whose adjusted XP fits the party's budget."""
    rng = random.Random(seed)
    target = budget(levels, difficulty)
    max_cr = max(0.25, min(3, sum(levels) / max(1, len(levels)) * 0.75))
    types = BIOME_TYPES.get(biome, {"beast", "humanoid"})
    pool = [m for m in srd.monsters_by_cr(max_cr, types) if (m.get("xp") or 0) > 0 and m.get("size") in
            ("Tiny", "Small", "Medium", "Large")]
    if not pool:
        pool = srd.monsters_by_cr(0.5)
    rng.shuffle(pool)
    for m in pool:
        xp = int(m["xp"])
        for count in range(1, 9):
            adj = xp * count * multiplier(count)
            if adj > target * 1.1:
                break
            if adj >= target * 0.6:
                return [(m["index"], count)]
    m = min(pool, key=lambda r: r["xp"])
    return [(m["index"], max(1, len(levels)))]
