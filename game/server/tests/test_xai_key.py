"""The Grok (xAI) key in Settings: stored encrypted, shown only as the last 4 characters."""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import User
from app.security import decrypt_secret

from .test_chat import _client


def test_save_show_and_remove_xai_key():
    with TestClient(app):
        c = _client("xaiuser")
        assert c.put("/api/me/xai-key", json={"key": "sk-ant-notagrokkey123"}).status_code == 400
        fake = "xai-" + "t" * 40 + "WXYZ"  # not a real key
        me = c.put("/api/me/xai-key", json={"key": fake}).json()
        assert me["has_xai_key"] and me["xai_key_last4"] == "WXYZ" and fake not in str(me)
        assert fake not in c.get("/api/me").text
        db = SessionLocal()
        try:
            u = db.get(User, me["id"])
            assert u.xai_key_enc and u.xai_key_enc != fake and decrypt_secret(u.xai_key_enc) == fake
        finally:
            db.close()
        me = c.delete("/api/me/xai-key").json()
        assert not me["has_xai_key"] and me["xai_key_last4"] is None
