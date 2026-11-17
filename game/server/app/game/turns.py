"""Typed combat: on their turn a player describes what their character does, in words, and the DM resolves it.

The DM uses combat tools (move, attack, cast, feature, action, end turn) that act only on the character whose turn
it is. Anything that needs the player's dice (attack rolls, spell attacks, spells with damage) becomes a roll
request; the game keeps the turn's steps in order in `enc["queue"]` and runs each one when its roll is made, so
"I stab him and then step back" happens in that order. With the game's auto-roll setting, steps run at once.
"""
from __future__ import annotations

import copy

from ..rules import character as ch
from ..rules import srd
from ..rules.character import RulesError
from ..world import battlemap as bm
from . import combat


def actor(enc: dict | None, chars: dict) -> dict | None:
    """The player character whose turn it is, if any."""
    if not enc:
        return None
    tid = (enc.get("turn") or {}).get("actor_id")
    t = enc["tokens"].get(tid) if tid else None
    if not t or t["kind"] != "pc" or not combat.can_act(enc, tid, chars):
        return None
    return t


# ── finding things by the names the DM uses ─────────────────────────────────

def _norm(s: str) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum() or c == " ").strip()


def find_token(enc: dict, chars: dict, name: str, kind: str | None = None) -> dict:
    key = _norm(name)
    living = [t for t in enc["tokens"].values() if (kind is None or t["kind"] == kind)
              and (combat.alive(t, chars) or (t["kind"] == "pc" and combat.present(t, chars)))]
    for test in (lambda t: _norm(t["name"]) == key, lambda t: _norm(t["name"]).startswith(key),
                 lambda t: key and key in _norm(t["name"]), lambda t: t["id"] == name):
        hits = [t for t in living if test(t)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            names = ", ".join(t["name"] for t in hits)
            raise RulesError(f"{name!r} could be any of: {names} — use the exact name")
    names = ", ".join(t["name"] for t in living)
    raise RulesError(f"no creature called {name!r} on the battlefield (there are: {names})")


def find_attack(s: dict, weapon: str) -> dict:
    atks = ch.attacks(s)
    key = _norm(weapon)
    for test in (lambda a: a["id"] == weapon, lambda a: _norm(a["name"]) == key,
                 lambda a: key and key in _norm(a["name"]), lambda a: key and _norm(a["name"]) in key):
        hit = next((a for a in atks if test(a)), None)
        if hit:
            return hit
    names = ", ".join(f"{a['name']} ({a['id']})" for a in atks)
    raise RulesError(f"{s['name']} has no attack called {weapon!r} (attacks: {names}). For an improvised attack use "
                     f"roll_check and apply_damage.")


def find_spell(s: dict, name: str) -> str:
    known = list(dict.fromkeys(ch.all_cantrips(s) + ch.ready_spells(s)))
    spells = srd.spells(ch.rs(s))
    key = _norm(name)
    for test in (lambda i: i == name, lambda i: _norm(spells.get(i, {}).get("name", i)) == key,
                 lambda i: key and key in _norm(spells.get(i, {}).get("name", i))):
        hit = next((i for i in known if test(i)), None)
        if hit:
            return hit
    names = ", ".join(spells.get(i, {}).get("name", i) for i in known) or "none"
    raise RulesError(f"{s['name']} doesn't have {name!r} ready (ready: {names})")


def find_feature(s: dict, name: str) -> dict:
    feats = ch.actions(s)
    key = _norm(name)
    for test in (lambda f: f["id"] == name, lambda f: _norm(f["name"]) == key, lambda f: key and key in _norm(f["name"])):
        hit = next((f for f in feats if test(f)), None)
        if hit:
            return hit
    names = ", ".join(f"{f['name']} ({f['id']})" for f in feats) or "none"
    raise RulesError(f"{s['name']} has no combat feature called {name!r} (features: {names})")


# ── running a step ──────────────────────────────────────────────────────────

ACTS = {"dodge", "dash", "disengage", "hide", "help", "ready", "use_item", "other"}


def _move_dest(enc: dict, chars: dict, t: dict, op: dict) -> tuple[int, int]:
    occ = combat.occupied(enc, chars, exclude=t["id"])
    budget = t["budget"]["move_ft"]
    if op.get("toward"):
        goal = enc["tokens"][op["toward"]]
        return bm.step_toward(enc, combat.pos(t), combat.pos(goal), budget, occ, int(op.get("stop") or 5))
    if op.get("away_from"):
        threat = enc["tokens"][op["away_from"]]
        opts = bm.reachable(enc, combat.pos(t), budget, occ)
        return max(opts, key=lambda p: (bm.distance_ft(p, combat.pos(threat)), -opts[p]))
    return int(op["x"]), int(op["y"])


def run_op(enc: dict, chars: dict, op: dict) -> list[dict]:
    tid = op["tid"]
    k = op["kind"]
    if k == "move":
        t = combat.require(enc, tid, chars)
        dest = _move_dest(enc, chars, t, op)
        if dest == combat.pos(t):
            raise RulesError(f"{t['name']} can't get any closer from here" if op.get("toward") else "that's where they already are")
        out = combat.move(enc, chars, tid, *dest)
        moved = combat.pos(t) == dest
        return [combat.line(f"{t['name']} moves to ({dest[0]},{dest[1]}).", "combat")] + out if moved else out
    if k == "attack":
        return combat.attack(enc, chars, tid, op["attack_id"], op["target_id"])
    if k == "cast":
        return combat.cast(enc, chars, tid, op["spell"], op.get("target_id"), op.get("slot_level"), op.get("x"), op.get("y"))
    if k == "feature":
        return combat.feature(enc, chars, tid, op["feature"], op.get("target_id"), op.get("x"), op.get("y"))
    if k == "act":
        if op["act"] in ("dodge", "dash", "disengage"):
            return combat.act(enc, chars, tid, op["act"])
        return combat.act(enc, chars, tid, "custom", op.get("note") or op["act"])
    raise RulesError(f"unknown step {k}")


def validate(enc: dict, chars: dict, op: dict) -> None:
    """Try the queued steps plus this one on a copy of the fight; raise RulesError if this one can't happen.
    Dice in the copy are thrown away, and hit points are restored after each step so a lucky simulated kill
    doesn't block a second attack on the same target."""
    e2, c2 = copy.deepcopy(enc), copy.deepcopy(chars)
    for step in list(enc.get("queue") or []) + [op]:
        hp = {tid: t.get("hp") for tid, t in e2["tokens"].items() if t["kind"] == "monster"}
        php = {cid: s.get("hp") for cid, s in c2.items()}
        try:
            run_op(e2, c2, step)
        except RulesError:
            if step is op:
                raise
        for tid, v in hp.items():
            e2["tokens"][tid]["hp"] = v
        for cid, v in php.items():
            c2[cid]["hp"] = v
            c2[cid]["dead"] = chars[cid].get("dead", False)
        e2["outcome"] = None


def execute_through(enc: dict, chars: dict, roll_id: str) -> tuple[list[dict], list[dict]]:
    """Run queued steps in order up to and including the one waiting on `roll_id`, plus any roll-free steps after
    it. Returns (that step's lines, all lines)."""
    q = enc.setdefault("queue", [])
    out: list[dict] = []
    mine: list[dict] = []
    reached = False
    while q:
        op = q[0]
        if op.get("roll_id") and op["roll_id"] != roll_id and (reached or not _rolled_earlier(op, roll_id, q)):
            break
        q.pop(0)
        name = enc["tokens"].get(op["tid"], {}).get("name", "They")
        try:
            lines = run_op(enc, chars, op)
        except RulesError as e:
            lines = [combat.line(f"{name} can't do that: {e}.", "system")]
        if op.get("roll_id") == roll_id:
            reached = True
            mine = lines
        out += lines
        if combat.check_end(enc, chars):
            q.clear()
            break
    return mine, out


def _rolled_earlier(op: dict, roll_id: str, q: list[dict]) -> bool:
    """True when `op` (another roll's step) comes before the step for `roll_id` — rolls run in order."""
    ids = [o.get("roll_id") for o in q if o.get("roll_id")]
    return roll_id in ids and ids.index(op["roll_id"]) < ids.index(roll_id)


# ── the DM's view of the battlefield ────────────────────────────────────────

def brief(enc: dict, chars: dict, tid: str) -> str:
    """Everything the DM needs to resolve one character's typed turn: a grid map, every creature with exact
    position, distance and (for the DM's eyes) hit points and AC, and the acting character's options."""
    t = enc["tokens"][tid]
    s = chars[t["character_id"]]
    w, h = enc["grid"]["w"], enc["grid"]["h"]
    grid = [list(row.replace("T", "o")) for row in enc["cells"]]
    legend = []
    letters = iter("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    digits = iter("123456789abcdefghijklmnopqrstuvwxyz")
    for o in enc["tokens"].values():
        if not (combat.alive(o, chars) or (o["kind"] == "pc" and combat.present(o, chars))):
            continue
        mark = "@" if o["id"] == tid else (next(letters) if o["kind"] == "pc" else next(digits))
        grid[o["y"]][o["x"]] = mark
        d = combat.dist(t, o)
        cond = combat.conds(o, chars)
        if o["kind"] == "pc":
            os_ = chars[o["character_id"]]
            stats = f"HP {os_['hp']}/{os_['hp_max']}, AC {ch.armor_class(os_)}"
        else:
            atk = ", ".join(f"{a['name']} ({'ranged ' + str(a['range']) + ' ft' if a['ranged'] else 'reach ' + str(a['reach']) + ' ft'})"
                            for a in o.get("actions", [])[:3])
            stats = f"HP {o['hp']}/{o['hp_max']}, AC {o['ac']}, attacks: {atk}"
        who = " (acting now)" if o["id"] == tid else ""
        legend.append(f"{mark} {o['name']}{who} at ({o['x']},{o['y']})" + ("" if o["id"] == tid else f", {d} ft away")
                      + f" — {stats}" + (f"; conditions: {', '.join(cond)}" if cond else ""))
    for b in enc.get("bystanders") or []:  # friendly NPCs on the field: they move only when you move them (move_npc)
        if 0 <= b["y"] < h and 0 <= b["x"] < w:
            grid[b["y"]][b["x"]] = "&"
        legend.append(f"& {b['name']} (NPC, not a combatant) at ({b['x']},{b['y']}), {combat.dist(t, b)} ft away")
    head = "    " + "".join(str(x // 10) if x >= 10 else " " for x in range(w)) + "\n    " + "".join(str(x % 10) for x in range(w))
    rows = "\n".join(f"{y:>3} " + "".join(r) for y, r in enumerate(grid))
    props: dict[str, list[str]] = {}
    for p in enc.get("props", []):
        props.setdefault(p["kind"], []).append(f"({p['x']},{p['y']})")
    obstacles = "; ".join(f"{k.replace('_', ' ')} {' '.join(v[:10])}" for k, v in props.items())

    b = t.get("budget") or {}
    extra = ch.extra_attacks(s)
    atk_left = b.get("attacks_left", 0) if t.get("attacked") else (extra if b.get("action") else 0)
    res = (f"Movement left: {b.get('move_ft', 0)} ft (speed {ch.speed(s)} ft). Action: {'available' if b.get('action') else 'used'}"
           f"{f' ({atk_left} weapon attack(s) left with the Attack action)' if atk_left else ''}. "
           f"Bonus action: {'available' if b.get('bonus') else 'used'}. Reaction: {'available' if t.get('reaction', True) else 'used'}.")
    weapons = "\n".join(f"- {a['name']} (id {a['id']}): {a['to_hit']:+d} to hit, {a['damage']} {a['damage_type']}, "
                        + (f"range {a['range_ft']}/{a['long_range_ft']} ft" if a['kind'] == 'ranged' else
                           f"reach {a['range_ft']} ft" + (f", thrown {a['long_range_ft']} ft" if a.get('long_range_ft') else ""))
                        + (f", mastery {a['mastery']}" if a.get("mastery") else "")
                        for a in ch.attacks(s))
    fx = combat.FX(s)
    spells = srd.spells(ch.rs(s))
    known = list(dict.fromkeys(ch.all_cantrips(s) + ch.ready_spells(s)))
    auto = [f"{spells.get(i, {}).get('name', i)} (level {spells.get(i, {}).get('level', 0)})" for i in known if i in fx]
    manual = [spells.get(i, {}).get("name", i) for i in known if i not in fx]
    pact = ch.pact_slots(s)
    slots = (f"{pact['max'] - pact['used']}/{pact['max']} pact slots (level {pact['level']})" if pact else
             ", ".join(f"level {k}: {v['max'] - v['used']}/{v['max']}"
                       for k, v in sorted(ch.spell_slots(s).items(), key=lambda kv: int(kv[0]))))
    feats = "\n".join(f"- {f['name']} (id {f['id']}, {f['kind']})"
                      + (f", {f['uses']['max'] - f['uses']['used']}/{f['uses']['max']} uses" if f.get("uses") else "")
                      + ("" if f.get("available", True) else " — none left")
                      for f in ch.actions(s))
    custom = [c["name"] for c in s.get("custom") or []]
    parts = [
        f"Battle map ({enc['terrain']}, {w}x{h} squares of 5 ft; x is the column, y the row): '#' wall, 'o' obstacle "
        f"(blocks movement), '~' {enc.get('difficult', 'difficult terrain')} (costs double), 'D' door, '.' open ground.",
        head, rows,
        "Obstacles: " + (obstacles or "none"),
        "Creatures:", *legend,
        f"\n{s['name']}'s turn. {res}",
        "Weapons:\n" + (weapons or "- none"),
        "Spells the game resolves: " + (", ".join(auto) or "none")
        + (f". Other spells ready (resolve them yourself with roll_check/apply_damage/heal/add_condition): {', '.join(manual)}" if manual else "")
        + (f". Spell slots: {slots}" if slots else ""),
        "Combat features:\n" + (feats or "- none"),
    ]
    if custom:
        parts.append("Custom features and items (rule them from their text): " + ", ".join(custom))
    return "\n".join(parts)
