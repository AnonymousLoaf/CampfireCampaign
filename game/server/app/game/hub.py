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
    member_games: set[str] = field(default_factory=set)  # games joined as a member (not via a TV link)
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

    async def chat(self, game_id: str, message: dict) -> None:
        """A chat message was posted, edited or deleted. Only members get it — never TV links."""
        msg = {"type": "chat", "game_id": game_id, "message": message}
        await asyncio.gather(*(self._send(c, msg) for c in list(self.conns) if game_id in c.member_games))

    def forget(self, game_id: str, user_id: str) -> None:
        """Someone left or was removed: stop sending them this game's chat."""
        for c in self.conns:
            if c.user_id == user_id:
                c.member_games.discard(game_id)
                c.games.discard(game_id)

    def watching(self, game_id: str) -> set[str]:
        """Users with this game open right now."""
        return {c.user_id for c in self.conns if c.user_id and game_id in c.member_games}

    async def lobby_changed(self, user_ids: list[str]) -> None:
        ids = set(user_ids)
        msg = {"type": "lobby"}
        await asyncio.gather(*(self._send(c, msg) for c in list(self.conns) if c.lobby and c.user_id in ids))


hub = Hub()
