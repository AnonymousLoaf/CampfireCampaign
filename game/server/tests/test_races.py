"""More races: original Campfire races in both editions, and players' homebrew races in the creator."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rules import campfire_races as cf
from app.rules import character as ch

STD = {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8}


def _payload(ruleset: str, race: str, name: str = "Racer") -> dict:
    opts = ch.creator_options(ruleset)
    fighter = next(x for x in opts["classes"] if x["index"] == "fighter")
    bg = opts["backgrounds"][0]
    p = {"ruleset": ruleset, "name": name, "race": race, "class": "fighter", "background": bg["index"],
         "ability_method": "standard", "abilities": dict(STD),
         "skills": [s for s in fighter["skill_choices"]["options"] if s not in bg["skills"]][:2],
         "equipment_option": fighter["equipment_options"][0]["id"], "fighting_style": "Defense"}
    if ruleset == "2024":
        p["background_asi"] = {bg["ability_options"][0]: 2, bg["ability_options"][1]: 1}
    return p


def _client(name):
    c = TestClient(app)
    assert c.post("/api/auth/register", json={"username": name, "password": "secret123", "display_name": name}).status_code == 200
    return c


@pytest.mark.parametrize("ruleset", ["2014", "2024"])
def test_creator_options_group_campfire_races(ruleset):
    races = ch.creator_options(ruleset)["races"]
    groups = [r["group"] for r in races]
    assert groups[0] == "srd" and set(groups) == {"srd", "campfire"}
    assert groups == sorted(groups, key=lambda g: g != "srd")  # SRD first, then Campfire
    camp = [r for r in races if r["group"] == "campfire"]
    assert len(camp) == 7 and all(r["source"] == "Campfire Campaign" and r["trait_details"] for r in camp)
    for r in camp:
        if ruleset == "2014":
            assert sum(r["ability_bonuses"].values()) == 3
        else:
            assert r["ability_bonuses"] == {}
    felari = next(r for r in camp if r["index"] == "campfire-felari")
    assert "Darkvision (60 ft.)" in felari["traits"]


def test_campfire_race_2014_and_2024():
    s14 = ch.create(_payload("2014", "campfire-lumari"))
    assert s14["abilities"]["INT"] == STD["INT"] + 2 and s14["abilities"]["CHA"] == STD["CHA"] + 1
    v = ch.view("x", "u", None, s14)
    assert v["race"] == "Lumari" and v["race_source"] == "campfire" and v["speed"] == 30
    assert "radiant" in v["resistances"]
    assert any(t["name"] == "Starfall Flare" and "short or long rest" in t["description"] for t in v["race_traits"])

    s24 = ch.create(_payload("2024", "campfire-galeborn"), starting_level=3)
    v = ch.view("x", "u", None, s24)
    assert v["race"] == "Galeborn" and v["level"] == 3
    assert "Perception" in v["skill_profs"]
    assert any(t["name"] == "Updraft" and "Proficiency Bonus" in t["description"] for t in v["race_traits"])
    base = {k: STD[k] + (s24["background_asi"] or {}).get(k, 0) for k in STD}
    assert s24["abilities"] == base  # 2024: no racial ability bonuses

    with pytest.raises(ch.RulesError):
        ch.create({**_payload("2014", "campfire-todling"), "subrace": "hill-dwarf"})
    assert ch.view("x", "u", None, ch.create(_payload("2014", "campfire-todling")))["race"] == "Todling"


def test_homebrew_race_crud_and_creation():
    with TestClient(app):
        a = _client("racer_a")
        b = _client("racer_b")
        good = {"speed": 35, "size": "small", "ability_bonuses": {"WIS": 2, "dex": 1}, "languages": ["Common", "Mothtongue"],
                "traits": [{"name": "Dust Wings", "text": "You can glide 30 ft per round while falling."}], "darkvision": 60}
        r = a.post("/api/custom", json={"kind": "race", "name": "Mothkin", "description": "Dusty moth folk.", "data": good})
        assert r.status_code == 200, r.text
        entry = r.json()
        assert entry["data"]["size"] == "Small" and entry["data"]["ability_bonuses"] == {"WIS": 2, "DEX": 1}
        for bad in ({"size": "Large"}, {"speed": 50}, {"speed": 15}, {"ability_bonuses": {"STR": 2, "DEX": 2}},
                    {"ability_bonuses": {"STR": 3}}, {"ability_bonuses": {"LUCK": 1}}, {"darkvision": 30},
                    {"traits": [{"name": "Long", "text": "x" * 601}]},
                    {"traits": [{"name": f"T{i}", "text": "ok"} for i in range(9)]}):
            r = a.post("/api/custom", json={"kind": "race", "name": "Bad", "data": {**good, **bad}})
            assert r.status_code == 400, (bad, r.text)
        # a full 8-trait race fits the raised data limit
        big = {**good, "traits": [{"name": f"Trait {i}", "text": "y" * 600} for i in range(8)]}
        assert a.post("/api/custom", json={"kind": "race", "name": "Big", "data": big}).status_code == 200
        # races are picked in the creator, not attached later
        mine = a.get("/api/characters").json()
        p14 = _payload("2014", "homebrew", "Moth One")
        p14["homebrew_race_id"] = entry["id"]
        r = a.post("/api/characters", json=p14)
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["race"] == "Mothkin" and v["race_source"] == "homebrew" and v["speed"] == 35
        assert v["abilities"]["WIS"] == STD["WIS"] + 2 and v["abilities"]["DEX"] == STD["DEX"] + 1
        assert [t["name"] for t in v["race_traits"]] == ["Darkvision (60 ft.)", "Dust Wings"]
        assert a.post(f"/api/characters/{v['id']}/custom", json={"entry_id": entry["id"]}).status_code == 400
        assert len(a.get("/api/characters").json()) == len(mine) + 1
        # 2024: ability bonuses are ignored; race id can ride in the race field too
        p24 = _payload("2024", f"homebrew:{entry['id']}", "Moth Two")
        r = a.post("/api/characters", json=p24)
        assert r.status_code == 200, r.text
        v24 = r.json()
        assert v24["race"] == "Mothkin" and v24["abilities"]["WIS"] == STD["WIS"] + p24["background_asi"].get("WIS", 0)
        # snapshot: editing or deleting the entry doesn't change the character
        assert a.put(f"/api/custom/{entry['id']}", json={"kind": "race", "name": "Renamed", "data": {**good, "speed": 25}}).status_code == 200
        assert a.delete(f"/api/custom/{entry['id']}").status_code == 200
        v = a.get(f"/api/characters/{v['id']}").json()
        assert v["race"] == "Mothkin" and v["speed"] == 35 and v["race_traits"]
        from app.db import SessionLocal
        from app.models import Character
        db = SessionLocal()
        try:
            sheet = db.get(Character, v["id"]).sheet
            assert sheet["homebrew_race"] == {"entry_id": entry["id"], "name": "Mothkin"}
            assert sheet["race_data"]["languages"] == ["Common", "Mothtongue"] and sheet["race_data"]["size"] == "Small"
        finally:
            db.close()
        # someone else's homebrew race is rejected
        other = b.post("/api/custom", json={"kind": "race", "name": "Secret", "data": good}).json()
        p = _payload("2014", "homebrew", "Thief")
        p["homebrew_race_id"] = other["id"]
        assert a.post("/api/characters", json=p).status_code == 400
        # a non-race entry is rejected too
        feat = a.post("/api/custom", json={"kind": "feat", "name": "Nope", "description": "x"}).json()
        p["homebrew_race_id"] = feat["id"]
        assert a.post("/api/characters", json=p).status_code == 400
        p.pop("homebrew_race_id")
        assert a.post("/api/characters", json=p).status_code == 400


def test_dm_prompt_lists_race_traits():
    from app.dm import prompt

    class _Ctx:
        def member_for_char(self, cid):
            return None

    s = ch.create(_payload("2014", "campfire-tideborn"))
    line = prompt._char_line(_Ctx(), "x", s)
    assert "Tideborn traits (Campfire Campaign race)" in line and "Gill-Breather" in line


def test_homebrew_validation_unit():
    d = cf.clean_homebrew_race({})
    assert d == {"speed": 30, "size": "Medium", "darkvision": 0, "ability_bonuses": {}, "languages": ["Common"], "traits": []}
    with pytest.raises(ValueError):
        cf.clean_homebrew_race({"ability_bonuses": {"STR": 1, "DEX": 1, "CON": 1, "INT": 1}})
