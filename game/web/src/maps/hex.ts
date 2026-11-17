// Pointy-top hexes in "odd-r" offset coordinates (odd rows shifted right by half a hex).

export const SQRT3 = Math.sqrt(3);

export function hexCenter(q: number, r: number, size: number): [number, number] {
  return [size * SQRT3 * (q + 0.5 * (r & 1)), size * 1.5 * r];
}

export function hexCorners(cx: number, cy: number, size: number): [number, number][] {
  const pts: [number, number][] = [];
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 180) * (60 * i - 30);
    pts.push([cx + size * Math.cos(a), cy + size * Math.sin(a)]);
  }
  return pts;
}

export function neighbors(q: number, r: number): [number, number][] {
  const odd = r & 1;
  return odd
    ? [
        [q + 1, r],
        [q - 1, r],
        [q, r - 1],
        [q + 1, r - 1],
        [q, r + 1],
        [q + 1, r + 1],
      ]
    : [
        [q + 1, r],
        [q - 1, r],
        [q - 1, r - 1],
        [q, r - 1],
        [q - 1, r + 1],
        [q, r + 1],
      ];
}

/** Steps between two hexes (odd-r offset → cube distance). */
export function hexDistance(a: [number, number], b: [number, number]): number {
  const cube = ([q, r]: [number, number]) => {
    const x = q - (r - (r & 1)) / 2;
    return [x, -x - r, r];
  };
  const [ax, ay, az] = cube(a);
  const [bx, by, bz] = cube(b);
  return Math.max(Math.abs(ax - bx), Math.abs(ay - by), Math.abs(az - bz));
}

/** Rough compass direction from one hex to another ("north-east"). */
export function compass(from: [number, number], to: [number, number]): string {
  const [x1, y1] = hexCenter(from[0], from[1], 1);
  const [x2, y2] = hexCenter(to[0], to[1], 1);
  const deg = (Math.atan2(x2 - x1, -(y2 - y1)) * 180) / Math.PI;
  const names = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"];
  return names[((Math.round(deg / 45) % 8) + 8) % 8];
}

/** World-space point → nearest hex (q, r). */
export function pixelToHex(x: number, y: number, size: number): [number, number] {
  const rApprox = Math.round(y / (size * 1.5));
  let best: [number, number] = [0, 0];
  let bestD = Infinity;
  for (let r = rApprox - 1; r <= rApprox + 1; r++) {
    const qApprox = Math.round(x / (size * SQRT3) - 0.5 * (r & 1));
    for (let q = qApprox - 1; q <= qApprox + 1; q++) {
      const [cx, cy] = hexCenter(q, r, size);
      const d = (cx - x) ** 2 + (cy - y) ** 2;
      if (d < bestD) {
        bestD = d;
        best = [q, r];
      }
    }
  }
  return best;
}

export const BIOME_COLORS: Record<string, string> = {
  "~": "#1f3b5c",
  "-": "#3f6e8c",
  ".": "#a8a35e",
  '"': "#7f9c4a",
  f: "#4f7a3a",
  F: "#2f5428",
  h: "#8a7a4e",
  M: "#7d7570",
  s: "#4f5f3f",
  d: "#d1b77a",
  n: "#dfe6ea",
};

export const BIOME_NAMES: Record<string, string> = {
  "~": "Deep water",
  "-": "Coast",
  ".": "Plains",
  '"': "Grassland",
  f: "Forest",
  F: "Dense forest",
  h: "Hills",
  M: "Mountains",
  s: "Swamp",
  d: "Desert",
  n: "Tundra",
};
