"""Notifications: a Discord webhook per game (optional). In-site notifications come through the WebSocket."""
from __future__ import annotations

import logging

import httpx

from .state import Ctx, parse_iso

log = logging.getLogger("game.notify")

LABELS = {"exploration": "your move", "roll": "dice to roll", "shop": "shopping", "combat": "combat turn"}


async def send_discord(url: str | None, text: str) -> None:
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"content": text[:1900]})
    except httpx.HTTPError as e:
        log.warning("discord webhook failed: %s", e)


async def notify_phase(ctx: Ctx) -> None:
    """Tell the group a new phase opened (skipped during live sessions — everyone's at the table)."""
    st = ctx.settings
    if st.get("live") or not st.get("discord_webhook"):
        return
    p = ctx.phase
    label = LABELS.get(p.get("type"))
    if not label:
        return
    names = ", ".join(ctx.user_name(u) for u in ctx.waiting_on()) or "everyone"
    d = parse_iso(p.get("deadline"))
    when = f" — deadline <t:{int(d.timestamp())}:R>" if d else ""
    await send_discord(st["discord_webhook"], f"**{ctx.game.name}**: {label} for {names}{when}.")


async def nudge(ctx: Ctx, user_id: str) -> None:
    name = ctx.user_name(user_id)
    await send_discord(ctx.settings.get("discord_webhook"), f"**{ctx.game.name}**: {name}, the party is waiting on you!")
