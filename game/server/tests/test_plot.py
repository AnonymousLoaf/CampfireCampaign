"""Campaign plots: a host-written story outline in My content that the host picks for a game; DM-only."""
import os
import tempfile

if "GAME_DATA_DIR" not in os.environ:
    os.environ["GAME_DATA_DIR"] = tempfile.mkdtemp(prefix="dndgame-plot-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.dm import prompt  # noqa: E402
from app.game import plot  # noqa: E402
from app.game.state import load  # noqa: E402
from app.main import app  # noqa: E402

from .test_chat import _character, _client  # noqa: E402

PLOT = {"kind": "plot", "name": "The Drowned Bell", "description": "Keep it spooky.",
        "data": {"premise": "A sunken temple bell rings at night and the townsfolk sleepwalk into the lake.",
                 "opening": "A child walks into the lake at dawn.",
                 "villain": "Mother Silt, a hag bound to the bell",
                 "acts": "Investigate the town\nFind the temple\n\nBreak the bell",
                 "secrets": ["The mayor made the pact"], "twists": ["Mother Silt is the mayor's sister"],
                 "npcs": [{"name": "Mayor Orrin", "role": "nervous mayor", "secret": "made the pact"}, {"role": "nameless"}],
                 "ending": "Ring the bell backwards at the solstice."}}


def test_clean_requires_premise_and_normalises():
    with pytest.raises(ValueError):
        plot.clean({"villain": "someone"})
    d = plot.clean(PLOT["data"])
    assert d["acts"] == ["Investigate the town", "Find the temple", "Break the bell"]
    assert d["npcs"] == [{"name": "Mayor Orrin", "role": "nervous mayor", "secret": "made the pact"}]
    block = plot.prompt_block(plot.snapshot({"id": "x", "name": "The Drowned Bell", "description": "n", "data": d}))
    assert "SECRET" in block and "Mayor Orrin" in block and "2. Find the temple" in block


def test_host_picks_plot_and_only_dm_and_host_see_it():
    with TestClient(app):
        host, player = _client("plothost"), _client("plotplayer")
        assert host.post("/api/custom", json={**PLOT, "data": {"villain": "x"}}).status_code == 400
        eid = host.post("/api/custom", json=PLOT).json()["id"]
        pid = player.post("/api/custom", json=PLOT).json()["id"]
        cid = _character(host, "Ash")
        # plots can't go on a character, and you can only pick your own
        assert host.post(f"/api/characters/{cid}/custom", json={"entry_id": eid}).status_code == 400
        assert host.post("/api/games", json={"name": "P", "character_id": cid, "plot_id": pid,
                                             "settings": {"ruleset": "2024"}}).status_code == 400
        gid = host.post("/api/games", json={"name": "P", "character_id": cid, "plot_id": eid,
                                            "settings": {"ruleset": "2024"}}).json()["id"]

        hv = host.get(f"/api/games/{gid}/view").json()
        assert hv["plot"] == {"name": "The Drowned Bell", "entry_id": eid} and hv["has_plot"]
        code = hv["game"]["invite_code"]
        assert player.post("/api/games/join", json={"invite_code": code,
                                                    "character_id": _character(player, "Bryn")}).status_code == 200
        pv = player.get(f"/api/games/{gid}/view")
        assert pv.json()["plot"] is None and pv.json()["has_plot"] and "Mother Silt" not in pv.text

        # the snapshot doesn't follow later library edits; the DM prompt has it
        host.put(f"/api/custom/{eid}", json={**PLOT, "name": "Renamed"})
        db = SessionLocal()
        try:
            sp = prompt.system_prompt(load(db, gid))
        finally:
            db.close()
        assert "The Drowned Bell" in sp and "Mother Silt" in sp and "Keep it spooky." in sp

        # only the host changes it, only in the lobby
        assert player.put(f"/api/games/{gid}/plot", json={"entry_id": None}).status_code == 400
        assert host.put(f"/api/games/{gid}/plot", json={"entry_id": None}).status_code == 200
        assert host.get(f"/api/games/{gid}/view").json()["plot"] is None
        assert host.put(f"/api/games/{gid}/plot", json={"entry_id": eid}).status_code == 200
        assert host.get(f"/api/games/{gid}/view").json()["plot"]["name"] == "Renamed"


def test_spotlight_labels_the_round_but_still_asks_everyone():
    from app.dm.tools import ToolBox
    with TestClient(app):
        host, player = _client("spothost"), _client("spotplayer")
        gid = host.post("/api/games", json={"name": "S", "character_id": _character(host, "Ash"),
                                            "settings": {"ruleset": "2024"}}).json()["id"]
        code = host.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]
        player.post("/api/games/join", json={"invite_code": code, "character_id": _character(player, "Bryn")})
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            ctx.game.status = "active"
            ctx.open_phase("exploration", "Bryn, now or never.")
            tb = ToolBox(ctx)
            assert "Bryn" in tb.call("spotlight", {"characters": ["bryn"]})
            ctx.phase["spotlight"] = tb.spotlight
            assert len(ctx.waiting_on()) == 2  # everyone is still asked
            ctx.save()
            db.commit()
        finally:
            db.close()
        hv = host.get(f"/api/games/{gid}/view").json()
        assert hv["phase"]["their_call"] == ["Bryn"]
        assert player.get(f"/api/games/{gid}/view").json()["phase"]["their_call"] == []
        hg = next(g for g in host.get("/api/games").json() if g["id"] == gid)
        assert hg["my_turn"] and hg["their_call"] == ["Bryn"]
        pg = next(g for g in player.get("/api/games").json() if g["id"] == gid)
        assert pg["my_turn"] and pg["their_call"] == []


def test_ready_made_plots_can_be_picked(client=None):
    """Every ready-made plot is valid, and a host can start a game with one."""
    from app.game import plot, plot_presets

    ids = [p["id"] for p in plot_presets.listing()]
    assert len(ids) >= 6 and len(set(ids)) == len(ids)
    for pid in ids:
        snap = plot.snapshot(plot_presets.entry(pid))
        assert snap["premise"] and snap["entry_id"] == pid
    assert plot_presets.entry("preset:nope") is None
