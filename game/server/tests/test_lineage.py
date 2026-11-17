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


def test_ddb_import_keeps_the_backstory():
    d = _ddb_json(legacy=False)
    d["notes"] = {"backstory": "<p>Raised by <strong>reapers</strong> in the barley fields.</p>"}
    assert ddb.to_sheet(d)["backstory"] == "Raised by reapers in the barley fields."


def test_a_homebrew_finesse_sickle_uses_dex_and_allows_sneak_attack():
    s = ch.create(_payload("2024", "halfling"))
    s["abilities"].update({"STR": 8, "DEX": 15})
    sickle = ch.make_item("sickle", 1, True)
    s["inventory"] = [i for i in s["inventory"] if not i.get("equipped")] + [sickle]
    plain = next(a for a in ch.attacks(s) if a["weapon_key"] == "sickle")
    assert not plain["finesse"] and plain["ability_mod"] == -1
    sickle["extra_properties"] = ["Finesse", "Bogus"]  # only known properties count
    sickle["name"] = "Sickle (finesse, homebrew)"
    a = next(a for a in ch.attacks(s) if a["weapon_key"] == "sickle")
    assert a["finesse"] and a["ability_mod"] == 2 and a["name"] == "Sickle (finesse, homebrew)"
    assert "Finesse" in a["properties"] and "Bogus" not in a["properties"]


def test_import_drops_entries_that_repeat_the_rules_and_keeps_real_extras():
    d = _ddb_json(legacy=False)
    d["race"]["racialTraits"] += [{"definition": {"name": n, "description": "<p>x</p>"}}
                                  for n in ("Size", "Speed", "Creature Type", "Fey Ancestry", "Elven Lineage Spells")]
    d["feats"] = [{"definition": {"name": "Soldier Ability Score Improvements", "description": "<p>x</p>"}},
                  {"definition": {"name": "Dark Bargain", "description": "<p>A campaign boon.</p>"}}]
    kept = {c["name"] for c in ddb.to_sheet(d)["custom"]}
    assert "Dark Bargain" in kept and "Starlit Grace" in kept
    assert not kept & {"Size", "Speed", "Creature Type", "Fey Ancestry", "Elven Lineage Spells",
                       "Soldier Ability Score Improvements"}


def test_ddb_placeholder_feats_are_not_imported():
    d = _ddb_json(legacy=False)
    ph = {"categories": [{"tagName": "__DISGUISE_FEAT"}, {"tagName": "__DISPLAY_WITH_DATA_ORIGIN"}]}
    d["feats"] = [{"definition": {"name": "Hero's Journey Boon", "description": "<p>At your GM's discretion…</p>", **ph}},
                  {"definition": {"name": "Faction Renown", "description": "<p>Azeroth is defined by…</p>", **ph}},
                  {"definition": {"name": "Polearm Master", "description": "<p>Bonus attack.</p>",
                                  "categories": [{"tagName": "General"}]}}]
    kept = {c["name"] for c in ddb.to_sheet(d)["custom"]}
    assert "Polearm Master" in kept and not kept & {"Hero's Journey Boon", "Faction Renown"}


def test_dm_grants_boons_players_cannot_detach_them():
    from fastapi.testclient import TestClient

    from app.db import SessionLocal
    from app.dm.tools import ToolBox
    from app.game.state import load
    from app.main import app

    from .test_chat import _character, _client

    with TestClient(app):
        host = _client("boonhost")
        cid = _character(host, "Teft")
        gid = host.post("/api/games", json={"name": "B", "character_id": cid, "settings": {"ruleset": "2024"}}).json()["id"]
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            tb = ToolBox(ctx)
            assert tb.call("grant_boon", {"character": "Teft", "kind": "dark_bargain", "name": "The Caretaker's Lantern",
                                          "description": "See in magical darkness; the Caretaker always knows where you are."}).startswith("Granted")
            assert tb.call("grant_boon", {"character": "Teft", "kind": "renown", "name": "Blue-coats",
                                          "description": "1: Vane owes you"}).startswith("Granted")
            assert tb.call("grant_boon", {"character": "Teft", "kind": "renown", "name": "Blue-coats",
                                          "description": "2: Vane owes you twice"}).startswith("Updated")
            names = [c["name"] for c in ctx.chars[cid]["custom"]]
            assert names == ["Dark Bargain: The Caretaker's Lantern", "Renown: Blue-coats"]
            ctx.save()
            db.commit()
        finally:
            db.close()
        sheet = host.get(f"/api/games/{gid}/view").json()["characters"][cid]
        entry = next(c for c in sheet["custom"] if c["name"] == "Renown: Blue-coats")
        assert entry["source"] == "dm" and "twice" in entry["description"]
        r = host.delete(f"/api/characters/{cid}/custom/{entry['entry_id']}")
        assert r.status_code == 400 and "DM" in r.text
