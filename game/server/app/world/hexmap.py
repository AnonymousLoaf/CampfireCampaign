"""Procedural world map: seeded hex grid with biomes, settlements, roads and points of interest.

Coordinates are "odd-r" offset (pointy-top hexes, odd rows shifted right), matching the frontend.
Code makes the geography; the AI DM names and flavours it.
"""
from __future__ import annotations

import heapq
import math
import random

W, H = 40, 30

BIOME_COST = {"~": None, "-": None, ".": 1.0, '"': 1.0, "f": 1.5, "F": 2.0, "h": 2.0, "M": 4.0,
              "s": 2.5, "d": 1.5, "n": 2.0}
BIOME_NAMES = {"~": "deep water", "-": "coast", ".": "plains", '"': "grassland", "f": "forest",
               "F": "dense forest", "h": "hills", "M": "mountains", "s": "swamp", "d": "desert", "n": "tundra"}
HEXES_PER_DAY = 4  # ~6 miles per hex, ~24 miles a day on open ground

_SYL_A = ["Ash", "Bram", "Cold", "Dun", "Eld", "Fen", "Gal", "Hollow", "Iron", "Kel", "Lorn", "Mar", "Nor",
          "Oak", "Pell", "Quill", "Raven", "Stone", "Thorn", "Umber", "Vale", "Wyn", "Yarrow", "Bright", "Grey"]
_SYL_B = ["ford", "wick", "holm", "stead", "mere", "watch", "gate", "bury", "dale", "hollow", "crest", "reach",
          "moor", "fall", "haven", "barrow", "brook", "march", "well", "keep"]
_POI = {"cave": ["Cave", "Grotto", "Hollow", "Den"], "ruins": ["Ruins", "Old Fort", "Fallen Hall", "Broken Tower"],
        "tower": ["Tower", "Spire", "Watchtower"], "camp": ["Camp", "Hideout", "Lair"],
        "shrine": ["Shrine", "Standing Stones", "Chapel"]}


# ── coordinates ─────────────────────────────────────────────────────────────

def to_cube(q: int, r: int) -> tuple[int, int, int]:
    x = q - (r - (r & 1)) // 2
    z = r
    return x, -x - z, z


def distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    ax, ay, az = to_cube(*a)
    bx, by, bz = to_cube(*b)
    return max(abs(ax - bx), abs(ay - by), abs(az - bz))


def neighbors(q: int, r: int) -> list[tuple[int, int]]:
    if r & 1:
        deltas = [(1, 0), (-1, 0), (0, -1), (1, -1), (0, 1), (1, 1)]
    else:
        deltas = [(1, 0), (-1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1)]
    return [(q + dq, r + dr) for dq, dr in deltas if 0 <= q + dq < W and 0 <= r + dr < H]


def within(center: tuple[int, int], radius: int) -> list[tuple[int, int]]:
    return [(q, r) for r in range(H) for q in range(W) if distance(center, (q, r)) <= radius]


# ── noise ───────────────────────────────────────────────────────────────────

def _value_noise(rng: random.Random, w: int, h: int, octaves: int = 4) -> list[list[float]]:
    out = [[0.0] * w for _ in range(h)]
    amp_total = 0.0
    for o in range(octaves):
        cell = max(2, 12 // (2 ** o))
        gw, gh = w // cell + 2, h // cell + 2
        grid = [[rng.random() for _ in range(gw)] for _ in range(gh)]
        amp = 0.5 ** o
        amp_total += amp
        for y in range(h):
            for x in range(w):
                fx, fy = x / cell, y / cell
                x0, y0 = int(fx), int(fy)
                tx, ty = fx - x0, fy - y0
                tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
                a = grid[y0][x0] * (1 - tx) + grid[y0][x0 + 1] * tx
                b = grid[y0 + 1][x0] * (1 - tx) + grid[y0 + 1][x0 + 1] * tx
                out[y][x] += (a * (1 - ty) + b * ty) * amp
    return [[v / amp_total for v in row] for row in out]


def place_name(rng: random.Random, used: set[str]) -> str:
    for _ in range(50):
        a, b = rng.choice(_SYL_A), rng.choice(_SYL_B)
        n = a + b
        if b in a.lower():
            continue
        if n not in used:
            used.add(n)
            return n
    n = f"{rng.choice(_SYL_A)}{rng.choice(_SYL_B)} {len(used)}"
    used.add(n)
    return n


# ── generation ──────────────────────────────────────────────────────────────

def generate(seed: int) -> dict:
    rng = random.Random(seed)
    elev = _value_noise(rng, W, H, 4)
    moist = _value_noise(rng, W, H, 3)
    rows: list[list[str]] = []
    for r in range(H):
        row = []
        for q in range(W):
            # fall off towards the edges so the map is a land mass with coasts
            dx, dy = (q - W / 2) / (W / 2), (r - H / 2) / (H / 2)
            e = elev[r][q] + 0.12 - 0.45 * max(0.0, math.hypot(dx, dy) - 0.7)
            m = moist[r][q]
            if e < 0.30:
                b = "~"
            elif e < 0.34:
                b = "-"
            elif e > 0.72:
                b = "M"
            elif e > 0.62:
                b = "h"
            elif r < 3 and e > 0.5:
                b = "n"
            elif m < 0.33:
                b = "d" if r > H * 0.6 else "."
            elif m < 0.45:
                b = '"'
            elif m < 0.58:
                b = "f"
            elif m < 0.68:
                b = "F"
            else:
                b = "s"
            row.append(b)
        rows.append(row)

    land = _largest_landmass(rows)
    used_names: set[str] = set()

    # settlements: prefer plains/grassland near water, spread apart
    def score(c):
        q, r = c
        b = rows[r][q]
        s = {".": 3, '"': 3, "f": 1.5, "h": 1, "d": 0.5, "s": 0.2, "F": 0.5, "n": 0.3, "M": 0}.get(b, 0)
        if any(rows[nr][nq] in "~-" for nq, nr in neighbors(q, r)):
            s += 2
        if q < 3 or q > W - 4 or r < 3 or r > H - 4:
            s -= 3  # keep towns off the map edges
        return s + rng.random()

    cands = sorted(land, key=score, reverse=True)
    settlements: list[dict] = []
    for c in cands:
        if len(settlements) >= 8:
            break
        if rows[c[1]][c[0]] == "M":
            continue
        if all(distance(c, (s["q"], s["r"])) >= 6 for s in settlements):
            settlements.append({"q": c[0], "r": c[1]})
    for i, s in enumerate(settlements):
        size = "city" if i == 0 else ("town" if i <= 2 else "village")
        s.update({
            "id": f"s{i}", "name": place_name(rng, used_names), "size": size,
            "shops": {"village": ["general", "inn", "temple"],
                      "town": ["general", "blacksmith", "alchemist", "inn", "temple"],
                      "city": ["general", "blacksmith", "alchemist", "magic", "inn", "temple"]}[size],
            "description": "",
        })

    # roads: minimum spanning tree over settlements, each edge routed by cheapest path
    roads: set[tuple[int, int]] = set()
    if settlements:
        connected = [settlements[0]]
        rest = settlements[1:]
        while rest:
            a, b = min(((a, b) for a in connected for b in rest),
                       key=lambda p: distance((p[0]["q"], p[0]["r"]), (p[1]["q"], p[1]["r"])))
            path = find_path(rows, (a["q"], a["r"]), (b["q"], b["r"]), set())
            if path:
                roads.update(path)
            connected.append(b)
            rest.remove(b)

    # points of interest
    pois = []
    poi_cands = [c for c in land if all(distance(c, (s["q"], s["r"])) >= 3 for s in settlements)]
    rng.shuffle(poi_cands)
    for c in poi_cands:
        if len(pois) >= 10:
            break
        if any(distance(c, (p["q"], p["r"])) < 4 for p in pois):
            continue
        b = rows[c[1]][c[0]]
        kind = {"M": "cave", "h": "cave", "F": "camp", "f": "camp", "s": "ruins", "d": "ruins"}.get(b)
        kind = kind or rng.choice(["ruins", "tower", "shrine"])
        pois.append({"id": f"p{len(pois)}", "kind": kind, "q": c[0], "r": c[1],
                     "name": f"{place_name(rng, used_names)} {rng.choice(_POI[kind])}", "description": ""})

    # start in the most central town or city (villages only if there's nothing bigger)
    bigger = [s for s in settlements if s["size"] != "village"] or settlements
    start = min(bigger, key=lambda s: distance((s["q"], s["r"]), (W // 2, H // 2))) if settlements \
        else {"q": W // 2, "r": H // 2, "id": None}
    world = {
        "seed": seed, "w": W, "h": H,
        "hexes": ["".join(row) for row in rows],
        "settlements": settlements, "pois": pois,
        "roads": sorted([list(c) for c in roads]),
        "party": {"q": start["q"], "r": start["r"]},
        "revealed": [],
        "gazetteer": {},
    }
    reveal(world, (start["q"], start["r"]), 3)
    return world


def _largest_landmass(rows) -> list[tuple[int, int]]:
    """Hexes of the biggest connected walkable region (so every settlement is reachable)."""
    seen: set = set()
    best: list = []
    for r in range(H):
        for q in range(W):
            if (q, r) in seen or BIOME_COST[rows[r][q]] is None:
                continue
            comp, stack = [], [(q, r)]
            seen.add((q, r))
            while stack:
                c = stack.pop()
                comp.append(c)
                for nb in neighbors(*c):
                    if nb not in seen and BIOME_COST[rows[nb[1]][nb[0]]] is not None:
                        seen.add(nb)
                        stack.append(nb)
            if len(comp) > len(best):
                best = comp
    return best


def find_path(rows, start: tuple[int, int], goal: tuple[int, int], roads: set) -> list[tuple[int, int]] | None:
    """A* over the hex grid; water is impassable, roads are cheap."""
    if start == goal:
        return [start]
    openq = [(0.0, start)]
    came: dict = {start: None}
    cost = {start: 0.0}
    while openq:
        _, cur = heapq.heappop(openq)
        if cur == goal:
            break
        for nb in neighbors(*cur):
            b = rows[nb[1]][nb[0]]
            c = BIOME_COST.get(b)
            if c is None and nb != goal:
                continue
            step = 0.5 if nb in roads else (c or 1.0)
            nc = cost[cur] + step
            if nb not in cost or nc < cost[nb]:
                cost[nb] = nc
                came[nb] = cur
                heapq.heappush(openq, (nc + distance(nb, goal), nb))
    if goal not in came:
        return None
    path = [goal]
    while path[-1] != start:
        path.append(came[path[-1]])
    return list(reversed(path))


def _revealed_set(world: dict) -> set[tuple[int, int]]:
    return {tuple(c) for c in world.get("revealed", [])}


def reveal(world: dict, center: tuple[int, int], radius: int) -> None:
    seen = _revealed_set(world)
    for c in within(center, radius):
        seen.add(c)
    world["revealed"] = sorted([list(c) for c in seen])


def biome_at(world: dict, q: int, r: int) -> str:
    return world["hexes"][r][q]


def settlement_at(world: dict, q: int, r: int) -> dict | None:
    return next((s for s in world["settlements"] if s["q"] == q and s["r"] == r), None)


def poi_at(world: dict, q: int, r: int) -> dict | None:
    return next((p for p in world["pois"] if p["q"] == q and p["r"] == r), None)


DIRECTIONS = {"n": (0, -1), "ne": (0.7071, -0.7071), "e": (1, 0), "se": (0.7071, 0.7071), "s": (0, 1),
              "sw": (-0.7071, 0.7071), "w": (-1, 0), "nw": (-0.7071, -0.7071)}
_DIR_WORDS = {"north": "n", "northeast": "ne", "north-east": "ne", "east": "e", "southeast": "se", "south-east": "se",
              "south": "s", "southwest": "sw", "south-west": "sw", "west": "w", "northwest": "nw", "north-west": "nw"}


def _pixel(q: int, r: int) -> tuple[float, float]:
    return math.sqrt(3) * (q + 0.5 * (r & 1)), 1.5 * r


def _from_pixel(x: float, y: float) -> tuple[int, int]:
    r = round(y / 1.5)
    q = round(x / math.sqrt(3) - 0.5 * (r & 1))
    return q, r


def hex_toward(world: dict, direction: str, hexes: int) -> tuple[int, int] | None:
    """The hex about `hexes` steps from the party in a compass direction ("n", "northeast", ...), pulled back toward
    the party until it lands on reachable ground. None if the direction is unknown or there is nowhere to go."""
    d = direction.strip().lower().replace(" ", "")
    d = _DIR_WORDS.get(d, d)
    if d not in DIRECTIONS:
        return None
    dx, dy = DIRECTIONS[d]
    start = (world["party"]["q"], world["party"]["r"])
    sx, sy = _pixel(*start)
    rows = [list(r) for r in world["hexes"]]
    roads = {tuple(c) for c in world.get("roads", [])}
    for n in range(max(1, hexes), 0, -1):
        q, r = _from_pixel(sx + dx * n * math.sqrt(3), sy + dy * n * math.sqrt(3))
        q, r = min(max(q, 0), world["w"] - 1), min(max(r, 0), world["h"] - 1)
        if (q, r) == start or BIOME_COST.get(rows[r][q]) is None:
            continue
        if find_path(rows, start, (q, r), roads):
            return q, r
    return None


def plan_travel(world: dict, dest: tuple[int, int]) -> dict:
    rows = [list(r) for r in world["hexes"]]
    start = (world["party"]["q"], world["party"]["r"])
    roads = {tuple(c) for c in world.get("roads", [])}
    path = find_path(rows, start, dest, roads)
    if not path:
        return {"ok": False, "reason": "no route over land"}
    total = 0.0
    for c in path[1:]:
        total += 0.5 if c in roads else (BIOME_COST.get(rows[c[1]][c[0]]) or 1.0)
    days = max(0.25, round(total / HEXES_PER_DAY * 4) / 4)
    biomes = [rows[c[1]][c[0]] for c in path[1:]]
    main = max(set(biomes), key=biomes.count) if biomes else rows[start[1]][start[0]]
    return {"ok": True, "path": [list(c) for c in path], "days": days, "hexes": len(path) - 1, "main_biome": main}


def apply_travel(world: dict, plan: dict) -> None:
    for c in plan["path"]:
        reveal(world, tuple(c), 1)
    end = tuple(plan["path"][-1])
    reveal(world, end, 2)
    world["party"] = {"q": end[0], "r": end[1]}


def view(world: dict) -> dict:
    seen = _revealed_set(world)
    revealed_rows = ["".join("1" if (q, r) in seen else "0" for q in range(world["w"])) for r in range(world["h"])]
    return {
        "w": world["w"], "h": world["h"], "hexes": world["hexes"], "revealed": revealed_rows,
        "settlements": [{k: s[k] for k in ("id", "name", "q", "r", "size", "shops", "description")}
                        for s in world["settlements"] if (s["q"], s["r"]) in seen or s.get("known")],
        "pois": [{k: p.get(k, "") for k in ("id", "name", "kind", "q", "r", "description")}
                 for p in world["pois"] if (p["q"], p["r"]) in seen],
        "roads": world.get("roads", []),
        "party": world["party"],
    }
