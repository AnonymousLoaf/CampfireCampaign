"""HTTP + WebSocket API (see docs/game/API.md)."""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Callable

import re

from fastapi import (APIRouter, Cookie, Depends, File, HTTPException, Request, Response, UploadFile, WebSocket,
                     WebSocketDisconnect)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from . import ddb
from .config import MODELS, claude_cli_available
from .db import SessionLocal, get_db
from .game import combat, flow
from .game.hub import Conn, hub
from .game import notify
from .game import plot as plot_rules
from .game.notify import nudge as send_nudge
from .game.state import LIVE_EDITABLE, Ctx, build_view, clean_settings, load, lock_for
from .config import DATA_DIR
from .models import (AbilityRoll, Character, ChatMessage, CustomEntry, DMCall, Game, LogEntry, Membership,
                     PushSubscription, SessionToken, User)
from .rules import character as ch
from .rules import dice, srd
from .rules import shop as shop_rules
from .rules.character import RulesError
from .security import decrypt_secret, encrypt_secret, hash_password, verify_password

router = APIRouter(prefix="/api")
COOKIE = "session"
log = logging.getLogger("game.api")


# ── auth ────────────────────────────────────────────────────────────────────

def _user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    st = db.get(SessionToken, token)
    return db.get(User, st.user_id) if st else None


def current_user(session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    u = _user_from_token(db, session)
    if not u:
        raise HTTPException(401, "sign in first")
    return u


def me_dict(u: User) -> dict:
    return {"id": u.id, "username": u.username, "display_name": u.display_name,
            "has_api_key": bool(u.api_key_enc), "api_key_last4": u.api_key_last4,
            "has_xai_key": bool(u.xai_key_enc), "xai_key_last4": u.xai_key_last4,
            "email": u.email, "notify": {"email": bool(u.notify_email), "push": bool(u.notify_push if u.notify_push is not None else True),
                                         "remind_minutes": u.remind_minutes if u.remind_minutes is not None else 60,
                                         "chat": bool(u.notify_chat)}}


def _login(resp: Response, db: Session, u: User) -> dict:
    tok = SessionToken(user_id=u.id)
    db.add(tok)
    db.commit()
    resp.set_cookie(COOKIE, tok.token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 90)
    return me_dict(u)


class RegisterBody(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=200)
    display_name: str = Field(min_length=1, max_length=40)


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/auth/register")
def register(body: RegisterBody, resp: Response, db: Session = Depends(get_db)):
    uname = body.username.strip().lower()
    if not uname.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "usernames can use letters, numbers, - and _")
    if db.scalar(select(User).where(User.username == uname)):
        raise HTTPException(400, "that username is taken")
    u = User(username=uname, display_name=body.display_name.strip(), password_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    return _login(resp, db, u)


@router.post("/auth/login")
def login(body: LoginBody, resp: Response, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(400, "wrong username or password")
    return _login(resp, db, u)


@router.post("/auth/logout")
def logout(resp: Response, session: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if session:
        st = db.get(SessionToken, session)
        if st:
            db.delete(st)
            db.commit()
    resp.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/me")
def get_me(u: User = Depends(current_user)):
    return me_dict(u)


class KeyBody(BaseModel):
    key: str = Field(min_length=10, max_length=400)


@router.put("/me/api-key")
def put_key(body: KeyBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    k = body.key.strip()
    if not k.startswith("sk-ant-"):
        raise HTTPException(400, "that doesn't look like a Claude API key (they start with sk-ant-)")
    u.api_key_enc = encrypt_secret(k)
    u.api_key_last4 = k[-4:]
    db.commit()
    return me_dict(u)


@router.delete("/me/api-key")
def delete_key(u: User = Depends(current_user), db: Session = Depends(get_db)):
    u.api_key_enc = None
    u.api_key_last4 = None
    db.commit()
    return me_dict(u)


@router.put("/me/xai-key")
def put_xai_key(body: KeyBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    k = body.key.strip()
    if not k.startswith("xai-"):
        raise HTTPException(400, "that doesn't look like an xAI (Grok) API key (they start with xai-)")
    u.xai_key_enc = encrypt_secret(k)
    u.xai_key_last4 = k[-4:]
    db.commit()
    return me_dict(u)


@router.delete("/me/xai-key")
def delete_xai_key(u: User = Depends(current_user), db: Session = Depends(get_db)):
    u.xai_key_enc = None
    u.xai_key_last4 = None
    db.commit()
    return me_dict(u)


class ClientLogBody(BaseModel):
    kind: str = Field(max_length=40)
    message: str = Field(default="", max_length=500)


CLIENT_LOG = DATA_DIR / "client-log.jsonl"


@router.post("/client-log")
def client_log(body: ClientLogBody, request: Request, u: User = Depends(current_user)):
    """A browser reports how a feature went on its device (the dice), so problems we can't see can be fixed."""
    try:
        if CLIENT_LOG.exists() and CLIENT_LOG.stat().st_size > 2_000_000:
            CLIENT_LOG.replace(CLIENT_LOG.with_suffix(".old.jsonl"))
        with CLIENT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "user": u.id,
                                "kind": body.kind, "message": body.message,
                                "ua": (request.headers.get("user-agent") or "")[:200]}) + "\n")
    except OSError:
        pass
    return {"ok": True}


@router.get("/meta")
def meta(u: User = Depends(current_user)):
    return {"engines": {"offline": True, "claude_code": claude_cli_available(), "api_key": bool(u.api_key_enc)},
            "models": MODELS, "email_available": notify.email_available(), "push_available": notify.push_available()}


class NotifyBody(BaseModel):
    email: str | None = None
    notify_email: bool | None = None
    notify_push: bool | None = None
    remind_minutes: int | None = Field(default=None, ge=0, le=10080)
    notify_chat: bool | None = None


@router.put("/me/notifications")
def put_notifications(body: NotifyBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    fields = body.model_fields_set
    if "email" in fields:
        e = (body.email or "").strip()
        if e and ("@" not in e or len(e) > 200 or " " in e):
            raise HTTPException(400, "that doesn't look like an email address")
        u.email = e or None
    if body.notify_email is not None:
        u.notify_email = body.notify_email
    if body.notify_push is not None:
        u.notify_push = body.notify_push
    if body.remind_minutes is not None:
        u.remind_minutes = body.remind_minutes
    if body.notify_chat is not None:
        u.notify_chat = body.notify_chat
    db.commit()
    return me_dict(u)


@router.get("/push/key")
def push_key(u: User = Depends(current_user)):
    return {"public_key": notify.vapid_public_key()}


class SubscribeBody(BaseModel):
    subscription: dict


@router.post("/push/subscribe")
def push_subscribe(body: SubscribeBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = body.subscription
    endpoint = str(sub.get("endpoint") or "")
    keys = sub.get("keys") or {}
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        raise HTTPException(400, "invalid push subscription")
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if row:
        row.user_id = u.id
        row.keys = {"p256dh": keys["p256dh"], "auth": keys["auth"]}
    else:
        db.add(PushSubscription(user_id=u.id, endpoint=endpoint, keys={"p256dh": keys["p256dh"], "auth": keys["auth"]}))
    db.commit()
    return {"ok": True}


class UnsubscribeBody(BaseModel):
    endpoint: str


@router.delete("/push/subscribe")
def push_unsubscribe(body: UnsubscribeBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint,
                                                   PushSubscription.user_id == u.id))
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.post("/push/test")
async def push_test(u: User = Depends(current_user)):
    await notify.notify_users([u.id], "Campfire Campaign", "Notifications are working on this device.", "/")
    return {"ok": True}


# ── rules & characters ──────────────────────────────────────────────────────

@router.get("/rules/creator")
def creator_options(ruleset: str = "2014"):
    from .rules.rulesets import available
    if ruleset not in available():
        raise HTTPException(400, f"the {ruleset} rules aren't installed on this server")
    return ch.creator_options(ruleset)


def _char_view(c: Character) -> dict:
    return ch.view(c.id, c.owner_id, c.game_id, c.sheet)


@router.get("/characters")
def my_characters(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Character).where(Character.owner_id == u.id).order_by(Character.created_at))
    return [_char_view(c) for c in rows]


@router.get("/characters/{cid}")
def get_character(cid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Character, cid)
    if not c or c.owner_id != u.id:
        raise HTTPException(404, "character not found")
    return _char_view(c)


@router.post("/characters/roll-abilities")
def roll_abilities(u: User = Depends(current_user), db: Session = Depends(get_db)):
    sets = [dice.ability_set() for _ in range(6)]
    r = AbilityRoll(user_id=u.id, sets=sets)
    db.add(r)
    db.commit()
    return {"roll_id": r.id, "sets": sets}


@router.post("/characters")
def create_character(body: dict, u: User = Depends(current_user), db: Session = Depends(get_db)):
    sets = None
    roll = None
    if body.get("ability_method") == "roll":
        roll = db.get(AbilityRoll, body.get("roll_id") or "")
        if not roll or roll.user_id != u.id or roll.used:
            raise HTTPException(400, "roll your ability scores first")
        sets = roll.sets
    homebrew = None
    race_req = str(body.get("race") or "")
    if race_req == "homebrew" or race_req.startswith("homebrew:"):  # one of my homebrew races from My content
        eid = str(body.get("homebrew_race_id") or race_req.partition(":")[2])
        entry = db.get(CustomEntry, eid) if eid else None
        if not entry or entry.user_id != u.id or entry.kind != "race":
            raise HTTPException(400, "that homebrew race isn't in your content library")
        homebrew = _custom_dict(entry)
    try:
        sheet = ch.create(body, sets, homebrew=homebrew)
    except RulesError as e:
        raise HTTPException(400, str(e))
    if roll:
        roll.used = True
    c = Character(owner_id=u.id, name=sheet["name"], sheet=sheet)
    db.add(c)
    db.commit()
    return _char_view(c)


class ImportBody(BaseModel):
    source: str = Field(max_length=2_000_000)


@router.post("/characters/import")
async def import_character(body: ImportBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        data = await run_in_threadpool(ddb.load_source, body.source)
        sheet = ddb.to_sheet(data)
    except RulesError as e:
        raise HTTPException(400, str(e))
    kept = sheet.pop("imported_custom", [])
    c = Character(owner_id=u.id, name=sheet["name"], sheet=sheet)
    db.add(c)
    db.commit()
    return {"character": _char_view(c), "issues": sheet.get("issues", []), "ruleset": sheet.get("ruleset", "2014"),
            "kept_as_custom": kept}


# ── editing a character safely (in or out of a game) ────────────────────────

async def _edit_character(u: User, cid: str, fn: Callable[[dict], Any]) -> dict:
    """Apply fn(sheet). Characters in an active game are edited through the game's lock so a DM turn can't clobber it."""
    db = SessionLocal()
    try:
        c = db.get(Character, cid)
        if not c or c.owner_id != u.id:
            raise HTTPException(404, "character not found")
        g = db.get(Game, c.game_id) if c.game_id else None
        gid = g.id if g and g.status == "active" else None
    finally:
        db.close()
    if gid:
        async with lock_for(gid):
            db = SessionLocal()
            try:
                ctx = load(db, gid)
                if ctx.game.dm_busy or ctx.phase.get("type") == "dm":
                    raise HTTPException(409, "the DM is writing — try again in a moment")
                try:
                    fn(ctx.chars[cid])
                except RulesError as e:
                    raise HTTPException(400, str(e))
                ctx.save()
                await flow.changed(ctx)
                row = db.get(Character, cid)
                return ch.view(row.id, row.owner_id, row.game_id, row.sheet)
            finally:
                db.close()
    from sqlalchemy.orm.attributes import flag_modified
    db = SessionLocal()
    try:
        c = db.get(Character, cid)
        sheet = json.loads(json.dumps(c.sheet))
        try:
            fn(sheet)
        except RulesError as e:
            raise HTTPException(400, str(e))
        c.sheet = sheet
        flag_modified(c, "sheet")
        db.commit()
        return ch.view(c.id, c.owner_id, c.game_id, c.sheet)
    finally:
        db.close()


# ── portraits ──────────────────────────────────────────────────────────────

PORTRAIT_DIR = DATA_DIR / "portraits"


@router.post("/characters/{cid}/portrait")
async def upload_portrait(cid: str, image: UploadFile = File(...), u: User = Depends(current_user)):
    from io import BytesIO

    from PIL import Image, UnidentifiedImageError
    raw = await image.read(3 * 1024 * 1024 + 1)
    if len(raw) > 3 * 1024 * 1024:
        raise HTTPException(400, "portraits can be up to 3 MB")
    try:
        img = Image.open(BytesIO(raw))
        if img.format not in ("PNG", "JPEG", "WEBP"):
            raise HTTPException(400, "use a PNG, JPEG or WebP image")
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "that file isn't an image")
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 4, (w - side) // 2 + side, (h - side) // 4 + side))
    out = min(640, side)  # big enough to view full size; small uploads aren't blown up
    img = img.resize((out, out), Image.LANCZOS)
    PORTRAIT_DIR.mkdir(parents=True, exist_ok=True)
    name = secrets.token_urlsafe(16) + ".webp"
    img.save(PORTRAIT_DIR / name, "WEBP", quality=85)
    old: dict = {}

    def fn(sheet: dict) -> None:
        old["name"] = sheet.get("portrait")
        sheet["portrait"] = name
    view = await _edit_character(u, cid, fn)
    if old.get("name"):
        (PORTRAIT_DIR / old["name"]).unlink(missing_ok=True)
    return view


class GeneratePortraitBody(BaseModel):
    notes: str = Field(default="", max_length=600)


@router.post("/characters/{cid}/portrait/generate")
async def generate_portrait(cid: str, body: GeneratePortraitBody, u: User = Depends(current_user)):
    """Paint a portrait with my Grok (xAI) key from the character's race, class and a short description."""
    import shutil

    from .game import art
    if not u.xai_key_enc:
        raise HTTPException(400, "save a Grok (xAI) API key in Settings first")
    db = SessionLocal()
    try:
        c = db.get(Character, cid)
        if not c or c.owner_id != u.id:
            raise HTTPException(404, "character not found")
        v = ch.view(c.id, c.owner_id, c.game_id, c.sheet)
        prompt = art.character_prompt(c.sheet, v, body.notes)
    finally:
        db.close()
    import secrets as _s
    prompt += f" Variation {_s.token_hex(3)}."  # asking again gives a new picture, not the cached one
    try:
        art_file = await art.generate(decrypt_secret(u.xai_key_enc), prompt, "1:1", 640)
    except art.ArtError as e:
        raise HTTPException(502, str(e))
    PORTRAIT_DIR.mkdir(parents=True, exist_ok=True)
    name = secrets.token_urlsafe(16) + ".webp"
    shutil.copyfile(art.ART_DIR / art_file, PORTRAIT_DIR / name)
    (art.ART_DIR / art_file).unlink(missing_ok=True)
    old: dict = {}

    def fn(sheet: dict) -> None:
        old["name"] = sheet.get("portrait")
        sheet["portrait"] = name
    view = await _edit_character(u, cid, fn)
    if old.get("name"):
        (PORTRAIT_DIR / old["name"]).unlink(missing_ok=True)
    return view


@router.get("/files/voice/{name}")
def get_voice(name: str):
    from .game.voices import AUDIO_DIR
    if not re.fullmatch(r"[0-9a-f]{12}-\d+\.mp3", name):
        raise HTTPException(404, "not found")
    path = AUDIO_DIR / name
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/files/art/{name}")
def get_art(name: str):
    from .game.art import ART_DIR
    if not re.fullmatch(r"[0-9a-f]{24}\.webp", name):
        raise HTTPException(404, "not found")
    path = ART_DIR / name
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.delete("/characters/{cid}/portrait")
async def delete_portrait(cid: str, u: User = Depends(current_user)):
    old: dict = {}

    def fn(sheet: dict) -> None:
        old["name"] = sheet.pop("portrait", None)
    view = await _edit_character(u, cid, fn)
    if old.get("name"):
        (PORTRAIT_DIR / old["name"]).unlink(missing_ok=True)
    return view


@router.get("/files/portraits/{name}")
def get_portrait(name: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,40}\.webp", name):
        raise HTTPException(404, "not found")
    path = PORTRAIT_DIR / name
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=31536000, immutable"})


# ── custom content library ──────────────────────────────────────────────────

CUSTOM_KINDS = {"feat", "feature", "spell", "item", "background", "species_trait", "race", "plot"}


class CustomBody(BaseModel):
    kind: str
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=6000)
    level: int | None = Field(default=None, ge=0, le=20)
    data: dict = Field(default_factory=dict)


def _custom_dict(e: CustomEntry) -> dict:
    return {"id": e.id, "kind": e.kind, "name": e.name, "description": e.description, "level": e.level,
            "data": e.data or {}, "created_at": e.created_at.isoformat() if e.created_at else None}


def _clean_custom(body: CustomBody) -> dict:
    if body.kind not in CUSTOM_KINDS:
        raise HTTPException(400, "kind must be one of: " + ", ".join(sorted(CUSTOM_KINDS)))
    data = {k: v for k, v in (body.data or {}).items() if isinstance(k, str) and len(k) < 40}
    limit = 4000
    if body.kind == "race":  # homebrew race: speed, size, bonuses, languages, up to 8 traits
        from .rules import campfire_races
        try:
            data = campfire_races.clean_homebrew_race(data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        limit = campfire_races.HOMEBREW_DATA_MAX
    elif body.kind == "plot":  # campaign plot: premise, villain, beats, NPCs, secrets, twists, ending
        try:
            data = plot_rules.clean(data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        limit = plot_rules.PLOT_DATA_MAX
    if len(json.dumps(data)) > limit:
        raise HTTPException(400, "too much extra data")
    return {"kind": body.kind, "name": body.name.strip(), "description": body.description.strip(), "level": body.level,
            "data": data}


@router.get("/custom")
def list_custom(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(CustomEntry).where(CustomEntry.user_id == u.id).order_by(CustomEntry.kind, CustomEntry.name))
    return [_custom_dict(e) for e in rows]


@router.post("/custom")
def create_custom(body: CustomBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.scalar(select(func.count(CustomEntry.id)).where(CustomEntry.user_id == u.id)) >= 500:
        raise HTTPException(400, "your library is full (500 entries)")
    e = CustomEntry(user_id=u.id, **_clean_custom(body))
    db.add(e)
    db.commit()
    return _custom_dict(e)


@router.put("/custom/{eid}")
def update_custom(eid: str, body: CustomBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(CustomEntry, eid)
    if not e or e.user_id != u.id:
        raise HTTPException(404, "entry not found")
    for k, v in _clean_custom(body).items():
        setattr(e, k, v)
    db.commit()
    return _custom_dict(e)


@router.delete("/custom/{eid}")
def delete_custom(eid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(CustomEntry, eid)
    if not e or e.user_id != u.id:
        raise HTTPException(404, "entry not found")
    db.delete(e)
    db.commit()
    return {"ok": True}


class AttachBody(BaseModel):
    entry_id: str


@router.post("/characters/{cid}/custom")
async def attach_custom(cid: str, body: AttachBody, u: User = Depends(current_user)):
    db = SessionLocal()
    try:
        e = db.get(CustomEntry, body.entry_id)
        if not e or e.user_id != u.id:
            raise HTTPException(404, "entry not found")
        if e.kind == "race":
            raise HTTPException(400, "homebrew races are chosen when you create a character")
        if e.kind == "plot":
            raise HTTPException(400, "campaign plots are picked by the host for a game, not added to a character")
        entry = _custom_dict(e)
    finally:
        db.close()

    def fn(sheet: dict) -> None:
        if any(c.get("entry_id") == entry["id"] for c in sheet.get("custom", [])):
            raise RulesError("that's already on this character")
        if entry["kind"] == "item":
            d = entry["data"]
            ch.add_item(sheet, "custom-" + entry["id"], 1, custom={
                "name": entry["name"][:60], "description": entry["description"][:1000],
                "value_cp": int(float(d.get("value_gp") or 0) * 100), "weight": d.get("weight") or 0,
                "category": d.get("category") or "Treasure"})
        sheet.setdefault("custom", []).append({"entry_id": entry["id"], "kind": entry["kind"], "name": entry["name"],
                                               "description": entry["description"], "level": entry["level"],
                                               "data": entry["data"], "source": "library"})
    return await _edit_character(u, cid, fn)


@router.delete("/characters/{cid}/custom/{entry_id}")
async def detach_custom(cid: str, entry_id: str, u: User = Depends(current_user)):
    def fn(sheet: dict) -> None:
        before = len(sheet.get("custom", []))
        if any(c.get("entry_id") == entry_id and c.get("source") == "dm" for c in sheet.get("custom", [])):
            raise RulesError("the DM gave that one: it goes away only in the story")
        sheet["custom"] = [c for c in sheet.get("custom", []) if c.get("entry_id") != entry_id]
        if len(sheet["custom"]) == before:
            raise RulesError("that isn't on this character")
    return await _edit_character(u, cid, fn)


def _in_active_game(db: Session, c: Character) -> bool:
    if not c.game_id:
        return False
    g = db.get(Game, c.game_id)
    return bool(g and g.status != "ended")


@router.delete("/characters/{cid}")
def delete_character(cid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Character, cid)
    if not c or c.owner_id != u.id:
        raise HTTPException(404, "character not found")
    if _in_active_game(db, c):
        raise HTTPException(400, "that character is in a game")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ── games ───────────────────────────────────────────────────────────────────

def _my_char(db: Session, u: User, cid: str | None) -> Character:
    c = db.get(Character, cid or "")
    if not c or c.owner_id != u.id:
        raise HTTPException(400, "choose one of your characters")
    if _in_active_game(db, c):
        raise HTTPException(400, f"{c.name} is already in a game")
    if c.sheet.get("dead"):
        raise HTTPException(400, f"{c.name} is dead")
    return c


@router.get("/games")
def my_games(u: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    mids = [m.game_id for m in db.scalars(select(Membership).where(Membership.user_id == u.id))]
    for g in db.scalars(select(Game).where(Game.id.in_(mids)).order_by(Game.updated_at.desc())):
        ctx = Ctx(db, g)
        host = db.get(User, g.host_id)
        out.append({"id": g.id, "name": g.name, "status": g.status, "phase_type": ctx.phase.get("type"),
                    "deadline": ctx.phase.get("deadline"), "my_turn": u.id in ctx.waiting_on(),
                    "their_call": ctx.their_call(u.id),
                    "player_count": len([m for m in ctx.members if m.role != "spectator"]),
                    "max_players": ctx.settings.get("max_players", 4), "ruleset": ctx.settings.get("ruleset", "2014"),
                    "role": next((m.role for m in ctx.members if m.user_id == u.id), None),
                    "host_name": host.display_name if host else "?", "invite_code": g.invite_code})
    return out


class CreateGameBody(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    settings: dict = Field(default_factory=dict)
    character_id: str
    plot_id: str | None = None


def _plot_snapshot(db: Session, u: User, entry_id: str) -> dict:
    e = db.get(CustomEntry, entry_id)
    if not e or e.user_id != u.id or e.kind != "plot":
        raise HTTPException(400, "that campaign plot isn't in your content library")
    try:
        return plot_rules.snapshot(_custom_dict(e))
    except ValueError as err:
        raise HTTPException(400, f"{e.name}: {err}")


@router.post("/games")
async def create_game(body: CreateGameBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _my_char(db, u, body.character_id)
    try:
        settings = clean_settings(body.settings)
    except RulesError as e:
        raise HTTPException(400, str(e))
    if c.sheet.get("ruleset", "2014") != settings.get("ruleset", "2014"):
        raise HTTPException(400, f"{c.name} was made with the {c.sheet.get('ruleset', '2014')} rules — pick a matching ruleset or character")
    if settings["dm_engine"] == "api_key" and not u.api_key_enc:
        raise HTTPException(400, "save a Claude API key in Settings first, or pick another DM engine")
    if settings["dm_engine"] == "claude_code" and not claude_cli_available():
        raise HTTPException(400, "Claude Code isn't installed on this computer")
    state: dict = {"phase": {"id": 0, "type": "lobby"}}
    if body.plot_id:
        state["plot"] = _plot_snapshot(db, u, body.plot_id)
    g = Game(name=body.name.strip(), host_id=u.id, settings=settings, state=state)
    db.add(g)
    db.flush()
    db.add(Membership(game_id=g.id, user_id=u.id, character_id=c.id, role="host"))
    c.game_id = g.id
    db.commit()
    await hub.lobby_changed([u.id])
    return {"id": g.id}


class JoinBody(BaseModel):
    invite_code: str
    character_id: str | None = None
    spectate: bool = False


@router.post("/games/join")
async def join_game(body: JoinBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    g = db.scalar(select(Game).where(Game.invite_code == body.invite_code.strip().upper()))
    if not g:
        raise HTTPException(404, "no game with that invite code")
    members = list(db.scalars(select(Membership).where(Membership.game_id == g.id)))
    if any(m.user_id == u.id for m in members):
        raise HTTPException(400, "you're already in that game")
    if body.spectate:
        if sum(1 for m in members if m.role == "spectator") >= 10:
            raise HTTPException(400, "that game already has 10 spectators")
        db.add(Membership(game_id=g.id, user_id=u.id, character_id=None, role="spectator"))
        db.commit()
        await flow.changed(g.id, [m.user_id for m in members] + [u.id])
        return {"id": g.id}
    if g.status != "lobby":
        raise HTTPException(400, "that game has already started — you can still join as a spectator")
    players = [m for m in members if m.role != "spectator"]
    if len(players) >= int((g.settings or {}).get("max_players", 4)):
        raise HTTPException(400, "that game is full")
    c = _my_char(db, u, body.character_id)
    if c.sheet.get("ruleset", "2014") != (g.settings or {}).get("ruleset", "2014"):
        raise HTTPException(400, f"that game uses the {(g.settings or {}).get('ruleset', '2014')} rules — pick a character made for them")
    db.add(Membership(game_id=g.id, user_id=u.id, character_id=c.id, role="player"))
    c.game_id = g.id
    db.commit()
    await flow.changed(g.id, [m.user_id for m in members] + [u.id])
    return {"id": g.id}


class PlotBody(BaseModel):
    entry_id: str | None = None


@router.put("/games/{gid}/plot")
async def set_plot(gid: str, body: PlotBody, u: User = Depends(current_user)):
    """Host only, before the game starts: pick a campaign plot from your library (or clear it with null)."""
    db = SessionLocal()
    try:
        snap = _plot_snapshot(db, u, body.entry_id) if body.entry_id else None
    finally:
        db.close()

    def fn(ctx: Ctx) -> None:
        if ctx.game.host_id != u.id:
            raise RulesError("only the host can choose the campaign plot")
        if ctx.game.status != "lobby":
            raise RulesError("the plot can only be changed before the game starts")
        if snap:
            ctx.state["plot"] = snap
        else:
            ctx.state.pop("plot", None)
    return await mutate(gid, u, fn)


def _member(ctx: Ctx, u: User) -> Membership:
    m = next((m for m in ctx.members if m.user_id == u.id), None)
    if not m:
        raise HTTPException(403, "you're not in this game")
    return m


@router.get("/games/{gid}/view")
def game_view(gid: str, character_id: str | None = None, u: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        ctx = load(db, gid)
    except RulesError:
        raise HTTPException(404, "game not found")
    _member(ctx, u)
    v = build_view(db, ctx, u.id)
    if character_id and ctx.encounter and character_id in ctx.controls(u.id):
        v["encounter"] = combat.view(ctx.encounter, ctx.chars, ctx.controls(u.id), prefer=character_id)
    return v


async def mutate(gid: str, u: User, fn: Callable[[Ctx], Any], allow_busy: bool = False) -> dict:
    """Run a state change under the game's lock, save, broadcast, and queue resolution if needed."""
    async with lock_for(gid):
        db = SessionLocal()
        try:
            try:
                ctx = load(db, gid)
            except RulesError:
                raise HTTPException(404, "game not found")
            _member(ctx, u)
            if not allow_busy and (ctx.game.dm_busy or ctx.phase.get("type") == "dm"):
                raise HTTPException(409, "the DM is writing — try again in a moment")
            try:
                res = fn(ctx) or {}
            except RulesError as e:
                raise HTTPException(400, str(e))
            ctx.save()
            await flow.changed(ctx)
            if res.get("resolve") and not ctx.waiting_on():
                flow.spawn(flow.resolve(gid))
            out = {"ok": True}
            out.update(res.get("return", {}))
            return out
        finally:
            db.close()


def _host(ctx: Ctx, u: User) -> None:
    if ctx.game.host_id != u.id:
        raise RulesError("only the host can do that")


@router.post("/games/{gid}/start")
async def start(gid: str, u: User = Depends(current_user)):
    return await mutate(gid, u, lambda ctx: flow.start_game(ctx, u.id))


def _remove_member(ctx: Ctx, m: Membership) -> dict:
    """Take a player (and their character) out of a game. The character keeps everything it earned and is free for
    another game. Not in the middle of a fight the character is part of."""
    if m.user_id == ctx.game.host_id:
        raise RulesError("the host can't leave their own game — delete it instead")
    enc = ctx.encounter
    if m.character_id and enc and any(t.get("character_id") == m.character_id for t in enc.get("tokens", [])):
        raise RulesError("not in the middle of a fight — try again once it's over")
    name = ctx.chars.get(m.character_id or "", {}).get("name") or ctx.user_name(m.user_id)
    p = ctx.phase
    p.get("submissions", {}).pop(m.user_id, None)
    if m.user_id in p.get("ready", []):
        p["ready"] = [x for x in p["ready"] if x != m.user_id]
    if p.get("pending_rolls"):
        p["pending_rolls"] = [r for r in p["pending_rolls"] if r.get("character_id") != m.character_id]
    if ctx.settings.get("speaker_id") == m.user_id:
        ctx.game.settings = {**(ctx.game.settings or {}), "speaker_id": None}
        ctx.settings["speaker_id"] = None
    c = ctx.db.get(Character, m.character_id) if m.character_id else None
    if c:
        c.sheet = ctx.chars.pop(c.id, c.sheet)
        c.game_id = None
    ctx.members = [x for x in ctx.members if x.id != m.id]
    ctx.db.delete(m)
    if ctx.game.status != "lobby" and m.role != "spectator":
        ctx.log("system", f"{name} has left the party.")
    return {"resolve": p.get("type") in ("exploration", "roll", "shop")}


@router.post("/games/{gid}/leave")
async def leave(gid: str, u: User = Depends(current_user)):
    res = await mutate(gid, u, lambda ctx: _remove_member(ctx, _member(ctx, u)))
    hub.forget(gid, u.id)
    await hub.lobby_changed([u.id])
    return res


class RemoveBody(BaseModel):
    user_id: str


@router.post("/games/{gid}/remove-player")
async def remove_player(gid: str, body: RemoveBody, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        _host(ctx, u)
        m = next((m for m in ctx.members if m.user_id == body.user_id), None)
        if not m:
            raise RulesError("they aren't in this game")
        return _remove_member(ctx, m)
    res = await mutate(gid, u, fn)
    hub.forget(gid, body.user_id)
    await hub.lobby_changed([body.user_id])  # the removed player's game list
    return res


@router.delete("/games/{gid}")
async def delete_game(gid: str, u: User = Depends(current_user)):
    """The host deletes a game for everyone. Characters are kept (freed for other games)."""
    async with lock_for(gid):
        db = SessionLocal()
        try:
            g = db.get(Game, gid)
            if not g:
                raise HTTPException(404, "game not found")
            if g.host_id != u.id:
                raise HTTPException(403, "only the host can delete a game")
            if g.dm_busy:
                raise HTTPException(409, "the DM is writing — try again in a moment")
            members = [m.user_id for m in db.scalars(select(Membership).where(Membership.game_id == gid))]
            db.execute(update(Character).where(Character.game_id == gid).values(game_id=None))
            for model in (LogEntry, DMCall, ChatMessage, Membership):
                db.execute(delete(model).where(model.game_id == gid))
            db.execute(delete(Game).where(Game.id == gid))
            db.commit()
        finally:
            db.close()
    await hub.game_changed(gid)
    await hub.lobby_changed(members)
    return {"ok": True}


# ── playing ─────────────────────────────────────────────────────────────────

class ActionBody(BaseModel):
    text: str = Field(default="", max_length=2000)
    travel_to: dict | None = None
    rest: str | None = None


def _need_phase(ctx: Ctx, *types: str) -> dict:
    p = ctx.phase
    if p.get("type") not in types:
        raise RulesError(f"you can't do that right now (phase: {p.get('type')})")
    return p


@router.post("/games/{gid}/action")
async def submit_action(gid: str, body: ActionBody, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        if ctx.phase.get("type") == "combat" and ctx.encounter and ctx.encounter.get("mode") == "classic":
            flow.declare_combat(ctx, u.id, body.text)  # typed combat: the acting player's turn, resolved by the DM
            return None
        p = _need_phase(ctx, "exploration")
        if u.id not in ctx.required_users():
            if ctx.settings.get("input_mode") == "single":
                raise RulesError("the table speaker is acting for the party")
            raise RulesError("your character can't act right now")
        text = body.text.strip()
        travel = body.travel_to
        if travel is not None:
            if not isinstance(travel, dict) or not (travel.get("settlement_id") or ("q" in travel and "r" in travel)):
                raise RulesError("bad travel destination")
            travel = {k: travel[k] for k in ("settlement_id", "q", "r") if k in travel}
        rest = body.rest if body.rest in ("short", "long") else None
        if body.rest and not rest:
            raise RulesError("rest must be short or long")
        if not text and not travel and not rest:
            raise RulesError("describe what you do")
        from .game.state import iso, now as _now
        prev = p.setdefault("submissions", {}).get(u.id)
        p["submissions"][u.id] = {"text": text, "travel_to": travel, "rest": rest, "edited": bool(prev),
                                  "updated_at": iso(_now())}
        p["paused"] = False
        return {"resolve": True}
    return await mutate(gid, u, fn)


@router.delete("/games/{gid}/action")
async def withdraw_action(gid: str, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        p = _need_phase(ctx, "exploration")
        p.get("submissions", {}).pop(u.id, None)
    return await mutate(gid, u, fn)


class RollBody(BaseModel):
    roll_id: str


@router.post("/games/{gid}/roll")
async def make_roll(gid: str, body: RollBody, u: User = Depends(current_user)):
    from .dm.tools import roll_pending

    def fn(ctx: Ctx):
        p = _need_phase(ctx, "roll")
        r = next((r for r in p.get("pending_rolls", []) if r["id"] == body.roll_id), None)
        if not r:
            raise RulesError("no such roll")
        if r.get("result") is not None:
            raise RulesError("already rolled")
        if not ctx.can_control(u.id, r["character_id"]):
            raise RulesError("that's not your roll")
        roll_pending(ctx, r)
        return {"resolve": True, "return": {"result": r["result"]}}
    return await mutate(gid, u, fn)


class ReadyBody(BaseModel):
    ready: bool


@router.post("/games/{gid}/ready")
async def set_ready(gid: str, body: ReadyBody, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        p = _need_phase(ctx, "shop")
        ready = set(p.get("ready", []))
        ready.add(u.id) if body.ready else ready.discard(u.id)
        p["ready"] = sorted(ready)
        return {"resolve": body.ready}
    return await mutate(gid, u, fn)


class CharBodyBase(BaseModel):
    character_id: str | None = None


class BuyBody(BaseModel):
    key: str
    qty: int = Field(default=1, ge=1, le=100)
    character_id: str | None = None


class SellBody(BaseModel):
    item_id: str
    qty: int = Field(default=1, ge=1, le=100)
    character_id: str | None = None


@router.post("/games/{gid}/shop/buy")
async def shop_buy(gid: str, body: BuyBody, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        _need_phase(ctx, "shop")
        cid = ctx.resolve_char(u.id, body.character_id)
        shop = ctx.state.get("shop")
        if not shop:
            raise RulesError("no shop is open")
        s = ctx.chars[cid]
        r = shop_rules.buy(s, shop, body.key, body.qty, cid)
        msg = f"{s['name']} buys {r['name']}" + (f" ×{r['qty']}" if r["qty"] > 1 else "") + f" for {shop_rules.fmt_cp(r['cost_cp'])}" \
            + (f" ({r['effect']})" if r.get("effect") else "")
        shop.setdefault("transactions", []).append(msg)
        ctx.log("event", msg + ".")
        _unready(ctx, u.id)
    return await mutate(gid, u, fn)


@router.post("/games/{gid}/shop/sell")
async def shop_sell(gid: str, body: SellBody, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        _need_phase(ctx, "shop")
        cid = ctx.resolve_char(u.id, body.character_id)
        shop = ctx.state.get("shop")
        if not shop:
            raise RulesError("no shop is open")
        s = ctx.chars[cid]
        r = shop_rules.sell(s, shop, body.item_id, body.qty)
        msg = f"{s['name']} sells {r['name']}" + (f" ×{r['qty']}" if r["qty"] > 1 else "") + f" for {shop_rules.fmt_cp(r['price_cp'])}"
        shop.setdefault("transactions", []).append(msg)
        ctx.log("event", msg + ".")
        _unready(ctx, u.id)
    return await mutate(gid, u, fn)


@router.post("/games/{gid}/shop/haggle")
async def shop_haggle(gid: str, body: CharBodyBase | None = None, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        _need_phase(ctx, "shop")
        cid = ctx.resolve_char(u.id, (body or CharBodyBase()).character_id)
        shop = ctx.state.get("shop")
        if not shop:
            raise RulesError("no shop is open")
        loc = ctx.state.get("location") or {}
        size = "town"
        if loc.get("settlement_id") and ctx.world:
            st = next((x for x in ctx.world["settlements"] if x["id"] == loc["settlement_id"]), None)
            size = st["size"] if st else size
        s = ctx.chars[cid]
        r = shop_rules.haggle(s, shop, cid, size)
        d = r["discount"]
        outcome = (f"{int(-d * 100)}% off" if d < 0 else "no discount" if d == 0 else f"prices {int(d * 100)}% higher — the keeper took offence")
        ctx.log("roll", f"{s['name']} haggles with {shop.get('keeper') or 'the keeper'}: Persuasion {r['roll']['total']} vs DC {r['dc']} — {outcome}.",
                None, {"roll": r["roll"], "dc": r["dc"], "character_id": cid})
        shop.setdefault("transactions", []).append(f"{s['name']} haggled ({outcome})")
        return {"return": {"discount": d, "roll": r["roll"]["total"], "dc": r["dc"]}}
    return await mutate(gid, u, fn)


def _unready(ctx: Ctx, uid: str) -> None:
    p = ctx.phase
    if uid in p.get("ready", []):
        p["ready"] = [x for x in p["ready"] if x != uid]


class EquipBody(BaseModel):
    item_id: str
    equipped: bool
    character_id: str | None = None


class UseBody(BaseModel):
    item_id: str
    target_character_id: str | None = None
    character_id: str | None = None


class GiveBody(BaseModel):
    item_id: str
    qty: int = Field(default=1, ge=1, le=1000)
    to_character_id: str
    character_id: str | None = None


@router.post("/games/{gid}/inventory/equip")
async def equip(gid: str, body: EquipBody, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        if ctx.phase.get("type") == "combat":
            raise RulesError("you can't change equipment mid-fight")
        cid = ctx.resolve_char(u.id, body.character_id)
        ch.equip(ctx.chars[cid], body.item_id, body.equipped)
    return await mutate(gid, u, fn)


@router.post("/games/{gid}/inventory/use")
async def use_item(gid: str, body: UseBody, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        cid = ctx.resolve_char(u.id, body.character_id)
        s = ctx.chars[cid]
        it = ch.find_inv(s, body.item_id)
        rec = srd.item(it["key"]) or {}
        heal_dice = rec.get("heal") or (it.get("custom") or {}).get("heal")
        if not heal_dice:
            raise RulesError(f"{it['name']} can't be used like that — describe it in your action instead")
        target = body.target_character_id or cid
        if target not in ctx.chars:
            raise RulesError("unknown target")
        enc = ctx.encounter
        before = dict(enc["turn"]) if enc else None
        if ctx.phase.get("type") == "combat" and enc:
            combat.use_item_in_combat(enc, ctx.chars, f"pc-{cid}")
        healed = ch.heal(ctx.chars[target], dice.roll(heal_dice).total)
        ch.remove_item(s, it["id"], 1)
        tname = ctx.chars[target]["name"]
        ctx.log("combat" if enc else "event",
                f"{s['name']} uses {it['name']}" + (f" on {tname}" if target != cid else "") + f": +{healed} HP.")
        if enc and ctx.phase.get("type") == "combat":
            flow.after_combat_change(ctx, before)
    return await mutate(gid, u, fn)


@router.post("/games/{gid}/inventory/give")
async def give_item(gid: str, body: GiveBody, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        if ctx.phase.get("type") == "combat":
            raise RulesError("you can't hand things over mid-fight")
        cid = ctx.resolve_char(u.id, body.character_id)
        if body.to_character_id not in ctx.chars or body.to_character_id == cid:
            raise RulesError("pick another party member")
        src, dst = ctx.chars[cid], ctx.chars[body.to_character_id]
        it = ch.find_inv(src, body.item_id)
        qty = min(body.qty, it["qty"])
        ch.remove_item(src, it["id"], qty)
        ch.add_item(dst, it["key"], qty, custom=it.get("custom"))
        ctx.log("event", f"{src['name']} gives {it['name']}" + (f" ×{qty}" if qty > 1 else "") + f" to {dst['name']}.")
    return await mutate(gid, u, fn)


# ── combat ──────────────────────────────────────────────────────────────────

class CharBody(BaseModel):
    character_id: str | None = None


class MoveBody(CharBody):
    x: int
    y: int


class AttackBody(CharBody):
    attack_id: str
    target_id: str


class CastBody(CharBody):
    spell_index: str
    target_id: str | None = None
    slot_level: int | None = None
    x: int | None = None
    y: int | None = None


class FeatureBody(CharBody):
    feature_id: str
    target_id: str | None = None
    x: int | None = None
    y: int | None = None


class ActBody(CharBody):
    kind: str
    text: str | None = None


def _combat(gid: str, u: User, body: CharBody, op: Callable[[dict, dict, str], list]):
    def fn(ctx: Ctx):
        _need_phase(ctx, "combat")
        enc = ctx.encounter
        if not enc:
            raise RulesError("no fight is in progress")
        cid = ctx.resolve_char(u.id, body.character_id)
        before = dict(enc["turn"])
        lines = op(enc, ctx.chars, f"pc-{cid}")
        ctx.log_lines(lines)
        flow.after_combat_change(ctx, before)
    return mutate(gid, u, fn)


@router.post("/games/{gid}/combat/move")
async def combat_move(gid: str, body: MoveBody, u: User = Depends(current_user)):
    return await _combat(gid, u, body, lambda e, c, t: combat.move(e, c, t, body.x, body.y))


@router.post("/games/{gid}/combat/attack")
async def combat_attack(gid: str, body: AttackBody, u: User = Depends(current_user)):
    return await _combat(gid, u, body, lambda e, c, t: combat.attack(e, c, t, body.attack_id, body.target_id))


@router.post("/games/{gid}/combat/cast")
async def combat_cast(gid: str, body: CastBody, u: User = Depends(current_user)):
    return await _combat(gid, u, body, lambda e, c, t: combat.cast(e, c, t, body.spell_index, body.target_id,
                                                                    body.slot_level, body.x, body.y))


@router.post("/games/{gid}/combat/feature")
async def combat_feature(gid: str, body: FeatureBody, u: User = Depends(current_user)):
    return await _combat(gid, u, body, lambda e, c, t: combat.feature(e, c, t, body.feature_id, body.target_id, body.x, body.y))


# ── levelling & spell preparation ───────────────────────────────────────────

def _do_level_up(sheet: dict, body: dict) -> dict:
    if not ch.level_offer(sheet):
        raise RulesError("no level-up is available yet")
    return ch.level_up(sheet, body)


@router.post("/games/{gid}/level-up")
async def game_level_up(gid: str, body: dict, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        if ctx.phase.get("type") == "combat":
            raise RulesError("level up after the fight")
        cid = ctx.resolve_char(u.id, body.get("character_id"))
        s = ctx.chars[cid]
        r = _do_level_up(s, body)
        ctx.log("event", f"{s['name']} reaches level {r['level']}! (+{r['hp_gained']} HP)")
        return {"return": r}
    return await mutate(gid, u, fn)


def _own_free_char(db: Session, u: User, cid: str) -> Character:
    c = db.get(Character, cid)
    if not c or c.owner_id != u.id:
        raise HTTPException(404, "character not found")
    if c.game_id:
        g = db.get(Game, c.game_id)
        if g and g.status == "active":
            raise HTTPException(400, "that character is in an active game — do it from the game screen")
    return c


@router.post("/characters/{cid}/level-up")
def character_level_up(cid: str, body: dict, u: User = Depends(current_user), db: Session = Depends(get_db)):
    from sqlalchemy.orm.attributes import flag_modified
    c = _own_free_char(db, u, cid)
    sheet = dict(c.sheet)
    try:
        r = _do_level_up(sheet, body)
    except RulesError as e:
        raise HTTPException(400, str(e))
    c.sheet = sheet
    flag_modified(c, "sheet")
    db.commit()
    return {"ok": True, **r}


class PrepareBody(BaseModel):
    spells: list[str]
    character_id: str | None = None


@router.post("/games/{gid}/prepare")
async def game_prepare(gid: str, body: PrepareBody, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        if ctx.phase.get("type") == "combat":
            raise RulesError("prepare spells after the fight")
        cid = ctx.resolve_char(u.id, body.character_id)
        ch.prepare(ctx.chars[cid], body.spells)
    return await mutate(gid, u, fn)


@router.post("/characters/{cid}/prepare")
def character_prepare(cid: str, body: PrepareBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    from sqlalchemy.orm.attributes import flag_modified
    c = _own_free_char(db, u, cid)
    sheet = dict(c.sheet)
    try:
        ch.prepare(sheet, body.spells)
    except RulesError as e:
        raise HTTPException(400, str(e))
    c.sheet = sheet
    flag_modified(c, "sheet")
    db.commit()
    return {"ok": True}


@router.post("/games/{gid}/combat/act")
async def combat_act(gid: str, body: ActBody, u: User = Depends(current_user)):
    return await _combat(gid, u, body, lambda e, c, t: combat.act(e, c, t, body.kind, body.text))


@router.post("/games/{gid}/combat/end-turn")
async def combat_end_turn(gid: str, body: CharBody | None = None, u: User = Depends(current_user)):
    return await _combat(gid, u, body or CharBody(), lambda e, c, t: combat.end_turn(e, c, t))


# ── host controls ───────────────────────────────────────────────────────────

@router.post("/games/{gid}/force-resolve")
async def force_resolve(gid: str, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        _host(ctx, u)
        if ctx.phase.get("type") not in ("exploration", "roll", "shop", "combat"):
            raise RulesError("there's nothing to resolve right now")
        ctx.phase["paused"] = False
    res = await mutate(gid, u, fn)
    flow.spawn(flow.resolve(gid, forced=True))
    return res


class NudgeBody(BaseModel):
    user_id: str


@router.post("/games/{gid}/nudge")
async def nudge(gid: str, body: NudgeBody, u: User = Depends(current_user)):
    target = {}

    def fn(ctx: Ctx):
        _host(ctx, u)
        if not any(m.user_id == body.user_id for m in ctx.members):
            raise RulesError("that player isn't in this game")
        ctx.log("system", f"The host nudges {ctx.user_name(body.user_id)} — the party is waiting.")
        target["ctx"] = ctx
    res = await mutate(gid, u, fn, allow_busy=True)
    if target.get("ctx"):
        await send_nudge(target["ctx"], body.user_id)
        await hub.lobby_changed([body.user_id])
    return res


class InviteBody(BaseModel):
    email: str = Field(min_length=3, max_length=200)


@router.post("/games/{gid}/invite")
async def invite_by_email(gid: str, body: InviteBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    g = db.get(Game, gid)
    if not g:
        raise HTTPException(404, "game not found")
    m = db.scalar(select(Membership).where(Membership.game_id == gid, Membership.user_id == u.id))
    if not m or m.role == "spectator":
        raise HTTPException(403, "only players in this game can send invites")
    to = body.email.strip()
    if "@" not in to or " " in to or "\n" in to or "\r" in to:
        raise HTTPException(400, "that doesn't look like an email address")
    try:
        await notify.send_invite(g.id, g.name, u.display_name, g.invite_code, to, started=g.status != "lobby")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        log.warning("invite email failed: %s", e)
        raise HTTPException(502, "couldn't send the email — check the server's mail settings")
    return {"ok": True}


class AwayBody(BaseModel):
    until: str | None = None  # ISO time; null = back now; "indefinite" = until I come back


@router.post("/games/{gid}/away")
async def set_away(gid: str, body: AwayBody, u: User = Depends(current_user)):
    from datetime import datetime, timedelta, timezone

    def fn(ctx: Ctx):
        m = _member(ctx, u)
        if not m.character_id:
            raise RulesError("spectators can't go away — they just watch")
        if not body.until:
            m.away_until = None
            ctx.log("system", f"{ctx.user_name(u.id)} is back.")
            return {"resolve": True}
        if body.until == "indefinite":
            until = datetime.now(timezone.utc) + timedelta(days=365)
        else:
            try:
                until = datetime.fromisoformat(body.until.replace("Z", "+00:00"))
            except ValueError:
                raise RulesError("bad date")
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until <= datetime.now(timezone.utc):
                raise RulesError("pick a time in the future")
        m.away_until = until
        ctx.log("system", f"{ctx.user_name(u.id)} is away — the DM will play {ctx.chars[m.character_id]['name']} cautiously until they're back.")
        if ctx.phase.get("type") == "combat":
            flow.after_combat_change(ctx, dict(ctx.encounter["turn"]) if ctx.encounter else None)
        return {"resolve": True}
    return await mutate(gid, u, fn, allow_busy=True)


@router.get("/games/{gid}/log")
def game_log(gid: str, before_id: int | None = None, limit: int = 50, kinds: str | None = None,
             u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not db.scalar(select(Membership).where(Membership.game_id == gid, Membership.user_id == u.id)):
        raise HTTPException(403, "you're not in this game")
    q = select(LogEntry).where(LogEntry.game_id == gid)
    if before_id:
        q = q.where(LogEntry.id < before_id)
    if kinds:
        q = q.where(LogEntry.kind.in_([k.strip() for k in kinds.split(",") if k.strip()]))
    limit = max(1, min(200, limit))
    rows = list(db.scalars(q.order_by(LogEntry.id.desc()).limit(limit + 1)))
    return {"entries": [{"id": l.id, "ts": l.ts.isoformat() if l.ts else None, "kind": l.kind, "author": l.author,
                         "text": l.text, "data": l.data} for l in rows[:limit]], "has_more": len(rows) > limit}


class SeenBody(BaseModel):
    log_id: int


@router.post("/games/{gid}/seen")
def mark_seen(gid: str, body: SeenBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.scalar(select(Membership).where(Membership.game_id == gid, Membership.user_id == u.id))
    if not m:
        raise HTTPException(403, "you're not in this game")
    if not m.last_seen_id or body.log_id > m.last_seen_id:
        m.last_seen_id = body.log_id
        db.commit()
    return {"ok": True}


# ── table chat ──────────────────────────────────────────────────────────────
# Out-of-character talk between the people in a game. Stored apart from the story log, so the DM never sees it.

CHAT_MAX = 1000


def _chat_dict(c: ChatMessage) -> dict:
    return {"id": c.id, "user_id": c.user_id, "author": c.author, "text": "" if c.deleted else c.text,
            "ts": c.ts.isoformat() if c.ts else None, "edited": c.edited_at is not None, "deleted": bool(c.deleted)}


def _chat_member(db: Session, gid: str, u: User) -> Membership:
    m = db.scalar(select(Membership).where(Membership.game_id == gid, Membership.user_id == u.id))
    if not m:
        raise HTTPException(403, "you're not in this game")
    return m


def _chat_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        raise HTTPException(400, "type a message first")
    if len(t) > CHAT_MAX:
        raise HTTPException(400, f"keep messages under {CHAT_MAX} characters")
    return t


class ChatBody(BaseModel):
    text: str = Field(max_length=4000)


@router.get("/games/{gid}/chat")
def chat_list(gid: str, before_id: int | None = None, limit: int = 50,
              u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Newest messages, oldest first; pass before_id to page back through history."""
    _chat_member(db, gid, u)
    q = select(ChatMessage).where(ChatMessage.game_id == gid)
    if before_id:
        q = q.where(ChatMessage.id < before_id)
    limit = max(1, min(200, limit))
    rows = list(db.scalars(q.order_by(ChatMessage.id.desc()).limit(limit + 1)))
    msgs = [_chat_dict(c) for c in rows[:limit]]
    msgs.reverse()
    return {"messages": msgs, "has_more": len(rows) > limit}


@router.post("/games/{gid}/chat")
async def chat_post(gid: str, body: ChatBody, u: User = Depends(current_user)):
    db = SessionLocal()
    try:
        m = _chat_member(db, gid, u)
        if m.role == "spectator":
            raise HTTPException(403, "spectators can read the chat but not post")
        text = _chat_text(body.text)
        g = db.get(Game, gid)
        c = ChatMessage(game_id=gid, user_id=u.id, author=u.display_name, text=text)
        db.add(c)
        db.flush()
        m.last_chat_seen_id = c.id  # your own message counts as read
        db.commit()
        out = _chat_dict(c)
        member_ids = [x.user_id for x in db.scalars(select(Membership).where(Membership.game_id == gid))]
        game_name, live = g.name, bool((g.settings or {}).get("live"))
    finally:
        db.close()
    await hub.chat(gid, out)
    flow.spawn(notify.notify_chat(gid, game_name, live, u.id, u.display_name, text, member_ids, hub.watching(gid)))
    return out


def _own_chat(db: Session, gid: str, mid: int, u: User, allow_host: bool = False) -> ChatMessage:
    _chat_member(db, gid, u)
    c = db.get(ChatMessage, mid)
    if not c or c.game_id != gid or c.deleted:
        raise HTTPException(404, "message not found")
    if c.user_id != u.id:
        g = db.get(Game, gid)
        if not (allow_host and g and g.host_id == u.id):
            raise HTTPException(403, "you can only change your own messages")
    return c


@router.patch("/games/{gid}/chat/{mid}")
async def chat_edit(gid: str, mid: int, body: ChatBody, u: User = Depends(current_user)):
    db = SessionLocal()
    try:
        c = _own_chat(db, gid, mid, u)
        c.text = _chat_text(body.text)
        c.edited_at = datetime.now(timezone.utc)
        db.commit()
        out = _chat_dict(c)
    finally:
        db.close()
    await hub.chat(gid, out)
    return out


@router.delete("/games/{gid}/chat/{mid}")
async def chat_delete(gid: str, mid: int, u: User = Depends(current_user)):
    """Delete your own message (the host can remove anyone's). Leaves a "message deleted" placeholder."""
    db = SessionLocal()
    try:
        c = _own_chat(db, gid, mid, u, allow_host=True)
        c.deleted = True
        c.text = ""
        db.commit()
        out = _chat_dict(c)
    finally:
        db.close()
    await hub.chat(gid, out)
    return out


class ChatSeenBody(BaseModel):
    message_id: int


@router.post("/games/{gid}/chat/seen")
def chat_seen(gid: str, body: ChatSeenBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _chat_member(db, gid, u)
    if not m.last_chat_seen_id or body.message_id > m.last_chat_seen_id:
        m.last_chat_seen_id = body.message_id
        db.commit()
    return {"ok": True}


@router.post("/games/{gid}/recap")
async def recap(gid: str, u: User = Depends(current_user)):
    from .dm import engines as eng
    db = SessionLocal()
    try:
        try:
            ctx = load(db, gid)
        except RulesError:
            raise HTTPException(404, "game not found")
        m = _member(ctx, u)
        q = select(LogEntry).where(LogEntry.game_id == gid, LogEntry.kind.in_(["narration", "event", "action"]))
        if m.last_seen_id:
            q = q.where(LogEntry.id > m.last_seen_id)
        rows = list(db.scalars(q.order_by(LogEntry.id.desc()).limit(60)))
        rows.reverse()
        if not rows:
            return {"text": "You're all caught up."}
        lines = [f"- [{r.kind}{' · ' + r.author if r.author else ''}] {r.text[:700]}" for r in rows]
        # The players' story summary, never the DM's private notes (they hold the campaign's secrets).
        known = (ctx.state.get("story_summary") or {}).get("text") or "(none)"
        user = (f"Story summary so far: {known}\n\nWhat happened since the player last looked "
                f"(oldest first):\n" + "\n".join(lines))
        try:
            engine = flow._engine_for(ctx)
            text = await engine.summarize(eng.RECAP_SYSTEM, user)
        except eng.DMError as e:
            raise HTTPException(400, f"couldn't make a recap: {e}")
        return {"text": text}
    finally:
        db.close()


_story_locks: dict[str, asyncio.Lock] = {}
STORY_MAX_CHARS = 60000  # of new log text per update; older entries are already in the previous summary


@router.post("/games/{gid}/story")
async def story_summary(gid: str, u: User = Depends(current_user)):
    """The players' 'story so far': a summary the DM keeps up to date, rewritten when new narration comes in."""
    from .dm import engines as eng
    lock = _story_locks.setdefault(gid, asyncio.Lock())
    async with lock:  # two players opening the tab at once share one write-up
        db = SessionLocal()
        try:
            try:
                ctx = load(db, gid)
            except RulesError:
                raise HTTPException(404, "game not found")
            _member(ctx, u)
            cur = ctx.state.get("story_summary") or {}
            upto = cur.get("upto_id") or 0
            rows = list(db.scalars(select(LogEntry).where(
                LogEntry.game_id == gid, LogEntry.id > upto,
                LogEntry.kind.in_(["narration", "event", "action"])).order_by(LogEntry.id)))
            if not any(r.kind == "narration" for r in rows):
                return {"text": cur.get("text", ""), "updated_at": cur.get("updated_at"), "upto_id": upto}
            lines, size = [], 0
            for r in reversed(rows):
                line = f"- [{r.kind}{' · ' + r.author if r.author and r.kind != 'narration' else ''}] {r.text[:1500]}"
                size += len(line)
                if size > STORY_MAX_CHARS:
                    break
                lines.append(line)
            lines.reverse()
            user = (f"Your previous story-so-far:\n{cur.get('text') or '(none yet — this is the first one)'}"
                    f"\n\nWhat has happened since (oldest first):\n" + "\n".join(lines))
            try:
                text = (await flow._engine_for(ctx).summarize(eng.STORY_SYSTEM, user)).strip()
            except eng.DMError as e:
                raise HTTPException(400, f"couldn't write the story so far: {e}")
            if not text:
                raise HTTPException(400, "couldn't write the story so far: the DM returned nothing")
            new = {"text": text, "upto_id": rows[-1].id, "updated_at": datetime.now(timezone.utc).isoformat()}
        finally:
            db.close()
        async with lock_for(gid):
            db = SessionLocal()
            try:
                ctx = load(db, gid)
                ctx.state["story_summary"] = new
                ctx.save()
            finally:
                db.close()
        return new


@router.post("/games/{gid}/retry-dm")
async def retry(gid: str, u: User = Depends(current_user)):
    return await mutate(gid, u, lambda ctx: flow.retry_dm(ctx, u.id))


@router.patch("/games/{gid}/settings")
async def patch_settings(gid: str, body: dict, u: User = Depends(current_user)):
    def fn(ctx: Ctx):
        _host(ctx, u)
        editable = LIVE_EDITABLE if ctx.game.status != "lobby" else None
        new = clean_settings(body, ctx.settings, editable)
        if new.get("speaker_id") and not any(m.user_id == new["speaker_id"] for m in ctx.members):
            raise RulesError("the speaker must be a player in this game")
        if new["dm_engine"] == "api_key" and not ctx.db.get(User, ctx.game.host_id).api_key_enc:
            raise RulesError("save a Claude API key in Settings first")
        if new["dm_engine"] == "claude_code" and not claude_cli_available():
            raise RulesError("Claude Code isn't installed on this computer")
        was_live = ctx.settings.get("live")
        ctx.game.settings = new
        ctx.settings = new
        if bool(new.get("live")) != bool(was_live):
            ctx.log("system", "Live session started — everyone's at the table." if new.get("live")
                    else "Live session ended — back to playing on your own time.")
        if any(k.endswith("_minutes") or k == "live" for k in body):
            ctx.reset_deadline()
    return await mutate(gid, u, fn, allow_busy=True)


@router.post("/games/{gid}/tv-link")
async def tv_link(gid: str, request: Request, u: User = Depends(current_user)):
    out = {}

    def fn(ctx: Ctx):
        _host(ctx, u)
        tok = secrets.token_urlsafe(18)
        ctx.state["tv_token"] = tok
        out["tv_token"] = tok
        out["url"] = f"{str(request.base_url).rstrip('/')}/#/tv/{tok}"
        return {"return": out}
    return await mutate(gid, u, fn, allow_busy=True)


def _game_for_tv(db: Session, token: str) -> Game | None:
    if not token or len(token) < 16:
        return None
    for g in db.scalars(select(Game).where(Game.status != "ended")):
        if (g.state or {}).get("tv_token") == token:
            return g
    return None


@router.get("/tv/{token}/view")
def tv_view(token: str, db: Session = Depends(get_db)):
    g = _game_for_tv(db, token)
    if not g:
        raise HTTPException(404, "this TV link has expired")
    ctx = load(db, g.id)
    v = build_view(db, ctx, None, tv=True)
    v["game"]["invite_code"] = None
    return v


# ── websocket ───────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    db = SessionLocal()
    try:
        user = _user_from_token(db, ws.cookies.get(COOKIE))
        uid = user.id if user else None
    finally:
        db.close()
    conn = Conn(ws=ws, user_id=uid)
    hub.add(conn)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if "subscribe" in msg and uid:
                target = msg["subscribe"]
                if target == "lobby":
                    conn.lobby = True
                else:
                    db = SessionLocal()
                    try:
                        if db.scalar(select(Membership).where(Membership.game_id == target, Membership.user_id == uid)):
                            conn.games.add(target)
                            conn.member_games.add(target)
                    finally:
                        db.close()
            elif "subscribe_tv" in msg:
                db = SessionLocal()
                try:
                    g = _game_for_tv(db, str(msg["subscribe_tv"]))
                    if g:
                        conn.games.add(g.id)
                finally:
                    db.close()
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(conn)
