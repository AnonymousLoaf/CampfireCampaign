"""Notifications: browser push (VAPID), email (SMTP, optional), and a Discord webhook per game.

Nothing is sent during a live session — everyone's at the table.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import smtplib
from datetime import timedelta
from email.message import EmailMessage

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from ..config import DATA_DIR
from ..db import SessionLocal
from ..models import Game, Membership, PushSubscription, User
from .state import Ctx, now, parse_iso

log = logging.getLogger("game.notify")

LABELS = {"exploration": "your move", "roll": "dice to roll", "shop": "shopping", "combat": "your combat turn"}
VAPID_PATH = DATA_DIR / "vapid_private.pem"
VAPID_SUB = os.environ.get("GAME_VAPID_SUB", "mailto:noreply@example.com")
PUBLIC_URL = os.environ.get("GAME_PUBLIC_URL", "")  # e.g. https://dnd.example.com — used in emails


# ── VAPID keys ──────────────────────────────────────────────────────────────

def _vapid_key() -> ec.EllipticCurvePrivateKey:
    if VAPID_PATH.exists():
        return serialization.load_pem_private_key(VAPID_PATH.read_bytes(), password=None)
    key = ec.generate_private_key(ec.SECP256R1())
    VAPID_PATH.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption()))
    return key


def vapid_public_key() -> str:
    pub = _vapid_key().public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(pub).rstrip(b"=").decode()


def push_available() -> bool:
    try:
        import pywebpush  # noqa: F401
        return True
    except ImportError:
        return False


# ── email ───────────────────────────────────────────────────────────────────

def email_available() -> bool:
    return bool(os.environ.get("GAME_SMTP_HOST"))


def _send_email_sync(to: str, subject: str, body: str) -> None:
    host = os.environ["GAME_SMTP_HOST"]
    port = int(os.environ.get("GAME_SMTP_PORT", "587"))
    user = os.environ.get("GAME_SMTP_USER")
    password = os.environ.get("GAME_SMTP_PASSWORD")
    sender = os.environ.get("GAME_SMTP_FROM", user or "dnd-game@localhost")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=20) as s:
        if os.environ.get("GAME_SMTP_TLS", "1") != "0":
            s.starttls()
        if user and password:
            s.login(user, password)
        s.send_message(msg)


# ── push ────────────────────────────────────────────────────────────────────

def _send_push_sync(subs: list[tuple[int, str, dict]], payload: dict) -> list[int]:
    """Send to each subscription; returns ids of subscriptions that are gone (to delete)."""
    from pywebpush import WebPushException, webpush
    pem = VAPID_PATH.read_text() if VAPID_PATH.exists() else None
    if not pem:
        _vapid_key()
        pem = VAPID_PATH.read_text()
    gone = []
    for sid, endpoint, keys in subs:
        try:
            webpush(subscription_info={"endpoint": endpoint, "keys": keys}, data=json.dumps(payload),
                    vapid_private_key=str(VAPID_PATH), vapid_claims={"sub": VAPID_SUB}, ttl=24 * 3600)
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):
                gone.append(sid)
            else:
                log.warning("push failed: %s", e)
        except Exception as e:  # network errors etc.
            log.warning("push failed: %s", e)
    return gone


async def notify_users(user_ids: list[str], title: str, body: str, url: str = "/") -> None:
    if not user_ids:
        return
    db = SessionLocal()
    try:
        users = list(db.scalars(select(User).where(User.id.in_(user_ids))))
        subs = {u.id: [(s.id, s.endpoint, s.keys) for s in db.scalars(select(PushSubscription).where(PushSubscription.user_id == u.id))]
                for u in users}
    finally:
        db.close()
    payload = {"title": title, "body": body, "url": url}
    for u in users:
        if u.notify_push and subs.get(u.id) and push_available():
            gone = await run_in_threadpool(_send_push_sync, subs[u.id], payload)
            if gone:
                db = SessionLocal()
                try:
                    for sid in gone:
                        row = db.get(PushSubscription, sid)
                        if row:
                            db.delete(row)
                    db.commit()
                finally:
                    db.close()
        if u.notify_email and u.email and email_available():
            link = (PUBLIC_URL.rstrip("/") + url) if PUBLIC_URL else ""
            try:
                await run_in_threadpool(_send_email_sync, u.email, title, body + (f"\n\n{link}" if link else ""))
            except Exception as e:
                log.warning("email to user %s failed: %s", u.id, e)


# ── discord ─────────────────────────────────────────────────────────────────

async def send_discord(url: str | None, text: str) -> None:
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"content": text[:1900]})
    except httpx.HTTPError as e:
        log.warning("discord webhook failed: %s", e)


# ── game events ─────────────────────────────────────────────────────────────

def _game_url(ctx: Ctx) -> str:
    return f"/#/game/{ctx.game.id}"


async def notify_phase(ctx: Ctx) -> None:
    """Tell the people the new phase waits on."""
    st = ctx.settings
    if st.get("live"):
        return
    p = ctx.phase
    label = LABELS.get(p.get("type"))
    if not label:
        return
    waiting = ctx.waiting_on()
    d = parse_iso(p.get("deadline"))
    prompt = (p.get("prompt") or "").strip()
    body = (prompt[:140] + "…" if len(prompt) > 140 else prompt) or f"The party is waiting on you."
    await notify_users(waiting, f"{ctx.game.name}: {label}", body, _game_url(ctx))
    if st.get("discord_webhook"):
        names = ", ".join(ctx.user_name(u) for u in waiting) or "everyone"
        when = f" — deadline <t:{int(d.timestamp())}:R>" if d else ""
        await send_discord(st["discord_webhook"], f"**{ctx.game.name}**: {label} for {names}{when}.")


async def nudge(ctx: Ctx, user_id: str) -> None:
    name = ctx.user_name(user_id)
    await notify_users([user_id], f"{ctx.game.name}: the party is waiting", "The host nudged you — it's your move.",
                       _game_url(ctx))
    await send_discord(ctx.settings.get("discord_webhook"), f"**{ctx.game.name}**: {name}, the party is waiting on you!")


async def send_reminders() -> None:
    """Remind players who still haven't acted, `remind_minutes` before the deadline (once per phase)."""
    from .state import load
    db = SessionLocal()
    try:
        games = list(db.scalars(select(Game).where(Game.status == "active", Game.dm_busy.is_(False))))
        todo: list[tuple[str, list[str], str, str]] = []
        for g in games:
            p = (g.state or {}).get("phase") or {}
            d = parse_iso(p.get("deadline"))
            if not d or p.get("type") not in LABELS or (g.settings or {}).get("live"):
                continue
            if d <= now():
                continue
            ctx = load(db, g.id)
            waiting = set(ctx.waiting_on())
            due = []
            for m in ctx.members:
                if m.user_id not in waiting or m.reminded_phase_id == p.get("id"):
                    continue
                u = ctx.users.get(m.user_id)
                mins = (u.remind_minutes if u else 60) or 0
                if mins <= 0:
                    continue
                if now() >= d - timedelta(minutes=mins):
                    m.reminded_phase_id = p.get("id")
                    due.append(m.user_id)
            if due:
                db.commit()
                left = d - now()
                hrs = int(left.total_seconds() // 3600)
                mins = int(left.total_seconds() % 3600 // 60)
                todo.append((g.name, due, f"/#/game/{g.id}", f"{hrs}h {mins}m" if hrs else f"{mins} minutes"))
    finally:
        db.close()
    for name, users, url, left in todo:
        await notify_users(users, f"{name}: {left} left to move", "Your character is waiting for your action.", url)
