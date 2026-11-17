"""Spoken narration: who says each line, stable per-character voice recipes, and the shared audio file."""
import asyncio

import numpy as np
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.game import voices
from app.game.state import load
from app.main import app
from app.models import LogEntry

from .test_chat import _character, _client

NAMES = ["Captain Ilsa Vane", "The Caretaker", "Pim", "Teft"]
TEXT = ('Vane walks backward to grin at Teft. "Stay close, scaleback. I\'d hate to lose my favor."\n\n'
        '"Crowbar! *Anyone!*" Vane shouts.\n\n'
        'A man waits at the lip, smiling. "The climb is terribly dark," says the Caretaker. "Please, take it."\n\n'
        '"Sorry," Pim whispers. "Sorry, sorry."\n\n'
        'Somewhere below, a voice calls out: "Who goes there?"')


def test_segments_attribute_each_quote():
    segs = voices.segments(TEXT, NAMES)
    said = [(t, s) for t, s in segs if s is not None]
    vane = " ".join(t for t, s in said if s == "Captain Ilsa Vane")
    assert "Stay close, scaleback" in vane and "Crowbar! Anyone!" in vane  # markdown stripped
    assert any(s == "The Caretaker" and t.startswith("The climb") for t, s in said)
    assert any(s == "The Caretaker" and t.startswith("Please") for t, s in said)  # same speaker continues
    assert ("Sorry, sorry.", "Pim") in said or any(s == "Pim" and "Sorry" in t for t, s in said)
    assert any(s == "?" and "Who goes there" in t for t, s in said)  # nobody named: a stranger's voice
    assert segs[0][1] is None and "walks backward" in segs[0][0]  # narration stays with the narrator


def test_recipes_are_stable_and_flavoured():
    a = voices.recipe_for("Captain Ilsa Vane", "she draws her sword")
    assert a == voices.recipe_for("Captain Ilsa Vane", "she draws her sword")
    assert all(v.startswith(("af_", "bf_")) for v, _ in a["mix"])
    dwarf = voices.recipe_for("Borin", "a gruff old dwarf smith, he grumbles")
    gnome = voices.recipe_for("Tink", "a nervous gnome tinker")
    assert dwarf["pitch"] < gnome["pitch"]
    assert all(v.startswith(("am_", "bm_")) for v, _ in dwarf["mix"])
    assert 0.75 <= dwarf["speed"] <= 1.3


class FakeKokoro:
    def __init__(self):
        self.calls = []

    def get_voice_style(self, name):
        return np.full((510, 1, 256), len(name), dtype=np.float32)

    def create(self, text, voice, speed, lang):
        self.calls.append((text, float(np.asarray(voice).mean()), speed))
        return np.sin(np.linspace(0, 40, int(2400 * len(text) / 10))).astype(np.float32) * 0.3, 24000


def test_render_mixes_voices_and_shifts_pitch(monkeypatch):
    fake = FakeKokoro()
    monkeypatch.setattr(voices, "_get_engine", lambda: fake)
    up = {"mix": [["af_bella", 1.0]], "speed": 1.0, "pitch": 12.0}  # an octave up: synthesise at half speed
    mp3 = voices.render([("Hello there.", voices.NARRATOR), ("Hi!", up)])
    assert mp3[:3] == b"ID3" or mp3[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
    assert fake.calls[1][2] == 0.5


def test_a_narration_gets_shared_audio(monkeypatch):
    fake = FakeKokoro()
    monkeypatch.setattr(voices, "_get_engine", lambda: fake)
    monkeypatch.setattr(voices, "available", lambda: True)
    with TestClient(app):
        host = _client("voicehost")
        gid = host.post("/api/games", json={"name": "V", "character_id": _character(host, "Teft"),
                                            "settings": {"ruleset": "2024"}}).json()["id"]
        db = SessionLocal()
        try:
            ctx = load(db, gid)
            ctx.state["npcs"] = [{"name": "Captain Ilsa Vane", "role": "blue-coat captain", "notes": "She owes Teft."}]
            ctx.log("narration", TEXT, "DM")
            ctx.save()
            db.commit()
            lid = max(e.id for e in db.query(LogEntry).filter(LogEntry.game_id == gid, LogEntry.kind == "narration"))
        finally:
            db.close()
        asyncio.run(voices.voice_narration(gid, lid))
        v = host.get(f"/api/games/{gid}/view").json()
        entry = next(e for e in v["log"] if e["id"] == lid)
        assert entry["data"]["audio"].endswith(".mp3") and "Captain Ilsa Vane" in entry["data"]["speakers"]
        r = host.get(entry["data"]["audio"])
        assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
        db = SessionLocal()
        try:
            saved = load(db, gid).state["voices"]
        finally:
            db.close()
        assert "captain ilsa vane" in saved and saved["captain ilsa vane"]["mix"][0][0].startswith(("af_", "bf_"))


def test_settings_voice_test_endpoint(monkeypatch):
    fake = FakeKokoro()
    monkeypatch.setattr(voices, "_get_engine", lambda: fake)
    with TestClient(app):
        c = _client("voicetester")
        monkeypatch.setattr(voices, "available", lambda: False)
        assert c.get("/api/voices").json()["available"] is False
        assert c.post("/api/voices/test", json={"text": "Hello"}).status_code == 503
        monkeypatch.setattr(voices, "available", lambda: True)
        listing = c.get("/api/voices").json()
        assert listing["available"] and "af_bella" in listing["voices"]
        r = c.post("/api/voices/test", json={"text": "Mind the forty-third rung.", "voice": "am_adam",
                                             "blend": "bm_george", "blend_weight": 0.3, "speed": 0.9, "pitch": 6})
        assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) > 100
        assert abs(fake.calls[-1][2] - 0.9 / 2 ** 0.5) < 1e-6  # half an octave up: synthesised slower, then raised
        assert c.post("/api/voices/test", json={"text": "x", "voice": "not_a_voice"}).status_code == 400



def test_voice_test_reads_quotes_in_the_voice_and_the_rest_as_narrator(monkeypatch):
    fake = FakeKokoro()
    monkeypatch.setattr(voices, "_get_engine", lambda: fake)
    monkeypatch.setattr(voices, "available", lambda: True)
    with TestClient(app):
        c = _client("voicesplit")
        r = c.post("/api/voices/test", json={"text": '"Patrons do not descend," the steward says. "Mind the rung."',
                                             "voice": "af_bella", "speed": 1.0, "pitch": 0})
        assert r.status_code == 200
        spoken = [(t, round(style, 1)) for t, style, _ in fake.calls]
        assert [t for t, _ in spoken] == ["Patrons do not descend,", "the steward says.", "Mind the rung."]
        assert spoken[0][1] == spoken[2][1] != spoken[1][1]  # quotes in Bella, the middle in the narrator
