"""Dice rolling. Every roll the game makes goes through here so it can be logged."""
from __future__ import annotations

import random
import re
from contextlib import contextmanager
from dataclasses import dataclass, field

_rng = random.SystemRandom()

_NOTATION = re.compile(r"^\s*(\d*)d(\d+)(?:\s*(kh|kl)(\d+))?\s*([+-]\s*\d+)?\s*$", re.I)


def set_seed(seed: int | None) -> None:
    """Tests use a seeded RNG; the game uses the system RNG."""
    global _rng
    _rng = random.Random(seed) if seed is not None else random.SystemRandom()


# A player's attack is rolled in two clicks: the d20 first, then the damage. The first click runs the attack on a
# copy of the fight and records every die except the damage dice; the second runs it for real, replaying those
# dice in order, so the to-hit roll the player saw stands and only the damage is thrown fresh.
_record: list[list[int]] | None = None
_replay: list[list[int]] | None = None
_in_damage = 0


@contextmanager
def scripted(record: list | None = None, replay: list | None = None):
    global _record, _replay
    old = (_record, _replay)
    _record, _replay = record, (list(replay) if replay is not None else None)
    try:
        yield
    finally:
        _record, _replay = old


def die(sides: int) -> int:
    if not _in_damage and _replay:
        if _replay[0][0] == sides:
            return _replay.pop(0)[1]
        _replay.clear()  # the run took another path: everything from here on is fresh
    v = _rng.randint(1, sides)
    if _record is not None and not _in_damage:
        _record.append([sides, v])
    return v


@dataclass
class Roll:
    notation: str
    rolls: list[int]
    kept: list[int]
    modifier: int
    total: int
    dropped: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"notation": self.notation, "rolls": self.rolls, "kept": self.kept,
                "dropped": self.dropped, "modifier": self.modifier, "total": self.total}


def roll(notation: str) -> Roll:
    """Roll dice notation like '2d6+3', 'd20', '4d6kh3', '1d8-1'."""
    m = _NOTATION.match(notation.replace(" ", ""))
    if not m:
        raise ValueError(f"bad dice notation: {notation!r}")
    n = int(m.group(1) or 1)
    sides = int(m.group(2))
    if n < 1 or n > 100 or sides < 1 or sides > 1000:
        raise ValueError(f"dice out of range: {notation!r}")
    keep_mode, keep_n = m.group(3), m.group(4)
    mod = int(m.group(5).replace(" ", "")) if m.group(5) else 0
    rolls = [die(sides) for _ in range(n)]
    kept = list(rolls)
    dropped: list[int] = []
    if keep_mode:
        k = int(keep_n)
        ordered = sorted(rolls, reverse=keep_mode.lower() == "kh")
        kept, dropped = ordered[:k], ordered[k:]
    return Roll(notation, rolls, kept, mod, sum(kept) + mod, dropped)


def d20(modifier: int = 0, advantage: str = "normal") -> dict:
    """A d20 test. advantage: normal | advantage | disadvantage."""
    a = die(20)
    rolls = [a]
    natural = a
    if advantage in ("advantage", "disadvantage"):
        b = die(20)
        rolls = [a, b]
        natural = max(a, b) if advantage == "advantage" else min(a, b)
    return {"rolls": rolls, "natural": natural, "modifier": modifier,
            "total": natural + modifier, "advantage": advantage,
            "crit": natural == 20, "fumble": natural == 1}


def damage(notation: str, crit: bool = False) -> Roll:
    """Roll damage; a critical hit doubles the dice (not the modifier)."""
    global _in_damage
    _in_damage += 1
    try:
        return _damage(notation, crit)
    finally:
        _in_damage -= 1


def _damage(notation: str, crit: bool) -> Roll:
    if not crit:
        return roll(notation)
    m = _NOTATION.match(notation.replace(" ", ""))
    if not m:
        raise ValueError(f"bad dice notation: {notation!r}")
    n = int(m.group(1) or 1) * 2
    rest = notation.replace(" ", "")[len(m.group(1) or ""):]
    return roll(f"{n}{rest}")


def ability_set() -> dict:
    """One 4d6-drop-lowest ability score."""
    r = roll("4d6kh3")
    return {"rolls": r.rolls, "dropped": r.dropped[0] if r.dropped else None, "total": r.total}


def fmt_mod(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)
