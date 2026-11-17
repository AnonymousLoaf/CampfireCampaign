"""Scene maps: the DM's local map outside combat, with fog of war."""
import pytest

from app.world import scenemap

# A fork: the party stands at the bottom; the left and right passages bend out of sight.
FORK = [
    "##########",
    "#...##...#",
    "###.##.###",
    "###.##.###",
    "###....###",
    "####..####",
    "####..####",
]
PARTY = [("a", {"name": "Teft", "hp": 10, "hp_max": 12}), ("b", {"name": "Salogel", "hp": 9, "hp_max": 9})]


def test_draw_validates_and_normalises():
    with pytest.raises(ValueError):
        scenemap.draw("dungeon", ["##"], {"x": 0, "y": 0})
    with pytest.raises(ValueError):
        scenemap.draw("dungeon", FORK, {"x": 40, "y": 2})
    sm = scenemap.draw("nowhere", ["#?#", "...", "#.#"], {"x": 0, "y": 0})
    assert sm["terrain"] == "road" and sm["cells"][0] == "#.#"  # unknown cells become floor
    assert sm["party"] in ((0, 1), (1, 0))  # moved off the wall onto the nearest floor


def test_fog_hides_round_the_corner_and_remembers():
    sm = scenemap.draw("dungeon", FORK, {"x": 4, "y": 6}, features=[{"label": "Gullet", "x": 1, "y": 1}],
                       npcs=[{"name": "Vane", "x": 1, "y": 1}])
    scenemap.refresh(sm, ["a", "b"])
    v = scenemap.view(sm, PARTY, "a")
    assert v["cells"][1][1] == " " and not v["labels"]  # the far end of the left passage is out of sight
    assert not any(t["name"] == "Vane" for t in v["tokens"])
    assert {t["name"] for t in v["tokens"]} == {"Teft", "Salogel"} and v["my_token_id"] == "pc-a"
    assert v["cells"][4][3] == "."  # the junction ahead is visible

    scenemap.update(sm, party_at={"x": 3, "y": 2})  # walk up the left passage
    scenemap.refresh(sm, ["a", "b"])
    v = scenemap.view(sm, PARTY, "a")
    assert v["cells"][1][1] == "." and v["labels"][0]["label"] == "Gullet"
    assert any(t["name"] == "Vane" for t in v["tokens"])
    # where they came from is still on the map, dimmed
    assert v["dim"] and all(v["cells"][y][x] != " " for x, y in v["dim"])


def test_sight_range_and_doors_block():
    sm = scenemap.draw("dungeon", ["..........", "....D.....", ".........."], {"x": 0, "y": 0}, sight_ft=20)
    vis = scenemap.visible(sm, [(0, 0)])
    assert (4, 0) in vis and (5, 0) not in vis  # 20 ft = 4 squares
    sm2 = scenemap.draw("dungeon", ["#####", "..D..", "#####"], {"x": 0, "y": 1})
    vis = scenemap.visible(sm2, [(0, 1)])
    assert (2, 1) in vis and (3, 1) not in vis  # you see the door, not past it


def test_update_cells_and_individual_positions():
    sm = scenemap.draw("cave", FORK, {"x": 4, "y": 5})
    scenemap.update(sm, set_cells=[{"x": 4, "y": 4, "cell": "#"}], character_positions={"b": {"x": 5, "y": 6}})
    assert sm["cells"][4][4] == "#"
    pos = scenemap.place_party(sm, ["a", "b"])
    assert pos["b"] == (5, 6) and pos["a"] != pos["b"]
    with pytest.raises(ValueError):
        scenemap.update(sm, set_cells=[{"x": 1, "y": 1, "cell": "X"}])
    text = scenemap.describe(sm, PARTY)
    assert "Salogel (5,6)" in text and "0123456789" in text


def test_dm_tools_and_game_view_hide_the_full_map():
    from fastapi.testclient import TestClient

    from app.db import SessionLocal
    from app.dm.tools import ToolBox
    from app.game.state import load
    from app.main import app

    from .test_chat import _character, _client

    with TestClient(app):
        host = _client("scenehost")
        gid = host.post("/api/games", json={"name": "S", "character_id": _character(host, "Ash"),
                                            "settings": {"ruleset": "2024"}}).json()["id"]
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            tb = ToolBox(ctx)
            out = tb.call("draw_scene_map", {"terrain": "dungeon", "rows": FORK, "party_at": {"x": 4, "y": 6},
                                             "features": [{"label": "Gullet", "x": 1, "y": 1}],
                                             "title": "The fork", "sight_ft": 60})
            assert out.startswith("ok") and "Ash (" in out
            assert tb.call("update_scene_map", {"characters": [{"name": "Nobody", "x": 1, "y": 1}]}).startswith("Error")
            ctx.save()
            db.commit()
        finally:
            db.close()
        sm = host.get(f"/api/games/{gid}/view").json()["scene_map"]
        assert sm["title"] == "The fork" and sm["cells"][1][1] == " " and not sm["labels"]
        assert [t["name"] for t in sm["tokens"]] == ["Ash"]


def test_open_air_is_not_fog_and_ladders_are_walkable():
    shaft = ["#=  #", "#=  #", "#=  #", "#....", "#####"]
    sm = scenemap.draw("cave", shaft, {"x": 1, "y": 0}, sight_ft=10)
    assert sm["party"] == (1, 0)  # a ladder square is somewhere you can stand
    scenemap.refresh(sm, ["a"])
    v = scenemap.view(sm, PARTY[:1], "a")
    assert v["cells"][0][2] == "v"  # the drop beside the rungs: seen, open air
    assert v["cells"][3][4] == " "  # out of a 10 ft light: unseen fog
    assert v["cells"][1][1] == "="


def test_fight_starts_on_the_scene_map_with_bystanders():
    from fastapi.testclient import TestClient

    from app.db import SessionLocal
    from app.dm.tools import ToolBox
    from app.game.combat import view as combat_view
    from app.game.state import load
    from app.main import app

    from .test_chat import _character, _client

    cave = ["############",
            "#..........#",
            "#..........#",
            "#.....######",
            "#.....#....#",
            "############"]
    with TestClient(app):
        host = _client("scenefight")
        gid = host.post("/api/games", json={"name": "F", "character_id": _character(host, "Ash"),
                                            "settings": {"ruleset": "2024"}}).json()["id"]
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            tb = ToolBox(ctx)
            tb.call("draw_scene_map", {"terrain": "cave", "rows": cave, "party_at": {"x": 2, "y": 2},
                                       "npcs": [{"name": "Pim", "x": 3, "y": 1},
                                                {"name": "Worg", "x": 9, "y": 1, "hostile": True}]})
            out = tb.call("start_combat", {"monsters": [{"name": "Wolf", "count": 1}], "terrain": "road"})
            assert not out.startswith("Error"), out
            enc = ctx.state["encounter"]
            assert enc["terrain"] == "cave" and enc["grid"] == {"w": 12, "h": 6}
            toks = {t["name"]: (t["x"], t["y"]) for t in enc["tokens"].values()}
            assert toks["Ash"] == (2, 2)  # where they stood (the wolf may already have moved on its turn)
            assert enc["bystanders"] == [{"name": "Pim", "x": 3, "y": 1}]
            assert enc["cells"][4][8] == " "  # the room round the corner was never seen: left out of the fight
            v = combat_view(enc, ctx.chars, [])
            assert any(t["kind"] == "npc" and t["name"] == "Pim" for t in v["tokens"])
        finally:
            db.close()


