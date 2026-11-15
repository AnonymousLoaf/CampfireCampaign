"""M3: 2024 rules, levels 6-10, masteries, feats; notifications, vacation, spectators, history."""
import os
import tempfile
import time

import pytest

if "GAME_DATA_DIR" not in os.environ:
    os.environ["GAME_DATA_DIR"] = tempfile.mkdtemp(prefix="dndgame-m3-")
os.environ.setdefault("GAME_TICK_SECONDS", "0.2")

from fastapi.testclient import TestClient  # noqa: E402

from app.game import combat  # noqa: E402
from app.main import app  # noqa: E402
from app.rules import character as ch  # noqa: E402
from app.rules import dice, srd  # noqa: E402
from app.rules.rulesets import R  # noqa: E402

CLASSES = list(R("2024").CLASSES)


def build(cls: str, ruleset: str = "2024", level: int = 1, **kw) -> dict:
    opts = ch.creator_options(ruleset)
    c = next(x for x in opts["classes"] if x["index"] == cls)
    bg = opts["backgrounds"][0]
    skills = [s for s in c["skill_choices"]["options"] if s not in bg["skills"]][: c["skill_choices"]["count"]]
    prim = R(ruleset).CLASSES[cls]["primary"][0]
    order = [prim] + [a for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA") if a != prim]
    payload = {"ruleset": ruleset, "name": f"{cls}-{ruleset}", "class": cls, "background": bg["index"],
               "ability_method": "standard", "abilities": dict(zip(order, [15, 14, 13, 12, 10, 8])),
               "skills": skills, "equipment_option": c["equipment_options"][0]["id"]}
    race = opts["races"][0]
    payload["race"] = race["index"]
    if race["subraces"]:
        payload["subrace"] = race["subraces"][0]["index"]
    if ruleset == "2024":
        ao = bg["ability_options"]
        payload["background_asi"] = {ao[0]: 2, ao[1]: 1}
        if c["weapon_mastery"]:
            payload["masteries"] = [o["weapon_key"] for o in c["mastery_options"]][: c["weapon_mastery"]]
    if c["fighting_styles"]:
        payload["fighting_style"] = "Defense"
    sc = c["spellcasting"]
    if sc:
        payload["cantrips"] = [x["index"] for x in sc["cantrips"]][: sc["cantrips_known"]]
        payload["spells"] = [x["index"] for x in sc["spells"]][: sc["spells_at_l1"]]
    payload.update(kw)
    return ch.create(payload, starting_level=level)


def setup_module():
    dice.set_seed(2024)


@pytest.mark.parametrize("cls", CLASSES)
def test_2024_every_class_to_10(cls):
    s = build(cls, "2024", 10)
    v = ch.view("x", "u", None, s)
    assert v["ruleset"] == "2024" and v["level"] == 10
    assert v["subclass"], cls
    assert v["feats"], "origin feat from the background"
    if R("2024").CLASSES[cls].get("spellcasting"):
        assert v["spellcasting"]["max_spell_level"] >= 3
        assert v["spellcasting"]["prepares"]


@pytest.mark.parametrize("cls", CLASSES)
def test_2014_every_class_to_10(cls):
    s = build(cls, "2014", 10)
    v = ch.view("x", "u", None, s)
    assert v["level"] == 10 and v["hp_max"] > 40
    if R("2014").CLASSES[cls].get("spellcasting") and R("2014").CLASSES[cls]["spellcasting"]["type"] == "full":
        assert v["spellcasting"]["max_spell_level"] == 5


def test_2024_background_asi_and_masteries():
    s = build("fighter", "2024", 1, masteries=[])  # empty → filled from the starting weapons
    assert s["background_asi"] and s["masteries"]
    v = ch.view("x", "u", None, s)
    assert any(a.get("mastery") for a in v["attacks"]) or not s["masteries"]
    with pytest.raises(ch.RulesError):
        build("fighter", "2024", 1, background_asi={"STR": 3})


def test_feat_instead_of_asi():
    s = build("fighter", "2024", 3)
    ch.award_xp(s, 2700)
    offer = ch.level_offer(s)
    assert offer["asi"]
    if offer["feat_options"]:
        feat = offer["feat_options"][0]["name"]
        ch.level_up(s, {"hp_method": "average", "feat": feat})
        assert feat in s["feats"]


def test_2024_monsters_parse():
    gob = srd.find_monster("goblin", "2024")
    assert gob and gob["_rules"] == "2024"
    acts = srd.monster_actions(gob)
    assert acts and all(a["to_hit"] >= 2 for a in acts)
    assert any(a["ranged"] for a in acts)
    bear = srd.find_monster("Brown Bear", "2024")
    assert srd.monster_multiattack(bear) == 2


def test_2024_fight_soak():
    for seed in range(8):
        dice.set_seed(seed)
        party = [(c, build(c, "2024", 5)) for c in ("fighter", "wizard", "cleric", "rogue")]
        chars = dict(party)
        enc, _ = combat.start([("goblin-warrior", 3), ("wolf", 2)], "forest", party, "side", seed=seed, ruleset="2024")
        for _ in range(300):
            if combat.check_end(enc, chars):
                break
            moved = False
            for cid in chars:
                if combat.can_act(enc, f"pc-{cid}", chars):
                    combat.auto_turn(enc, chars, f"pc-{cid}", "ai")
                    combat.advance(enc, chars)
                    moved = True
            if not moved:
                combat.advance(enc, chars)
        assert combat.check_end(enc, chars) in ("victory", "defeat")


def _client(name):
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"username": name, "password": "secret123", "display_name": name.title()})
    assert r.status_code == 200, r.text
    return c


def _wait(c, gid, types, timeout=12):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = c.get(f"/api/games/{gid}/view").json()
        if v["phase"]["type"] in types and not v["dm"]["busy"]:
            return v
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {types}: {v['phase']}")


def test_m3_api_flow():
    with TestClient(app):
        a, b, watcher = _client("m3host"), _client("m3player"), _client("m3watch")
        assert a.get("/api/rules/creator?ruleset=2024").status_code == 200
        # notifications settings + push subscription bookkeeping
        r = a.put("/api/me/notifications", json={"email": "host@example.com", "notify_email": True, "remind_minutes": 30})
        assert r.status_code == 200 and r.json()["notify"]["remind_minutes"] == 30
        assert len(a.get("/api/push/key").json()["public_key"]) > 40
        sub = {"endpoint": "https://push.example.invalid/abc", "keys": {"p256dh": "x" * 20, "auth": "y" * 10}}
        assert a.post("/api/push/subscribe", json={"subscription": sub}).status_code == 200
        assert a.request("DELETE", "/api/push/subscribe", json={"endpoint": sub["endpoint"]}).status_code == 200
        # 2024 characters and game
        opts = a.get("/api/rules/creator?ruleset=2024").json()
        fighter = next(x for x in opts["classes"] if x["index"] == "fighter")
        bg = opts["backgrounds"][0]
        race = opts["races"][0]

        def payload(name):
            p = {"ruleset": "2024", "name": name, "race": race["index"], "class": "fighter", "background": bg["index"],
                 "ability_method": "standard", "abilities": {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8},
                 "skills": [s for s in fighter["skill_choices"]["options"] if s not in bg["skills"]][:2],
                 "equipment_option": fighter["equipment_options"][0]["id"], "fighting_style": "Defense",
                 "background_asi": {bg["ability_options"][0]: 2, bg["ability_options"][1]: 1}}
            if race["subraces"]:
                p["subrace"] = race["subraces"][0]["index"]
            return p
        ca = a.post("/api/characters", json=payload("Vex Ironside"))
        assert ca.status_code == 200, ca.text
        cb = b.post("/api/characters", json=payload("Tamsin Reed"))
        assert cb.status_code == 200, cb.text
        r = a.post("/api/games", json={"name": "M3", "character_id": ca.json()["id"], "settings": {"ruleset": "2014"}})
        assert r.status_code == 400  # ruleset mismatch
        gid = a.post("/api/games", json={"name": "M3", "character_id": ca.json()["id"],
                                         "settings": {"ruleset": "2024", "starting_level": 6}}).json()["id"]
        code = a.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]
        assert b.post("/api/games/join", json={"invite_code": code, "character_id": cb.json()["id"]}).status_code == 200
        assert watcher.post("/api/games/join", json={"invite_code": code, "spectate": True}).status_code == 200
        assert a.post(f"/api/games/{gid}/start").status_code == 200
        v = _wait(a, gid, {"exploration"})
        assert all(c["level"] == 6 for c in v["characters"].values())
        wv = watcher.get(f"/api/games/{gid}/view").json()
        assert wv["me"]["role"] == "spectator" and not wv["me"]["controls"]
        assert watcher.post(f"/api/games/{gid}/action", json={"text": "hi"}).status_code == 400
        # vacation: b goes away → the round resolves with only a's action
        assert b.post(f"/api/games/{gid}/away", json={"until": "indefinite"}).status_code == 200
        v = a.get(f"/api/games/{gid}/view").json()
        assert v["phase"]["waiting_on"] == [v["me"]["user_id"]]
        a.post(f"/api/games/{gid}/action", json={"text": "I look around"})
        a.post(f"/api/games/{gid}/action", json={"text": "I look around carefully"})  # edit
        v = _wait(a, gid, {"exploration", "roll"})
        # combat with an away player: the AI plays them
        if v["phase"]["type"] == "roll":
            for r_ in v["phase"]["pending_rolls"]:
                if r_["user_id"] == v["me"]["user_id"]:
                    a.post(f"/api/games/{gid}/roll", json={"roll_id": r_["id"]})
            v = _wait(a, gid, {"exploration"})
        a.post(f"/api/games/{gid}/action", json={"text": "We attack the bandits on the road"})
        v = _wait(a, gid, {"combat"})
        for _ in range(80):
            v = a.get(f"/api/games/{gid}/view").json()
            if v["phase"]["type"] == "exploration" and not v["encounter"]:
                break
            if v["phase"]["type"] == "combat" and not v["dm"]["busy"]:
                a.post(f"/api/games/{gid}/force-resolve")
            time.sleep(0.15)
        v = _wait(a, gid, {"exploration"}, timeout=20)
        assert any("DM plays Tamsin" in l["text"] for l in v["log"]) or any("Victory" in l["text"] for l in v["log"])
        # history, seen and recap
        page = a.get(f"/api/games/{gid}/log?limit=5&kinds=narration,event").json()
        assert page["entries"] and "has_more" in page
        assert v["me"]["unseen_count"] > 0
        newest = v["log"][-1]["id"]
        assert a.post(f"/api/games/{gid}/seen", json={"log_id": newest}).status_code == 200
        assert a.get(f"/api/games/{gid}/view").json()["me"]["unseen_count"] == 0
        rec = b.post(f"/api/games/{gid}/recap")
        assert rec.status_code == 200 and rec.json()["text"]
        assert b.post(f"/api/games/{gid}/away", json={"until": None}).status_code == 200
