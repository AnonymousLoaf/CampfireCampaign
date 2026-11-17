import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Encounter, Token } from "../api/types";
import { initials } from "../util/format";
import { getCtx, useCanvasSize } from "./useCanvas";
import { distanceFt } from "./combatUtil";

const TERRAIN_STYLE: Record<string, { floor: string; floorAlt: string; wall: string; obstacle: string; grid: string; difficult: string }> = {
  road: { floor: "#8b7b55", floorAlt: "#7d8a4e", wall: "#4b4238", obstacle: "#5b4a33", grid: "rgba(0,0,0,0.18)", difficult: "rgba(90,120,60,0.55)" },
  forest: { floor: "#4e6b35", floorAlt: "#466230", wall: "#2a3a1f", obstacle: "#24401c", grid: "rgba(0,0,0,0.2)", difficult: "rgba(30,60,25,0.55)" },
  tavern: { floor: "#7a5734", floorAlt: "#6f4f2f", wall: "#3a2a1c", obstacle: "#4a3020", grid: "rgba(0,0,0,0.22)", difficult: "rgba(60,40,20,0.5)" },
  cave: { floor: "#5a5550", floorAlt: "#524d48", wall: "#22201e", obstacle: "#3a3633", grid: "rgba(0,0,0,0.25)", difficult: "rgba(40,60,80,0.5)" },
  dungeon: { floor: "#4f4d4a", floorAlt: "#484643", wall: "#1c1b1a", obstacle: "#353330", grid: "rgba(0,0,0,0.35)", difficult: "rgba(70,60,50,0.55)" },
  ruins: { floor: "#7b7466", floorAlt: "#726b5e", wall: "#3d3932", obstacle: "#55504a", grid: "rgba(0,0,0,0.22)", difficult: "rgba(90,85,70,0.55)" },
  camp: { floor: "#6f7a45", floorAlt: "#7d6f4c", wall: "#3f3a28", obstacle: "#4a3b24", grid: "rgba(0,0,0,0.18)", difficult: "rgba(80,100,50,0.5)" },
  swamp: { floor: "#4a5a3a", floorAlt: "#435235", wall: "#252e1d", obstacle: "#2f3a24", grid: "rgba(0,0,0,0.22)", difficult: "rgba(40,70,70,0.6)" },
  town: { floor: "#86796a", floorAlt: "#7d7062", wall: "#5a3e2b", obstacle: "#4a3a2a", grid: "rgba(0,0,0,0.2)", difficult: "rgba(150,100,60,0.45)" },
};

/** What a player could know about a creature on the map — shown when its token is clicked. Nothing here acts. */
function TokenCard({ token, from, x, y, isActor, onClose }: { token: Token; from: Token | null; x: number; y: number; isActor: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: x + 12, top: y - 10 });
  // Keep the card inside the map: flip left near the right edge, lift it near the bottom.
  useLayoutEffect(() => {
    const el = ref.current;
    const parent = el?.offsetParent as HTMLElement | null;
    if (!el || !parent) return;
    let left = x + 12;
    let top = y - 10;
    if (left + el.offsetWidth > parent.clientWidth - 8) left = x - 12 - el.offsetWidth;
    if (top + el.offsetHeight > parent.clientHeight - 8) top = parent.clientHeight - 8 - el.offsetHeight;
    setPos({ left: Math.max(8, left), top: Math.max(8, top) });
  }, [x, y]);
  const isPc = token.kind === "pc";
  const wounds = WOUNDS[token.hp_state] ?? cap(token.hp_state);
  const dist = from && from.id !== token.id ? distanceFt(from, token) : null;
  return (
    <div className="token-card" ref={ref} style={pos} role="dialog" aria-label={token.name}>
      <div className="token-card-head">
        <span className="char-dot" style={{ background: token.color }} />
        <strong>{token.name}</strong>
        {isActor && <span className="badge gold">Their turn</span>}
        <div className="grow" />
        <button className="icon-btn tiny" onClick={onClose} aria-label="Close">
          ✕
        </button>
      </div>
      {isPc ? (
        <div className="token-card-stats">
          {token.hp !== null && token.hp_max !== null && (
            <span>
              HP <strong>{token.hp}</strong>/{token.hp_max}
            </span>
          )}
          {token.ac !== null && (
            <span>
              AC <strong>{token.ac}</strong>
            </span>
          )}
          {token.hp_state === "down" && <span className="badge red">Down</span>}
          {token.hp_state === "dead" && <span className="badge red">Dead</span>}
        </div>
      ) : (
        <div className="token-card-stats">
          <span className={`badge ${token.hp_state === "bloodied" ? "red" : ""}`}>{wounds}</span>
        </div>
      )}
      {token.conditions.length > 0 && <div className="small">{token.conditions.join(", ")}</div>}
      {dist !== null && <div className="muted small">{dist} ft from you</div>}
    </div>
  );
}

const WOUNDS: Record<string, string> = { healthy: "Unhurt", hurt: "Wounded", bloodied: "Bloodied", dead: "Dead", down: "Down" };

export default function BattleMap({
  encounter,
  actorTokenId,
  viewerTokenId,
  interactive = true,
  portraits,
}: {
  encounter: Encounter;
  /** Whose turn it is — drawn with a gold ring so everyone can see. */
  actorTokenId?: string | null;
  /** The viewer's own token, for "N ft from you" on the info card. */
  viewerTokenId?: string | null;
  /** false = no hover chips or info cards (TV view). */
  interactive?: boolean;
  /** character_id → portrait URL; drawn clipped inside PC token circles. */
  portraits?: Record<string, string | null | undefined>;
}) {
  const { wrapRef, canvasRef, size } = useCanvasSize();
  // Preload portraits; redraw once each image arrives.
  const [imgTick, setImgTick] = useState(0);
  const portraitFor = (t: Token): HTMLImageElement | null => {
    const url = t.portrait_url || (t.character_id ? portraits?.[t.character_id] : null);
    return url ? portraitImage(url, () => setImgTick((n) => n + 1)) : null;
  };
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  const [inspect, setInspect] = useState<{ id: string; x: number; y: number } | null>(null);
  const { w, h } = encounter.grid;
  const cell = Math.max(8, Math.floor(Math.min(size.w / w, size.h / h)));
  const ox = Math.floor((size.w - cell * w) / 2);
  const oy = Math.floor((size.h - cell * h) / 2);
  const style = TERRAIN_STYLE[encounter.terrain] ?? TERRAIN_STYLE.road;

  const propMap = useMemo(() => new Map((encounter.props ?? []).map((p) => [`${p.x},${p.y}`, p.kind])), [encounter.props]);
  const legend = useMemo(() => {
    const kinds = [...new Set((encounter.props ?? []).map((p) => p.kind))];
    const hasDifficult = encounter.cells.some((r) => r.includes("~"));
    return { kinds, hasDifficult };
  }, [encounter.props, encounter.cells]);
  const inspected = inspect ? encounter.tokens.find((t) => t.id === inspect.id) ?? null : null;
  const viewer = viewerTokenId ? encounter.tokens.find((t) => t.id === viewerTokenId) ?? null : null;

  // Close the info card if its creature leaves the map.
  useEffect(() => {
    if (inspect && !inspected) setInspect(null);
  }, [inspect, inspected]);

  useEffect(() => {
    const ctx = getCtx(canvasRef.current);
    if (!ctx) return;
    ctx.fillStyle = "#0d0b09";
    ctx.fillRect(0, 0, size.w, size.h);

    for (let y = 0; y < h; y++) {
      const row = encounter.cells[y] ?? "";
      for (let x = 0; x < w; x++) {
        const c = row[x] ?? " ";
        const px = ox + x * cell;
        const py = oy + y * cell;
        if (c === " ") continue;
        ctx.fillStyle = (x + y) % 2 ? style.floor : style.floorAlt;
        ctx.fillRect(px, py, cell, cell);
        if (c !== "#") decorateFloor(ctx, encounter.terrain, px, py, cell, x, y);
        if (c === "#") {
          ctx.fillStyle = style.wall;
          ctx.fillRect(px, py, cell, cell);
          ctx.fillStyle = "rgba(255,255,255,0.05)";
          ctx.fillRect(px, py, cell, cell * 0.25);
        } else if (c === "T") {
          const kind = propMap.get(`${x},${y}`);
          if (kind) drawProp(ctx, kind, px, py, cell, { left: row[x - 1] === "T" && propMap.get(`${x - 1},${y}`) === kind, right: row[x + 1] === "T" && propMap.get(`${x + 1},${y}`) === kind });
          else drawObstacle(ctx, encounter.terrain, px, py, cell, style.obstacle);
        } else if (c === "~") {
          ctx.fillStyle = style.difficult;
          ctx.fillRect(px, py, cell, cell);
          ctx.strokeStyle = "rgba(255,255,255,0.15)";
          ctx.lineWidth = 1;
          for (let i = 1; i < 3; i++) {
            ctx.beginPath();
            ctx.moveTo(px + (cell * i) / 3, py + cell * 0.2);
            ctx.lineTo(px + (cell * i) / 3 - cell * 0.15, py + cell * 0.8);
            ctx.stroke();
          }
        } else if (c === "D") {
          ctx.fillStyle = "#9a6b3a";
          ctx.fillRect(px + cell * 0.1, py + cell * 0.35, cell * 0.8, cell * 0.3);
        }
        ctx.strokeStyle = style.grid;
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, cell - 1, cell - 1);
      }
    }

    // Tokens.
    const sorted = [...encounter.tokens].sort((a, b) => (a.hp_state === "dead" ? -1 : 0) - (b.hp_state === "dead" ? -1 : 0));
    for (const t of sorted) drawToken(ctx, t, ox + t.x * cell, oy + t.y * cell, cell * (t.size || 1), {
      actor: t.id === actorTokenId,
      target: false,
      selected: t.id === inspect?.id,
      hovered: !!hover && hover.x === t.x && hover.y === t.y,
      inTemplate: false,
    }, portraitFor(t));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [encounter, size, cell, ox, oy, w, h, style, propMap, actorTokenId, inspect?.id, hover, canvasRef, portraits, imgTick]);

  const squareAt = (e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left - ox) / cell);
    const y = Math.floor((e.clientY - rect.top - oy) / cell);
    if (x < 0 || y < 0 || x >= w || y >= h) return null;
    return { x, y };
  };

  // Clicking a creature shows what you could know about it. Nothing on the map acts: you type what you do.
  const onClick = (e: React.MouseEvent) => {
    if (!interactive) return;
    const sq = squareAt(e);
    if (!sq) return;
    // On touch screens there is no hover: a tap also shows what's on the square.
    if (!hover || hover.x !== sq.x || hover.y !== sq.y) setHover(sq);
    const tok = encounter.tokens.find((t) => t.x === sq.x && t.y === sq.y && t.hp_state !== "dead");
    if (tok) {
      const rect = canvasRef.current!.getBoundingClientRect();
      setInspect(inspect?.id === tok.id ? null : { id: tok.id, x: e.clientX - rect.left, y: e.clientY - rect.top });
    } else {
      setInspect(null);
    }
  };

  const hoverTok = hover ? encounter.tokens.find((t) => t.x === hover.x && t.y === hover.y) : undefined;
  const hoverCell = hover ? encounter.cells[hover.y]?.[hover.x] : undefined;
  const hoverTerrain = !hover || hoverTok
    ? null
    : hoverCell === "T"
      ? `${PROP_LABEL[propMap.get(`${hover.x},${hover.y}`) ?? ""] ?? "Obstacle"} — blocks movement`
      : hoverCell === "#"
        ? "Wall — blocks movement"
        : hoverCell === "~"
          ? `${cap(encounter.difficult ?? "difficult terrain")} — difficult terrain (costs double movement)`
          : hoverCell === "D"
            ? "Door"
            : null;

  return (
    <div className="map-wrap" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        onClick={onClick}
        onMouseMove={(e) => {
          if (!interactive) return;
          const sq = squareAt(e);
          if (!sq) setHover(null);
          else if (!hover || hover.x !== sq.x || hover.y !== sq.y) setHover(sq);
        }}
        onMouseLeave={() => setHover(null)}
        style={{ cursor: interactive && hoverTok && hoverTok.hp_state !== "dead" ? "pointer" : "default", touchAction: "manipulation" }}
      />
      {hoverTok && interactive && !inspected && (
        <div className="map-overlay top-left">
          <span className="map-chip">
            {hoverTok.name} · {hoverTok.kind === "pc" ? (hoverTok.hp !== null && hoverTok.hp_max !== null ? `HP ${hoverTok.hp}/${hoverTok.hp_max}` : hoverTok.hp_state) : WOUNDS[hoverTok.hp_state] ?? hoverTok.hp_state}
            {hoverTok.conditions.length ? ` · ${hoverTok.conditions.join(", ")}` : ""}
          </span>
        </div>
      )}
      {hoverTerrain && (
        <div className="map-overlay top-left">
          <span className="map-chip">{hoverTerrain}</span>
        </div>
      )}
      {inspected && inspect && interactive && (
        <TokenCard token={inspected} from={viewer} x={inspect.x} y={inspect.y} isActor={inspected.id === actorTokenId} onClose={() => setInspect(null)} />
      )}
      {(legend.kinds.length > 0 || legend.hasDifficult) && (
        <div className="map-overlay bottom-left">
          <span className="map-chip small">
            {legend.kinds.map((k) => PROP_LABEL[k] ?? k).join(" · ")}
            {legend.kinds.length ? " block movement" : ""}
            {legend.hasDifficult ? `${legend.kinds.length ? " · " : ""}${cap(encounter.difficult ?? "difficult terrain")} costs double` : ""}
          </span>
        </div>
      )}
    </div>
  );
}

const PROP_LABEL: Record<string, string> = {
  table: "Table", bar: "Bar counter", barrel: "Barrel", tree: "Tree", boulder: "Boulder",
  stalagmite: "Stalagmite", cart: "Broken cart",
  pillar: "Pillar", statue: "Statue", chest: "Chest", altar: "Altar", tent: "Tent", campfire: "Campfire",
  crate: "Crate", log: "Fallen log", dead_tree: "Dead tree", stall: "Market stall", well: "Well",
};

/** Hash a square to a stable pseudo-random number in [0, 1). */
function hash2(x: number, y: number) {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return s - Math.floor(s);
}

/** Subtle floor texture for the M2 terrains (older terrains stay plain). */
function decorateFloor(ctx: CanvasRenderingContext2D, terrain: string, px: number, py: number, cell: number, x: number, y: number) {
  const r = hash2(x, y);
  if (terrain === "dungeon") {
    // flagstone seams
    ctx.strokeStyle = "rgba(0,0,0,0.28)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(px, py + cell * (0.45 + r * 0.1));
    ctx.lineTo(px + cell, py + cell * (0.45 + r * 0.1));
    ctx.moveTo(px + cell * (y % 2 ? 0.3 : 0.7), py);
    ctx.lineTo(px + cell * (y % 2 ? 0.3 : 0.7), py + cell * 0.5);
    ctx.stroke();
  } else if (terrain === "ruins") {
    if (r < 0.35) {
      // a crack
      ctx.strokeStyle = "rgba(30,25,20,0.45)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(px + cell * 0.15, py + cell * (0.2 + r));
      ctx.lineTo(px + cell * 0.45, py + cell * 0.5);
      ctx.lineTo(px + cell * 0.6, py + cell * (0.35 + r * 0.5));
      ctx.lineTo(px + cell * 0.9, py + cell * 0.75);
      ctx.stroke();
    }
    if (r > 0.8) {
      ctx.fillStyle = "rgba(80,110,50,0.35)"; // moss
      ctx.beginPath();
      ctx.arc(px + cell * 0.7, py + cell * 0.3, cell * 0.12, 0, Math.PI * 2);
      ctx.fill();
    }
  } else if (terrain === "camp") {
    ctx.fillStyle = "rgba(60,45,25,0.35)";
    for (let i = 0; i < 3; i++) {
      const h = hash2(x * 3 + i, y * 7 - i);
      ctx.fillRect(px + cell * h, py + cell * hash2(y + i, x - i), Math.max(1, cell * 0.06), Math.max(1, cell * 0.06));
    }
  } else if (terrain === "town") {
    // cobblestones: two offset rows of rounded stones
    ctx.strokeStyle = "rgba(40,30,22,0.35)";
    ctx.lineWidth = 1;
    for (let row = 0; row < 2; row++) {
      const yy = py + cell * (row * 0.5);
      const off = (row + y) % 2 ? cell * 0.25 : 0;
      for (let k = -1; k < 2; k++) {
        const xx = px + off + k * cell * 0.5;
        const x0 = Math.max(px, xx);
        const x1 = Math.min(px + cell, xx + cell * 0.5);
        if (x1 - x0 > 2) ctx.strokeRect(x0 + 0.5, yy + 0.5, x1 - x0 - 1, cell * 0.5 - 1);
      }
    }
    if (r > 0.85) {
      ctx.fillStyle = "rgba(255,255,255,0.06)";
      ctx.fillRect(px + cell * 0.1, py + cell * 0.55, cell * 0.35, cell * 0.35);
    }
  } else if (terrain === "swamp") {
    if (r < 0.45) {
      ctx.fillStyle = "rgba(40,70,75,0.45)"; // murky water
      ctx.beginPath();
      ctx.ellipse(px + cell / 2, py + cell / 2, cell * (0.3 + r * 0.3), cell * 0.22, r * 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(180,210,200,0.18)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(px + cell * 0.5, py + cell * 0.5, cell * 0.12, 0, Math.PI);
      ctx.stroke();
    }
  }
}

function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Draw a named obstacle. `join` says whether the same object continues left/right (bar counter, cart). */
function drawProp(ctx: CanvasRenderingContext2D, kind: string, px: number, py: number, cell: number, join: { left: boolean; right: boolean }) {
  const cx = px + cell / 2;
  const cy = py + cell / 2;
  const line = (c: string, w = 1) => {
    ctx.strokeStyle = c;
    ctx.lineWidth = w;
  };
  switch (kind) {
    case "table": {
      // round wooden table with four stools
      ctx.fillStyle = "#3b2414";
      for (const [dx, dy] of [[-0.36, 0], [0.36, 0], [0, -0.36], [0, 0.36]]) {
        ctx.beginPath();
        ctx.arc(cx + dx * cell, cy + dy * cell, cell * 0.09, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = "#9b6a3c";
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.28, 0, Math.PI * 2);
      ctx.fill();
      line("rgba(40,20,8,0.8)", Math.max(1, cell * 0.04));
      ctx.stroke();
      line("rgba(255,230,190,0.25)");
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.17, Math.PI * 1.1, Math.PI * 1.7);
      ctx.stroke();
      break;
    }
    case "bar": {
      const x0 = join.left ? px : px + cell * 0.1;
      const x1 = join.right ? px + cell : px + cell * 0.9;
      ctx.fillStyle = "#5a3418";
      ctx.fillRect(x0, py + cell * 0.22, x1 - x0, cell * 0.56);
      ctx.fillStyle = "#8a5428";
      ctx.fillRect(x0, py + cell * 0.22, x1 - x0, cell * 0.14);
      line("rgba(20,10,4,0.8)", Math.max(1, cell * 0.04));
      ctx.strokeRect(x0, py + cell * 0.22, x1 - x0, cell * 0.56);
      // a tankard on top
      ctx.fillStyle = "#c9b48a";
      ctx.fillRect(cx - cell * 0.06, py + cell * 0.12, cell * 0.12, cell * 0.14);
      break;
    }
    case "barrel": {
      ctx.fillStyle = "#7a4a22";
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.34, 0, Math.PI * 2);
      ctx.fill();
      line("#2c1a0c", Math.max(1, cell * 0.05));
      ctx.stroke();
      line("#b08d55", Math.max(1, cell * 0.04));
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.22, 0, Math.PI * 2);
      ctx.stroke();
      break;
    }
    case "tree": {
      ctx.fillStyle = "rgba(0,0,0,0.3)";
      ctx.beginPath();
      ctx.arc(cx + cell * 0.06, cy + cell * 0.08, cell * 0.42, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#1f3d17";
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.44, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#2f5a22";
      for (const [dx, dy, r] of [[-0.14, -0.1, 0.22], [0.14, -0.06, 0.2], [0, 0.14, 0.2]]) {
        ctx.beginPath();
        ctx.arc(cx + dx * cell, cy + dy * cell, r * cell, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = "#4a2f18";
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.06, 0, Math.PI * 2);
      ctx.fill();
      break;
    }
    case "boulder": {
      ctx.fillStyle = "rgba(0,0,0,0.3)";
      ctx.beginPath();
      ctx.ellipse(cx + cell * 0.05, cy + cell * 0.12, cell * 0.38, cell * 0.26, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#77736c";
      ctx.beginPath();
      ctx.moveTo(px + cell * 0.14, py + cell * 0.66);
      ctx.lineTo(px + cell * 0.22, py + cell * 0.3);
      ctx.lineTo(px + cell * 0.5, py + cell * 0.16);
      ctx.lineTo(px + cell * 0.8, py + cell * 0.32);
      ctx.lineTo(px + cell * 0.86, py + cell * 0.68);
      ctx.lineTo(px + cell * 0.5, py + cell * 0.82);
      ctx.closePath();
      ctx.fill();
      line("#3c3a36", Math.max(1, cell * 0.04));
      ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,0.18)";
      ctx.beginPath();
      ctx.moveTo(px + cell * 0.3, py + cell * 0.32);
      ctx.lineTo(px + cell * 0.5, py + cell * 0.22);
      ctx.lineTo(px + cell * 0.58, py + cell * 0.36);
      ctx.closePath();
      ctx.fill();
      break;
    }
    case "stalagmite": {
      ctx.fillStyle = "#6a655e";
      ctx.beginPath();
      ctx.moveTo(px + cell * 0.2, py + cell * 0.85);
      ctx.lineTo(cx, py + cell * 0.1);
      ctx.lineTo(px + cell * 0.8, py + cell * 0.85);
      ctx.closePath();
      ctx.fill();
      line("#2e2b28", Math.max(1, cell * 0.04));
      ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,0.15)";
      ctx.beginPath();
      ctx.moveTo(cx, py + cell * 0.14);
      ctx.lineTo(px + cell * 0.38, py + cell * 0.8);
      ctx.lineTo(px + cell * 0.46, py + cell * 0.8);
      ctx.closePath();
      ctx.fill();
      break;
    }
    case "cart": {
      const x0 = join.left ? px : px + cell * 0.08;
      const x1 = join.right ? px + cell : px + cell * 0.92;
      ctx.fillStyle = "#6b4626";
      ctx.fillRect(x0, py + cell * 0.25, x1 - x0, cell * 0.5);
      line("#2c1a0c", Math.max(1, cell * 0.04));
      ctx.strokeRect(x0, py + cell * 0.25, x1 - x0, cell * 0.5);
      for (let i = 1; i < 3; i++) {
        ctx.beginPath();
        ctx.moveTo(x0, py + cell * (0.25 + 0.166 * i));
        ctx.lineTo(x1, py + cell * (0.25 + 0.166 * i));
        ctx.stroke();
      }
      ctx.fillStyle = "#2c1a0c";
      ctx.beginPath();
      ctx.arc(cx, py + cell * (join.left ? 0.8 : 0.2), cell * 0.12, 0, Math.PI * 2);
      ctx.fill();
      break;
    }
    case "pillar": {
      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.beginPath();
      ctx.arc(cx + cell * 0.05, cy + cell * 0.07, cell * 0.38, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#8c877e";
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.38, 0, Math.PI * 2);
      ctx.fill();
      line("#3a3732", Math.max(1, cell * 0.05));
      ctx.stroke();
      line("rgba(255,255,255,0.22)", Math.max(1, cell * 0.04));
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.24, 0, Math.PI * 2);
      ctx.stroke();
      break;
    }
    case "statue": {
      ctx.fillStyle = "#5e5a53";
      ctx.fillRect(px + cell * 0.18, py + cell * 0.62, cell * 0.64, cell * 0.24); // plinth
      ctx.fillStyle = "#9a958b";
      ctx.beginPath();
      ctx.arc(cx, py + cell * 0.26, cell * 0.12, 0, Math.PI * 2); // head
      ctx.fill();
      ctx.beginPath(); // body
      ctx.moveTo(cx - cell * 0.18, py + cell * 0.62);
      ctx.lineTo(cx - cell * 0.1, py + cell * 0.38);
      ctx.lineTo(cx + cell * 0.1, py + cell * 0.38);
      ctx.lineTo(cx + cell * 0.18, py + cell * 0.62);
      ctx.closePath();
      ctx.fill();
      line("#2e2b27", Math.max(1, cell * 0.035));
      ctx.stroke();
      break;
    }
    case "chest": {
      ctx.fillStyle = "#6b3f1d";
      ctx.fillRect(px + cell * 0.18, py + cell * 0.32, cell * 0.64, cell * 0.42);
      ctx.fillStyle = "#86522a";
      ctx.fillRect(px + cell * 0.18, py + cell * 0.32, cell * 0.64, cell * 0.14);
      line("#2a170a", Math.max(1, cell * 0.04));
      ctx.strokeRect(px + cell * 0.18, py + cell * 0.32, cell * 0.64, cell * 0.42);
      ctx.fillStyle = "#d9b44a"; // clasp
      ctx.fillRect(cx - cell * 0.05, py + cell * 0.42, cell * 0.1, cell * 0.12);
      break;
    }
    case "altar": {
      ctx.fillStyle = "#9b958a";
      ctx.fillRect(px + cell * 0.1, py + cell * 0.28, cell * 0.8, cell * 0.44);
      line("#3c3833", Math.max(1, cell * 0.04));
      ctx.strokeRect(px + cell * 0.1, py + cell * 0.28, cell * 0.8, cell * 0.44);
      ctx.fillStyle = "#f0c860"; // candles
      for (const dx of [-0.25, 0.25]) {
        ctx.beginPath();
        ctx.arc(cx + dx * cell, py + cell * 0.38, cell * 0.05, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = "#7a1e1e"; // cloth
      ctx.fillRect(cx - cell * 0.12, py + cell * 0.28, cell * 0.24, cell * 0.44);
      break;
    }
    case "tent": {
      ctx.fillStyle = "#a3874f";
      ctx.beginPath();
      ctx.moveTo(px + cell * 0.08, py + cell * 0.88);
      ctx.lineTo(cx, py + cell * 0.1);
      ctx.lineTo(px + cell * 0.92, py + cell * 0.88);
      ctx.closePath();
      ctx.fill();
      line("#4a3a1c", Math.max(1, cell * 0.045));
      ctx.stroke();
      ctx.fillStyle = "#3a2c12"; // flap
      ctx.beginPath();
      ctx.moveTo(cx - cell * 0.12, py + cell * 0.88);
      ctx.lineTo(cx, py + cell * 0.45);
      ctx.lineTo(cx + cell * 0.12, py + cell * 0.88);
      ctx.closePath();
      ctx.fill();
      break;
    }
    case "campfire": {
      ctx.fillStyle = "#555048"; // ring of stones
      for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2;
        ctx.beginPath();
        ctx.arc(cx + Math.cos(a) * cell * 0.3, cy + Math.sin(a) * cell * 0.3, cell * 0.08, 0, Math.PI * 2);
        ctx.fill();
      }
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, cell * 0.24);
      g.addColorStop(0, "#fff1a8");
      g.addColorStop(0.5, "#ff9a2e");
      g.addColorStop(1, "rgba(200,40,10,0.2)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.24, 0, Math.PI * 2);
      ctx.fill();
      break;
    }
    case "stall": {
      // striped awning over a counter of goods; joins with the stall square beside it
      const x0 = join.left ? px : px + cell * 0.06;
      const x1 = join.right ? px + cell : px + cell * 0.94;
      ctx.fillStyle = "#6b4a2a";
      ctx.fillRect(x0, py + cell * 0.55, x1 - x0, cell * 0.33);
      const stripes = 4;
      for (let i = 0; i < stripes; i++) {
        ctx.fillStyle = (i + (join.left ? 1 : 0)) % 2 ? "#e9dcc0" : "#a8322a";
        ctx.fillRect(x0 + ((x1 - x0) / stripes) * i, py + cell * 0.12, (x1 - x0) / stripes + 0.5, cell * 0.4);
      }
      line("rgba(40,20,10,0.8)", Math.max(1, cell * 0.04));
      ctx.strokeRect(x0, py + cell * 0.12, x1 - x0, cell * 0.4);
      for (const [dx, c] of [[0.3, "#d9a03a"], [0.55, "#7fa83a"], [0.78, "#c0502a"]] as [number, string][]) {
        ctx.fillStyle = c; // produce on the counter
        ctx.beginPath();
        ctx.arc(px + cell * dx, py + cell * 0.68, cell * 0.07, 0, Math.PI * 2);
        ctx.fill();
      }
      break;
    }
    case "well": {
      ctx.fillStyle = "rgba(0,0,0,0.3)";
      ctx.beginPath();
      ctx.arc(cx + cell * 0.05, cy + cell * 0.07, cell * 0.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#8d8780";
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.4, 0, Math.PI * 2);
      ctx.fill();
      line("#3c3833", Math.max(1, cell * 0.05));
      ctx.stroke();
      ctx.fillStyle = "#1f3a4a";
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.24, 0, Math.PI * 2);
      ctx.fill();
      line("rgba(170,210,230,0.35)", Math.max(1, cell * 0.03));
      ctx.beginPath();
      ctx.arc(cx - cell * 0.04, cy - cell * 0.04, cell * 0.12, Math.PI, Math.PI * 1.6);
      ctx.stroke();
      ctx.fillStyle = "#5a3a1e"; // winch beam
      ctx.fillRect(px + cell * 0.08, cy - cell * 0.04, cell * 0.84, cell * 0.08);
      break;
    }
    case "crate": {
      ctx.fillStyle = "#8a6236";
      ctx.fillRect(px + cell * 0.14, py + cell * 0.14, cell * 0.72, cell * 0.72);
      line("#3a2512", Math.max(1, cell * 0.045));
      ctx.strokeRect(px + cell * 0.14, py + cell * 0.14, cell * 0.72, cell * 0.72);
      ctx.beginPath();
      ctx.moveTo(px + cell * 0.14, py + cell * 0.14);
      ctx.lineTo(px + cell * 0.86, py + cell * 0.86);
      ctx.moveTo(px + cell * 0.86, py + cell * 0.14);
      ctx.lineTo(px + cell * 0.14, py + cell * 0.86);
      ctx.stroke();
      break;
    }
    case "log": {
      ctx.fillStyle = "#5c3d1f";
      ctx.fillRect(px + (join.left ? 0 : cell * 0.08), py + cell * 0.32, cell - (join.left ? 0 : cell * 0.08) - (join.right ? 0 : cell * 0.08), cell * 0.36);
      line("#2a1a0b", Math.max(1, cell * 0.04));
      ctx.beginPath();
      ctx.moveTo(px + cell * 0.2, py + cell * 0.42);
      ctx.lineTo(px + cell * 0.8, py + cell * 0.42);
      ctx.moveTo(px + cell * 0.3, py + cell * 0.56);
      ctx.lineTo(px + cell * 0.7, py + cell * 0.56);
      ctx.stroke();
      if (!join.right) {
        ctx.fillStyle = "#a07445"; // cut end
        ctx.beginPath();
        ctx.ellipse(px + cell * 0.88, cy, cell * 0.07, cell * 0.18, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      break;
    }
    case "dead_tree": {
      line("#3b2d22", Math.max(2, cell * 0.09));
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx - cell * 0.32, cy - cell * 0.26);
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + cell * 0.3, cy - cell * 0.3);
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + cell * 0.26, cy + cell * 0.3);
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx - cell * 0.22, cy + cell * 0.32);
      ctx.stroke();
      ctx.fillStyle = "#4a3a2c";
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.13, 0, Math.PI * 2);
      ctx.fill();
      break;
    }
    default:
      ctx.fillStyle = "#4a3a2a";
      ctx.fillRect(px + cell * 0.15, py + cell * 0.15, cell * 0.7, cell * 0.7);
  }
}

function drawObstacle(ctx: CanvasRenderingContext2D, terrain: string, px: number, py: number, cell: number, color: string) {
  const cx = px + cell / 2;
  const cy = py + cell / 2;
  if (terrain === "forest") {
    ctx.fillStyle = "#1d3517";
    ctx.beginPath();
    ctx.arc(cx, cy, cell * 0.45, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#2c5222";
    ctx.beginPath();
    ctx.arc(cx - cell * 0.08, cy - cell * 0.08, cell * 0.3, 0, Math.PI * 2);
    ctx.fill();
  } else if (terrain === "cave") {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(px + cell * 0.15, py + cell * 0.85);
    ctx.lineTo(px + cell * 0.3, py + cell * 0.2);
    ctx.lineTo(px + cell * 0.7, py + cell * 0.15);
    ctx.lineTo(px + cell * 0.88, py + cell * 0.8);
    ctx.closePath();
    ctx.fill();
  } else {
    // crates / tables
    ctx.fillStyle = color;
    ctx.fillRect(px + cell * 0.12, py + cell * 0.12, cell * 0.76, cell * 0.76);
    ctx.strokeStyle = "rgba(0,0,0,0.5)";
    ctx.lineWidth = 1;
    ctx.strokeRect(px + cell * 0.12, py + cell * 0.12, cell * 0.76, cell * 0.76);
    ctx.beginPath();
    ctx.moveTo(px + cell * 0.12, py + cell * 0.12);
    ctx.lineTo(px + cell * 0.88, py + cell * 0.88);
    ctx.stroke();
  }
}

/** Shared portrait image cache: loads once per URL, calls `onLoad` for every requester when ready. */
const portraitCache = new Map<string, { img: HTMLImageElement; waiting: Set<() => void> | null }>();
function portraitImage(url: string, onLoad: () => void): HTMLImageElement {
  let e = portraitCache.get(url);
  if (!e) {
    const img = new Image();
    const entry = { img, waiting: new Set<() => void>() as Set<() => void> | null };
    img.onload = img.onerror = () => {
      const w = entry.waiting;
      entry.waiting = null;
      w?.forEach((f) => f());
    };
    img.src = url;
    portraitCache.set(url, entry);
    e = entry;
  }
  if (e.waiting) e.waiting.add(onLoad);
  return e.img;
}

function drawToken(
  ctx: CanvasRenderingContext2D,
  t: Token,
  px: number,
  py: number,
  size: number,
  flags: { actor: boolean; target: boolean; selected: boolean; hovered: boolean; inTemplate?: boolean },
  portrait: HTMLImageElement | null = null,
) {
  const cx = px + size / 2;
  const cy = py + size / 2;
  const r = size * 0.4;
  const dead = t.hp_state === "dead";
  const down = t.hp_state === "down";

  if (t.raging && !dead) {
    // red aura
    const g = ctx.createRadialGradient(cx, cy, r * 0.8, cx, cy, r * 1.5);
    g.addColorStop(0, "rgba(255, 60, 30, 0.55)");
    g.addColorStop(1, "rgba(255, 60, 30, 0)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(cx, cy, r * 1.5, 0, Math.PI * 2);
    ctx.fill();
  }
  if (flags.inTemplate && !dead) {
    ctx.strokeStyle = "#ffb15a";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(cx, cy, r + 3, 0, Math.PI * 2);
    ctx.stroke();
  }

  if (flags.actor) {
    ctx.strokeStyle = "#ffd36b";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(cx, cy, r + 4, 0, Math.PI * 2);
    ctx.stroke();
  }
  if (flags.target || flags.selected) {
    // selected = the token whose info card is open (a neutral ring, not a target marker)
    ctx.strokeStyle = flags.selected ? "rgba(235, 240, 255, 0.9)" : "rgba(255, 90, 74, 0.7)";
    ctx.lineWidth = 2;
    ctx.setLineDash(flags.selected ? [3, 3] : [4, 3]);
    ctx.beginPath();
    ctx.arc(cx, cy, r + (flags.actor ? 7 : 4), 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.globalAlpha = dead ? 0.35 : down ? 0.6 : 1;
  ctx.fillStyle = "rgba(0,0,0,0.45)";
  ctx.beginPath();
  ctx.arc(cx + 1.5, cy + 2, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = down || dead ? "#666" : t.color || (t.kind === "pc" ? "#2e86c1" : "#8e2b2b");
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();
  const showPortrait = !!portrait && portrait.complete && portrait.naturalWidth > 0;
  if (showPortrait) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r - 1, 0, Math.PI * 2);
    ctx.clip();
    if (down || dead) ctx.filter = "grayscale(1)";
    ctx.drawImage(portrait!, cx - r, cy - r, r * 2, r * 2);
    ctx.restore();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
  }
  ctx.lineWidth = t.kind === "monster" ? 2.5 : 2;
  ctx.strokeStyle = t.kind === "monster" ? "#2a0b0b" : t.color || "#f3e7c9";
  if (t.kind === "pc" && !showPortrait) ctx.strokeStyle = "#f3e7c9";
  if (t.hp_state === "bloodied") ctx.strokeStyle = "#ff4d3d";
  ctx.stroke();

  if (!showPortrait) {
    ctx.fillStyle = "#fff";
    ctx.font = `700 ${Math.max(8, Math.round(r * 0.8))}px Inter, system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(initials(t.name), cx, cy + 1);
  }
  ctx.globalAlpha = 1;

  if (dead) {
    ctx.strokeStyle = "#d33";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(cx - r * 0.7, cy - r * 0.7);
    ctx.lineTo(cx + r * 0.7, cy + r * 0.7);
    ctx.moveTo(cx + r * 0.7, cy - r * 0.7);
    ctx.lineTo(cx - r * 0.7, cy + r * 0.7);
    ctx.stroke();
  } else if (down) {
    ctx.fillStyle = "#fff";
    ctx.font = `700 ${Math.max(8, Math.round(r * 0.6))}px Inter, sans-serif`;
    ctx.fillText("z", cx + r * 0.8, cy - r * 0.8);
  }

  // Status badges: concentrating (blue ring, top-left), marked (red crosshair, top-right).
  if (!dead && t.concentrating) {
    const bx = cx - r * 0.85;
    const by = cy - r * 0.85;
    const br = Math.max(3, r * 0.3);
    ctx.fillStyle = "#13202e";
    ctx.beginPath();
    ctx.arc(bx, by, br, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#7fc4ff";
    ctx.lineWidth = Math.max(1, br * 0.35);
    ctx.beginPath();
    ctx.arc(bx, by, br * 0.6, 0, Math.PI * 2);
    ctx.stroke();
  }
  if (!dead && t.marked) {
    const bx = cx + r * 0.85;
    const by = cy - r * 0.85;
    const br = Math.max(3, r * 0.3);
    ctx.strokeStyle = "#ff5a4a";
    ctx.lineWidth = Math.max(1, br * 0.3);
    ctx.beginPath();
    ctx.arc(bx, by, br * 0.7, 0, Math.PI * 2);
    ctx.moveTo(bx - br, by);
    ctx.lineTo(bx + br, by);
    ctx.moveTo(bx, by - br);
    ctx.lineTo(bx, by + br);
    ctx.stroke();
  }

  // HP bar.
  if (!dead && t.hp !== null && t.hp_max) {
    const bw = size * 0.8;
    const bx = px + size * 0.1;
    const by = py + size * 0.88;
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.fillRect(bx, by, bw, Math.max(3, size * 0.08));
    const frac = Math.max(0, Math.min(1, t.hp / t.hp_max));
    ctx.fillStyle = frac > 0.5 ? "#4cc46a" : frac > 0.25 ? "#e3b23c" : "#e04a3a";
    ctx.fillRect(bx, by, bw * frac, Math.max(3, size * 0.08));
  } else if (!dead && t.hp_state === "bloodied" && t.hp === null) {
    ctx.fillStyle = "#e04a3a";
    ctx.fillRect(px + size * 0.1, py + size * 0.88, size * 0.8 * 0.4, Math.max(3, size * 0.08));
  }
}
