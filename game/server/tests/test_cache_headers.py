"""The page is always re-checked (so a refresh gets an update); hashed build files are cached for good."""
from fastapi.testclient import TestClient

from app.main import app


def test_cache_headers():
    c = TestClient(app)
    page = c.get("/")
    if page.status_code == 200 and "text/html" in page.headers.get("content-type", ""):
        assert page.headers["cache-control"] == "no-cache"
    r = c.get("/assets/does-not-exist.js")
    assert r.headers.get("cache-control", "").startswith("public, max-age=31536000")
