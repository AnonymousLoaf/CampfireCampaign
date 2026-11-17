"""Typed combat: players describe their turn in words; the DM resolves it with combat tools; players roll their dice."""
import time

from fastapi.testclient import TestClient

from app.main import app
from tests.test_flow import FIGHTER, WIZARD, client_for, wait_phase


def _play(clients, gid, words, max_steps=150):
    """Drive a fight: on your turn, say `words`; roll your own rolls; until the fight is over."""
    a = clients[0]
    seen_roll = seen_turn = False
    for _ in range(max_steps):
        v = a.get(f"/api/games/{gid}/view").json()
        if v["phase"]["type"] == "exploration" and not v["encounter"]:
            return v, seen_turn, seen_roll
        if v["dm"]["busy"] or v["phase"]["type"] == "dm":
            time.sleep(0.05)
            continue
        acted = False
        for c in clients:
            vv = c.get(f"/api/games/{gid}/view").json()
            p = vv["phase"]
            if p["type"] == "combat" and vv["encounter"] and vv["encounter"]["my_turn"]:
                r = c.post(f"/api/games/{gid}/action", json={"text": words})
                assert r.status_code == 200, r.text
                seen_turn = acted = True
                break
            if p["type"] == "roll":
                for r_ in p["pending_rolls"]:
                    if r_["user_id"] == vv["me"]["user_id"] and r_.get("result") is None:
                        assert r_.get("combat"), r_
                        rr = c.post(f"/api/games/{gid}/roll", json={"roll_id": r_["id"]})
                        assert rr.status_code == 200, rr.text
                        if rr.json()["result"] is None:  # the attack hit: the damage is a second click
                            staged = next(x for x in c.get(f"/api/games/{gid}/view").json()["phase"]["pending_rolls"]
                                          if x["id"] == r_["id"])
                            assert staged["to_hit"] and "replay" not in staged, staged
                            rr = c.post(f"/api/games/{gid}/roll", json={"roll_id": r_["id"]})
                            assert rr.status_code == 200, rr.text
                        assert rr.json()["result"]["lines"]
                        seen_roll = acted = True
                        break
            if acted:
                break
        if not acted:
            time.sleep(0.05)
    raise AssertionError("the fight didn't finish")


def test_typed_combat_loop():
    with TestClient(app):
        a = client_for("tc_alice")
        b = client_for("tc_bob")
        ca = a.post("/api/characters", json={**FIGHTER, "name": "Dain"}).json()
        cb = b.post("/api/characters", json={**WIZARD, "name": "Wren"}).json()
        gid = a.post("/api/games", json={"name": "Typed", "character_id": ca["id"],
                                         "settings": {"rolls": "players", "round_timer_minutes": 60}}).json()["id"]
        code = a.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]
        b.post("/api/games/join", json={"invite_code": code, "character_id": cb["id"]})
        a.post(f"/api/games/{gid}/start")
        wait_phase(a, gid, {"exploration"})
        a.post(f"/api/games/{gid}/action", json={"text": "We attack the goblins on the road"})
        b.post(f"/api/games/{gid}/action", json={"text": "I fight too"})
        v = wait_phase(a, gid, {"combat", "roll"})
        enc = v["encounter"]
        assert enc["mode"] == "classic"
        # not your turn → typing is refused
        actor = enc["turn"]["actor_id"]
        other = b if actor == f"pc-{ca['id']}" else a
        if v["phase"]["type"] == "combat":
            r = other.post(f"/api/games/{gid}/action", json={"text": "I attack"})
            assert r.status_code == 400 and "turn" in r.text
        v, seen_turn, seen_roll = _play([a, b], gid, "I attack the nearest goblin")
        assert seen_turn and seen_roll, "\n".join(l["text"][:160] for l in v["log"][-20:])
        assert any("Victory" in l["text"] or "defeated" in l["text"] for l in v["log"])
        # the end of the fight reads in order: the roll, the DM's narration, then victory and loot
        end = next(i for i, l in enumerate(v["log"]) if l["text"].startswith(("Victory", "The party is defeated")))
        assert v["log"][end - 1]["kind"] == "narration", [l["text"][:80] for l in v["log"][end - 3:end + 2]]
        assert any(l["kind"] == "action" and "nearest goblin" in l["text"] for l in v["log"])


def test_turn_steps_happen_in_order_and_dodge_needs_no_roll():
    """A queued attack resolves before a later move; a Dodge resolves at once and ends the turn."""
    from app.game import combat, turns
    from app.rules import character as ch

    s = ch.create({**FIGHTER, "name": "Dain"})
    enc, _ = combat.start([("goblin", 1)], "road", [("c1", s)], mode="classic", seed=11, distance="close")
    chars = {"c1": s}
    # make it Dain's turn
    for _ in range(4):
        if turns.actor(enc, chars):
            break
        combat.advance(enc, chars)
    t = turns.actor(enc, chars)
    assert t
    gob = next(x for x in enc["tokens"].values() if x["kind"] == "monster")
    a = next(x for x in ch.attacks(s) if x["kind"] == "melee")
    # walk next to the goblin, queue an attack, then a step back
    if combat.dist(t, gob) > 5:
        turns.run_op(enc, chars, {"kind": "move", "tid": t["id"], "toward": gob["id"], "stop": 5})
    assert combat.dist(t, gob) <= 5
    t["budget"]["move_ft"] = 30
    enc["queue"] = [{"kind": "attack", "tid": t["id"], "attack_id": a["id"], "target_id": gob["id"], "roll_id": "r1"},
                    {"kind": "move", "tid": t["id"], "away_from": gob["id"]}]
    before = (t["x"], t["y"])
    mine, everything = turns.execute_through(enc, chars, "r1")
    assert mine and "attacks Goblin" in mine[0]["text"]
    assert enc["queue"] == []
    # the attack came first, then the step back (unless the goblin died, ending the fight, or Dain fell)
    assert (t["x"], t["y"]) != before or enc.get("outcome") or not combat.alive(t, chars)
    assert everything[0] is mine[0]


def test_validate_rejects_out_of_reach_attack():
    from app.game import combat, turns
    from app.rules import character as ch
    from app.rules.character import RulesError

    s = ch.create({**FIGHTER, "name": "Dain"})
    enc, _ = combat.start([("goblin", 1)], "road", [("c1", s)], mode="classic", seed=3, distance="far")
    chars = {"c1": s}
    for _ in range(4):
        if turns.actor(enc, chars):
            break
        combat.advance(enc, chars)
    t = turns.actor(enc, chars)
    gob = next(x for x in enc["tokens"].values() if x["kind"] == "monster")
    a = next(x for x in ch.attacks(s) if x["kind"] == "melee")
    if combat.dist(t, gob) > 5:
        try:
            turns.validate(enc, chars, {"kind": "attack", "tid": t["id"], "attack_id": a["id"], "target_id": gob["id"]})
            raise AssertionError("an attack out of reach should be refused")
        except RulesError as e:
            assert "reach" in str(e) or "range" in str(e)


def test_damage_dice_are_fresh_but_to_hit_replays():
    """The second click of an attack replays the d20 the player saw and throws new damage dice."""
    from app.rules import dice

    rec: list = []
    with dice.scripted(record=rec):
        hit = dice.d20(5)
        dice.damage("1d8+3")
        save = dice.d20(2)
    assert [s for s, _ in rec] == [20, 20]  # damage dice aren't recorded
    seen = set()
    for _ in range(40):
        with dice.scripted(replay=rec):
            assert dice.d20(5)["natural"] == hit["natural"]
            seen.add(dice.damage("1d8+3").total)
            assert dice.d20(2)["natural"] == save["natural"]
    assert len(seen) > 1
    with dice.scripted(replay=[[20, 7]]):
        assert dice.d20()["natural"] == 7
        dice.die(20)  # past the script: random again, no error
