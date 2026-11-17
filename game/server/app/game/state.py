"""Loading a game into memory, saving it back, phases, and the per-user GameView."""
from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..models import Character, Game, LogEntry, Membership, User
from ..rules import character as ch
from ..rules import shop as shop_rules
from ..rules.character import RulesError
from ..world import hexmap
from ..world import scenemap
from .art import art_url
from . import combat

DEFAULT_SETTINGS = {
    "story_type": "sandbox", "tone": "heroic", "length": "short", "difficulty": "normal",
    "death_rule": "standard", "rest_rule": "standard", "starting_level": 1, "max_players": 4,
    "leveling": "xp", "magic_level": "standard", "economy": "standard", "sell_rate": 0.5, "ruleset": "2014",
    "rolls": "players", "combat_mode": "side", "narration_length": "medium", "content_limits": "",
    "round_timer_minutes": 1440, "combat_timer_minutes": None, "timeout_policy": "ai",
    "input_mode": "individual", "speaker_id": None, "live": False, "live_timer_minutes": 5,
    "dm_engine": "offline", "dm_model": "claude-opus-5-5", "discord_webhook": None,
    "ai_art": True,  # paint scenes and monsters with the host's Grok key, when they've saved one
}
ENUMS = {
    "story_type": {"dungeon_crawl", "mystery", "heist", "war", "horror", "wilderness", "intrigue", "seafaring", "sandbox"},
    "tone": {"heroic", "gritty", "dark", "lighthearted"}, "length": {"one_shot", "short", "open"},
    "difficulty": {"story", "normal", "hard", "deadly"}, "death_rule": {"heroic", "standard", "permadeath"},
    "rest_rule": {"standard", "gritty", "epic"}, "leveling": {"xp", "milestone"},
    "magic_level": {"low", "standard", "high"}, "economy": {"scarce", "standard", "rich"}, "ruleset": {"2014", "2024"},
    "rolls": {"players", "auto"}, "combat_mode": {"side", "classic"}, "narration_length": {"short", "medium", "long"},
    "timeout_policy": {"ai", "skip", "pause"}, "input_mode": {"individual", "single"},
    "dm_engine": {"offline", "claude_code", "api_key"}, "dm_model": {"claude-opus-5-5", "claude-sonnet-5-5"},
}
RANGES = {"starting_level": (1, 10), "max_players": (1, 6), "sell_rate": (0.1, 1.0),
          "round_timer_minutes": (5, 7200), "combat_timer_minutes": (5, 7200), "live_timer_minutes": (1, 60)}
LIVE_EDITABLE = {"round_timer_minutes", "combat_timer_minutes", "live", "live_timer_minutes", "input_mode", "speaker_id",
                 "timeout_policy", "rolls", "combat_mode", "narration_length", "dm_engine", "dm_model",
                 "discord_webhook", "content_limits", "ai_art"}

_locks: dict[str, asyncio.Lock] = {}


def lock_for(game_id: str) -> asyncio.Lock:
    if game_id not in _locks:
        _locks[game_id] = asyncio.Lock()
    return _locks[game_id]


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def parse_iso(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def clean_settings(raw: dict, base: dict | None = None, only: set | None = None) -> dict:
    out = dict(base or DEFAULT_SETTINGS)
    for k, v in (raw or {}).items():
        if k not in DEFAULT_SETTINGS or (only is not None and k not in only):
            continue
        if k in ENUMS:
            if v not in ENUMS[k]:
                raise RulesError(f"invalid value for {k}")
        elif k in RANGES:
            if v is None and k == "combat_timer_minutes":
                out[k] = None
                continue
            lo, hi = RANGES[k]
            try:
                v = type(lo)(v)
            except (TypeError, ValueError):
                raise RulesError(f"invalid value for {k}")
            if not lo <= v <= hi:
                raise RulesError(f"{k} must be between {lo} and {hi}")
        elif k in ("live", "ai_art"):
            v = bool(v)
        elif k in ("content_limits", "discord_webhook", "speaker_id"):
            v = (str(v)[:2000] if v else None) if k != "content_limits" else str(v or "")[:2000]
            if k == "discord_webhook" and v and not v.startswith("https://discord.com/api/webhooks/") \
                    and not v.startswith("https://discordapp.com/api/webhooks/"):
                raise RulesError("the Discord webhook must be a discord.com/api/webhooks URL")
        out[k] = v
    return out


class Ctx:
    """A game loaded into memory. Mutate freely, then call save()."""

    def __init__(self, db: Session, game: Game):
        self.db = db
        self.game = game
        self.settings: dict = {**DEFAULT_SETTINGS, **(game.settings or {})}
        self.state: dict = copy.deepcopy(game.state or {})
        self.world: dict | None = copy.deepcopy(game.world) if game.world else None
        self.summary: str = game.summary or ""
        self.members: list[Membership] = list(db.scalars(select(Membership).where(Membership.game_id == game.id)))
        self.users: dict[str, User] = {u.id: u for u in db.scalars(
            select(User).where(User.id.in_([m.user_id for m in self.members])))} if self.members else {}
        ids = [m.character_id for m in self.members if m.character_id]
        self.char_rows: dict[str, Character] = {c.id: c for c in db.scalars(
            select(Character).where(Character.id.in_(ids)))} if ids else {}
        self.chars: dict[str, dict] = {cid: copy.deepcopy(c.sheet) for cid, c in self.char_rows.items()}
        self.logs: list[tuple[str, str | None, str, dict | None]] = []
        self.notify_text: str | None = None

    # ── logging ──
    def log(self, kind: str, text: str, author: str | None = None, data: dict | None = None) -> None:
        if text:
            self.logs.append((kind, author, text, data))

    def log_lines(self, lines: list[dict]) -> None:
        for l in lines:
            self.log(l["kind"], l["text"], None, l.get("data"))

    # ── lookups ──
    @property
    def phase(self) -> dict:
        return self.state.setdefault("phase", {"id": 0, "type": "lobby"})

    @property
    def encounter(self) -> dict | None:
        return self.state.get("encounter")

    def party(self) -> list[tuple[str, dict]]:
        return [(m.character_id, self.chars[m.character_id]) for m in self.members
                if m.character_id and m.character_id in self.chars]

    def living_party(self) -> list[tuple[str, dict]]:
        return [(cid, s) for cid, s in self.party() if not s.get("dead")]

    def member_for_char(self, cid: str) -> Membership | None:
        return next((m for m in self.members if m.character_id == cid), None)

    def user_name(self, uid: str | None) -> str:
        u = self.users.get(uid or "")
        return u.display_name if u else "?"

    def speaker_id(self) -> str:
        sid = self.settings.get("speaker_id")
        if sid and any(m.user_id == sid for m in self.members):
            return sid
        return self.game.host_id

    def controls(self, uid: str | None) -> list[str]:
        if not uid:
            return []
        if self.settings.get("input_mode") == "single" and uid == self.speaker_id():
            return [cid for cid, _ in self.party()]
        m = next((m for m in self.members if m.user_id == uid), None)
        return [m.character_id] if m and m.character_id else []

    def can_control(self, uid: str, cid: str) -> bool:
        return cid in self.controls(uid)

    def resolve_char(self, uid: str, cid: str | None) -> str:
        cid = cid or next((m.character_id for m in self.members if m.user_id == uid), None)
        if not cid or not self.can_control(uid, cid):
            raise RulesError("you can't act for that character")
        return cid

    def find_char_by_name(self, name: str) -> str | None:
        key = (name or "").strip().lower()
        if not key:
            return None
        for cid, s in self.party():
            n = s["name"].lower()
            if n == key or n.split()[0] == key.split()[0]:
                return cid
        return None

    def is_away(self, m: Membership) -> bool:
        if not m.away_until:
            return False
        au = m.away_until if m.away_until.tzinfo else m.away_until.replace(tzinfo=timezone.utc)
        return au > now()

    def away_chars(self) -> list[str]:
        """Characters whose players are on vacation (the AI plays them)."""
        if self.settings.get("input_mode") == "single":
            return []
        return [m.character_id for m in self.members if m.character_id and self.is_away(m)
                and m.character_id in self.chars and not self.chars[m.character_id].get("dead")]

    def required_users(self) -> list[str]:
        """Who must act for the current phase to resolve early."""
        if self.settings.get("input_mode") == "single":
            return [self.speaker_id()]
        out = []
        for m in self.members:
            s = self.chars.get(m.character_id or "")
            if s and not s.get("dead") and not self.is_away(m):
                out.append(m.user_id)
        return out

    # ── phases ──
    def timer_minutes(self, ptype: str) -> int:
        st = self.settings
        if st.get("live"):
            return int(st.get("live_timer_minutes") or 5)
        if ptype == "combat" and st.get("combat_timer_minutes"):
            return int(st["combat_timer_minutes"])
        return int(st.get("round_timer_minutes") or 1440)

    def open_phase(self, ptype: str, prompt: str | None = None, **extra) -> dict:
        pid = self.phase.get("id", 0) + 1
        opened = now()
        deadline = None if ptype in ("dm", "lobby", "ended") else opened + timedelta(minutes=self.timer_minutes(ptype))
        self.state["phase"] = {"id": pid, "type": ptype, "prompt": prompt, "opened_at": iso(opened),
                               "deadline": iso(deadline), "submissions": {}, "ready": [], "pending_rolls": [],
                               "error": None, **extra}
        return self.state["phase"]

    def reset_deadline(self) -> None:
        if self.phase.get("type") in ("dm", "lobby", "ended"):
            return
        self.phase["deadline"] = iso(now() + timedelta(minutes=self.timer_minutes(self.phase["type"])))

    def waiting_on(self) -> list[str]:
        p = self.phase
        t = p.get("type")
        req = self.required_users()
        if t == "exploration":
            return [u for u in req if u not in p.get("submissions", {})]
        if t == "shop":
            return [u for u in req if u not in p.get("ready", [])]
        if t == "roll":
            pending = [r for r in p.get("pending_rolls", []) if r.get("result") is None]
            if self.settings.get("input_mode") == "single":
                return [self.speaker_id()] if pending else []
            return sorted({r["user_id"] for r in pending if r["user_id"] in req})
        if t == "combat" and self.encounter:
            enc = self.encounter
            out = []
            away = set(self.away_chars())
            for cid, _ in self.living_party():
                if cid in away:
                    continue
                if combat.can_act(enc, f"pc-{cid}", self.chars):
                    m = self.member_for_char(cid)
                    who = self.speaker_id() if self.settings.get("input_mode") == "single" else (m.user_id if m else None)
                    if who and who not in out:
                        out.append(who)
            return out
        return []

    def their_call(self, uid: str) -> list[str]:
        """Exploration: names of the characters the DM's question is for, when it isn't for this player's
        character. Everyone is still asked; this only labels the round as someone else's call."""
        p = self.phase
        if p.get("type") != "exploration" or not p.get("spotlight") or self.settings.get("input_mode") == "single":
            return []
        mine = {m.character_id for m in self.members if m.user_id == uid}
        if mine & set(p["spotlight"]):
            return []
        return [self.chars[c]["name"] for c in p["spotlight"] if c in self.chars]

    # ── persistence ──
    def save(self) -> None:
        game = self.db.get(Game, self.game.id)
        game.state = self.state
        flag_modified(game, "state")
        game.world = self.world
        flag_modified(game, "world")
        game.summary = self.summary
        for cid, sheet in self.chars.items():
            row = self.db.get(Character, cid)
            if row:
                row.sheet = sheet
                row.name = sheet.get("name", row.name)
                flag_modified(row, "sheet")
        for kind, author, text, data in self.logs:
            self.db.add(LogEntry(game_id=game.id, kind=kind, author=author, text=text[:20000], data=data))
        self.logs = []
        self.db.commit()
        self.game = game


def load(db: Session, game_id: str) -> Ctx:
    game = db.get(Game, game_id)
    if not game:
        raise RulesError("game not found")
    db.refresh(game)
    return Ctx(db, game)


# ── view ────────────────────────────────────────────────────────────────────

def build_view(db: Session, ctx: Ctx, uid: str | None, tv: bool = False) -> dict:
    game = ctx.game
    p = ctx.phase
    is_host = uid == game.host_id
    my_member = next((m for m in ctx.members if m.user_id == uid), None)
    controls = ctx.controls(uid)
    waiting = ctx.waiting_on()
    members = []
    for m in ctx.members:
        acted = m.user_id not in waiting and p.get("type") in ("exploration", "shop", "roll", "combat")
        members.append({"user_id": m.user_id, "display_name": ctx.user_name(m.user_id), "character_id": m.character_id,
                        "role": m.role, "has_acted": acted, "ready": m.user_id in p.get("ready", []),
                        "away_until": iso(m.away_until) if ctx.is_away(m) else None})
    last_seen = my_member.last_seen_id if my_member else None
    unseen = 0
    if my_member:
        from sqlalchemy import func
        q = select(func.count(LogEntry.id)).where(LogEntry.game_id == game.id, LogEntry.kind.in_(["narration", "event"]))
        if last_seen:
            q = q.where(LogEntry.id > last_seen)
        unseen = db.scalar(q) or 0
    chat_unseen = 0
    if my_member and not tv:
        from ..models import ChatMessage
        q = select(func.count(ChatMessage.id)).where(ChatMessage.game_id == game.id, ChatMessage.deleted.is_(False),
                                                     ChatMessage.user_id.is_distinct_from(uid))
        if my_member.last_chat_seen_id:
            q = q.where(ChatMessage.id > my_member.last_chat_seen_id)
        chat_unseen = db.scalar(q) or 0
    chars = {cid: ch.view(cid, ctx.char_rows[cid].owner_id, game.id, s) for cid, s in ctx.chars.items()}
    enc0 = ctx.encounter
    if enc0:  # combat-only actions (e.g. an active Spiritual Weapon)
        for t in enc0["tokens"].values():
            if t["kind"] == "pc" and t.get("spiritual_weapon") and t["character_id"] in chars:
                chars[t["character_id"]]["actions"].append({
                    "id": "spiritual_weapon", "name": "Spiritual Weapon attack", "kind": "bonus",
                    "description": "Your spectral weapon strikes an enemy within 60 ft.", "target": "enemy",
                    "range_ft": 60, "uses": None, "available": True})
    subs = p.get("submissions", {})
    phase = {
        "id": p.get("id", 0), "type": p.get("type", "lobby"), "prompt": p.get("prompt"),
        "opened_at": p.get("opened_at"), "deadline": p.get("deadline"), "waiting_on": waiting,
        "my_submission": subs.get(uid) if uid else None,
        "submissions_visible": [{"user_id": k, "text": v.get("text"), "travel_to": v.get("travel_to"), "rest": v.get("rest"),
                                 "edited": bool(v.get("edited")), "updated_at": v.get("updated_at")}
                                for k, v in subs.items()],
        "pending_rolls": p.get("pending_rolls", []), "error": p.get("error"),
        "spotlight": [ctx.chars[c]["name"] for c in p.get("spotlight") or [] if c in ctx.chars],
        "their_call": ctx.their_call(uid) if uid else [],
    }
    world = hexmap.view(ctx.world) if ctx.world else None
    enc = ctx.encounter
    shop = ctx.state.get("shop") if p.get("type") == "shop" or tv else None
    logs = list(db.scalars(select(LogEntry).where(LogEntry.game_id == game.id).order_by(LogEntry.id.desc()).limit(150)))
    logs.reverse()
    tv_token = ctx.state.get("tv_token")
    return {
        "game": {"id": game.id, "name": game.name, "status": game.status, "invite_code": game.invite_code,
                 "host_id": game.host_id, "settings": _public_settings(ctx.settings, is_host),
                 "created_at": iso(game.created_at)},
        "me": {"user_id": uid, "character_id": my_member.character_id if my_member else None, "is_host": is_host,
               "is_speaker": bool(uid) and ctx.settings.get("input_mode") == "single" and uid == ctx.speaker_id(),
               "controls": controls, "role": my_member.role if my_member else None,
               "last_seen_id": last_seen, "unseen_count": unseen,
               "last_chat_seen_id": my_member.last_chat_seen_id if my_member else None, "chat_unseen": chat_unseen},
        "plot": ({"name": ctx.state["plot"].get("name"), "entry_id": ctx.state["plot"].get("entry_id")}
                 if is_host and ctx.state.get("plot") else None),  # the plot itself stays DM-only
        "has_plot": bool(ctx.state.get("plot")),
        "tv_url": f"/#/tv/{tv_token}" if (is_host and tv_token) else None,
        "members": members,
        "characters": chars,
        "phase": phase,
        "world": world,
        "location": ctx.state.get("location") or {"name": "", "settlement_id": None, "description": ""},
        "scene": ctx.state.get("scene") or {"type": "town", "time_of_day": "morning", "weather": "clear", "day": 1, "hour": 8},
        "encounter": combat.view(enc, ctx.chars, controls) if enc else None,
        "scene_art": art_url((ctx.state.get("scene_art") or {}).get("name")),
        "scene_map": scenemap.view(ctx.state["scene_map"], ctx.party(), my_member.character_id if my_member else None)
                     if ctx.state.get("scene_map") else None,
        "shop": shop_rules.stock_view(shop) if shop else None,
        "npcs": ctx.state.get("npcs", []),
        "quests": ctx.state.get("quests", []),
        "log": [{"id": l.id, "ts": iso(l.ts), "kind": l.kind, "author": l.author, "text": l.text, "data": l.data}
                for l in logs],
        "dm": {"engine": ctx.settings.get("dm_engine"), "model": ctx.settings.get("dm_model"), "busy": bool(game.dm_busy)},
    }


def _public_settings(s: dict, is_host: bool) -> dict:
    out = dict(s)
    if not is_host:
        out["discord_webhook"] = None
    return out
