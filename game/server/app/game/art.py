"""AI art from the host's Grok (xAI) key: scene backgrounds, monster portraits, character portraits.

Everything is optional. Without a key, or with the game's "ai_art" setting off, nothing happens and the game looks
as it always did. Images are generated in the background after a DM turn so play never waits on them, cached on
disk by prompt (the same monster looks the same in every game, and costs once), and capped per game.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
from io import BytesIO

import httpx

from ..config import DATA_DIR

log = logging.getLogger(__name__)

ART_DIR = DATA_DIR / "art"
API_URL = "https://api.x.ai/v1/images/generations"
MODEL = "grok-imagine-image"
GAME_CAP = 60  # images per game, so a long campaign can't run up a surprise bill (~$0.02 each)
STYLE = ("Painterly dark-fantasy illustration in the style of tabletop RPG book art, rich atmosphere, dramatic "
         "lighting. No text, no letters, no logos, no watermark, no borders, no UI.")

_inflight: dict[str, asyncio.Future] = {}


class ArtError(Exception):
    pass


def art_name(prompt: str, aspect: str) -> str:
    return hashlib.sha1(f"{MODEL}|{aspect}|{prompt}".encode()).hexdigest()[:24] + ".webp"


def art_url(name: str | None) -> str | None:
    return f"/api/files/art/{name}" if name else None


def cached(prompt: str, aspect: str) -> str | None:
    name = art_name(prompt, aspect)
    return name if (ART_DIR / name).exists() else None


async def _request(key: str, prompt: str, aspect: str) -> bytes:
    body = {"model": MODEL, "prompt": prompt, "n": 1, "response_format": "b64_json", "aspect_ratio": aspect,
            "resolution": "1k"}
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(API_URL, json=body, headers={"Authorization": f"Bearer {key}"})
    if r.status_code != 200:
        try:
            msg = r.json().get("error") or r.text
        except ValueError:
            msg = r.text
        raise ArtError(f"xAI said {r.status_code}: {str(msg)[:200]}")
    data = (r.json().get("data") or [{}])[0]
    if data.get("b64_json"):
        return base64.b64decode(data["b64_json"])
    if data.get("url"):
        async with httpx.AsyncClient(timeout=60) as client:
            img = await client.get(data["url"])
        img.raise_for_status()
        return img.content
    raise ArtError("xAI returned no image")


def _save(raw: bytes, name: str, max_side: int) -> None:
    from PIL import Image
    img = Image.open(BytesIO(raw)).convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    ART_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ART_DIR / (name + ".tmp")
    img.save(tmp, "WEBP", quality=82)
    tmp.replace(ART_DIR / name)


async def generate(key: str, prompt: str, aspect: str = "1:1", max_side: int = 1024) -> str:
    """The image for this prompt: from the cache, or generated now. Returns the file name."""
    name = art_name(prompt, aspect)
    if (ART_DIR / name).exists():
        return name
    if name in _inflight:  # the same picture is already being made (two players, two tabs)
        return await asyncio.shield(_inflight[name])
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    _inflight[name] = fut
    try:
        raw = await _request(key, prompt, aspect)
        await asyncio.to_thread(_save, raw, name, max_side)
        fut.set_result(name)
        return name
    except Exception as e:
        fut.set_exception(e)
        fut.exception()  # mark retrieved
        raise
    finally:
        _inflight.pop(name, None)


# ── prompts ──────────────────────────────────────────────────────────────────

def scene_prompt(ctx) -> tuple[str, str]:
    """(signature, prompt) for the party's current surroundings; the signature changes when the scene does."""
    st = ctx.state
    loc = st.get("location") or {}
    sc = st.get("scene") or {}
    sm = st.get("scene_map") or {}
    enc = ctx.encounter
    place = sm.get("title") or loc.get("name") or "a fantasy land"
    kind = (enc or {}).get("terrain") or sc.get("type") or "wilderness"
    tod = sc.get("time_of_day", "day")
    weather = sc.get("weather") or "clear"
    sig = "|".join([place, loc.get("name", ""), kind, tod])  # weather alone doesn't repaint the scene
    desc = (loc.get("description") or "")[:500]
    prompt = (f"A wide establishing view of {place}"
              + (f" in {loc['name']}" if loc.get("name") and loc.get("name") != place else "")
              + f". {desc} Setting: {kind}, {tod}, {weather} weather. Mood: {ctx.settings.get('tone', 'heroic')}. "
              "An environment scene with no characters in the foreground. " + STYLE)
    return sig, prompt


def monster_prompt(t: dict) -> str:
    kind = f" ({t['ctype']})" if t.get("ctype") else ""
    return (f"Portrait of a {t['name'].rstrip('0123456789 ').strip()}{kind}, a creature from Dungeons-and-Dragons-style "
            "fantasy, head and shoulders, facing the viewer, menacing, dark background. " + STYLE)


def character_prompt(sheet: dict, race: str, cls: str, notes: str = "") -> str:
    looks = notes.strip() or (sheet.get("appearance") or "").strip()
    back = (sheet.get("backstory") or "").strip()[:300]
    return (f"Character portrait of {sheet.get('name', 'an adventurer')}, a {race} {cls} adventurer, head and "
            "shoulders, facing the viewer, heroic. "
            + (f"Appearance: {looks[:400]}. " if looks else "")
            + (f"Background: {back}. " if back and not looks else "")
            + STYLE)


# ── keeping a game's art up to date ─────────────────────────────────────────

def host_key(ctx) -> str | None:
    from ..models import User
    from ..security import decrypt_secret
    if not ctx.settings.get("ai_art", True):
        return None
    host = ctx.db.get(User, ctx.game.host_id)
    if not host or not host.xai_key_enc:
        return None
    try:
        return decrypt_secret(host.xai_key_enc)
    except Exception:  # noqa: BLE001 — a key we can't read is just "no key"
        return None


async def refresh_game_art(game_id: str) -> None:
    """After a DM turn: paint the current scene and any monster without a portrait (in the background)."""
    from ..db import SessionLocal
    from .flow import changed
    from .state import load, lock_for

    db = SessionLocal()
    try:
        ctx = load(db, game_id)
        key = host_key(ctx)
        if not key:
            return
        art = ctx.state.get("art") or {}
        used = int(art.get("count", 0))
        jobs: list[tuple[str, str, str, str]] = []  # (what, id, prompt, aspect)
        sig, sp = scene_prompt(ctx)
        if (ctx.state.get("scene_art") or {}).get("sig") != sig:
            jobs.append(("scene", sig, sp, "16:9"))
        for t in ((ctx.encounter or {}).get("tokens") or {}).values():
            if t.get("kind") == "monster" and t.get("monster_index") and not t.get("art"):
                p = monster_prompt(t)
                if not any(j[2] == p for j in jobs):
                    jobs.append(("monster", t["monster_index"], p, "1:1"))
    finally:
        db.close()

    results: list[tuple[str, str, str]] = []
    for what, ident, prompt, aspect in jobs:
        fresh = not cached(prompt, aspect)
        if fresh and used >= GAME_CAP:
            continue
        try:
            name = await generate(key, prompt, aspect, 1280 if what == "scene" else 512)
        except Exception as e:  # noqa: BLE001 — art is a nice-to-have; never break the game over it
            log.warning("art for %s failed: %s", game_id, e)
            continue
        used += 1 if fresh else 0
        results.append((what, ident, name))
    if not results:
        return

    async with lock_for(game_id):
        db = SessionLocal()
        try:
            ctx = load(db, game_id)
            for what, ident, name in results:
                if what == "scene":
                    ctx.state["scene_art"] = {"sig": ident, "name": name}
                else:
                    for t in ((ctx.encounter or {}).get("tokens") or {}).values():
                        if t.get("monster_index") == ident:
                            t["art"] = name
            ctx.state["art"] = {"count": used}
            ctx.save()
        finally:
            db.close()
    await changed(game_id, [])
