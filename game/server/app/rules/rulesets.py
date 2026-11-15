"""One place to get the rules for a ruleset ("2014" = SRD 5.1, "2024" = SRD 5.2).

Character and combat code call `R(sheet)` / `R("2024")` instead of importing class tables directly,
so the same engine runs both editions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from . import classes as c14

# 2024 half casters (paladin, ranger) cast from level 1.
HALF_CASTER_SLOTS_2024 = {1: {"1": 2}, 2: {"1": 2}, 3: {"1": 3}, 4: {"1": 3}, 5: {"1": 4, "2": 2}, 6: {"1": 4, "2": 2},
                          7: {"1": 4, "2": 3}, 8: {"1": 4, "2": 3}, 9: {"1": 4, "2": 3, "3": 2}, 10: {"1": 4, "2": 3, "3": 2}}


@dataclass
class Rules:
    key: str
    CLASSES: dict
    BACKGROUNDS: dict
    SPELL_EFFECTS: dict
    FULL_SLOTS: dict
    HALF_SLOTS: dict
    PACT_SLOTS: dict
    XP_THRESHOLDS: dict
    PROF_BONUS: dict
    MAX_LEVEL: int
    FEATS: dict = field(default_factory=dict)
    MASTERY: dict = field(default_factory=dict)
    MASTERY_DESCRIPTIONS: dict = field(default_factory=dict)
    SPECIES: dict = field(default_factory=dict)
    ASI_LEVELS: dict = field(default_factory=dict)

    def is_asi_level(self, cls_key: str, level: int) -> bool:
        if self.ASI_LEVELS:
            return level in (self.ASI_LEVELS.get(cls_key) or [])
        return any(f["name"] == "Ability Score Improvement" for f in self.CLASSES[cls_key]["features"].get(level, []))

    def max_spell_level(self, cls_key: str, level: int) -> int:
        sc = self.CLASSES[cls_key].get("spellcasting")
        if not sc:
            return 0
        t = sc["type"]
        if t == "full":
            table = self.FULL_SLOTS.get(level, {})
        elif t == "half":
            table = self.HALF_SLOTS.get(level, {})
        else:
            return self.PACT_SLOTS.get(level, (0, 0))[1]
        return max((int(k) for k in table), default=0)

    def prof_bonus(self, level: int) -> int:
        return self.PROF_BONUS.get(level, 2 + (max(1, level) - 1) // 4)

    def spell_target(self, index: str) -> str:
        eff = self.SPELL_EFFECTS.get(index)
        if not eff:
            return "none"
        if eff.get("target"):
            return eff["target"]
        if eff.get("area"):
            return "self" if eff.get("from_self") and eff["area"]["shape"] == "sphere" else "point"
        if eff["kind"] in ("heal", "buff", "cleanse", "revive"):
            return "ally"
        if eff["kind"] == "teleport":
            return "point"
        return "enemy"

    def spell_kind(self, index: str) -> str:
        eff = self.SPELL_EFFECTS.get(index)
        if not eff:
            return "utility"
        return {"sleep": "save", "save_condition": "save", "buff": "utility", "mark": "utility", "teleport": "utility",
                "summon_weapon": "attack", "cleanse": "heal", "revive": "heal"}.get(eff["kind"], eff["kind"])


@lru_cache(maxsize=1)
def _r2014() -> Rules:
    return Rules("2014", c14.CLASSES, c14.BACKGROUNDS, c14.SPELL_EFFECTS, c14.FULL_CASTER_SLOTS, c14.HALF_CASTER_SLOTS,
                 c14.PACT_SLOTS, c14.XP_THRESHOLDS, c14.PROF_BONUS, c14.MAX_LEVEL,
                 FEATS={"Grappler": {"name": "Grappler", "description": "Advantage on attacks against a creature you are grappling.",
                                     "category": "general"}},
                 ASI_LEVELS=getattr(c14, "ASI_LEVELS", {}))


@lru_cache(maxsize=1)
def _r2024() -> Rules:
    try:
        from . import classes_2024 as c24  # written alongside the 2024 dataset
    except ImportError:
        return _r2014()
    return Rules("2024", c24.CLASSES_2024, c24.BACKGROUNDS_2024, getattr(c24, "SPELL_EFFECTS_2024", c14.SPELL_EFFECTS),
                 getattr(c24, "FULL_CASTER_SLOTS_2024", c14.FULL_CASTER_SLOTS),
                 getattr(c24, "HALF_CASTER_SLOTS_2024", HALF_CASTER_SLOTS_2024),
                 getattr(c24, "PACT_SLOTS_2024", c14.PACT_SLOTS), c14.XP_THRESHOLDS, c14.PROF_BONUS,
                 getattr(c24, "MAX_LEVEL_2024", c14.MAX_LEVEL), FEATS=getattr(c24, "FEATS_2024", {}),
                 MASTERY=getattr(c24, "MASTERY_BY_ITEM", getattr(c24, "MASTERY", {})),
                 MASTERY_DESCRIPTIONS=getattr(c24, "MASTERY_DESCRIPTIONS", {}), SPECIES=getattr(c24, "SPECIES_2024", {}),
                 ASI_LEVELS=getattr(c24, "ASI_LEVELS_2024", {}))


def R(sheet_or_key) -> Rules:
    key = sheet_or_key if isinstance(sheet_or_key, str) else (sheet_or_key or {}).get("ruleset", "2014")
    return _r2024() if key == "2024" else _r2014()


def available() -> list[str]:
    try:
        from . import classes_2024  # noqa: F401
        from . import srd
        return ["2014", "2024"] if srd.data_2024()["spells"] else ["2014"]
    except ImportError:
        return ["2014"]
