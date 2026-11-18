"""Prepared spells change on a long rest; the party journal and notes; campaign stats and the epilogue."""
import os
import tempfile

if "GAME_DATA_DIR" not in os.environ:
    os.environ["GAME_DATA_DIR"] = tempfile.mkdtemp(prefix="dndgame-journal-")

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.dm.tools import ToolBox  # noqa: E402
from app.game.state import load  # noqa: E402
from app.main import app  # noqa: E402
from app.rules import character as ch  # noqa: E402

from .test_chat import _character, _client  # noqa: E402
from .test_flow import wait_phase  # noqa: E402
from .test_m2 import build  # noqa: E402


def test_prepared_spells_open_after_long_rest_and_lock_on_cast():
    s = build("cleric", 3)
    assert ch.can_change_prepared(s)  # new to the game: free to set up
    ch.use_slot(s, 1)
    assert not ch.can_change_prepared(s)
    ch.long_rest(s)
    assert ch.can_change_prepared(s)
    assert not ch.can_change_prepared(build("sorcerer", 3))  # knows a fixed list


def _game(host, player=None):
    gid = host.post("/api/games", json={"name": "J", "character_id": _character(host, "Ash"),
                                        "settings": {"ruleset": "2024", "round_timer_minutes": 60}}).json()["id"]
    if player:
        code = host.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]
        assert player.post("/api/games/join", json={"invite_code": code,
                                                    "character_id": _character(player, "Bryn")}).status_code == 200
    assert host.post(f"/api/games/{gid}/start").status_code == 200
    wait_phase(host, gid, {"exploration"})
    return gid


def test_journal_notes_stats_and_epilogue():
    with TestClient(app):
        host, player = _client("jhost"), _client("jplayer")
        gid = _game(host, player)

        # the DM writes in the journal and marks the story complete; stats come from combat lines
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            tb = ToolBox(ctx)
            assert tb.call("journal", {"kind": "clue", "text": "The bell rings only at low tide."}) == "ok"
            assert tb.call("journal", {"kind": "clue", "text": "The bell rings only at low tide."}) == "already in the journal"
            tb.call("upsert_quest", {"title": "Silence the bell"})
            tb.call("upsert_quest", {"title": "Silence the bell", "status": "done"})
            tb.call("story_complete", {"note": "The bell was broken."})
            cid = next(iter(ctx.chars))
            ctx.state["encounter"] = {"tokens": {
                "p": {"id": "p", "kind": "pc", "character_id": cid},
                "g": {"id": "g", "kind": "monster", "hp": 0}}}
            ctx.log("combat", "Ash hits the goblin", data={"attacker": "p", "target": "g", "hit": True, "crit": True,
                                                          "roll": {"natural": 20}, "damage": 9})
            ctx.log("combat", "again", data={"attacker": "p", "target": "g", "hit": True, "damage": 2})
            st = ctx.state["stats"][cid]
            assert st == {"attacks": 2, "hits": 2, "crits": 1, "nat20": 1, "damage_dealt": 11, "kills": 1}
            ctx.state.pop("encounter")
            ctx.save()
        finally:
            db.close()

        v = player.get(f"/api/games/{gid}/view").json()
        assert any(e["kind"] == "clue" for e in v["journal"]) and v["story_complete"]
        q = next(q for q in v["quests"] if q["title"] == "Silence the bell")
        assert q["status"] == "done" and "ended_day" in q

        # players' notes: anyone writes, only the writer or the host removes
        assert player.post(f"/api/games/{gid}/notes", json={"text": "Ask the ferryman about the tides"}).status_code == 200
        nid = player.get(f"/api/games/{gid}/view").json()["party_notes"][0]["id"]
        assert host.delete(f"/api/games/{gid}/notes/{nid}").status_code == 200
        assert player.get(f"/api/games/{gid}/view").json()["party_notes"] == []

        # only the host ends it; the epilogue keeps the stats
        assert player.post(f"/api/games/{gid}/end").status_code == 400
        assert host.post(f"/api/games/{gid}/end").status_code == 200
        v = wait_phase(host, gid, {"ended"})
        ep = v["epilogue"]
        assert ep["status"] == "done" and ep["text"] and ep["stats"][cid]["kills"] == 1
        assert ep["party"]["quests_done"] >= 1 and v["game"]["status"] == "ended"
        assert any(l["kind"] == "narration" and (l["data"] or {}).get("epilogue") for l in v["log"])
        assert host.post(f"/api/games/{gid}/end").status_code == 400  # already over
