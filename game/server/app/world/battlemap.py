"""Battle maps: generated square grids and 5e grid movement.

Rules follow skills/dnd/scripts/battlemap.py: one square is 5 ft, every step (diagonals
included) costs 5 ft, difficult terrain costs double, walls and obstacles block, and a
diagonal step can't cut a wall corner.

Cells: '#' wall, '.' floor, 'T' obstacle, '~' difficult terrain, 'D' door, ' ' outside the map.
"""
from __future__ import annotations

import heapq
import random

TERRAINS = ("road", "forest", "tavern", "cave", "dungeon", "ruins", "camp", "swamp")
BLOCKING = set("#T ")


def _dungeon(rng: random.Random) -> list[list[str]]:
    """Two or three rooms joined by corridors, with pillars and a chest or altar."""
    w, h = 22, 14
    g = [["#"] * w for _ in range(h)]
    rooms = [(1, 2, 7, 10), (9, 1, 13, 6), (9, 8, 13, 12), (15, 3, 20, 10)]
    rng.shuffle(rooms)
    rooms = sorted(rooms[:3], key=lambda r: r[0])
    for x0, y0, x1, y1 in rooms:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[y][x] = "."
    for (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) in zip(rooms, rooms[1:]):
        ax, ay = (ax0 + ax1) // 2, (ay0 + ay1) // 2
        bx, by = (bx0 + bx1) // 2, (by0 + by1) // 2
        for x in range(min(ax, bx), max(ax, bx) + 1):
            g[ay][x] = "." if g[ay][x] == "#" else g[ay][x]
        for y in range(min(ay, by), max(ay, by) + 1):
            g[y][bx] = "." if g[y][bx] == "#" else g[y][bx]
    big = max(rooms, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
    x0, y0, x1, y1 = big
    if x1 - x0 >= 4 and y1 - y0 >= 4:
        for px, py in ((x0 + 1, y0 + 1), (x1 - 1, y0 + 1), (x0 + 1, y1 - 1), (x1 - 1, y1 - 1)):
            g[py][px] = "T"
    for _ in range(4):
        x, y = rng.randrange(w), rng.randrange(h)
        if g[y][x] == ".":
            g[y][x] = "~"
    return g


def _ruins(rng: random.Random) -> list[list[str]]:
    w, h = 20, 14
    g = [["." for _ in range(w)] for _ in range(h)]
    # broken outer walls with gaps
    for x in range(3, w - 3):
        for y in (2, h - 3):
            if rng.random() < 0.65:
                g[y][x] = "#"
    for y in range(2, h - 2):
        for x in (3, w - 4):
            if rng.random() < 0.6:
                g[y][x] = "#"
    for _ in range(10):
        x, y = rng.randrange(w), rng.randrange(h)
        if g[y][x] == ".":
            g[y][x] = "~"
    for _ in range(6):
        x, y = rng.randint(5, w - 6), rng.randint(4, h - 5)
        g[y][x] = "T"
    return g


def _camp(rng: random.Random) -> list[list[str]]:
    w, h = 20, 13
    g = [["." for _ in range(w)] for _ in range(h)]
    cx, cy = w // 2 + 2, h // 2
    g[cy][cx] = "T"  # campfire
    for dx, dy in ((-3, -2), (3, -2), (-3, 2), (3, 2)):  # tents
        g[cy + dy][cx + dx] = "T"
    for _ in range(int(w * h * 0.08)):
        x, y = rng.randrange(w), rng.randrange(h)
        if g[y][x] == "." and abs(x - cx) + abs(y - cy) > 4:
            g[y][x] = "T" if rng.random() < 0.5 else "~"
    for y in range(h):
        for x in (0, 1):
            g[y][x] = "." if g[y][x] == "T" else g[y][x]
    return g


def _swamp(rng: random.Random) -> list[list[str]]:
    w, h = 20, 14
    g = [["~" if rng.random() < 0.42 else "." for _ in range(w)] for _ in range(h)]
    for _ in range(int(w * h * 0.06)):
        x, y = rng.randrange(w), rng.randrange(h)
        g[y][x] = "T"
    for y in range(h // 2 - 1, h // 2 + 1):  # a firmer path across
        for x in range(w):
            if g[y][x] == "T":
                g[y][x] = "."
    for y in range(h):
        for x in (0, 1, w - 2, w - 1):
            if g[y][x] == "T":
                g[y][x] = "."
    return g


def generate(terrain: str, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    if terrain == "dungeon":
        g = _dungeon(rng)
        w, h = len(g[0]), len(g)
    elif terrain == "ruins":
        g = _ruins(rng)
        w, h = len(g[0]), len(g)
    elif terrain == "camp":
        g = _camp(rng)
        w, h = len(g[0]), len(g)
    elif terrain == "swamp":
        g = _swamp(rng)
        w, h = len(g[0]), len(g)
    elif terrain == "tavern":
        w, h = 16, 12
        g = [["#"] * w for _ in range(h)]
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                g[y][x] = "."
        g[h - 1][w // 2] = "D"
        for x in range(2, 7):  # the bar
            g[2][x] = "T"
        for _ in range(6):  # tables
            x, y = rng.randint(3, w - 4), rng.randint(4, h - 3)
            g[y][x] = "T"
        g[rng.randint(4, h - 3)][w - 2] = "~"  # spilled ale / broken chairs
    elif terrain == "cave":
        w, h = 20, 14
        g = [["#" if rng.random() < 0.42 else "." for _ in range(w)] for _ in range(h)]
        for _ in range(4):  # cellular automaton smoothing
            ng = [row[:] for row in g]
            for y in range(h):
                for x in range(w):
                    walls = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                                if (dx or dy) and (not (0 <= x + dx < w and 0 <= y + dy < h) or g[y + dy][x + dx] == "#"))
                    ng[y][x] = "#" if walls >= 5 else "."
            g = ng
        for y in range(h // 2 - 1, h // 2 + 2):  # guarantee a passage across
            for x in range(1, w - 1):
                if g[y][x] == "#":
                    g[y][x] = "."
        for _ in range(8):
            x, y = rng.randrange(w), rng.randrange(h)
            if g[y][x] == ".":
                g[y][x] = "~"
    elif terrain == "forest":
        w, h = 18, 14
        g = [["." for _ in range(w)] for _ in range(h)]
        for _ in range(int(w * h * 0.16)):
            x, y = rng.randrange(w), rng.randrange(h)
            g[y][x] = "T"
        for _ in range(int(w * h * 0.12)):
            x, y = rng.randrange(w), rng.randrange(h)
            if g[y][x] == ".":
                g[y][x] = "~"
        for y in range(h):  # clear the deployment edges
            for x in (0, 1, w - 2, w - 1):
                if g[y][x] == "T":
                    g[y][x] = "."
    else:  # road
        terrain = "road"
        w, h = 20, 12
        g = [["." for _ in range(w)] for _ in range(h)]
        road_y = h // 2
        for y in range(h):
            for x in range(w):
                if abs(y - road_y) <= 1:
                    continue
                r = rng.random()
                if r < 0.10 and abs(y - road_y) > 2:
                    g[y][x] = "T"
                elif r < 0.22:
                    g[y][x] = "~"
    props = _props(terrain, g, rng)
    return {"terrain": terrain, "grid": {"w": w, "h": h}, "cells": ["".join(row) for row in g],
            "props": props, "difficult": DIFFICULT_NAMES.get(terrain, "difficult terrain")}


DIFFICULT_NAMES = {"road": "brush", "forest": "undergrowth", "tavern": "broken furniture", "cave": "rubble",
                   "dungeon": "rubble", "ruins": "fallen masonry", "camp": "brush", "swamp": "bog"}


def _props(terrain: str, g: list[list[str]], rng: random.Random) -> list[dict]:
    """Name every obstacle square so the map can draw a table, tree, barrel… instead of a block.
    May add a few extra obstacles (barrels, a cart, stalagmites) for flavour."""
    h, w = len(g), len(g[0])
    props: list[dict] = []

    def floor_spots(pred=lambda x, y: True):
        return [(x, y) for y in range(h) for x in range(w) if g[y][x] == "." and pred(x, y)]

    if terrain == "tavern":
        near_wall = floor_spots(lambda x, y: any(g[y + dy][x + dx] == "#" for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                                                 if 0 <= x + dx < w and 0 <= y + dy < h) and y > 3 and abs(x - w // 2) > 1)
        rng.shuffle(near_wall)
        for x, y in near_wall[:3]:
            g[y][x] = "T"
            props.append({"x": x, "y": y, "kind": "barrel"})
    elif terrain == "road":
        road_y = h // 2
        cands = [x for x in range(4, w - 4) if all(g[road_y - 1][x + i] == "." for i in (0, 1))]
        if cands:
            x = rng.choice(cands)
            for i in (0, 1):
                g[road_y - 1][x + i] = "T"
                props.append({"x": x + i, "y": road_y - 1, "kind": "cart"})
    elif terrain == "cave":
        spots = floor_spots(lambda x, y: 2 < x < w - 3)
        rng.shuffle(spots)
        for x, y in spots[:5]:
            g[y][x] = "T"
            props.append({"x": x, "y": y, "kind": rng.choice(["stalagmite", "boulder"])})

    elif terrain == "dungeon":
        spots = floor_spots()
        rng.shuffle(spots)
        for (x, y), kind in zip(spots[:2], ["chest", rng.choice(["altar", "statue"])]):
            g[y][x] = "T"
            props.append({"x": x, "y": y, "kind": kind})
    elif terrain == "camp":
        cx, cy = w // 2 + 2, h // 2
        props.append({"x": cx, "y": cy, "kind": "campfire"})
        for dx, dy in ((-3, -2), (3, -2), (-3, 2), (3, 2)):
            props.append({"x": cx + dx, "y": cy + dy, "kind": "tent"})

    named = {(p["x"], p["y"]) for p in props}
    for y in range(h):
        for x in range(w):
            if g[y][x] != "T" or (x, y) in named:
                continue
            if terrain == "dungeon":
                kind = "pillar"
            elif terrain == "ruins":
                kind = rng.choice(["pillar", "statue", "boulder"])
            elif terrain == "camp":
                kind = rng.choice(["crate", "log", "tree"])
            elif terrain == "swamp":
                kind = rng.choice(["dead_tree", "dead_tree", "log"])
            elif terrain == "tavern":
                kind = "bar" if y == 2 else "table"
            elif terrain == "forest":
                kind = "tree" if rng.random() < 0.85 else "boulder"
            elif terrain == "road":
                kind = "tree" if rng.random() < 0.7 else "boulder"
            else:
                kind = "boulder"
            props.append({"x": x, "y": y, "kind": kind})
    return props


def cell(m: dict, x: int, y: int) -> str:
    if not (0 <= x < m["grid"]["w"] and 0 <= y < m["grid"]["h"]):
        return " "
    return m["cells"][y][x]


def passable(m: dict, x: int, y: int) -> bool:
    return cell(m, x, y) not in BLOCKING


def distance_ft(a: tuple[int, int], b: tuple[int, int]) -> int:
    return 5 * max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def reachable(m: dict, start: tuple[int, int], budget_ft: int, occupied: set[tuple[int, int]]) -> dict:
    """Squares reachable within budget_ft → cost in feet (Dijkstra)."""
    best = {start: 0}
    q = [(0, start)]
    while q:
        c, (x, y) = heapq.heappop(q)
        if c > best.get((x, y), 1e9):
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not dx and not dy:
                    continue
                nx, ny = x + dx, y + dy
                if not passable(m, nx, ny):
                    continue
                if dx and dy and (not passable(m, x + dx, y) or not passable(m, x, y + dy)):
                    continue  # no cutting wall corners
                step = 10 if cell(m, nx, ny) == "~" else 5
                nc = c + step
                if nc > budget_ft or (nx, ny) in occupied:
                    continue
                if nc < best.get((nx, ny), 1e9):
                    best[(nx, ny)] = nc
                    heapq.heappush(q, (nc, (nx, ny)))
    return best


def deploy(m: dict, count: int, side: str, taken: set[tuple[int, int]], rng: random.Random) -> list[tuple[int, int]]:
    """Starting squares: PCs on the left edge, enemies on the right."""
    w, h = m["grid"]["w"], m["grid"]["h"]
    cols = range(0, max(2, w // 4)) if side == "left" else range(w - 1, w - 1 - max(2, w // 4), -1)
    spots = [(x, y) for x in cols for y in range(h) if passable(m, x, y) and (x, y) not in taken]
    spots.sort(key=lambda p: (abs(p[1] - h // 2) + (p[0] if side == "left" else w - 1 - p[0]) * 0.5, rng.random()))
    out = spots[:count]
    if len(out) < count:  # fall back to any floor
        extra = [(x, y) for y in range(h) for x in range(w) if passable(m, x, y) and (x, y) not in taken
                 and (x, y) not in out]
        out += extra[: count - len(out)]
    return out


def step_toward(m: dict, start: tuple[int, int], goal: tuple[int, int], budget_ft: int,
                occupied: set[tuple[int, int]], stop_within_ft: int = 5) -> tuple[int, int]:
    """Best square to move to that ends closest to goal (stopping when within stop_within_ft)."""
    if distance_ft(start, goal) <= stop_within_ft:
        return start
    opts = reachable(m, start, budget_ft, occupied - {start})
    return min(opts, key=lambda p: (max(0, distance_ft(p, goal) - stop_within_ft), opts[p]))
