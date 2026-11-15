"""M3 rules data: 2014 and 2024 class tables to level 10, backgrounds, feats, mastery, species, spell effects."""
import json

import pytest

from app.config import SRD_2024_PATH, SRD_PATH
from app.rules import classes as c14
from app.rules import classes_2024 as c24

D14 = json.loads(SRD_PATH.read_text(encoding="utf-8"))
D24 = json.loads(SRD_2024_PATH.read_text(encoding="utf-8"))
EQ14 = {e["index"] for e in D14["equipment"]}
EQ24 = {e["index"] for e in D24["equipment"]}
SP14 = {s["index"] for s in D14["spells"]}
SP24 = {s["index"] for s in D24["spells"]}
WEAPONS24 = {e["index"] for e in D24["equipment"] if e.get("damage")}
CLASS_NAMES = {c["name"] for c in c24.CLASSES_2024.values()}

RULESETS = [("2014", c14.CLASSES, SP14), ("2024", c24.CLASSES_2024, SP24)]


@pytest.mark.parametrize("ruleset,classes,spells", RULESETS)
def test_features_every_level(ruleset, classes, spells):
    assert len(classes) == 12
    for key, c in classes.items():
        for lvl in range(1, 11):
            assert lvl in c["features"], f"{ruleset} {key} missing level {lvl}"
        asi = [l for l, fs in c["features"].items() if any(f["name"] == "Ability Score Improvement" for f in fs)]
        assert 4 in asi and 8 in asi, f"{ruleset} {key} ASI levels {asi}"
        if key == "fighter":
            assert 6 in asi
        if key == "rogue":
            assert 10 in asi
        assert c["subclasses"], key
        for fs in c["features"].values():
            for f in fs:
                u = f.get("uses")
                if u:
                    assert u["per"] in ("short", "long")
                    mx = u["max"]
                    assert isinstance(mx, (int, str, dict)), (key, f["name"])
                    if isinstance(mx, dict):
                        assert all(isinstance(k, int) for k in mx)


@pytest.mark.parametrize("ruleset,classes,spells", RULESETS)
def test_items_and_spells_exist(ruleset, classes, spells):
    for key, c in classes.items():
        for opt in c["equipment_options"]:
            for item, qty, _eq in opt["items"]:
                assert item in EQ14, f"{ruleset} {key} item {item}"
        for item, qty in c["gear"]:
            assert item in EQ14, f"{ruleset} {key} gear {item}"
        sc = c["spellcasting"]
        if sc:
            for lvl, idxs in (sc.get("always") or {}).items():
                for i in idxs:
                    assert i in spells, f"{ruleset} {key} always {i}"
            assert len(sc["cantrips_known"]) in (0, 10), key
            if ruleset == "2024":
                assert len(sc["prepared"]) == 10 and sc["prepares"]
            elif sc.get("known"):
                assert len(sc["spells_known"]) == 10


def test_slot_tables():
    for table in (c14.FULL_CASTER_SLOTS, c14.HALF_CASTER_SLOTS, c14.PACT_SLOTS, c24.HALF_CASTER_SLOTS_2024):
        assert sorted(table) == list(range(1, 11))
    assert c14.MAX_LEVEL == 10 and c24.MAX_LEVEL_2024 == 10
    assert set(range(1, 12)) <= set(c14.XP_THRESHOLDS) and c14.PROF_BONUS[9] == 4
    assert c14.max_spell_level("wizard", 9) == 5 and c14.max_spell_level("paladin", 9) == 3
    assert c24.max_spell_level_2024("paladin", 1) == 1 and c24.max_spell_level_2024("warlock", 9) == 5


def test_spell_effects_exist():
    assert set(c14.SPELL_EFFECTS) <= SP14, set(c14.SPELL_EFFECTS) - SP14
    assert set(c24.SPELL_EFFECTS_2024) <= SP24, set(c24.SPELL_EFFECTS_2024) - SP24
    for k in ("hunter-s-mark", "cure-wounds", "fireball", "divine-smite" if "divine-smite" in c24.SPELL_EFFECTS_2024 else "fireball"):
        assert k in c24.SPELL_EFFECTS_2024
    assert c24.SPELL_EFFECTS_2024["cure-wounds"]["dice"] == "2d8"


def test_backgrounds_feats_species():
    assert len(c24.BACKGROUNDS_2024) == 4
    for b in c24.BACKGROUNDS_2024.values():
        assert b["origin_feat"] in c24.FEATS_2024, b
        assert len(b["ability_options"]) == 3 and len(b["skills"]) == 2
        for item, _q in b["items"]:
            assert item in EQ14, (b["index"], item)
    assert c24.FEATS_2024["Magic Initiate"]["category"] == "origin"
    assert {f["category"] for f in c24.FEATS_2024.values()} >= {"origin", "general", "fighting_style", "epic"}
    species24 = {s["index"] for s in D24["species"]}
    subs24 = {s["index"] for s in D24["subspecies"]}
    assert set(c24.SPECIES_2024) == species24
    for k, sp in c24.SPECIES_2024.items():
        assert set(sp["subspecies"]) <= subs24, k


def test_mastery():
    assert set(c24.MASTERY) <= WEAPONS24, set(c24.MASTERY) - WEAPONS24
    assert set(c24.MASTERY.values()) <= set(c24.MASTERY_DESCRIPTIONS)
    for old, new in c24.ITEM_ALIASES_2024.items():
        assert old in EQ14, old
        assert new in EQ24, new
    assert c24.MASTERY_BY_ITEM["crossbow-light"] == "Slow"


def test_spell_class_lists():
    assert set(c24.SPELL_CLASSES_2024) == SP24
    for idx, cls in c24.SPELL_CLASSES_2024.items():
        assert set(cls) <= CLASS_NAMES, (idx, cls)
    for key, c in c24.CLASSES_2024.items():
        sc = c["spellcasting"]
        if sc:
            assert sc["list"] in CLASS_NAMES
            n = sum(1 for cl in c24.SPELL_CLASSES_2024.values() if sc["list"] in cl)
            assert n > 10, (key, n)
