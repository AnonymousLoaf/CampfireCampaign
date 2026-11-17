import { useEffect, useRef } from "react";

/**
 * A 3D d20 drawn on a canvas: it tumbles across a felt table, bounces, and comes to rest with the rolled number
 * facing up. No libraries — an icosahedron, a rotation matrix and painter's-order shading.
 */

type V = [number, number, number];
type M = number[]; // 3×3, row-major

const PHI = (1 + Math.sqrt(5)) / 2;

const dot = (a: V, b: V) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: V, b: V): V => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const sub = (a: V, b: V): V => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const norm = (a: V): V => {
  const l = Math.hypot(...a) || 1;
  return [a[0] / l, a[1] / l, a[2] / l];
};
const mul = (a: M, b: M): M => {
  const o = new Array(9).fill(0);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) for (let k = 0; k < 3; k++) o[i * 3 + j] += a[i * 3 + k] * b[k * 3 + j];
  return o;
};
const apply = (m: M, v: V): V => [
  m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
  m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
  m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
];
/** Rotation of `angle` radians about a unit axis (Rodrigues). */
function rot(axis: V, angle: number): M {
  const [x, y, z] = norm(axis);
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  const t = 1 - c;
  return [t * x * x + c, t * x * y - s * z, t * x * z + s * y, t * x * y + s * z, t * y * y + c, t * y * z - s * x, t * x * z - s * y, t * y * z + s * x, t * z * z + c];
}

// ── the solid ────────────────────────────────────────────────────────────────
const VERTS: V[] = (
  [
    [-1, PHI, 0], [1, PHI, 0], [-1, -PHI, 0], [1, -PHI, 0],
    [0, -1, PHI], [0, 1, PHI], [0, -1, -PHI], [0, 1, -PHI],
    [PHI, 0, -1], [PHI, 0, 1], [-PHI, 0, -1], [-PHI, 0, 1],
  ] as V[]
).map(norm);

type Face = { v: [number, number, number]; c: V; n: V; num: number };

const FACES: Face[] = (() => {
  const edge = Math.min(...VERTS.slice(1).map((v) => Math.hypot(...sub(v, VERTS[0]))));
  const near = (a: number, b: number) => Math.abs(Math.hypot(...sub(VERTS[a], VERTS[b])) - edge) < 1e-6;
  const faces: Face[] = [];
  for (let a = 0; a < 12; a++)
    for (let b = a + 1; b < 12; b++)
      for (let c = b + 1; c < 12; c++) {
        if (!near(a, b) || !near(b, c) || !near(a, c)) continue;
        const cen = norm([(VERTS[a][0] + VERTS[b][0] + VERTS[c][0]) / 3, (VERTS[a][1] + VERTS[b][1] + VERTS[c][1]) / 3, (VERTS[a][2] + VERTS[b][2] + VERTS[c][2]) / 3]);
        let n = norm(cross(sub(VERTS[b], VERTS[a]), sub(VERTS[c], VERTS[a])));
        let v: [number, number, number] = [a, b, c];
        if (dot(n, cen) < 0) {
          n = [-n[0], -n[1], -n[2]];
          v = [a, c, b];
        }
        faces.push({ v, c: cen, n, num: 0 });
      }
  // Number them like a real die: opposite faces add up to 21.
  let k = 1;
  for (const f of faces) {
    if (f.num) continue;
    const opp = faces.find((g) => !g.num && g !== f && dot(g.n, f.n) < -0.99)!;
    f.num = k;
    opp.num = 21 - k;
    k++;
  }
  return faces;
})();

/** The orientation that shows `value` face-on to the viewer, point up. */
function restingOrientation(value: number): M {
  const f = FACES.find((x) => x.num === value) ?? FACES[0];
  const z: V = [0, 0, 1];
  const axis = cross(f.n, z);
  const ang = Math.acos(Math.max(-1, Math.min(1, dot(f.n, z))));
  const r1 = Math.hypot(...axis) < 1e-6 ? (ang > 1 ? rot([1, 0, 0], Math.PI) : rot(z, 0)) : rot(axis, ang);
  const tip = apply(r1, sub(VERTS[f.v[0]], f.c));
  const spin = Math.atan2(tip[0], tip[1]);
  return mul(rot(z, spin), r1);
}

function shade(hex: string, k: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  const n = m ? parseInt(m[1], 16) : 0x8b1e1e;
  const ch = (s: number) => {
    const c = (n >> s) & 255;
    const v = k >= 1 ? c + (255 - c) * (k - 1) : c * k;
    return Math.max(0, Math.min(255, Math.round(v)));
  };
  return `rgb(${ch(16)},${ch(8)},${ch(0)})`;
}

const LIGHT = norm([-0.45, 0.65, 0.8]);

export default function Dice3D({
  value,
  color = "#8b1e1e",
  tone = "",
  width,
  height,
  duration = 1700,
  instant = false,
  from,
  onLanded,
}: {
  value: number;
  color?: string;
  tone?: "crit" | "fumble" | "";
  width: number;
  height: number;
  duration?: number;
  instant?: boolean;
  /** Which side the die is thrown in from (random if not set). */
  from?: "left" | "right";
  onLanded?: () => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const landedRef = useRef(onLanded);
  landedRef.current = onLanded;
  const toneRef = useRef(tone); // crit/fumble styling shows only once the die has stopped
  toneRef.current = tone;

  useEffect(() => {
    const cv = ref.current;
    const ctx = cv?.getContext("2d");
    if (!cv || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = width * dpr;
    cv.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const R = Math.min(width, height) * 0.27;
    const tableY = height * 0.8;
    const finalM = restingOrientation(value);
    const spinAxis = norm([Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5]);
    const spinTurns = (5 + Math.random() * 3) * Math.PI * 2;
    const fromLeft = from ? from === "left" : Math.random() < 0.5;
    const startX = fromLeft ? -R * 1.5 : width + R * 1.5;
    const restX = width / 2;
    const bounces = 3;

    const draw = (t: number) => {
      const tone = t >= 1 ? toneRef.current : "";
      const e = 1 - Math.pow(1 - t, 3);
      const m = mul(finalM, rot(spinAxis, spinTurns * (1 - e)));
      const x = startX + (restX - startX) * Math.min(1, e * 1.08);
      const hop = Math.abs(Math.sin(Math.PI * bounces * Math.min(1, t * 1.15))) * height * 0.32 * Math.pow(1 - Math.min(1, t * 1.15), 1.6);
      const y = tableY - R * 0.95 - hop;

      ctx.clearRect(0, 0, width, height);
      // shadow on the felt
      const sh = Math.max(0.25, 1 - hop / (height * 0.4));
      ctx.fillStyle = `rgba(0,0,0,${0.35 * sh})`;
      ctx.beginPath();
      ctx.ellipse(x, tableY, R * 0.95 * sh, R * 0.22 * sh, 0, 0, Math.PI * 2);
      ctx.fill();

      const pts = VERTS.map((v) => {
        const p = apply(m, v);
        const persp = 3.2 / (3.2 - p[2]);
        return { x: x + p[0] * R * persp, y: y - p[1] * R * persp, z: p[2] };
      });
      const faces = FACES.map((f) => ({ f, n: apply(m, f.n), c: apply(m, f.c) }))
        .filter((o) => o.n[2] > 0)
        .sort((a, b) => a.c[2] - b.c[2]);
      const edge = tone === "crit" ? "#ffd36b" : tone === "fumble" ? "#2a0f0f" : "rgba(255,240,220,0.55)";
      for (const { f, n, c } of faces) {
        const lit = 0.45 + 0.75 * Math.max(0, dot(n, LIGHT));
        ctx.beginPath();
        f.v.forEach((vi, i) => (i ? ctx.lineTo(pts[vi].x, pts[vi].y) : ctx.moveTo(pts[vi].x, pts[vi].y)));
        ctx.closePath();
        ctx.fillStyle = shade(tone === "fumble" ? "#3b3030" : color, lit);
        ctx.fill();
        ctx.strokeStyle = edge;
        ctx.lineWidth = tone === "crit" ? 2 : 1.2;
        ctx.lineJoin = "round";
        ctx.stroke();
        if (n[2] > 0.2) {
          const persp = 3.2 / (3.2 - c[2]);
          const cx = x + c[0] * R * persp * 0.98;
          const cy = y - c[1] * R * persp * 0.98;
          const size = R * 0.36 * Math.sqrt(n[2]);
          ctx.font = `700 ${size.toFixed(1)}px Cinzel, Georgia, serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillStyle = tone === "crit" && f.num === value ? "#ffe9a8" : `rgba(255,248,235,${0.35 + 0.65 * n[2]})`;
          ctx.fillText(String(f.num), cx, cy + size * 0.04);
          if (f.num === 6 || f.num === 9) ctx.fillRect(cx - size * 0.22, cy + size * 0.42, size * 0.44, Math.max(1, size * 0.07));
        }
      }
    };

    if (instant) {
      draw(1);
      landedRef.current?.();
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    let done = false;
    const frame = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      draw(t);
      if (t < 1) raf = requestAnimationFrame(frame);
      else if (!done) {
        done = true;
        landedRef.current?.();
      }
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [value, color, width, height, duration, instant, from]);

  return <canvas ref={ref} className="dice3d" style={{ width, height }} aria-hidden />;
}
