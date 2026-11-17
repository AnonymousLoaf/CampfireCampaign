"""AI art with the host's Grok key: scene backgrounds, monster portraits, character portraits (xAI faked)."""
import asyncio
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.db import SessionLocal
from app.dm.tools import ToolBox
from app.game import art
from app.game.state import load
from app.main import app

from .test_chat import _character, _client

FAKE_KEY = "xai-" + "f" * 40  # never sent anywhere: the request is replaced below


def _png(color=(120, 60, 30)) -> bytes:
    b = BytesIO()
    Image.new("RGB", (64, 48), color).save(b, "PNG")
    return b.getvalue()


def _fake(monkeypatch):
    calls = []

    async def fake_request(key, prompt, aspect):
        assert key == FAKE_KEY
        calls.append((prompt, aspect))
        return _png((len(calls) * 20 % 255, 80, 40))
    monkeypatch.setattr(art, "_request", fake_request)
    return calls


def test_no_key_means_no_art(monkeypatch):
    calls = _fake(monkeypatch)
    with TestClient(app):
        host = _client("artnokey")
        gid = host.post("/api/games", json={"name": "A", "character_id": _character(host, "Ash"),
                                            "settings": {"ruleset": "2024"}}).json()["id"]
        asyncio.run(art.refresh_game_art(gid))
        assert calls == [] and host.get(f"/api/games/{gid}/view").json()["scene_art"] is None


def test_scene_and_monster_art_with_the_hosts_key(monkeypatch):
    calls = _fake(monkeypatch)
    with TestClient(app):
        host = _client("arthost")
        assert host.put("/api/me/xai-key", json={"key": FAKE_KEY}).status_code == 200
        gid = host.post("/api/games", json={"name": "A", "character_id": _character(host, "Ash"),
                                            "settings": {"ruleset": "2024"}}).json()["id"]
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            ctx.state["location"] = {"name": "The Swallow", "settlement_id": None, "description": "A bone shaft."}
            ctx.state["scene"] = {"type": "cave", "time_of_day": "night", "weather": "still", "day": 1, "hour": 22}
            ToolBox(ctx).call("start_combat", {"monsters": [{"name": "Wolf", "count": 2}], "terrain": "cave"})
            ctx.save()
            db.commit()
        finally:
            db.close()
        asyncio.run(art.refresh_game_art(gid))
        assert len(calls) == 2  # one scene, one portrait shared by both wolves
        assert calls[0][1] == "16:9" and "The Swallow" in calls[0][0] and "cave" in calls[0][0]
        assert calls[1][1] == "1:1" and "Wolf" in calls[1][0] and "Wolf 1" not in calls[1][0]
        v = host.get(f"/api/games/{gid}/view").json()
        assert v["scene_art"].startswith("/api/files/art/")
        wolves = [t for t in v["encounter"]["tokens"] if t["kind"] == "monster"]
        assert wolves and all(t["portrait_url"] and t["portrait_url"].startswith("/api/files/art/") for t in wolves)
        img = host.get(v["scene_art"])
        assert img.status_code == 200 and img.headers["content-type"] == "image/webp"
        # nothing changed: no new pictures; the same wolf in another game comes from the cache for free
        asyncio.run(art.refresh_game_art(gid))
        assert len(calls) == 2
        # the host can switch it off
        assert host.patch(f"/api/games/{gid}/settings", json={"ai_art": False}).status_code == 200


def test_generate_a_character_portrait(monkeypatch):
    calls = _fake(monkeypatch)
    with TestClient(app):
        c = _client("artportrait")
        cid = _character(c, "Teft")
        assert c.post(f"/api/characters/{cid}/portrait/generate", json={}).status_code == 400  # no key yet
        c.put("/api/me/xai-key", json={"key": FAKE_KEY})
        r = c.post(f"/api/characters/{cid}/portrait/generate", json={"notes": "bronze scales, scarred snout"})
        assert r.status_code == 200, r.text
        assert r.json()["portrait_url"] and "Also: bronze scales" in calls[-1][0] and "Teft" in calls[-1][0]
        assert c.get(r.json()["portrait_url"]).status_code == 200
        # nothing typed: painted from the sheet alone (race, class, gear)
        r = c.post(f"/api/characters/{cid}/portrait/generate", json={})
        assert r.status_code == 200, r.text
        prompt = calls[-1][0]
        assert "Fighter" in prompt and "Wearing and carrying:" in prompt and "Also:" not in prompt


def test_paid_pictures_are_counted_outside_the_game_state(monkeypatch):
    calls = _fake(monkeypatch)
    with TestClient(app):
        host = _client("artcount")
        host.put("/api/me/xai-key", json={"key": FAKE_KEY})
        gid = host.post("/api/games", json={"name": "A", "character_id": _character(host, "Ash"),
                                            "settings": {"ruleset": "2024"}}).json()["id"]
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            ctx.state["location"] = {"name": "Count Keep", "settlement_id": None, "description": "Unique place 7781."}
            ctx.save()
            db.commit()
            stale = load(SessionLocal(), gid)  # a DM turn that loaded the game before the art was made
        finally:
            db.close()
        asyncio.run(art.refresh_game_art(gid))
        assert len(calls) == 1
        stale.save()  # ...and saves over the state afterwards
        stale.db.commit()
        stale.db.close()
        db = SessionLocal()
        try:
            from app.models import Game
            assert db.get(Game, gid).art_count == 1
        finally:
            db.close()


def test_npcs_get_portraits_in_the_journal_and_on_the_map(monkeypatch):
    calls = _fake(monkeypatch)
    with TestClient(app):
        host = _client("artnpc")
        host.put("/api/me/xai-key", json={"key": FAKE_KEY})
        gid = host.post("/api/games", json={"name": "A", "character_id": _character(host, "Ash"),
                                            "settings": {"ruleset": "2024"}}).json()["id"]
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            tb = ToolBox(ctx)
            tb.call("upsert_npc", {"name": "Captain Ilsa Vane", "role": "blue-coat captain", "notes": "Owes Teft two favours."})
            tb.call("draw_scene_map", {"terrain": "cave", "rows": ["#####", "#...#", "#####"], "party_at": {"x": 1, "y": 1},
                                       "npcs": [{"name": "Vane", "x": 3, "y": 1}]})
            ctx.save()
            db.commit()
        finally:
            db.close()
        asyncio.run(art.refresh_game_art(gid))
        npc_calls = [p for p, a in calls if "Captain Ilsa Vane" in p]
        assert len(npc_calls) == 1 and "blue-coat captain" in npc_calls[0]
        v = host.get(f"/api/games/{gid}/view").json()
        url = v["npcs"][0]["portrait_url"]
        assert url and url.startswith("/api/files/art/") and "art" not in v["npcs"][0]
        assert [t["portrait_url"] for t in v["scene_map"]["tokens"] if t["name"] == "Vane"] == [url]
        asyncio.run(art.refresh_game_art(gid))  # once only
        assert len([p for p, a in calls if "Captain Ilsa Vane" in p]) == 1
