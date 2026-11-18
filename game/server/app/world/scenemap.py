"""Scene maps: the DM's grid of the party's immediate surroundings outside combat, with fog of war.

The DM draws the area (a street with a portal, a tunnel fork, a shaft with rungs) using the battle-map cell
alphabet, places the party, NPCs and labelled features, and moves them as the story goes. Players only see what
their characters can see: line of sight from each character, within the light's reach. What they've seen before
stays on the map, dimmed, without the people in it. The full map never leaves the server.

Cells: '#' wall / cliff / building, '.' floor or open ground, 'D' door or gate (blocks sight), 'T' obstacle,
'~' difficult terrain, '=' ladder / rungs / rope / narrow bridge, ' ' void (open air, a drop, a pit).
In the players' view a seen void square is sent as 'v' (drawn as open air) and an unseen one as ' ' (fog).
"""
from __future__ import annotations

from . import battlemap as bm

MAX_W, MAX_H = 32, 24
CELLS = set("#.DT~= ")
SIGHT_BLOCKING = set("#D")
NPC_MAX, FEATURE_MAX = 16, 20


def _clip(s, n: int) -> str:
    return str(s or "").strip()[:n]


def _grid(rows) -> list[str]:
    if isinstance(rows, str):
        rows = rows.split("\n")
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows: give the map as a list of strings, one per row")
    rows = [str(r).rstrip("\r") for r in rows][:MAX_H]
    w = min(MAX_W, max(len(r) for r in rows))
    if w < 3 or len(rows) < 3:
        raise ValueError("the map must be at least 3x3")
    out = []
    for r in rows:
        r = r[:w].ljust(w)
        out.append("".join(c if c in CELLS else "." for c in r))
    return out


def _xy(p, sm: dict) -> tuple[int, int]:
    try:
        x, y = int(p["x"]), int(p["y"])
    except (TypeError, KeyError, ValueError):
        raise ValueError("positions need integer x and y")
    if not (0 <= x < sm["w"] and 0 <= y < sm["h"]):
        raise ValueError(f"({x},{y}) is off the map ({sm['w']}x{sm['h']}, 0-based)")
    return x, y


def _npcs(items, sm: dict) -> list[dict]:
    out = []
    for n in (items or [])[:NPC_MAX]:
        if not isinstance(n, dict) or not _clip(n.get("name"), 40):
            continue
        x, y = _xy(n, sm)
        out.append({"name": _clip(n["name"], 40), "x": x, "y": y, "hostile": bool(n.get("hostile"))})
    return out


def _features(items, sm: dict) -> list[dict]:
    out = []
    for f in (items or [])[:FEATURE_MAX]:
        if not isinstance(f, dict) or not _clip(f.get("label"), 40):
            continue
        x, y = _xy(f, sm)
        out.append({"label": _clip(f["label"], 40), "x": x, "y": y})
    return out


def draw(terrain: str, rows, party_at: dict, features=None, npcs=None, sight_ft: int | None = None,
         title: str = "") -> dict:
    cells = _grid(rows)
    sm = {"title": _clip(title, 60), "terrain": terrain if terrain in bm.TERRAINS else "road",
          "w": len(cells[0]), "h": len(cells), "cells": cells,
          "sight": max(2, min(40, int(sight_ft) // 5)) if sight_ft else None, "positions": {}, "seen": ""}
    sm["party"] = _passable_near(sm, *_xy(party_at, sm))
    sm["features"] = _features(features, sm)
    sm["npcs"] = _npcs(npcs, sm)
    return sm


def update(sm: dict, party_at=None, npcs=None, add_features=None, remove_features=None, set_cells=None,
           character_positions=None) -> None:
    for c in (set_cells or [])[:200]:
        x, y = _xy(c, sm)
        ch = str(c.get("cell", "."))[:1] or "."
        if ch not in CELLS:
            raise ValueError(f"unknown cell {ch!r}; use one of # . D T ~ = or space")
        row = sm["cells"][y]
        sm["cells"][y] = row[:x] + ch + row[x + 1:]
    if party_at:
        sm["party"] = _passable_near(sm, *_xy(party_at, sm))
        sm["positions"] = {}  # the party moved together: regroup around the new spot
    for cid, p in (character_positions or {}).items():
        sm["positions"][cid] = _xy(p, sm)
    if npcs is not None:
        sm["npcs"] = _npcs(npcs, sm)
    if remove_features:
        drop = {str(x).strip().lower() for x in remove_features}
        sm["features"] = [f for f in sm["features"] if f["label"].lower() not in drop]
    if add_features:
        sm["features"] = (sm["features"] + _features(add_features, sm))[:FEATURE_MAX]


def _passable_near(sm: dict, x: int, y: int) -> tuple[int, int]:
    if sm["cells"][y][x] not in "# T":
        return x, y
    best = min(((cx, cy) for cy in range(sm["h"]) for cx in range(sm["w"]) if sm["cells"][cy][cx] in ".~D="),
               key=lambda p: bm.distance_ft(p, (x, y)), default=(x, y))
    return best


def place_party(sm: dict, char_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Where each character stands: explicit positions, else gathered around the party spot."""
    out: dict[str, tuple[int, int]] = {}
    taken: set[tuple[int, int]] = set()
    for cid in char_ids:
        if cid in sm.get("positions", {}):
            out[cid] = tuple(sm["positions"][cid])
            taken.add(out[cid])
    px, py = sm["party"]
    spots = sorted(((x, y) for y in range(sm["h"]) for x in range(sm["w"]) if sm["cells"][y][x] in ".~D="),
                   key=lambda p: (bm.distance_ft(p, (px, py)), abs(p[0] - px) + abs(p[1] - py)))
    for cid in char_ids:
        if cid in out:
            continue
        spot = next((s for s in spots if s not in taken), (px, py))
        out[cid] = spot
        taken.add(spot)
    return out


def _line(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    (x0, y0), (x1, y1) = a, b
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err, pts = dx + dy, []
    while True:
        pts.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return pts
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def visible(sm: dict, eyes: list[tuple[int, int]]) -> set[tuple[int, int]]:
    """Squares any of the characters can see: in range of the light, with no wall or door in between."""
    out: set[tuple[int, int]] = set()
    rng = sm.get("sight")
    for ex, ey in eyes:
        for y in range(sm["h"]):
            for x in range(sm["w"]):
                if (x, y) in out:
                    continue
                if rng is not None and max(abs(x - ex), abs(y - ey)) > rng:
                    continue
                pts = _line((ex, ey), (x, y))
                if all(sm["cells"][py][px] not in SIGHT_BLOCKING for px, py in pts[1:-1]):
                    out.add((x, y))
    return out


def refresh(sm: dict, char_ids: list[str]) -> set[tuple[int, int]]:
    """Recompute what the party sees now and remember it. Returns the visible squares."""
    pos = place_party(sm, char_ids)
    vis = visible(sm, list(pos.values()) or [tuple(sm["party"])])
    seen = sm.get("seen") or ""
    if len(seen) != sm["w"] * sm["h"]:
        seen = "0" * (sm["w"] * sm["h"])
    s = list(seen)
    for x, y in vis:
        s[y * sm["w"] + x] = "1"
    sm["seen"] = "".join(s)
    return vis


def view(sm: dict, party: list[tuple[str, dict]], viewer_char: str | None) -> dict:
    """What players get: an Encounter-shaped map (so the battle-map renderer draws it) with unseen squares blanked."""
    ids = [cid for cid, _ in party]
    pos = place_party(sm, ids)
    vis = visible(sm, list(pos.values()) or [tuple(sm["party"])])
    seen = sm.get("seen") or ""
    w = sm["w"]

    def known(x: int, y: int) -> bool:
        return (x, y) in vis or (len(seen) == w * sm["h"] and seen[y * w + x] == "1")

    def shown(x: int, y: int) -> str:
        if not known(x, y):
            return " "
        c = sm["cells"][y][x]
        return "v" if c == " " else c

    cells = ["".join(shown(x, y) for x in range(w)) for y in range(sm["h"])]
    dim = [[x, y] for y in range(sm["h"]) for x in range(w) if known(x, y) and (x, y) not in vis]
    tokens = []
    for cid, s in party:
        x, y = pos[cid]
        tokens.append({"id": f"pc-{cid}", "name": s["name"], "kind": "pc", "character_id": cid, "x": x, "y": y,
                       "hp": s.get("hp"), "hp_max": s.get("hp_max"),
                       "hp_state": "dead" if s.get("dead") else ("down" if s.get("hp", 1) <= 0 else "healthy"),
                       "ac": None, "conditions": [], "speed": 30, "size": 1, "color": s.get("color", "#c9a227")})
    for i, n in enumerate(sm.get("npcs", [])):
        if (n["x"], n["y"]) in vis:
            tokens.append({"id": f"npc-{i}", "name": n["name"], "kind": "monster" if n["hostile"] else "npc", "character_id": None,
                           "x": n["x"], "y": n["y"], "hp": None, "hp_max": None, "hp_state": "healthy", "ac": None,
                           "conditions": [], "speed": 30, "size": 1,
                           "color": "#b03a2e" if n["hostile"] else "#5a7d9a"})
    return {"title": sm.get("title", ""), "terrain": sm["terrain"], "grid": {"w": w, "h": sm["h"]}, "cells": cells,
            "props": [], "difficult": bm.DIFFICULT_NAMES.get(sm["terrain"], "difficult terrain"),
            "labels": [f for f in sm.get("features", []) if known(f["x"], f["y"])], "dim": dim,
            "tokens": tokens, "my_token_id": f"pc-{viewer_char}" if viewer_char else None,
            "round": 0, "mode": "classic", "turn": {"side": None, "actor_id": None}, "my_turn": False,
            "budget": None, "reachable": [], "targets": []}


def describe(sm: dict, party: list[tuple[str, dict]]) -> str:
    """For the DM's turn context: the full map with coordinates, who is where, and what the party can see."""
    ids = [cid for cid, _ in party]
    pos = place_party(sm, ids)
    names = {cid: s["name"] for cid, s in party}
    lines = [f"Scene map \"{sm.get('title', '')}\" ({sm['terrain']}, {sm['w']}x{sm['h']}, x→ y↓ from 0; "
             f"sight {'unlimited' if sm.get('sight') is None else str(sm['sight'] * 5) + ' ft'}):"]
    lines.append("   " + "".join(str(x % 10) for x in range(sm["w"])))
    lines += [f"{y:>2} {row}" for y, row in enumerate(sm["cells"])]
    lines.append("Party: " + ", ".join(f"{names[c]} ({x},{y})" for c, (x, y) in pos.items()))
    if sm.get("npcs"):
        lines.append("NPCs: " + ", ".join(f"{n['name']} ({n['x']},{n['y']}){' hostile' if n['hostile'] else ''}"
                                         for n in sm["npcs"]))
    if sm.get("features"):
        lines.append("Features: " + ", ".join(f"{f['label']} ({f['x']},{f['y']})" for f in sm["features"]))
    return "\n".join(lines)


def battle_map(sm: dict, char_ids: list[str]) -> dict:
    """The scene map as a battle map: what the party has seen is the battlefield (open air becomes 'v', which
    blocks movement); squares they've never seen are left out, so a fight doesn't reveal them."""
    vis = refresh(sm, char_ids)
    w, h = sm["w"], sm["h"]
    seen = sm.get("seen") or ""

    def cell(x: int, y: int) -> str:
        if len(seen) == w * h and seen[y * w + x] != "1" and (x, y) not in vis:
            return " "
        c = sm["cells"][y][x]
        return "v" if c == " " else c

    return {"terrain": sm["terrain"], "grid": {"w": w, "h": h},
            "cells": ["".join(cell(x, y) for x in range(w)) for y in range(h)], "props": [],
            "difficult": bm.DIFFICULT_NAMES.get(sm["terrain"], "difficult terrain"),
            "title": sm.get("title", ""), "visible": [[x, y] for x, y in vis]}


# ── a split party: the main map plus side maps, each for the characters who went off on their own ──

def side_members(state: dict) -> set[str]:
    return {c for m in state.get("side_maps") or [] for c in m.get("members") or []}


def maps_with_party(state: dict, party: list[tuple[str, dict]]) -> list[tuple[str, dict, list[tuple[str, dict]]]]:
    """[(map id, map, the characters on it)]: the main map ("main") has everyone not on a side map."""
    away = side_members(state)
    out = []
    if state.get("scene_map"):
        out.append(("main", state["scene_map"], [(c, s) for c, s in party if c not in away]))
    for m in state.get("side_maps") or []:
        members = set(m.get("members") or [])
        out.append((m["id"], m, [(c, s) for c, s in party if c in members]))
    return out


def map_of(state: dict, cid: str | None) -> str | None:
    """Id of the map a character is on (a side map, else the main one if drawn)."""
    for m in state.get("side_maps") or []:
        if cid and cid in (m.get("members") or []):
            return m["id"]
    return "main" if state.get("scene_map") else None


def take_from_side_maps(state: dict, cids: set[str], keep: str | None = None) -> None:
    """These characters are somewhere else now: off every side map but `keep`; side maps left empty go away."""
    maps = []
    for m in state.get("side_maps") or []:
        if m["id"] != keep:
            m["members"] = [c for c in m.get("members") or [] if c not in cids]
        if m.get("members"):
            maps.append(m)
    state["side_maps"] = maps
