/**
 * Physics dice that roll across the whole screen and land on the server's results.
 *
 * How the result is guaranteed: each throw is first simulated offscreen with cannon-es (fixed time step, so it's
 * deterministic). When the dice have settled we look at which face of each die ended up on top, and swap the
 * numbers printed on the die so that face shows the value the server rolled. Then the recorded motion is played
 * back with three.js. It looks like a free, random throw and always shows the real roll.
 *
 * Loaded lazily (three.js + cannon-es are ~150 KB gzipped) the first time someone rolls.
 */
import * as CANNON from "cannon-es";
import * as THREE from "three";

export type Sides = 4 | 6 | 8 | 10 | 12 | 20;
export interface DieSpec {
  sides: Sides;
  value: number;
  color: string;
  /** Faded after landing: the dropped die of an advantage / disadvantage pair. */
  dropped?: boolean;
  /** Glow after landing. */
  glow?: "crit" | "fumble" | null;
}

const VIEW_H = 20; // world units across the screen's height
const STEP = 1 / 60;
const MAX_STEPS = 60 * 8;

// ── geometry ────────────────────────────────────────────────────────────────

interface Face {
  normal: THREE.Vector3;
  centroid: THREE.Vector3;
  verts: number[]; // indices into the die's unique vertices, counter-clockwise seen from outside
  tris: number[]; // triangle indices in the non-indexed geometry
}

interface DieShape {
  sides: Sides;
  geometry: THREE.BufferGeometry; // non-indexed, one group per face
  faces: Face[];
  verts: THREE.Vector3[];
  shape: CANNON.ConvexPolyhedron;
}

function d10Geometry(r: number): THREE.BufferGeometry {
  // Pentagonal trapezohedron with planar kite faces: ring heights ±h, apex height h(1+cos36)/(1-cos36).
  const h = 0.105;
  const apex = (h * (1 + Math.cos(Math.PI / 5))) / (1 - Math.cos(Math.PI / 5));
  const ring: THREE.Vector3[] = [];
  for (let i = 0; i < 10; i++) {
    const a = (i * Math.PI) / 5;
    ring.push(new THREE.Vector3(Math.cos(a), i % 2 === 0 ? h : -h, Math.sin(a)));
  }
  const top = new THREE.Vector3(0, apex, 0);
  const bot = new THREE.Vector3(0, -apex, 0);
  const tri: THREE.Vector3[] = [];
  const push = (...p: THREE.Vector3[]) => tri.push(...p.map((v) => v.clone().multiplyScalar(r)));
  for (let k = 0; k < 5; k++) {
    const p0 = ring[2 * k], p1 = ring[(2 * k + 1) % 10], p2 = ring[(2 * k + 2) % 10], p3 = ring[(2 * k + 3) % 10];
    push(top, p2, p1); // top kite: apex, even (up), odd (down), even (up)
    push(top, p1, p0);
    push(bot, p1, p2); // bottom kite: apex, odd (down), even (up), odd (down)
    push(bot, p2, p3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(tri.flatMap((v) => [v.x, v.y, v.z]), 3));
  g.computeVertexNormals();
  return g;
}

function baseGeometry(sides: Sides, r: number): THREE.BufferGeometry {
  switch (sides) {
    case 4:
      return new THREE.TetrahedronGeometry(r * 1.25).toNonIndexed();
    case 6:
      return new THREE.BoxGeometry(r * 1.25, r * 1.25, r * 1.25).toNonIndexed();
    case 8:
      return new THREE.OctahedronGeometry(r * 1.1).toNonIndexed();
    case 10:
      return d10Geometry(r * 1.05);
    case 12:
      return new THREE.DodecahedronGeometry(r * 1.05).toNonIndexed();
    default:
      return new THREE.IcosahedronGeometry(r * 1.05).toNonIndexed();
  }
}

function buildShape(sides: Sides, r: number): DieShape {
  const g = baseGeometry(sides, r);
  const pos = g.getAttribute("position") as THREE.BufferAttribute;
  const triCount = pos.count / 3;
  const verts: THREE.Vector3[] = [];
  const vIndex = (p: THREE.Vector3) => {
    const i = verts.findIndex((v) => v.distanceToSquared(p) < 1e-6);
    if (i >= 0) return i;
    verts.push(p.clone());
    return verts.length - 1;
  };
  const faces: Face[] = [];
  const flipped: boolean[] = []; // triangles wound inward (rendered and used the other way round)
  for (let t = 0; t < triCount; t++) {
    const a = new THREE.Vector3().fromBufferAttribute(pos, t * 3);
    const b = new THREE.Vector3().fromBufferAttribute(pos, t * 3 + 1);
    const c = new THREE.Vector3().fromBufferAttribute(pos, t * 3 + 2);
    const n = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a)).normalize();
    const mid = new THREE.Vector3().add(a).add(b).add(c).multiplyScalar(1 / 3);
    flipped[t] = n.dot(mid) < 0; // the solid is centred on the origin: outward normals point away from it
    if (flipped[t]) n.negate();
    let f = faces.find((x) => x.normal.dot(n) > 0.999);
    if (!f) {
      f = { normal: n, centroid: new THREE.Vector3(), verts: [], tris: [] };
      faces.push(f);
    }
    f.tris.push(t);
    for (const p of [a, b, c]) {
      const i = vIndex(p);
      if (!f.verts.includes(i)) f.verts.push(i);
    }
  }
  for (const f of faces) {
    f.centroid = f.verts.reduce((acc, i) => acc.add(verts[i]), new THREE.Vector3()).multiplyScalar(1 / f.verts.length);
    const u = new THREE.Vector3().subVectors(verts[f.verts[0]], f.centroid).normalize();
    const w = new THREE.Vector3().crossVectors(f.normal, u);
    const ang = (i: number) => {
      const d = new THREE.Vector3().subVectors(verts[i], f.centroid);
      return Math.atan2(d.dot(w), d.dot(u));
    };
    f.verts.sort((x, y) => ang(x) - ang(y));
  }
  // Rebuild the geometry: one material group per face, UVs projected onto each face.
  const out = new THREE.BufferGeometry();
  const P: number[] = [], N: number[] = [], UV: number[] = [];
  faces.forEach((f, fi) => {
    const u = new THREE.Vector3().subVectors(verts[f.verts[0]], f.centroid).normalize();
    const w = new THREE.Vector3().crossVectors(f.normal, u);
    const R = Math.max(...f.verts.map((i) => verts[i].distanceTo(f.centroid)));
    const start = P.length / 3;
    for (const t of f.tris) {
      for (const k of flipped[t] ? [0, 2, 1] : [0, 1, 2]) {
        const p = new THREE.Vector3().fromBufferAttribute(pos, t * 3 + k);
        const d = new THREE.Vector3().subVectors(p, f.centroid);
        P.push(p.x, p.y, p.z);
        N.push(f.normal.x, f.normal.y, f.normal.z);
        UV.push(0.5 + (d.dot(u) / R) * 0.5, 0.5 + (d.dot(w) / R) * 0.5);
      }
    }
    out.addGroup(start, P.length / 3 - start, fi);
  });
  out.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  out.setAttribute("normal", new THREE.Float32BufferAttribute(N, 3));
  out.setAttribute("uv", new THREE.Float32BufferAttribute(UV, 2));
  const shape = new CANNON.ConvexPolyhedron({
    vertices: verts.map((v) => new CANNON.Vec3(v.x, v.y, v.z)),
    faces: faces.map((f) => f.verts),
  });
  return { sides, geometry: out, faces, verts, shape };
}

// ── face textures ───────────────────────────────────────────────────────────

function shade(hex: string, amt: number): string {
  const n = parseInt(hex.slice(1), 16);
  const ch = (s: number) => Math.max(0, Math.min(255, Math.round(((n >> s) & 255) * (1 + amt))));
  return `rgb(${ch(16)},${ch(8)},${ch(0)})`;
}

function faceTexture(label: string, color: string, sides: Sides, cornerLabels?: { u: number; v: number; text: string }[]): THREE.CanvasTexture {
  const S = 128;
  const c = document.createElement("canvas");
  c.width = c.height = S;
  const g = c.getContext("2d")!;
  g.fillStyle = color;
  g.fillRect(0, 0, S, S);
  const grad = g.createRadialGradient(S * 0.4, S * 0.35, 4, S / 2, S / 2, S * 0.75);
  grad.addColorStop(0, "rgba(255,255,255,0.18)");
  grad.addColorStop(1, "rgba(0,0,0,0.18)");
  g.fillStyle = grad;
  g.fillRect(0, 0, S, S);
  g.fillStyle = "#f6ecd6";
  g.strokeStyle = shade(color, -0.55);
  g.lineWidth = 4;
  g.textAlign = "center";
  g.textBaseline = "middle";
  const draw = (text: string, x: number, y: number, size: number) => {
    g.font = `800 ${size}px Georgia, 'Times New Roman', serif`;
    g.strokeText(text, x, y);
    g.fillText(text, x, y);
    if (text === "6" || text === "9") g.fillRect(x - size * 0.22, y + size * 0.42, size * 0.44, size * 0.07);
  };
  if (cornerLabels) {
    for (const l of cornerLabels) draw(l.text, l.u * S, (1 - l.v) * S, 30);
  } else {
    const size = sides === 20 ? 46 : sides === 12 || sides === 10 ? 50 : 60;
    draw(label, S / 2, S / 2, label.length > 1 ? size * 0.82 : size);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

/** Materials for a die whose faces show `labels` (d4: values at the vertices). */
function dieMaterials(d: DieShape, labels: number[], color: string): THREE.MeshStandardMaterial[] {
  return d.faces.map((f, fi) => {
    let tex: THREE.CanvasTexture;
    if (d.sides === 4) {
      // a d4 reads the number at the top point: each face shows each corner's value near that corner
      const u = new THREE.Vector3().subVectors(d.verts[f.verts[0]], f.centroid).normalize();
      const w = new THREE.Vector3().crossVectors(f.normal, u);
      const R = Math.max(...f.verts.map((i) => d.verts[i].distanceTo(f.centroid)));
      const corners = f.verts.map((vi) => {
        const p = new THREE.Vector3().subVectors(d.verts[vi], f.centroid).multiplyScalar(0.55);
        return { u: 0.5 + (p.dot(u) / R) * 0.5, v: 0.5 + (p.dot(w) / R) * 0.5, text: String(labels[vi]) };
      });
      tex = faceTexture("", color, 4, corners);
    } else {
      tex = faceTexture(String(labels[fi]), color, d.sides);
    }
    return new THREE.MeshStandardMaterial({ map: tex, roughness: 0.45, metalness: 0.08, transparent: true });
  });
}

// ── the table ───────────────────────────────────────────────────────────────

export interface Landed {
  /** Screen position (CSS px, relative to the container) where the dice came to rest, for the caption. */
  x: number;
  y: number;
}

export class DiceTable {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private shapes = new Map<string, DieShape>();
  private meshes: THREE.Mesh[] = [];
  private raf = 0;
  private w = 1;
  private h = 1;
  private disposed = false;

  constructor(private host: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.domElement.className = "dice-canvas";
    host.appendChild(this.renderer.domElement);
    this.camera = new THREE.PerspectiveCamera(30, 1, 1, 200);
    this.scene.add(new THREE.HemisphereLight(0xfff4e0, 0x2a2018, 1.1));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(-8, 30, -10);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    const sc = sun.shadow.camera as THREE.OrthographicCamera;
    sc.left = sc.bottom = -30;
    sc.right = sc.top = 30;
    this.scene.add(sun);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.ShadowMaterial({ opacity: 0.35 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    this.scene.add(floor);
    this.resize();
  }

  resize(): void {
    this.w = Math.max(1, this.host.clientWidth);
    this.h = Math.max(1, this.host.clientHeight);
    this.renderer.setSize(this.w, this.h, false);
    this.renderer.domElement.style.width = `${this.w}px`;
    this.renderer.domElement.style.height = `${this.h}px`;
    this.camera.aspect = this.w / this.h;
    const dist = VIEW_H / 2 / Math.tan((this.camera.fov * Math.PI) / 360);
    this.camera.position.set(0, dist, 0);
    this.camera.up.set(0, 0, -1);
    this.camera.lookAt(0, 0, 0);
    this.camera.updateProjectionMatrix();
  }

  /** The walls, a little inside the screen edges so a die resting against one is still fully in view. */
  private halfExtents(): { hx: number; hz: number } {
    const m = this.dieRadius() * 1.1;
    return { hz: VIEW_H / 2 - m, hx: (VIEW_H / 2) * (this.w / this.h) - m };
  }

  private dieRadius(): number {
    const px = Math.max(24, Math.min(58, Math.min(this.w, this.h) * 0.06));
    return (px * VIEW_H) / this.h;
  }

  private shape(sides: Sides, r: number): DieShape {
    const key = `${sides}:${r.toFixed(3)}`;
    let s = this.shapes.get(key);
    if (!s) {
      s = buildShape(sides, r);
      this.shapes.set(key, s);
    }
    return s;
  }

  clear(): void {
    cancelAnimationFrame(this.raf);
    for (const m of this.meshes) {
      this.scene.remove(m);
      for (const mat of m.material as THREE.MeshStandardMaterial[]) {
        mat.map?.dispose();
        mat.dispose();
      }
    }
    this.meshes = [];
    this.renderer.render(this.scene, this.camera);
  }

  /** Throw the dice from a random edge; resolves once they've come to rest on the given values. */
  throw(specs: DieSpec[], instant = false): Promise<Landed> {
    this.clear();
    const { hx, hz } = this.halfExtents();
    const r = this.dieRadius();
    // ── simulate offscreen ──
    const world = new CANNON.World({ gravity: new CANNON.Vec3(0, -9.82 * 6, 0), allowSleep: true });
    world.defaultContactMaterial.friction = 0.35;
    world.defaultContactMaterial.restitution = 0.45;
    const plane = (pos: CANNON.Vec3, axis: CANNON.Vec3, angle: number) => {
      const b = new CANNON.Body({ mass: 0, shape: new CANNON.Plane() });
      b.position.copy(pos);
      b.quaternion.setFromAxisAngle(axis, angle);
      world.addBody(b);
    };
    plane(new CANNON.Vec3(0, 0, 0), new CANNON.Vec3(1, 0, 0), -Math.PI / 2); // floor
    plane(new CANNON.Vec3(-hx, 0, 0), new CANNON.Vec3(0, 1, 0), Math.PI / 2); // left wall, facing +x
    plane(new CANNON.Vec3(hx, 0, 0), new CANNON.Vec3(0, 1, 0), -Math.PI / 2); // right wall
    plane(new CANNON.Vec3(0, 0, -hz), new CANNON.Vec3(0, 1, 0), 0); // top wall (screen top), facing +z
    plane(new CANNON.Vec3(0, 0, hz), new CANNON.Vec3(0, 1, 0), Math.PI); // bottom wall

    // from a random edge, at a random point along it, toward a random spot in the middle of the screen
    const edge = Math.floor(Math.random() * 4);
    const along = (Math.random() * 2 - 1) * 0.7;
    const inset = r * 1.6;
    const shapes = specs.map((s) => this.shape(s.sides, r));
    const bodies = specs.map((_, i) => {
      const spread = (i - (specs.length - 1) / 2) * r * 2.4;
      let x: number, z: number;
      if (edge === 0) [x, z] = [-hx + inset, along * hz + spread];
      else if (edge === 1) [x, z] = [hx - inset, along * hz + spread];
      else if (edge === 2) [x, z] = [along * hx + spread, -hz + inset];
      else [x, z] = [along * hx + spread, hz - inset];
      x = Math.max(-hx + inset, Math.min(hx - inset, x));
      z = Math.max(-hz + inset, Math.min(hz - inset, z));
      const body = new CANNON.Body({ mass: 1, shape: shapes[i].shape, linearDamping: 0.12, angularDamping: 0.12,
                                     allowSleep: true, sleepSpeedLimit: 0.12, sleepTimeLimit: 0.5 });
      body.position.set(x, r * 2 + Math.random() * r * 2, z);
      body.quaternion.setFromEuler(Math.random() * 6.28, Math.random() * 6.28, Math.random() * 6.28);
      const tx = (Math.random() * 2 - 1) * hx * 0.4;
      const tz = (Math.random() * 2 - 1) * hz * 0.4;
      const dir = new CANNON.Vec3(tx - x, 0, tz - z);
      dir.normalize();
      const speed = (18 + Math.random() * 10) * (VIEW_H / 20);
      body.velocity.set(dir.x * speed, 4 + Math.random() * 6, dir.z * speed);
      body.angularVelocity.set((Math.random() * 2 - 1) * 22, (Math.random() * 2 - 1) * 22, (Math.random() * 2 - 1) * 22);
      world.addBody(body);
      return body;
    });
    const frames: { p: number[]; q: number[] }[][] = [];
    for (let step = 0; step < MAX_STEPS; step++) {
      world.step(STEP);
      frames.push(bodies.map((b) => ({ p: [b.position.x, b.position.y, b.position.z],
                                       q: [b.quaternion.x, b.quaternion.y, b.quaternion.z, b.quaternion.w] })));
      if (step > 30 && bodies.every((b) => b.sleepState === CANNON.Body.SLEEPING)) break;
    }

    // ── finish flat: a die that stopped leaning on an edge tips onto its nearest face ──
    const down = new THREE.Vector3(0, -1, 0);
    const lastF = frames[frames.length - 1];
    const lowest = (i: number, q: THREE.Quaternion) => Math.min(...shapes[i].verts.map((v) => v.clone().applyQuaternion(q).y));
    const tips = bodies.map((_, i) => {
      const q0 = new THREE.Quaternion(lastF[i].q[0], lastF[i].q[1], lastF[i].q[2], lastF[i].q[3]);
      let best = -Infinity;
      let n = down;
      for (const f of shapes[i].faces) {
        const wn = f.normal.clone().applyQuaternion(q0);
        const d = wn.dot(down);
        if (d > best) [best, n] = [d, wn];
      }
      const q1 = new THREE.Quaternion().setFromUnitVectors(n, down).multiply(q0);
      return { q0, q1, y0: lastF[i].p[1], y1: -lowest(i, q1), tilt: Math.acos(Math.min(1, best)) };
    });
    const maxTilt = Math.max(...tips.map((t) => t.tilt));
    if (maxTilt > 0.005 || tips.some((t) => Math.abs(t.y1 - t.y0) > 0.005)) {
      const k = Math.max(4, Math.min(20, Math.round(maxTilt * 40))); // ~0.1-0.33 s, longer for a bigger lean
      for (let j = 1; j <= k; j++) {
        const t = j / k;
        const e = t * t * (3 - 2 * t);
        frames.push(
          bodies.map((_, i) => {
            const T = tips[i];
            const q = T.q0.clone().slerp(T.q1, e);
            const y = Math.max(T.y0 + (T.y1 - T.y0) * e, -lowest(i, q)); // never sink into the table mid-tip
            return { p: [lastF[i].p[0], y, lastF[i].p[2]], q: [q.x, q.y, q.z, q.w] };
          }),
        );
      }
    }

    // ── put the server's numbers on the faces that came up ──
    const up = new THREE.Vector3(0, 1, 0);
    this.meshes = specs.map((spec, i) => {
      const d = shapes[i];
      const last = frames[frames.length - 1][i];
      const q = new THREE.Quaternion(last.q[0], last.q[1], last.q[2], last.q[3]);
      const n = spec.sides === 4 ? d.verts.length : d.faces.length;
      const labels = Array.from({ length: n }, (_, k) => k + 1);
      let topIdx = 0;
      if (spec.sides === 4) {
        let best = -Infinity;
        d.verts.forEach((v, vi) => {
          const y = v.clone().applyQuaternion(q).y;
          if (y > best) [best, topIdx] = [y, vi];
        });
      } else {
        let best = -Infinity;
        d.faces.forEach((f, fi) => {
          const dot = f.normal.clone().applyQuaternion(q).dot(up);
          if (dot > best) [best, topIdx] = [dot, fi];
        });
      }
      const want = Math.max(1, Math.min(spec.sides, Math.round(spec.value)));
      const at = labels.indexOf(want);
      [labels[at], labels[topIdx]] = [labels[topIdx], labels[at]];
      const mesh = new THREE.Mesh(d.geometry, dieMaterials(d, labels, spec.color));
      mesh.castShadow = true;
      this.scene.add(mesh);
      return mesh;
    });

    // ── play it back ──
    const place = (fi: number) => {
      const f = frames[Math.max(0, Math.min(frames.length - 1, fi))];
      this.meshes.forEach((m, i) => {
        m.position.set(f[i].p[0], f[i].p[1], f[i].p[2]);
        m.quaternion.set(f[i].q[0], f[i].q[1], f[i].q[2], f[i].q[3]);
      });
      this.renderer.render(this.scene, this.camera);
    };
    const settle = (): Landed => {
      specs.forEach((s, i) => {
        const mats = this.meshes[i].material as THREE.MeshStandardMaterial[];
        for (const m of mats) {
          if (s.dropped) m.opacity = 0.35;
          if (s.glow === "crit") m.emissive = new THREE.Color(0x3a7a2a);
          if (s.glow === "fumble") m.emissive = new THREE.Color(0x7a1e1e);
        }
      });
      this.renderer.render(this.scene, this.camera);
      const c = this.meshes
        .filter((_, i) => !specs[i].dropped)
        .reduce((acc, m) => acc.add(m.position), new THREE.Vector3())
        .multiplyScalar(1 / Math.max(1, specs.filter((s) => !s.dropped).length))
        .project(this.camera);
      return { x: ((c.x + 1) / 2) * this.w, y: ((1 - c.y) / 2) * this.h };
    };
    if (instant) {
      place(frames.length - 1);
      return Promise.resolve(settle());
    }
    return new Promise((resolve, reject) => {
      // The clock starts at the first frame we draw: a frame's timestamp can be a little earlier than
      // performance.now() was when the throw began, and a negative time must never index the recording.
      let t0: number | null = null;
      let done = false;
      const end = () => {
        if (done) return;
        done = true;
        window.clearTimeout(guard);
        cancelAnimationFrame(this.raf);
        try {
          place(frames.length - 1);
          resolve(settle());
        } catch (e) {
          reject(e);
        }
      };
      // Whatever happens to the animation (a hidden tab, a GPU hiccup), the roll always finishes.
      const guard = window.setTimeout(end, (frames.length / 60) * 1000 + 2500);
      const tick = (now: number) => {
        if (this.disposed || done) return;
        try {
          if (t0 === null) t0 = now;
          const fi = Math.max(0, Math.floor(((now - t0) / 1000) * 60));
          place(fi);
          if (fi >= frames.length - 1) return end();
          this.raf = requestAnimationFrame(tick);
        } catch (e) {
          done = true;
          window.clearTimeout(guard);
          reject(e);
        }
      };
      this.raf = requestAnimationFrame(tick);
    });
  }

  /** Do the slow first-time work ahead of a roll: build every die shape, its physics hull, and compile the
   * shaders (the first frame drawn with a new material is the expensive one). Leaves the table empty. */
  warmUp(): void {
    const r = this.dieRadius();
    const sides: Sides[] = [4, 6, 8, 10, 12, 20];
    const meshes = sides.map((s) => {
      const d = this.shape(s, r);
      const n = s === 4 ? d.verts.length : d.faces.length;
      const m = new THREE.Mesh(d.geometry, dieMaterials(d, Array.from({ length: n }, (_, k) => k + 1), "#777777"));
      m.castShadow = true;
      m.position.set(0, -40, 0); // below the floor: compiled, never seen
      this.scene.add(m);
      return m;
    });
    this.renderer.compile(this.scene, this.camera);
    this.renderer.render(this.scene, this.camera);
    // Keep them (hidden): disposing their materials would release the compiled shaders the real dice reuse.
    for (const m of meshes) m.visible = false;
    this.renderer.render(this.scene, this.camera);
  }

  dispose(): void {
    this.disposed = true;
    this.clear();
    for (const s of this.shapes.values()) s.geometry.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}

export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!c.getContext("webgl2"); // three.js needs WebGL 2
  } catch {
    return false;
  }
}
