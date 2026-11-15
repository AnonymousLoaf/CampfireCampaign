"""WebSocket hub: tells connected browsers when a game (or their lobby) changed."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from fastapi import WebSocket


@dataclass(eq=False)
class Conn:
    ws: WebSocket
    user_id: str | None
    games: set[str] = field(default_factory=set)
    lobby: bool = False


class Hub:
    def __init__(self) -> None:
        self.conns: set[Conn] = set()

    def add(self, c: Conn) -> None:
        self.conns.add(c)

    def remove(self, c: Conn) -> None:
        self.conns.discard(c)

    async def _send(self, c: Conn, msg: dict) -> None:
        try:
            await c.ws.send_text(json.dumps(msg))
        except Exception:
            self.conns.discard(c)

    async def game_changed(self, game_id: str) -> None:
        msg = {"type": "update", "game_id": game_id}
        await asyncio.gather(*(self._send(c, msg) for c in list(self.conns) if game_id in c.games))

    async def lobby_changed(self, user_ids: list[str]) -> None:
        ids = set(user_ids)
        msg = {"type": "lobby"}
        await asyncio.gather(*(self._send(c, msg) for c in list(self.conns) if c.lobby and c.user_id in ids))


hub = Hub()
