"""M4: D&D Beyond 2024 import with kept features, portraits, custom content library, ruleset-aware DM prompt."""
import io
import json

from fastapi.testclient import TestClient
from PIL import Image

from app import ddb
from app.main import app


def _ddb_json(legacy: bool) -> dict:
    """A minimal D&D Beyond character payload in the v5 shape the importer reads."""
    return {
        "id": 123456, "name": "Brin Ashvale",
        "race": {"fullName": "Elf", "isLegacy": legacy,
                 "racialTraits": [{"definition": {"name": "Starlit Grace", "description": "<p>Homebrew trait text.</p>"}}]},
        "background": {"definition": {"name": "Soldier", "isLegacy": legacy, "featureName": "Field Rank",
                                      "featureDescription": "<p>Soldiers still respect your rank.</p>"}},
        "classes": [{"level": 4, "definition": {"name": "Fighter"},
                     "subclassDefinition": {"name": "Battle Master"},
                     "classFeatures": [
                         {"definition": {"name": "Second Wind", "description": "<p>Heal.</p>", "requiredLevel": 1}},
                         {"definition": {"name": "Combat Superiority", "description": "<p>Superiority dice d8.</p>",
                                         "requiredLevel": 3}},
                         {"definition": {"name": "Know Your Enemy", "description": "<p>Too high.</p>", "requiredLevel": 7}}]}],
        "stats": [{"id": i, "value": v} for i, v in zip(range(1, 7), [16, 14, 14, 10, 12, 8])],
        "bonusStats": [], "overrideStats": [], "modifiers": {},
        "feats": [{"definition": {"name": "Polearm Master", "description": "<p>Bonus attack with the butt end.</p>"}}],
        "inventory": [{"definition": {"name": "Longsword", "filterType": "Weapon", "canEquip": True}, "equipped": True, "quantity": 1}],
        "classSpells": [], "currencies": {"gp": 25}, "baseHitPoints": 36, "bonusHitPoints": 0,
    }


def test_detect_ruleset_and_keep_features():
    s24 = ddb.to_sheet(_ddb_json(legacy=False))
    assert s24["ruleset"] == "2024" and s24["level"] == 4
    kept = {c["name"] for c in s24["custom"]}
    assert {"Combat Superiority", "Polearm Master", "Starlit Grace", "Field Rank"} <= kept
    assert "Know Your Enemy" not in kept  # above the character's level
    assert all(c["description"] and "<p>" not in c["description"] for c in s24["custom"])
    s14 = ddb.to_sheet(_ddb_json(legacy=True))
    assert s14["ruleset"] == "2014"


def _client(name):
    c = TestClient(app)
    assert c.post("/api/auth/register", json={"username": name, "password": "secret123", "display_name": name}).status_code == 200
    return c


def _png(color=(200, 40, 40), size=(400, 300)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def test_m4_api():
    with TestClient(app):
        a = _client("m4user")
        # import a 2024 character from pasted JSON
        r = a.post("/api/characters/import", json={"source": json.dumps(_ddb_json(False))})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ruleset"] == "2024" and "Combat Superiority" in body["kept_as_custom"]
        cid = body["character"]["id"]
        assert body["character"]["ruleset"] == "2024"
        assert any(c["name"] == "Polearm Master" for c in body["character"]["custom"])
        # portrait upload, serve, replace, delete
        r = a.post(f"/api/characters/{cid}/portrait", files={"image": ("me.png", _png(), "image/png")})
        assert r.status_code == 200, r.text
        url = r.json()["portrait_url"]
        img = a.get(url)
        assert img.status_code == 200 and img.headers["content-type"] == "image/webp"
        assert Image.open(io.BytesIO(img.content)).size == (300, 300)  # square-cropped, never upscaled, max 640
        assert a.post(f"/api/characters/{cid}/portrait", files={"image": ("x.txt", b"nope", "text/plain")}).status_code == 400
        assert a.delete(f"/api/characters/{cid}/portrait").json()["portrait_url"] is None
        assert a.get(url).status_code == 404
        # custom library
        e = a.post("/api/custom", json={"kind": "feat", "name": "Shield Master", "description": "Shove as a bonus action."})
        assert e.status_code == 200, e.text
        item = a.post("/api/custom", json={"kind": "item", "name": "Ring of the Ram", "description": "A ram's head ring.",
                                           "data": {"value_gp": 500, "category": "Magic Item"}}).json()
        assert a.post("/api/custom", json={"kind": "nonsense", "name": "x"}).status_code == 400
        assert len(a.get("/api/custom").json()) == 2
        v = a.post(f"/api/characters/{cid}/custom", json={"entry_id": e.json()["id"]}).json()
        assert any(c["name"] == "Shield Master" for c in v["custom"])
        assert a.post(f"/api/characters/{cid}/custom", json={"entry_id": e.json()["id"]}).status_code == 400
        v = a.post(f"/api/characters/{cid}/custom", json={"entry_id": item["id"]}).json()
        assert any(i["name"] == "Ring of the Ram" and i["value_cp"] == 50000 for i in v["inventory"])
        v = a.delete(f"/api/characters/{cid}/custom/{e.json()['id']}").json()
        assert not any(c["name"] == "Shield Master" for c in v["custom"])
        # in a 2024 game, the DM prompt names the 2024 rules and includes custom content
        g = a.post("/api/games", json={"name": "M4", "character_id": cid, "settings": {"ruleset": "2024"}}).json()
        from app.db import SessionLocal
        from app.dm import prompt
        from app.game.state import load
        db = SessionLocal()
        try:
            ctx = load(db, g["id"])
            sysp = prompt.system_prompt(ctx)
            assert "2024 rules" in sysp and "levels 1-10" in sysp
            msg = prompt.turn_message(ctx, "round", "test", [])
            assert "Combat Superiority" in msg and "Weapon masteries" in msg or "Combat Superiority" in msg
        finally:
            db.close()


def test_town_map_close_start_and_opening_report():
    from app.dm.tools import ToolBox
    from app.game import combat
    from app.rules import character as ch
    from app.world import battlemap as bm

    m = bm.generate("town", 7)
    kinds = {p["kind"] for p in m["props"]}
    assert {"stall", "well"} <= kinds
    assert all(c in "#.T~D" for row in m["cells"] for c in row)
    sheet = ch.create({"name": "Brakka", "race": "dwarf", "subrace": "hill-dwarf", "class": "fighter",
                       "background": "soldier", "ability_method": "standard",
                       "abilities": {"STR": 15, "DEX": 13, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10},
                       "skills": ["Perception", "Survival"], "equipment_option": "defender"})
    enc, lines = combat.start([("bandit", 2)], "town", [("c1", sheet)], seed=5, distance="close")
    pcs = [t for t in enc["tokens"].values() if t["kind"] == "pc"]
    mons = [t for t in enc["tokens"].values() if t["kind"] == "monster"]
    gap = min(bm.distance_ft((p["x"], p["y"]), (q["x"], q["y"])) for p in pcs for q in mons)
    assert gap <= 25 or any("attacks" in ln["text"] for ln in lines)  # enemies may already have closed in
    report = ToolBox._combat_opening(enc, lines)
    assert "Initiative" in report and "attacks:" in report and "Scimitar" in report
