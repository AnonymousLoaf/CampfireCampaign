"""Typed travel (the DM moves the party by place or direction), and leaving, removing and deleting games."""
import time

from fastapi.testclient import TestClient

from app.main import app
from app.world import hexmap
from tests.test_flow import FIGHTER, WIZARD, client_for, wait_phase


def test_hex_toward_heads_the_right_way_and_lands_on_reachable_ground():
    w = hexmap.generate(7)
    start = (w["party"]["q"], w["party"]["r"])
    sx, sy = hexmap._pixel(*start)
    for d, (dx, dy) in hexmap.DIRECTIONS.items():
        dest = hexmap.hex_toward(w, d, 4)
        if dest is None:
            continue
        x, y = hexmap._pixel(*dest)
        assert (x - sx) * dx + (y - sy) * dy > 0, (d, start, dest)  # moved roughly that way
        assert hexmap.BIOME_COST[w["hexes"][dest[1]][dest[0]]] is not None
        assert hexmap.plan_travel(w, dest)["ok"]
    assert hexmap.hex_toward(w, "northeast", 4) == hexmap.hex_toward(w, "ne", 4)
    assert hexmap.hex_toward(w, "sideways", 4) is None


def test_typed_travel_moves_the_party_and_map_clicks_are_not_needed():
    with TestClient(app):
        a = client_for("tr_alice")
        ca = a.post("/api/characters", json={**FIGHTER, "name": "Rook"}).json()
        gid = a.post("/api/games", json={"name": "Roads", "character_id": ca["id"],
                                         "settings": {"round_timer_minutes": 60}}).json()["id"]
        a.post(f"/api/games/{gid}/start")
        v = wait_phase(a, gid, {"exploration"})
        here = dict(v["world"]["party"])
        # pick a direction with somewhere to go (the offline DM calls travel with a direction)
        from app.db import SessionLocal
        from app.models import Game
        db = SessionLocal()
        world = db.get(Game, gid).world
        db.close()
        way = next(d for d in ("east", "west", "north", "south") if hexmap.hex_toward(world, d, 4))
        r = a.post(f"/api/games/{gid}/action", json={"text": f"We head {way} along the road"})
        assert r.status_code == 200, r.text
        before = v["phase"]["id"]
        for _ in range(100):
            v = a.get(f"/api/games/{gid}/view").json()
            if v["phase"]["type"] == "exploration" and v["phase"]["id"] != before and not v["dm"]["busy"]:
                break
            time.sleep(0.1)
        assert v["world"]["party"] != here, "\n".join(l["text"][:160] for l in v["log"][-6:])
        assert any("travels to" in l["text"] for l in v["log"])


def test_story_so_far_is_a_cached_summary():
    with TestClient(app):
        a = client_for("st_alice")
        ca = a.post("/api/characters", json={**FIGHTER, "name": "Wren"}).json()
        gid = a.post("/api/games", json={"name": "Tales", "character_id": ca["id"],
                                         "settings": {"round_timer_minutes": 60}}).json()["id"]
        a.post(f"/api/games/{gid}/start")
        wait_phase(a, gid, {"exploration"})
        first = a.post(f"/api/games/{gid}/story").json()
        assert first["text"] and first["upto_id"] > 0 and first["updated_at"]
        # nothing new since: the same write-up comes back without asking the DM again
        assert a.post(f"/api/games/{gid}/story").json() == first
        assert client_for("st_bob").post(f"/api/games/{gid}/story").status_code == 403


def test_leave_remove_and_delete():
    with TestClient(app):
        host = client_for("hm_host")
        p1 = client_for("hm_p1")
        p2 = client_for("hm_p2")
        ch = host.post("/api/characters", json={**FIGHTER, "name": "Hale"}).json()
        c1 = p1.post("/api/characters", json={**WIZARD, "name": "Ivo"}).json()
        c2 = p2.post("/api/characters", json={**FIGHTER, "name": "Juno"}).json()
        gid = host.post("/api/games", json={"name": "Doomed", "character_id": ch["id"],
                                            "settings": {"round_timer_minutes": 60}}).json()["id"]
        code = host.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]
        p1.post("/api/games/join", json={"invite_code": code, "character_id": c1["id"]})
        p2.post("/api/games/join", json={"invite_code": code, "character_id": c2["id"]})
        host.post(f"/api/games/{gid}/start")
        wait_phase(host, gid, {"exploration"})

        # the host can't leave; a player can, mid-campaign, and their character is free again
        assert host.post(f"/api/games/{gid}/leave").status_code == 400
        assert p1.post(f"/api/games/{gid}/leave").status_code == 200
        assert not [g for g in p1.get("/api/games").json() if g["id"] == gid]
        assert next(c for c in p1.get("/api/characters").json() if c["id"] == c1["id"])["game_id"] is None
        assert p1.get(f"/api/games/{gid}/view").status_code == 403

        # only the host removes players
        p2_uid = p2.get("/api/me").json()["id"]
        host_uid = host.get("/api/me").json()["id"]
        assert p2.post(f"/api/games/{gid}/remove-player", json={"user_id": host_uid}).status_code == 400
        assert host.post(f"/api/games/{gid}/remove-player", json={"user_id": p2_uid}).status_code == 200
        v = host.get(f"/api/games/{gid}/view").json()
        assert [m["user_id"] for m in v["members"]] == [host_uid]
        assert any("has left the party" in l["text"] for l in v["log"])
        assert p2.delete(f"/api/characters/{c2['id']}").status_code == 200  # free, so deletable

        # delete: host only; the game is gone, the host's character survives
        assert p1.delete(f"/api/games/{gid}").status_code == 403
        assert host.delete(f"/api/games/{gid}").status_code == 200
        assert host.get(f"/api/games/{gid}/view").status_code == 404
        assert not [g for g in host.get("/api/games").json() if g["id"] == gid]
        assert next(c for c in host.get("/api/characters").json() if c["id"] == ch["id"])["game_id"] is None
