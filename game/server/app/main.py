"""FastAPI app: API, WebSocket, deadline scheduler, and the built frontend."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import TICK_SECONDS, WEB_DIST
from .db import init_db
from .game import flow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(flow.scheduler(TICK_SECONDS))
    yield
    task.cancel()


app = FastAPI(title="Campfire Campaign", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def www_redirect(request: Request, call_next):
    """www.campfirecampaign.com → campfirecampaign.com, keeping the path (and the #/game/… link, which the
    browser carries over itself)."""
    host = (request.headers.get("host") or "").lower()
    if host.startswith("www."):
        url = f"https://{host[4:]}{request.url.path}"
        if request.url.query:
            url += f"?{request.url.query}"
        return RedirectResponse(url, status_code=301)
    return await call_next(request)


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    """The page itself is always re-checked, so a refresh picks up an update; the hashed build files never
    change under their names, so browsers may keep them for good."""
    resp = await call_next(request)
    p = request.url.path
    if p.startswith("/assets/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif not p.startswith("/api") and (p == "/" or p.endswith(".html") or p.endswith("sw.js")):
        resp.headers["Cache-Control"] = "no-cache"
    return resp

if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
else:
    @app.get("/", response_class=HTMLResponse)
    def no_frontend():
        return ("<h1>Game server running</h1><p>The frontend isn't built yet. In <code>game/web</code> run "
                "<code>npm install</code> then <code>npm run build</code>, or use <code>npm run dev</code> "
                "and open http://localhost:5173.</p>")
