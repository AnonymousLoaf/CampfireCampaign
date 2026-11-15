import type { CharacterView, Encounter, SpellArea, Token } from "../api/types";

/**
 * Squares covered by an area of effect. Spheres and cubes are centred on `point`;
 * cones and lines start at `origin` (the caster) and point toward `point`.
 * Cubes use the size as their side length, spheres as their radius (5e grid rules, 5 ft squares).
 */
export function templateSquares(
  enc: Encounter,
  area: SpellArea | null,
  origin: [number, number],
  point: [number, number],
): [number, number][] {
  const out: [number, number][] = [];
  const inMap = (x: number, y: number) => x >= 0 && y >= 0 && x < enc.grid.w && y < enc.grid.h && cellAt(enc, x, y) !== " ";
  if (!area) return inMap(point[0], point[1]) ? [point] : [];
  const cells = area.size_ft / 5;
  const [px, py] = point;
  const [ox, oy] = origin;
  for (let y = 0; y < enc.grid.h; y++) {
    for (let x = 0; x < enc.grid.w; x++) {
      if (!inMap(x, y)) continue;
      let hit = false;
      if (area.shape === "sphere") {
        hit = Math.max(Math.abs(x - px), Math.abs(y - py)) <= cells;
      } else if (area.shape === "cube") {
        const half = Math.max(0, (cells - 1) / 2);
        hit = Math.abs(x - px) <= Math.ceil(half) && Math.abs(y - py) <= Math.ceil(half);
      } else {
        const dx = px - ox;
        const dy = py - oy;
        const len = Math.hypot(dx, dy) || 1;
        const ux = dx / len;
        const uy = dy / len;
        const vx = x - ox;
        const vy = y - oy;
        const along = vx * ux + vy * uy;
        const across = Math.abs(vx * uy - vy * ux);
        if (x === ox && y === oy) continue;
        if (area.shape === "line") hit = along > 0 && along <= cells + 0.01 && across <= 0.5;
        else hit = along > 0 && along <= cells + 0.01 && across <= along * 0.5 + 0.5; // cone: width = distance
      }
      if (hit) out.push([x, y]);
    }
  }
  return out;
}

const BLOCKING = new Set(["#", "T", " "]);

export function cellAt(enc: Encounter, x: number, y: number): string {
  if (x < 0 || y < 0 || x >= enc.grid.w || y >= enc.grid.h) return " ";
  return enc.cells[y]?.[x] ?? " ";
}

/** 5e grid distance in feet (every step, diagonals included, is 5 ft). */
export function distanceFt(a: { x: number; y: number }, b: { x: number; y: number }): number {
  return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y)) * 5;
}

const alive = (t: Token) => t.hp_state !== "dead" && t.hp_state !== "down";

/**
 * Client-side fallback for squares a token can reach with `budgetFt` of movement.
 * Used when I'm acting for a party member whose token isn't `my_token_id` (the server
 * only sends `reachable` for that one). The server still validates every move.
 */
export function computeReachable(enc: Encounter, token: Token, budgetFt: number): [number, number][] {
  const cost = new Map<string, number>();
  const key = (x: number, y: number) => `${x},${y}`;
  const occupied = new Map<string, Token>();
  for (const t of enc.tokens) if (t.id !== token.id && t.hp_state !== "dead") occupied.set(key(t.x, t.y), t);
  const queue: [number, number, number][] = [[token.x, token.y, 0]];
  cost.set(key(token.x, token.y), 0);
  while (queue.length) {
    queue.sort((a, b) => a[2] - b[2]);
    const [x, y, c] = queue.shift()!;
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++) {
        if (!dx && !dy) continue;
        const nx = x + dx;
        const ny = y + dy;
        const cell = cellAt(enc, nx, ny);
        if (BLOCKING.has(cell)) continue;
        // no squeezing diagonally between two walls
        if (dx && dy && BLOCKING.has(cellAt(enc, x + dx, y)) && BLOCKING.has(cellAt(enc, x, y + dy))) continue;
        const occ = occupied.get(key(nx, ny));
        if (occ && occ.kind !== token.kind && alive(occ)) continue; // can't pass through enemies
        const nc = c + (cell === "~" ? 10 : 5);
        if (nc > budgetFt) continue;
        const k = key(nx, ny);
        if ((cost.get(k) ?? Infinity) <= nc) continue;
        cost.set(k, nc);
        queue.push([nx, ny, nc]);
      }
  }
  const out: [number, number][] = [];
  for (const [k] of cost) {
    const [x, y] = k.split(",").map(Number);
    if (x === token.x && y === token.y) continue;
    if (occupied.has(k)) continue; // can't end on another creature
    out.push([x, y]);
  }
  return out;
}

/** Client-side fallback for what a character could target from their token. */
export function computeTargets(enc: Encounter, token: Token, ch: CharacterView | undefined): Encounter["targets"] {
  if (!ch) return [];
  const out: Encounter["targets"] = [];
  for (const t of enc.tokens) {
    if (t.id === token.id || t.hp_state === "dead") continue;
    const d = distanceFt(token, t);
    const enemy = t.kind !== token.kind;
    const attack_ids = enemy
      ? ch.attacks.filter((a) => d <= (a.long_range_ft ?? a.range_ft)).map((a) => a.id)
      : [];
    const spells = [...(ch.spellcasting?.cantrips ?? []), ...(ch.spellcasting?.spells ?? [])].filter((s) => s.combat);
    const spell_indexes = spells
      .filter((s) => (enemy ? s.kind !== "heal" : s.kind === "heal"))
      .filter((s) => s.range_ft === null || d <= Math.max(5, s.range_ft))
      .map((s) => s.index);
    if (attack_ids.length || spell_indexes.length) out.push({ token_id: t.id, attack_ids, spell_indexes });
  }
  return out;
}
