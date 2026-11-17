"""Invite by email: a player emails a friend the invite code and a join link."""
import os
import tempfile

if "GAME_DATA_DIR" not in os.environ:
    os.environ["GAME_DATA_DIR"] = tempfile.mkdtemp(prefix="dndgame-invite-")
os.environ.setdefault("GAME_TICK_SECONDS", "0.2")

from fastapi.testclient import TestClient  # noqa: E402

from app.game import notify  # noqa: E402
from app.main import app  # noqa: E402
from tests.test_chat import _game  # noqa: E402


def test_invite_by_email(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "_send_email_sync", lambda to, subject, body: sent.append((to, subject, body)))
    monkeypatch.setattr(notify, "PUBLIC_URL", "https://game.example")
    monkeypatch.setattr(notify, "_invites_sent", {})
    with TestClient(app):
        gid, host, player, watcher, outsider = _game("inv1")
        code = host.get(f"/api/games/{gid}/view").json()["game"]["invite_code"]

        # no SMTP settings → a clear error, nothing sent
        monkeypatch.delenv("GAME_SMTP_HOST", raising=False)
        r = host.post(f"/api/games/{gid}/invite", json={"email": "friend@example.com"})
        assert r.status_code == 400 and "email isn't set up" in r.json()["detail"]

        monkeypatch.setenv("GAME_SMTP_HOST", "smtp.example.com")
        r = host.post(f"/api/games/{gid}/invite", json={"email": " friend@example.com "})
        assert r.status_code == 200, r.text
        to, subject, body = sent[-1]
        assert to == "friend@example.com"
        assert "Inv1Host" in subject and "Chat test" in subject
        assert f"https://game.example/#/join/{code}" in body and code in body

        # players can invite; spectators and outsiders can't; junk addresses are refused
        assert player.post(f"/api/games/{gid}/invite", json={"email": "a@b.co"}).status_code == 200
        assert watcher.post(f"/api/games/{gid}/invite", json={"email": "a@b.co"}).status_code == 403
        assert outsider.post(f"/api/games/{gid}/invite", json={"email": "a@b.co"}).status_code == 403
        assert host.post(f"/api/games/{gid}/invite", json={"email": "not an email"}).status_code == 400
        assert host.post(f"/api/games/{gid}/invite", json={"email": "a@b.co\nBcc: x@y.z"}).status_code == 400

        # at most 20 invites per game per hour
        for _ in range(notify.INVITE_LIMIT_PER_HOUR - 2):
            assert host.post(f"/api/games/{gid}/invite", json={"email": "a@b.co"}).status_code == 200
        r = host.post(f"/api/games/{gid}/invite", json={"email": "a@b.co"})
        assert r.status_code == 400 and "invites" in r.json()["detail"]

        # an SMTP failure comes back as a 502, not a crash
        monkeypatch.setattr(notify, "_invites_sent", {})
        def boom(*a):
            raise OSError("connection refused")
        monkeypatch.setattr(notify, "_send_email_sync", boom)
        assert host.post(f"/api/games/{gid}/invite", json={"email": "a@b.co"}).status_code == 502
