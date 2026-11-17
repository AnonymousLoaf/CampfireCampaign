"""2024 species magic: lineage spells and species cantrips, for created and D&D Beyond-imported characters."""
from app import ddb
from app.rules import character as ch

from .test_m4 import _ddb_json
from .test_races import _payload


def _names(view: dict, key: str) -> list[str]:
    return [c["name"] for c in (view["spellcasting"] or {}).get(key) or []]


def test_wood_elf_rogue_gets_druidcraft_and_a_spells_section():
    p = _payload("2024", "elf")
    p.update({"class": "rogue", "subrace": "elven-lineage-wood-elf", "fighting_style": None})
    opts = ch.creator_options("2024")
    rogue = next(x for x in opts["classes"] if x["index"] == "rogue")
    bg = next(x for x in opts["backgrounds"] if x["index"] == p["background"])
    p["skills"] = [s for s in rogue["skill_choices"]["options"] if s not in bg["skills"]][:rogue["skill_choices"]["count"]]
    p["equipment_option"] = rogue["equipment_options"][0]["id"]
    s = ch.create(p)
    v = ch.view("x", "u", None, s)
    assert v["spellcasting"] and "Druidcraft" in _names(v, "cantrips") and v["speed"] == 35
    s3 = ch.create(p, starting_level=3)
    assert "Longstrider" in _names(ch.view("x", "u", None, s3), "spells")


def test_infernal_tiefling_gets_thaumaturgy_and_fire_bolt():
    p = _payload("2024", "tiefling")
    p["subrace"] = "fiendish-legacy-infernal"
    s = ch.create(p, starting_level=3)
    v = ch.view("x", "u", None, s)
    assert {"Thaumaturgy", "Fire Bolt"} <= set(_names(v, "cantrips"))
    assert "Hellish Rebuke" in _names(v, "spells")
    assert v["spellcasting"]["ability"] in ("INT", "WIS", "CHA")


def test_halfling_brings_no_species_spells():
    s = ch.create(_payload("2024", "halfling"))
    assert ch.species_spells(s) == ([], [])


def test_ddb_import_reads_the_lineage_from_species_options():
    d = _ddb_json(legacy=False)
    d["options"] = {"race": [{"definition": {"name": "Wood Elf Lineage"}}, {"definition": {"name": "Wood Elf - Charisma"}}]}
    d["spells"] = {"race": [{"definition": {"name": "Druidcraft"}}]}
    s = ddb.to_sheet(d)
    assert s["subrace"] == "elven-lineage-wood-elf" and s["lineage_ability"] == "CHA"
    assert "Druidcraft" in _names(ch.view("x", "u", None, s), "cantrips")


def test_ddb_import_falls_back_to_the_lineage_spell_and_flags_unknowns():
    d = _ddb_json(legacy=False)
    d["spells"] = {"race": [{"definition": {"name": "Dancing Lights"}}]}  # no lineage option, but a drow's spell
    assert ddb.to_sheet(d)["subrace"] == "elven-lineage-drow"
    s = ddb.to_sheet(_ddb_json(legacy=False))  # nothing to go on
    assert s["subrace"] is None and any("lineage" in i["issue"] for i in s["issues"])


def test_ddb_import_brings_magic_initiate_spells():
    d = _ddb_json(legacy=False)
    d["feats"] = [{"definition": {"name": "Magic Initiate (Wizard)", "description": "<p>Two cantrips and a spell.</p>"}}]
    d["spells"] = {"feat": [{"definition": {"name": "True Strike", "level": 0}},
                            {"definition": {"name": "Poison Spray", "level": 0}},
                            {"definition": {"name": "Disguise Self", "level": 1}}]}
    d["options"] = {"feat": [{"definition": {"name": "Charisma"}}]}
    s = ddb.to_sheet(d)
    v = ch.view("x", "u", None, s)
    assert "Magic Initiate" in s["feats"] and s["mi_ability"] == "CHA"
    assert {"True Strike", "Poison Spray"} <= set(_names(v, "cantrips")) and "Disguise Self" in _names(v, "spells")
