"""FastAPI app: API, WebSocket, deadline scheduler, and the built frontend."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
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

if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
else:
    @app.get("/", response_class=HTMLResponse)
    def no_frontend():
        return ("<h1>Game server running</h1><p>The frontend isn't built yet. In <code>game/web</code> run "
                "<code>npm install</code> then <code>npm run build</code>, or use <code>npm run dev</code> "
                "and open http://localhost:5173.</p>")
