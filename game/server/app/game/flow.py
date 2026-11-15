"""The turn engine: phases, deadlines, round resolution and DM calls.

Pattern for every phase: it opens with a deadline → players act or mark ready → it resolves
when everyone required is done, the deadline passes (timeout policy applies), or the host forces it.
Resolving usually queues a DM call; while the DM writes, the phase is "dm" and actions are refused.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import timedelta

from sqlalchemy import select

from ..config import DEFAULT_MODEL
from ..db import SessionLocal
from ..dm import engines, prompt
from ..dm.tools import TOOLS, ToolBox, do_travel, rest_party, roll_pending
from ..rules import loot
from ..rules import shop as shop_rules
from ..rules import srd


def srd_name(index: str) -> str:
    return srd.monsters().get(index, {}).get("name", index)
from ..models import DMCall, Game, LogEntry, User
from ..rules import character as ch
from ..rules.character import RulesError
from ..rules.rulesets import R
from ..security import decrypt_secret
from ..world import hexmap
from . import combat, turns
from .hub import hub
from .notify import notify_phase
from .state import Ctx, iso, load, lock_for, now, parse_iso

log = logging.getLogger("game.flow")

_tasks: set[asyncio.Task] = set()


def spawn(coro) -> None:
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def changed(ctx_or_id, lobby_users: list[str] | None = None) -> None:
    gid = ctx_or_id if isinstance(ctx_or_id, str) else ctx_or_id.game.id
    await hub.game_changed(gid)
    if lobby_users is None and not isinstance(ctx_or_id, str):
        lobby_users = [m.user_id for m in ctx_or_id.members]
    if lobby_users:
        await hub.lobby_changed(lobby_users)


# ── starting ────────────────────────────────────────────────────────────────

def start_game(ctx: Ctx, uid: str) -> None:
    g = ctx.game
    if g.host_id != uid:
        raise RulesError("only the host can start the game")
    if g.status != "lobby":
        raise RulesError("the game has already started")
    if not ctx.party():
        raise RulesError("at least one player needs a character")
    seed = random.randrange(1 << 30)
    ctx.world = hexmap.generate(seed)
    start = next(s for s in ctx.world["settlements"] if s["q"] == ctx.world["party"]["q"] and s["r"] == ctx.world["party"]["r"])
    start["known"] = True
    ctx.state["location"] = {"name": start["name"], "settlement_id": start["id"], "description": ""}
    ctx.state["scene"] = {"type": "town", "time_of_day": "morning", "weather": "clear", "day": 1, "hour": 8}
    lvl = int(ctx.settings.get("starting_level", 1))
    for _, s in ctx.party():
        while s["level"] < min(lvl, R(s).MAX_LEVEL):
            ch.level_up(s, ch.auto_choices(s))
        s["xp"] = max(s.get("xp", 0), R(s).XP_THRESHOLDS[s["level"]])
        s["level_target"] = max(s.get("level_target", 1), s["level"])
    g.status = "active"
    names = ", ".join(s["name"] for _, s in ctx.party())
    ctx.log("system", f"The adventure begins. Party: {names}.")
    queue_dm(ctx, "opening",
             "Open the campaign. Introduce the starting settlement and set up the story type for this game, with a bang "
             "aimed at the party. Use name_place to give 2-4 key places names and descriptions that fit the story, "
             "record the first quest (upsert_quest) and any NPC you introduce (upsert_npc), and write the first "
             "update_summary with the campaign's hidden premise so you can stay consistent later.")


def queue_dm(ctx: Ctx, reason: str, body: str) -> None:
    restore = dict(ctx.phase)
    ctx.state["pending_dm"] = {"reason": reason, "body": body, "restore_phase": restore}
    ctx.open_phase("dm")
    spawn(run_dm(ctx.game.id))


# ── resolution ──────────────────────────────────────────────────────────────

def _char_label(ctx: Ctx, cid: str) -> str:
    s = ctx.chars[cid]
    m = ctx.member_for_char(cid)
    return f"{s['name']} ({ctx.user_name(m.user_id) if m else '?'})"


async def resolve(game_id: str, forced: bool = False) -> None:
    async with lock_for(game_id):
        db = SessionLocal()
        try:
            ctx = load(db, game_id)
            if ctx.game.status != "active" or ctx.game.dm_busy:
                return
            p = ctx.phase
            t = p.get("type")
            if t in ("dm", "lobby", "ended", None):
                return
            waiting = ctx.waiting_on()
            deadline = parse_iso(p.get("deadline"))
            overdue = bool(deadline and now() >= deadline)
            if waiting and not forced and not overdue:
                return
            policy = ctx.settings.get("timeout_policy", "ai")
            if waiting and policy == "pause" and not forced:
                if not p.get("paused"):
                    p["paused"] = True
                    ctx.log("system", "The deadline passed. The game is paused until everyone acts "
                                      "(the host can force the round).")
                    ctx.save()
                    await changed(ctx)
                return
            eff_policy = "skip" if (forced and policy == "pause") else policy
            if t == "exploration":
                _resolve_exploration(ctx, waiting, eff_policy)
            elif t == "roll":
                _resolve_rolls(ctx)
            elif t == "shop":
                _resolve_shop(ctx)
            elif t == "combat":
                _resolve_combat_timeout(ctx, eff_policy)
            ctx.save()
            await changed(ctx)
        finally:
            db.close()


def _resolve_exploration(ctx: Ctx, waiting: list[str], policy: str) -> None:
    p = ctx.phase
    subs: dict = p.get("submissions", {})
    single = ctx.settings.get("input_mode") == "single"
    lines = ["Player actions this round:"]
    for uid, sub in subs.items():
        text = (sub.get("text") or "").strip()
        if single:
            who = f"The whole party (typed by {ctx.user_name(uid)})"
            ctx.log("action", text or "(travel)", f"Party · {ctx.user_name(uid)}")
        else:
            cid = next((m.character_id for m in ctx.members if m.user_id == uid), None)
            if not cid:
                continue
            who = _char_label(ctx, cid)
            ctx.log("action", text or "(travel)", ctx.chars[cid]["name"])
        dest = sub.get("travel_to")
        rest = sub.get("rest")
        lines.append(f"- {who}: {text or '(no words — see travel/rest)'}"
                     + (f" [wants to travel to {_dest_name(ctx, dest)}]" if dest else "")
                     + (f" [wants a {rest} rest]" if rest else ""))
    if not single:
        for uid in waiting:
            cid = next((m.character_id for m in ctx.members if m.user_id == uid), None)
            if not cid:
                continue
            note = ("didn't act in time — play them cautiously and in character (they follow the party's lead)"
                    if policy == "ai" else "holds back this round and does nothing notable")
            lines.append(f"- {_char_label(ctx, cid)}: ({note})")
        for cid in ctx.away_chars():
            lines.append(f"- {_char_label(ctx, cid)}: (their player is away — play them cautiously and in character, "
                         f"following the party's lead; never put words in their mouth beyond small talk)")
    # travel by majority vote
    votes: dict[str, int] = {}
    dests: dict[str, dict] = {}
    for sub in subs.values():
        d = sub.get("travel_to")
        if d:
            key = d.get("settlement_id") or f"{d.get('q')},{d.get('r')}"
            votes[key] = votes.get(key, 0) + 1
            dests[key] = d
    if votes:
        key, n = max(votes.items(), key=lambda kv: kv[1])
        need = 1 if single else len(ctx.required_users()) // 2 + 1
        if n >= need:
            try:
                result = do_travel(ctx, _dest_coords(ctx, dests[key]))
                lines.append("")
                lines.append(f"Travel (already resolved by the game): {result}")
                lines.append("Narrate the journey briefly and the arrival with a bang.")
            except RulesError as e:
                lines.append(f"(Travel failed: {e})")
        else:
            lines.append(f"(Travel vote not passed: {n} of {need} needed.)")
    # rest by majority vote
    rvotes: dict[str, int] = {}
    for sub in subs.values():
        if sub.get("rest") in ("short", "long"):
            rvotes[sub["rest"]] = rvotes.get(sub["rest"], 0) + 1
    if rvotes:
        kind, n = max(rvotes.items(), key=lambda kv: (kv[1], kv[0] == "long"))
        need = 1 if single else len(ctx.required_users()) // 2 + 1
        if n >= need:
            loc = ctx.state.get("location") or {}
            wild = not loc.get("settlement_id")
            interrupted = kind == "long" and wild and random.random() < 0.25 and ctx.living_party()
            if interrupted:
                levels = [s["level"] for _, s in ctx.living_party()]
                biome = hexmap.biome_at(ctx.world, ctx.world["party"]["q"], ctx.world["party"]["r"]) if ctx.world else "."
                from ..rules import xp as xp_rules
                specs = xp_rules.random_encounter(levels, ctx.settings.get("difficulty", "normal"), biome)
                names = ", ".join(f"{c} × {srd_name(i)}" for i, c in specs)
                result = rest_party(ctx, "short")
                lines.append("")
                lines.append(f"Rest (resolved by the game): the long rest is interrupted after an hour — {names} find the camp. "
                             f"Everyone only got a short rest ({result}). Stage the interruption and call start_combat "
                             f"with terrain 'camp' if it comes to blows.")
            else:
                result = rest_party(ctx, kind)
                lines.append("")
                lines.append(f"Rest (already resolved by the game): the party takes a {kind} rest. {result}. "
                             f"Narrate the rest briefly and what greets them after.")
        else:
            lines.append(f"(Rest vote not passed: {n} of {need} needed.)")
    lines.append("")
    lines.append("Resolve these actions: call roll_check where outcomes are uncertain, apply consequences with tools, "
                 "then narrate.")
    queue_dm(ctx, "round", "\n".join(lines))


def _dest_name(ctx: Ctx, d: dict) -> str:
    w = ctx.world
    if d.get("settlement_id"):
        s = next((s for s in w["settlements"] if s["id"] == d["settlement_id"]), None)
        return s["name"] if s else "?"
    q, r = int(d.get("q", 0)), int(d.get("r", 0))
    st = hexmap.settlement_at(w, q, r) or hexmap.poi_at(w, q, r)
    return st["name"] if st else f"hex ({q},{r}), {hexmap.BIOME_NAMES[hexmap.biome_at(w, q, r)]}"


def _dest_coords(ctx: Ctx, d: dict) -> tuple[int, int]:
    if d.get("settlement_id"):
        s = next((s for s in ctx.world["settlements"] if s["id"] == d["settlement_id"]), None)
        if not s:
            raise RulesError("unknown settlement")
        return s["q"], s["r"]
    q, r = int(d["q"]), int(d["r"])
    if not (0 <= q < ctx.world["w"] and 0 <= r < ctx.world["h"]):
        raise RulesError("that hex is off the map")
    return q, r


def _resolve_rolls(ctx: Ctx) -> None:
    p = ctx.phase
    lines = ["Roll results:"]
    combat_rolls = False
    for r in p.get("pending_rolls", []):
        if r.get("result") is None:
            roll_pending(ctx, r)
            r["auto"] = True
        res = r["result"]
        late = " (rolled automatically — the player missed the deadline)" if r.get("auto") else ""
        if r.get("combat"):
            combat_rolls = True
            lines.append(f"- {r['label']}{late}, resolved by the game: " + " ".join(res.get("lines") or []))
            continue
        verdict = "" if res.get("success") is None else (" — SUCCESS" if res["success"] else " — FAILURE")
        lines.append(f"- {r['label']}: {res['total']} (d20 {res.get('natural')}{res['modifier']:+d}) vs DC {r['dc']}{verdict}{late}")
    enc = ctx.encounter
    if enc and enc.get("queue"):  # steps left after the last roll (shouldn't happen, but never leave them hanging)
        _, rest = turns.execute_through(enc, ctx.chars, "")
        ctx.log_lines(rest)
    if enc and combat.check_end(enc, ctx.chars):
        _finish_combat(ctx, enc["outcome"])
        return
    lines.append("")
    if enc and enc.get("declared"):
        actor = enc["tokens"].get(enc["declared"]["tid"], {}).get("name", "the character")
        lines.append(f"Narrate what these results mean for {actor}'s turn (exactly these hits, misses and damage). If "
                     f"their declared action has more to it, resolve that too; then call combat_end_turn and narrate what "
                     f"the enemies do next.")
    else:
        lines.append("Narrate what these results mean, applying consequences with tools.")
    queue_dm(ctx, "combat_rolls" if combat_rolls else "rolls", "\n".join(lines))


def declare_combat(ctx: Ctx, uid: str, text: str) -> None:
    """A player types what their character does on their combat turn; the DM resolves it."""
    enc = ctx.encounter
    if not enc or enc.get("outcome"):
        raise RulesError("no fight is in progress")
    t = turns.actor(enc, ctx.chars)
    if not t:
        raise RulesError("it isn't a player's turn yet")
    if not ctx.can_control(uid, t["character_id"]):
        raise RulesError(f"it's {t['name']}'s turn")
    text = text.strip()[:1000]
    if not text:
        raise RulesError("describe what you do")
    enc["declared"] = {"tid": t["id"], "text": text}
    ctx.log("action", text, f"{t['name']} · {ctx.user_name(uid)}")
    body = _combat_turn_body(ctx, t["id"], f"{t['name']}'s player says: \"{text}\"")
    queue_dm(ctx, "combat_turn", body)


def _combat_turn_body(ctx: Ctx, tid: str, declared: str) -> str:
    enc = ctx.encounter
    since = enc.get("round_log") or []
    parts = []
    if since:
        parts.append("Since your last narration (already resolved by the game):")
        parts += [f"- {ln}" for ln in since[-30:]]
        parts.append("")
    parts.append(f"Round {enc['round']}. {declared}")
    parts.append("")
    parts.append(turns.brief(enc, ctx.chars, tid))
    parts.append("")
    parts.append(
        "Resolve this turn with the combat tools, in the order it happens. Interpret the player's words generously but "
        "by the rules: movement up to their speed, one action (Attack = their listed number of weapon attacks), one bonus "
        "action if a feature or spell gives one, free object interactions. If they ask for more than a turn allows, "
        "resolve what fits and say what didn't. Improvised actions (shove, grapple, swing from the chandelier, throw sand) "
        "are combat_action 'other' plus roll_check/apply_damage/add_condition as you rule. If the player's rolls are "
        "needed, narrate up to the moment of the roll and stop; you'll get the results. If nothing needs a roll, narrate "
        "the outcome, call combat_end_turn, and narrate what the enemies do next. If the action is unclear or "
        "impossible and you changed nothing, say so in character and ask them again — their turn stays open.")
    return "\n".join(parts)


def _auto_combat_turns(ctx: Ctx, policy: str, only_away: bool) -> bool:
    """Play the turns of characters whose players missed the deadline (or are away). Returns True if a DM
    narration was queued (or the fight ended)."""
    enc = ctx.encounter
    if not enc:
        return False
    away = set(ctx.away_chars())
    played = False
    for _ in range(len(enc["order"]) * 2 + 2):
        t = turns.actor(enc, ctx.chars)
        if not t or enc.get("queue"):
            break
        if only_away and t["character_id"] not in away:
            break
        pol = "ai" if t["character_id"] in away else policy
        enc.pop("declared", None)
        ctx.log_lines(combat.auto_turn(enc, ctx.chars, t["id"], pol))
        ctx.log_lines(combat.advance(enc, ctx.chars))
        enc.pop("round_complete", None)
        played = True
        if combat.check_end(enc, ctx.chars):
            break
        if not only_away:
            policy, only_away = policy, True  # after the late player's turn, keep going only for away players
    if not played:
        return False
    if combat.check_end(enc, ctx.chars):
        _finish_combat(ctx, enc["outcome"])
        return True
    nxt = turns.actor(enc, ctx.chars)
    body = ["What happened (already resolved by the game):"] + [f"- {ln}" for ln in (enc.get("round_log") or [])[-30:]]
    body.append("")
    body.append("Narrate this briefly (exactly these results)" + (f", and end by turning to {nxt['name']}: what do they do?"
                                                                   if nxt else "."))
    queue_dm(ctx, "combat_auto", "\n".join(body))
    return True


def _resolve_shop(ctx: Ctx) -> None:
    shop = ctx.state.get("shop") or {}
    tx = shop.get("transactions", [])
    lines = [f"The party has finished at {shop.get('name', 'the shop')} ({shop.get('keeper', '')})."]
    if tx:
        lines.append("What they did: " + "; ".join(tx[-30:]) + ".")
    else:
        lines.append("They browsed but bought and sold nothing.")
    rooms = [c for c in shop.get("rooms", []) if c in ctx.chars]
    if rooms:
        lines.append("Rooms paid for (already resolved): " + rest_party(ctx, "long", rooms) + ".")
    lines.append("Briefly narrate leaving the shop (a line from the keeper is welcome), then move the story on.")
    ctx.state["shop"] = None
    queue_dm(ctx, "shop_done", "\n".join(lines))


def _resolve_combat_timeout(ctx: Ctx, policy: str) -> None:
    enc = ctx.encounter
    if not enc:
        ctx.open_phase("exploration", ctx.phase.get("prompt"))
        return
    if enc.get("mode") == "classic":  # typed combat: the late player's character acts (AI or Dodge), then narrate
        if not _auto_combat_turns(ctx, "ai" if policy == "ai" else "skip", only_away=False):
            ctx.reset_deadline()
        return
    for cid, _ in ctx.living_party():
        tid = f"pc-{cid}"
        if combat.can_act(enc, tid, ctx.chars):
            ctx.log_lines(combat.auto_turn(enc, ctx.chars, tid, "ai" if policy == "ai" else "skip"))
            ctx.log_lines(combat.advance(enc, ctx.chars))
    after_combat_change(ctx, enc["turn"].copy())


def play_away(ctx: Ctx) -> None:
    """The AI takes combat turns for characters whose players are on vacation."""
    enc = ctx.encounter
    if not enc:
        return
    away = ctx.away_chars()
    for _ in range(len(away) * 3 + 3):
        acted = False
        for cid in away:
            tid = f"pc-{cid}"
            if not enc.get("outcome") and combat.can_act(enc, tid, ctx.chars):
                ctx.log_lines(combat.auto_turn(enc, ctx.chars, tid, "ai"))
                ctx.log_lines(combat.advance(enc, ctx.chars))
                acted = True
        if not acted:
            break


def after_combat_change(ctx: Ctx, turn_before: dict | None = None) -> None:
    """After any combat change: end the fight, narrate a finished round, or keep going."""
    enc = ctx.encounter
    if not enc:
        return
    if not combat.check_end(enc, ctx.chars) and not enc.get("round_complete"):
        play_away(ctx)
    outcome = combat.check_end(enc, ctx.chars)
    if outcome:
        _finish_combat(ctx, outcome)
        return
    if enc.pop("round_complete", False):
        body = ["Combat log for the round just played (already resolved by the game):"]
        body += [f"- {l}" for l in enc.get("round_log", [])[-40:]]
        if enc.get("custom_actions"):
            body.append("")
            body.append("Custom actions players declared (resolve each with roll_check/apply_damage/add_condition as needed):")
            body += [f"- {a['name']}: {a['text']}" for a in enc["custom_actions"]]
        body.append("")
        body.append(f"Narrate this round vividly but briefly (about 80-140 words). The fight continues into round {enc['round']}.")
        enc["round_log"] = []
        enc["custom_actions"] = []
        queue_dm(ctx, "combat_round", "\n".join(body))
        return
    if turn_before is not None and turn_before != enc["turn"]:
        ctx.reset_deadline()


def _finish_combat(ctx: Ctx, outcome: str) -> None:
    enc = ctx.encounter
    body = ["Final combat log (already resolved by the game):"]
    body += [f"- {l}" for l in enc.get("round_log", [])[-40:]]
    if enc.get("custom_actions"):
        body += [f"- (custom) {a['name']}: {a['text']}" for a in enc["custom_actions"]]
    party = ctx.living_party()
    conscious = [(cid, s) for cid, s in party if s["hp"] > 0]
    if outcome == "victory":
        each = enc.get("xp", 0) // max(1, len(conscious) or len(party) or 1)
        ups = []
        for _, s in (conscious or party):
            if ctx.settings.get("leveling") == "xp" and ch.award_xp(s, each):
                ups.append(f"{s['name']} can level up!")
        ctx.log("event", f"Victory! {each} XP each." + (" " + " ".join(ups) if ups else ""))
        body.append(f"Outcome: VICTORY. {each} XP each awarded automatically." + (" " + " ".join(ups) if ups else ""))
        mons = [{"cr": t.get("cr", 0), "ctype": t.get("ctype")} for t in enc["tokens"].values() if t["kind"] == "monster"]
        tr = loot.roll_treasure(mons, ctx.settings.get("magic_level", "standard"))
        takers = conscious or party
        found = []
        if tr["cp"] and takers:
            share = tr["cp"] // len(takers)
            for _, s in takers:
                s["gold_cp"] = s.get("gold_cp", 0) + share
            found.append(f"{shop_rules.fmt_cp(tr['cp'])} in coin ({shop_rules.fmt_cp(share)} each)")
        for key in tr["items"]:
            cid, s = random.choice(takers)
            ch.add_item(s, key, 1)
            found.append(f"{srd.item(key)['name']} (to {s['name']})")
        if found:
            ctx.log("event", "Loot: " + "; ".join(found) + ".")
            body.append("Loot found (already given out by the game): " + "; ".join(found) + ". Mention it in the narration.")
        else:
            body.append("They found no coin. Grant a plot item with grant_item only if the story calls for it.")
    elif outcome == "defeat":
        for _, s in party:
            if s["hp"] <= 0 and not s.get("dead") and ctx.settings.get("death_rule") != "permadeath":
                s["hp"] = 1
                ch.remove_condition(s, "Unconscious")
                s["death_saves"] = {"success": 0, "fail": 0}
        ctx.log("event", "The party is defeated.")
        body.append("Outcome: DEFEAT. Every character fell. Those not dead wake later with 1 HP. Narrate what the enemies "
                    "did with them (captured, robbed, left for dead, rescued) — a setback, not the end of the story.")
    else:
        body.append(f"Outcome: the fight ended ({outcome}).")
    dead = [s["name"] for _, s in ctx.party() if s.get("dead")]
    if dead:
        body.append(f"Dead: {', '.join(dead)}.")
    combat.finish(enc, ctx.chars)
    ctx.state["encounter"] = None
    queue_dm(ctx, "combat_end", "\n".join(body))


# ── DM calls ────────────────────────────────────────────────────────────────

def _engine_for(ctx: Ctx):
    st = ctx.settings
    kind = st.get("dm_engine", "offline")
    model = st.get("dm_model") or DEFAULT_MODEL
    if kind == "api_key":
        host = ctx.db.get(User, ctx.game.host_id)
        key = decrypt_secret(host.api_key_enc) if host and host.api_key_enc else None
        if not key:
            raise engines.DMError("the host hasn't saved a Claude API key (Settings → API key)")
        return engines.ApiKeyEngine(key, model)
    if kind == "claude_code":
        return engines.ClaudeCodeEngine(model)
    return engines.OfflineEngine()


def _prompt_from(text: str) -> str | None:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        return None
    last = paras[-1]
    qs = re.findall(r"[^.!?]*\?", last)
    return (qs[-1].strip() if qs else last)[:300]


async def run_dm(game_id: str) -> None:
    async with lock_for(game_id):
        db = SessionLocal()
        ctx = load(db, game_id)
        pd = ctx.state.get("pending_dm")
        if not pd or ctx.game.dm_busy:
            db.close()
            return
        ctx.game.dm_busy = True
        db.commit()
    await changed(game_id, [])
    t0 = now()
    toolbox = ToolBox(ctx)
    call = DMCall(game_id=game_id, engine=ctx.settings.get("dm_engine", "offline"),
                  model=ctx.settings.get("dm_model"), reason=pd["reason"])
    try:
        engine = _engine_for(ctx)
        recent = [(l.kind, l.author, l.text) for l in reversed(list(db.scalars(
            select(LogEntry).where(LogEntry.game_id == game_id).order_by(LogEntry.id.desc()).limit(30))))]
        system = prompt.system_prompt(ctx)
        user = prompt.turn_message(ctx, pd["reason"], pd["body"], recent)
        result = await engine.run(system, user, TOOLS, toolbox.call, reason=pd["reason"])
    except Exception as e:  # engine failures roll back everything the DM did this call
        msg = str(e) if isinstance(e, (engines.DMError, RulesError)) else f"unexpected error: {e}"
        log.exception("DM call failed for %s", game_id) if not isinstance(e, engines.DMError) else None
        async with lock_for(game_id):
            db.close()
            db = SessionLocal()
            try:
                ctx2 = load(db, game_id)
                restore = dict(pd.get("restore_phase") or {"id": 0, "type": "exploration"})
                if restore.get("type") in ("lobby", None):
                    restore["type"] = "exploration"
                restore["error"] = msg
                restore["id"] = ctx2.phase.get("id", 0) + 1
                restore["deadline"] = None
                ctx2.state["phase"] = restore
                ctx2.game.dm_busy = False
                ctx2.log("system", f"The DM couldn't continue: {msg}. The host can retry.")
                call.ok = False
                call.error = msg[:2000]
                call.duration_ms = int((now() - t0).total_seconds() * 1000)
                db.add(call)
                ctx2.save()
                await changed(ctx2)
            finally:
                db.close()
        return

    async with lock_for(game_id):
        try:
            ctx.log("narration", result.text, "DM")
            ctx.state["pending_dm"] = None
            p_text = _prompt_from(result.text)
            enc = ctx.encounter
            if enc and enc.get("mode") == "classic":
                enc["round_log"] = []  # the DM has narrated everything so far
                enc.pop("round_complete", None)
            if toolbox.pending_rolls:
                ctx.open_phase("roll", p_text, pending_rolls=toolbox.pending_rolls)
            elif enc and enc.get("outcome"):
                _finish_combat(ctx, enc["outcome"])
            elif enc and enc.get("mode") == "classic":
                _after_typed_dm(ctx, toolbox, p_text)
            elif ctx.encounter and not ctx.encounter.get("outcome"):
                ctx.open_phase("combat", p_text)
                if ctx.away_chars():
                    after_combat_change(ctx, dict(ctx.encounter["turn"]))
            elif toolbox.opened_shop and ctx.state.get("shop"):
                ctx.open_phase("shop", p_text)
            else:
                ctx.open_phase("exploration", p_text)
            ctx.game.dm_busy = False
            call.duration_ms = result.duration_ms
            call.input_tokens = result.input_tokens
            call.output_tokens = result.output_tokens
            call.cache_read_tokens = result.cache_read_tokens
            call.cache_write_tokens = result.cache_write_tokens
            call.cost_usd = result.cost_usd
            call.model = result.model
            db.add(call)
            ctx.save()
            await changed(ctx)
            await notify_phase(ctx)
        except Exception:
            log.exception("saving DM result failed for %s", game_id)
            db.rollback()
            g = db.get(Game, game_id)
            if g:
                g.dm_busy = False
                db.commit()
        finally:
            db.close()


def _after_typed_dm(ctx: Ctx, toolbox: ToolBox, p_text: str | None) -> None:
    """After the DM's response in typed combat: open the next player's turn, or finish a turn the DM left open."""
    enc = ctx.encounter
    declared = enc.get("declared")
    if declared and not toolbox.ended_turn:
        t = enc["tokens"].get(declared["tid"])
        if toolbox.combat_steps == 0 and t and combat.can_act(enc, t["id"], ctx.chars):
            enc.pop("declared", None)  # the DM asked them to clarify: same player, same turn
        else:  # the DM resolved the action but forgot to end the turn: end it, and narrate what follows
            lines = (combat.end_turn(enc, ctx.chars, t["id"]) if t and combat.can_act(enc, t["id"], ctx.chars)
                     else combat.advance(enc, ctx.chars))
            enc.pop("declared", None)
            enc.pop("round_complete", None)
            ctx.log_lines(lines)
            if combat.check_end(enc, ctx.chars):
                _finish_combat(ctx, enc["outcome"])
                return
            if lines:
                nxt = turns.actor(enc, ctx.chars)
                queue_dm(ctx, "combat_auto", "\n".join(
                    ["What happened next (already resolved by the game):"] + [f"- {ln['text']}" for ln in lines] +
                    ["", "Narrate this briefly (exactly these results)" +
                     (f", and end by turning to {nxt['name']}: what do they do?" if nxt else ".")]))
                return
    ctx.open_phase("combat", p_text)
    t = turns.actor(enc, ctx.chars)
    if t and t["character_id"] in ctx.away_chars():
        _auto_combat_turns(ctx, "ai", only_away=True)


def retry_dm(ctx: Ctx, uid: str) -> None:
    if ctx.game.host_id != uid:
        raise RulesError("only the host can retry")
    p = ctx.phase
    if not p.get("error"):
        raise RulesError("there's nothing to retry")
    pd = ctx.state.get("pending_dm")
    if not pd:
        raise RulesError("there's nothing to retry")
    pd["restore_phase"] = {k: v for k, v in p.items() if k != "error"}
    ctx.open_phase("dm")
    spawn(run_dm(ctx.game.id))


# ── deadlines ───────────────────────────────────────────────────────────────

async def tick() -> None:
    db = SessionLocal()
    try:
        games = list(db.scalars(select(Game).where(Game.status == "active", Game.dm_busy.is_(False))))
        due = []
        for g in games:
            p = (g.state or {}).get("phase") or {}
            d = parse_iso(p.get("deadline"))
            if d and now() >= d and p.get("type") not in ("dm", "lobby", "ended") and not p.get("paused"):
                due.append(g.id)
    finally:
        db.close()
    for gid in due:
        try:
            await resolve(gid)
        except Exception:
            log.exception("resolving %s failed", gid)
    try:
        from .notify import send_reminders
        await send_reminders()
    except Exception:
        log.exception("reminders failed")


async def recover_on_startup() -> None:
    """A server restart mid-DM-call leaves games stuck; retry their pending DM calls."""
    db = SessionLocal()
    try:
        for g in db.scalars(select(Game).where(Game.status == "active")):
            st = g.state or {}
            if g.dm_busy or ((st.get("phase") or {}).get("type") == "dm" and st.get("pending_dm")):
                g.dm_busy = False
                db.commit()
                spawn(run_dm(g.id))
    finally:
        db.close()


async def scheduler(interval: float) -> None:
    await recover_on_startup()
    while True:
        await asyncio.sleep(interval)
        try:
            await tick()
        except Exception:
            log.exception("tick failed")
