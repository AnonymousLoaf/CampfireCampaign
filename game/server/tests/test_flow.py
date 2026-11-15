"""End-to-end: two players, the offline DM, a full loop of exploration → shop → combat."""
import os
import tempfile
import time

_tmp = tempfile.mkdtemp(prefix="dndgame-test-")
os.environ["GAME_DATA_DIR"] = _tmp
os.environ["GAME_TICK_SECONDS"] = "0.2"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

FIGHTER = {"name": "Brakka", "race": "dwarf", "subrace": "hill-dwarf", "class": "fighter", "background": "soldier",
           "ability_method": "standard", "abilities": {"STR": 15, "DEX": 13, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10},
           "skills": ["Perception", "Survival"], "equipment_option": "defender", "color": "#aa3333"}
WIZARD = {"name": "Ilsa", "race": "elf", "subrace": "high-elf", "class": "wizard", "background": "sage",
          "ability_method": "pointbuy", "abilities": {"STR": 8, "DEX": 14, "CON": 14, "INT": 15, "WIS": 12, "CHA": 8},
          "skills": ["Investigation", "Insight"], "equipment_option": "scholar",
          "cantrips": ["fire-bolt", "ray-of-frost", "mage-hand"],
          "spells": ["magic-missile", "sleep", "burning-hands", "shield", "mage-armor", "thunderwave"]}


def client_for(name):
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"username": name, "password": "secret123", "display_name": name.title()})
    assert r.status_code == 200, r.text
    return c


def wait_phase(c, gid, types, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = c.get(f"/api/games/{gid}/view").json()
        if v["phase"]["type"] in types and not v["dm"]["busy"]:
            return v
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {types}; last phase {v['phase']}")


def test_full_loop():
    with TestClient(app) as boot:  # runs lifespan (db init, scheduler)
        a = client_for("alice")
        b = client_for("bob")
        ca = a.post("/api/characters", json=FIGHTER)
        assert ca.status_code == 200, ca.text
        cb = b.post("/api/characters", json=WIZARD)
        assert cb.status_code == 200, cb.text
        g = a.post("/api/games", json={"name": "Test Run", "character_id": ca.json()["id"],
                                       "settings": {"rolls": "players", "round_timer_minutes": 60}}).json()
        gid = g["id"]
        code = a.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]
        assert b.post("/api/games/join", json={"invite_code": code, "character_id": cb.json()["id"]}).status_code == 200
        assert b.post(f"/api/games/{gid}/start").status_code == 400  # only host
        r = a.post(f"/api/games/{gid}/start")
        assert r.status_code == 200, r.text

        v = wait_phase(a, gid, {"exploration"})
        assert v["world"] and v["world"]["settlements"]
        assert any(l["kind"] == "narration" for l in v["log"])
        assert v["quests"]

        # exploration → shop
        assert a.post(f"/api/games/{gid}/action", json={"text": "I head to the market to shop"}).status_code == 200
        v = a.get(f"/api/games/{gid}/view").json()
        assert v["phase"]["waiting_on"] == [v["members"][1]["user_id"]]
        assert b.post(f"/api/games/{gid}/action", json={"text": "I tag along"}).status_code == 200
        v = wait_phase(a, gid, {"shop"})
        assert v["shop"]["stock"]
        item = v["shop"]["stock"][0]
        r = a.post(f"/api/games/{gid}/shop/buy", json={"key": item["key"], "qty": 1})
        assert r.status_code in (200, 400), r.text
        assert a.post(f"/api/games/{gid}/ready", json={"ready": True}).status_code == 200
        assert b.post(f"/api/games/{gid}/ready", json={"ready": True}).status_code == 200
        v = wait_phase(a, gid, {"exploration"})
        assert v["shop"] is None

        # exploration → combat
        a.post(f"/api/games/{gid}/action", json={"text": "We attack the goblins on the road"})
        b.post(f"/api/games/{gid}/action", json={"text": "I attack too"})
        v = wait_phase(a, gid, {"combat"})
        enc = v["encounter"]
        assert enc and enc["tokens"]
        # play combat: each player attacks the nearest monster if possible, then ends turn; host forces stalls
        for _ in range(60):
            v = a.get(f"/api/games/{gid}/view").json()
            if v["phase"]["type"] == "exploration" and not v["encounter"]:
                break
            if v["dm"]["busy"] or v["phase"]["type"] == "dm":
                time.sleep(0.1)
                continue
            for c in (a, b):
                vv = c.get(f"/api/games/{gid}/view").json()
                e = vv.get("encounter")
                if not e or not e["my_turn"]:
                    continue
                if e["targets"]:
                    t = e["targets"][0]
                    if t["attack_ids"]:
                        c.post(f"/api/games/{gid}/combat/attack", json={"attack_id": t["attack_ids"][0], "target_id": t["token_id"]})
                    elif t["spell_indexes"]:
                        c.post(f"/api/games/{gid}/combat/cast", json={"spell_index": t["spell_indexes"][0], "target_id": t["token_id"]})
                c.post(f"/api/games/{gid}/combat/end-turn", json={})
            v = a.get(f"/api/games/{gid}/view").json()
            if v["phase"]["type"] == "combat" and v["phase"]["waiting_on"]:
                a.post(f"/api/games/{gid}/force-resolve")
            time.sleep(0.15)
        v = wait_phase(a, gid, {"exploration"}, timeout=15)
        assert any("Victory" in l["text"] or "defeated" in l["text"] for l in v["log"]), [l["text"] for l in v["log"][-10:]]

        # single input mode + TV link
        r = a.patch(f"/api/games/{gid}/settings", json={"input_mode": "single", "live": True})
        assert r.status_code == 200, r.text
        v = a.get(f"/api/games/{gid}/view").json()
        assert v["me"]["is_speaker"] and len(v["me"]["controls"]) == 2
        assert b.post(f"/api/games/{gid}/action", json={"text": "hi"}).status_code == 400
        tv = a.post(f"/api/games/{gid}/tv-link").json()
        tvv = TestClient(app).get(f"/api/tv/{tv['tv_token']}/view")
        assert tvv.status_code == 200 and tvv.json()["me"]["user_id"] is None


BARB = {"name": "Grukk", "race": "half-orc", "class": "barbarian", "background": "outlander",
        "ability_method": "standard", "abilities": {"STR": 15, "DEX": 13, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10},
        "skills": ["Intimidation", "Perception"], "equipment_option": "reaver"}


def test_m2_loop():
    with TestClient(app):
        a = client_for("carol")
        b = client_for("dave")
        ca = a.post("/api/characters", json=BARB)
        assert ca.status_code == 200, ca.text
        cb = b.post("/api/characters", json={**WIZARD, "name": "Mira"})
        assert cb.status_code == 200, cb.text
        assert a.post(f"/api/characters/{ca.json()['id']}/level-up", json={"hp_method": "average"}).status_code == 400
        g = a.post("/api/games", json={"name": "M2 Run", "character_id": ca.json()["id"],
                                       "settings": {"starting_level": 5, "round_timer_minutes": 60}}).json()
        gid = g["id"]
        code = a.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]
        b.post("/api/games/join", json={"invite_code": code, "character_id": cb.json()["id"]})
        assert a.post(f"/api/games/{gid}/start").status_code == 200
        v = wait_phase(a, gid, {"exploration"})
        chars = v["characters"]
        barb = chars[ca.json()["id"]]
        wiz = chars[cb.json()["id"]]
        assert barb["level"] == 5 and wiz["level"] == 5
        assert any(x["id"] == "rage" for x in barb["actions"])
        assert wiz["spellcasting"]["max_spell_level"] == 3 and wiz["spellcasting"]["spellbook"]
        # prepare spells (wizard picks from the spellbook)
        book = [s["index"] for s in wiz["spellcasting"]["options"]]
        mx = wiz["spellcasting"]["prepared_max"]
        r = b.post(f"/api/games/{gid}/prepare", json={"spells": book[:mx]})
        assert r.status_code == 200, r.text
        # rest vote: both vote a long rest in town
        a.post(f"/api/games/{gid}/action", json={"text": "", "rest": "long"})
        b.post(f"/api/games/{gid}/action", json={"text": "", "rest": "long"})
        v = wait_phase(a, gid, {"exploration"})
        assert any("long rest" in l["text"] for l in v["log"])
        # shop with haggling
        a.post(f"/api/games/{gid}/action", json={"text": "We visit the market to shop"})
        b.post(f"/api/games/{gid}/action", json={"text": "me too"})
        v = wait_phase(a, gid, {"shop"})
        r = a.post(f"/api/games/{gid}/shop/haggle", json={})
        assert r.status_code == 200, r.text
        assert a.post(f"/api/games/{gid}/shop/haggle", json={}).status_code == 400
        v = a.get(f"/api/games/{gid}/view").json()
        assert ca.json()["id"] in v["shop"]["discounts"]
        a.post(f"/api/games/{gid}/ready", json={"ready": True})
        b.post(f"/api/games/{gid}/ready", json={"ready": True})
        wait_phase(a, gid, {"exploration"})
        # combat with features and an area spell
        a.post(f"/api/games/{gid}/action", json={"text": "We attack the orcs in the dungeon"})
        b.post(f"/api/games/{gid}/action", json={"text": "attack"})
        v = wait_phase(a, gid, {"combat"})
        assert v["encounter"]["terrain"] == "dungeon"
        if v["encounter"]["my_turn"]:
            r = a.post(f"/api/games/{gid}/combat/feature", json={"feature_id": "rage"})
            assert r.status_code == 200, r.text
        vb = b.get(f"/api/games/{gid}/view").json()
        e = vb["encounter"]
        if e and e["my_turn"] and e["point_spells"]:
            mon = next(t for t in e["tokens"] if t["kind"] == "monster")
            ps = e["point_spells"][0]
            b.post(f"/api/games/{gid}/combat/cast", json={"spell_index": ps["spell_index"], "x": mon["x"], "y": mon["y"]})
        for _ in range(80):
            v = a.get(f"/api/games/{gid}/view").json()
            if v["phase"]["type"] == "exploration" and not v["encounter"]:
                break
            if v["phase"]["type"] == "combat" and not v["dm"]["busy"]:
                a.post(f"/api/games/{gid}/force-resolve")
            time.sleep(0.15)
        v = wait_phase(a, gid, {"exploration"}, timeout=20)
        assert any(("Victory" in l["text"]) or ("defeated" in l["text"]) for l in v["log"])
