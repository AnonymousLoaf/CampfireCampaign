import { useCallback, useEffect, useRef, useState } from "react";
import type { TravelTo, World } from "../api/types";
import { BIOME_COLORS, BIOME_NAMES, hexCenter, hexCorners, neighbors, pixelToHex } from "./hex";
import { getCtx, useCanvasSize } from "./useCanvas";

type View = { x: number; y: number; scale: number }; // world-space point at canvas origin, zoom

const BASE = 18; // hex radius at scale 1

export default function WorldMap({
  world,
  destination,
  onPick,
  locationName,
  interactive = true,
  autoFit = false,
}: {
  world: World;
  destination?: TravelTo;
  onPick?: (t: TravelTo, label: string) => void;
  locationName?: string;
  interactive?: boolean;
  autoFit?: boolean;
}) {
  const { wrapRef, canvasRef, size } = useCanvasSize();
  const [view, setView] = useState<View | null>(null);
  const [hover, setHover] = useState<{ q: number; r: number } | null>(null);
  const drag = useRef<{ sx: number; sy: number; vx: number; vy: number; moved: boolean } | null>(null);

  const revealed = useCallback((q: number, r: number) => world.revealed[r]?.[q] === "1", [world]);

  // Centre on the party the first time, and (in TV/autoFit mode) whenever the party moves.
  const partyKey = `${world.party.q},${world.party.r}`;
  const centredOn = useRef<string | null>(null);
  const userMoved = useRef(false); // once the player pans or zooms, stop recentring on resizes
  useEffect(() => {
    if (!size.w || !size.h) return; // wait until the canvas has been measured
    // Recentre on first show, when the canvas resizes (until the player moves the map), whenever the
    // party moves, and always in TV/autoFit mode.
    if (centredOn.current !== partyKey) userMoved.current = false;
    if (view && !autoFit && centredOn.current === partyKey && userMoved.current) return;
    const scale = autoFit ? Math.max(0.8, Math.min(3, size.w / (22 * BASE * 1.732))) : view?.scale ?? 1.4;
    const [px, py] = hexCenter(world.party.q, world.party.r, BASE * scale);
    setView({ x: px - size.w / 2, y: py - size.h / 2, scale });
    centredOn.current = partyKey;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partyKey, size.w, size.h, autoFit]);

  // Draw.
  useEffect(() => {
    const ctx = getCtx(canvasRef.current);
    if (!ctx || !view) return;
    const s = BASE * view.scale;
    ctx.fillStyle = "#0d0b09";
    ctx.fillRect(0, 0, size.w, size.h);
    ctx.save();
    ctx.translate(-view.x, -view.y);

    // Visible range (rough cull).
    const r0 = Math.max(0, Math.floor(view.y / (s * 1.5)) - 1);
    const r1 = Math.min(world.h - 1, Math.ceil((view.y + size.h) / (s * 1.5)) + 1);
    const q0 = Math.max(0, Math.floor(view.x / (s * 1.732)) - 1);
    const q1 = Math.min(world.w - 1, Math.ceil((view.x + size.w) / (s * 1.732)) + 1);

    for (let r = r0; r <= r1; r++) {
      const row = world.hexes[r] ?? "";
      for (let q = q0; q <= q1; q++) {
        const code = row[q] ?? "~";
        const [cx, cy] = hexCenter(q, r, s);
        const pts = hexCorners(cx, cy, s);
        ctx.beginPath();
        pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.closePath();
        if (revealed(q, r)) {
          ctx.fillStyle = BIOME_COLORS[code] ?? "#555";
          ctx.fill();
          // Terrain texture marks.
          drawBiomeMark(ctx, code, cx, cy, s);
          ctx.strokeStyle = "rgba(0,0,0,0.18)";
          ctx.lineWidth = 1;
          ctx.stroke();
        } else {
          ctx.fillStyle = "#1a1612";
          ctx.fill();
          ctx.strokeStyle = "rgba(255,255,255,0.03)";
          ctx.stroke();
        }
      }
    }

    // Roads: connect adjacent road hexes.
    const roadSet = new Set(world.roads.map(([q, r]) => `${q},${r}`));
    ctx.strokeStyle = "rgba(120, 85, 45, 0.9)";
    ctx.lineWidth = Math.max(1.5, s * 0.16);
    ctx.lineCap = "round";
    ctx.setLineDash([s * 0.35, s * 0.2]);
    for (const [q, r] of world.roads) {
      for (const [nq, nr] of neighbors(q, r)) {
        if (!roadSet.has(`${nq},${nr}`)) continue;
        if (nr < r || (nr === r && nq < q)) continue; // draw each pair once
        if (!revealed(q, r) && !revealed(nq, nr)) continue;
        const [x1, y1] = hexCenter(q, r, s);
        const [x2, y2] = hexCenter(nq, nr, s);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
    }
    ctx.setLineDash([]);

    // POIs.
    for (const p of world.pois) {
      const [cx, cy] = hexCenter(p.q, p.r, s);
      drawPoi(ctx, p.kind, cx, cy, s);
      if (view.scale > 1.1) label(ctx, p.name, cx, cy + s * 0.95, s * 0.5, "#e8dcc0");
    }

    // Settlements.
    for (const st of world.settlements) {
      if (!revealed(st.q, st.r)) continue;
      const [cx, cy] = hexCenter(st.q, st.r, s);
      drawSettlement(ctx, st.size, cx, cy, s);
      label(ctx, st.name, cx, cy + s * 1.05, Math.max(10, s * (st.size === "city" ? 0.66 : 0.56)), "#fff3d6");
    }

    // Destination ring.
    const dest = destinationHex(world, destination);
    if (dest) {
      const [cx, cy] = hexCenter(dest[0], dest[1], s);
      ctx.strokeStyle = "#ffd36b";
      ctx.lineWidth = 3;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      hexCorners(cx, cy, s * 0.92).forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);
      // dotted line from party
      const [px, py] = hexCenter(world.party.q, world.party.r, s);
      ctx.strokeStyle = "rgba(255, 211, 107, 0.6)";
      ctx.lineWidth = 2;
      ctx.setLineDash([3, 6]);
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(cx, cy);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Hover outline.
    if (hover && interactive) {
      const [cx, cy] = hexCenter(hover.q, hover.r, s);
      ctx.strokeStyle = "rgba(255,255,255,0.7)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      hexCorners(cx, cy, s).forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      ctx.stroke();
    }

    // Party marker.
    {
      const [cx, cy] = hexCenter(world.party.q, world.party.r, s);
      ctx.fillStyle = "rgba(0,0,0,0.45)";
      ctx.beginPath();
      ctx.ellipse(cx, cy + s * 0.35, s * 0.45, s * 0.16, 0, 0, Math.PI * 2);
      ctx.fill();
      // banner pole
      ctx.strokeStyle = "#2a1d10";
      ctx.lineWidth = Math.max(2, s * 0.1);
      ctx.beginPath();
      ctx.moveTo(cx - s * 0.15, cy + s * 0.35);
      ctx.lineTo(cx - s * 0.15, cy - s * 0.75);
      ctx.stroke();
      ctx.fillStyle = "#c9302c";
      ctx.beginPath();
      ctx.moveTo(cx - s * 0.12, cy - s * 0.75);
      ctx.lineTo(cx + s * 0.55, cy - s * 0.55);
      ctx.lineTo(cx - s * 0.12, cy - s * 0.3);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = "#ffd36b";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    ctx.restore();
  }, [world, view, size, hover, destination, interactive, revealed, canvasRef]);

  const toWorld = (clientX: number, clientY: number) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: clientX - rect.left + (view?.x ?? 0), y: clientY - rect.top + (view?.y ?? 0) };
  };

  const onMouseDown = (e: React.MouseEvent) => {
    if (!view) return;
    drag.current = { sx: e.clientX, sy: e.clientY, vx: view.x, vy: view.y, moved: false };
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!view) return;
    const d = drag.current;
    if (d) {
      const dx = e.clientX - d.sx;
      const dy = e.clientY - d.sy;
      if (Math.abs(dx) + Math.abs(dy) > 4) d.moved = true;
      if (d.moved) {
        userMoved.current = true;
        setView({ ...view, x: d.vx - dx, y: d.vy - dy });
      }
    }
    if (!interactive) return;
    const p = toWorld(e.clientX, e.clientY);
    const [q, r] = pixelToHex(p.x, p.y, BASE * view.scale);
    if (q >= 0 && r >= 0 && q < world.w && r < world.h) {
      if (!hover || hover.q !== q || hover.r !== r) setHover({ q, r });
    } else if (hover) setHover(null);
  };
  const onMouseUp = (e: React.MouseEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!view || !d || d.moved || !interactive || !onPick) return;
    const p = toWorld(e.clientX, e.clientY);
    const [q, r] = pixelToHex(p.x, p.y, BASE * view.scale);
    if (q < 0 || r < 0 || q >= world.w || r >= world.h) return;
    if (q === world.party.q && r === world.party.r) return;
    const st = world.settlements.find((x) => x.q === q && x.r === r && revealed(q, r));
    if (st) onPick({ settlement_id: st.id }, st.name);
    else {
      const poi = world.pois.find((x) => x.q === q && x.r === r);
      const biome = BIOME_NAMES[world.hexes[r]?.[q] ?? ""] ?? "Unknown";
      onPick({ q, r }, poi ? poi.name : revealed(q, r) ? `${biome} (${q}, ${r})` : `Unexplored (${q}, ${r})`);
    }
  };
  const onWheel = (e: React.WheelEvent) => {
    if (!view) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    const ns = Math.max(0.4, Math.min(4, view.scale * factor));
    const k = ns / view.scale;
    userMoved.current = true;
    setView({ scale: ns, x: (view.x + mx) * k - mx, y: (view.y + my) * k - my });
  };

  const hoverInfo = (() => {
    if (!hover) return null;
    if (!revealed(hover.q, hover.r)) return "Unexplored";
    const st = world.settlements.find((x) => x.q === hover.q && x.r === hover.r);
    if (st) return `${st.name} — ${st.size}${st.shops.length ? ` · shops: ${st.shops.join(", ")}` : ""}`;
    const poi = world.pois.find((x) => x.q === hover.q && x.r === hover.r);
    if (poi) return `${poi.name} (${poi.kind})`;
    return BIOME_NAMES[world.hexes[hover.r]?.[hover.q] ?? ""] ?? "";
  })();

  return (
    <div className="map-wrap" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={() => {
          drag.current = null;
          setHover(null);
        }}
        onWheel={onWheel}
        style={{ cursor: interactive ? (drag.current?.moved ? "grabbing" : "pointer") : "default" }}
      />
      <div className="map-overlay top-left">
        {locationName && <span className="map-chip">📍 {locationName}</span>}
        {hoverInfo && interactive && <span className="map-chip muted">{hoverInfo}</span>}
      </div>
      {interactive && (
        <div className="map-overlay bottom-right">
          <button className="icon-btn" title="Zoom in" onClick={() => view && setView({ ...view, scale: Math.min(4, view.scale * 1.25) })}>
            ＋
          </button>
          <button className="icon-btn" title="Zoom out" onClick={() => view && setView({ ...view, scale: Math.max(0.4, view.scale / 1.25) })}>
            －
          </button>
          <button
            className="icon-btn"
            title="Centre on party"
            onClick={() => {
              if (!view) return;
              const [px, py] = hexCenter(world.party.q, world.party.r, BASE * view.scale);
              setView({ ...view, x: px - size.w / 2, y: py - size.h / 2 });
            }}
          >
            ⌖
          </button>
        </div>
      )}
    </div>
  );
}

function destinationHex(world: World, d: TravelTo | undefined): [number, number] | null {
  if (!d) return null;
  if ("settlement_id" in d) {
    const st = world.settlements.find((s) => s.id === d.settlement_id);
    return st ? [st.q, st.r] : null;
  }
  return [d.q, d.r];
}

function label(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, px: number, color: string) {
  ctx.font = `600 ${Math.round(px)}px Cinzel, Georgia, serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(0,0,0,0.75)";
  ctx.strokeText(text, x, y);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}

function drawBiomeMark(ctx: CanvasRenderingContext2D, code: string, cx: number, cy: number, s: number) {
  if (s < 9) return;
  ctx.save();
  switch (code) {
    case "f":
    case "F": {
      ctx.fillStyle = code === "F" ? "#1f3d1b" : "#365f2a";
      const n = code === "F" ? 3 : 2;
      for (let i = 0; i < n; i++) {
        const ox = (i - (n - 1) / 2) * s * 0.42;
        const oy = (i % 2) * s * 0.18 - s * 0.05;
        ctx.beginPath();
        ctx.moveTo(cx + ox, cy + oy - s * 0.38);
        ctx.lineTo(cx + ox + s * 0.2, cy + oy + s * 0.12);
        ctx.lineTo(cx + ox - s * 0.2, cy + oy + s * 0.12);
        ctx.closePath();
        ctx.fill();
      }
      break;
    }
    case "M": {
      ctx.fillStyle = "#5c5550";
      ctx.beginPath();
      ctx.moveTo(cx - s * 0.5, cy + s * 0.3);
      ctx.lineTo(cx - s * 0.1, cy - s * 0.45);
      ctx.lineTo(cx + s * 0.3, cy + s * 0.3);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#eee";
      ctx.beginPath();
      ctx.moveTo(cx - s * 0.22, cy - s * 0.22);
      ctx.lineTo(cx - s * 0.1, cy - s * 0.45);
      ctx.lineTo(cx + s * 0.02, cy - s * 0.22);
      ctx.closePath();
      ctx.fill();
      break;
    }
    case "h": {
      ctx.strokeStyle = "#6e6040";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(cx - s * 0.18, cy + s * 0.15, s * 0.25, Math.PI, 0);
      ctx.arc(cx + s * 0.22, cy + s * 0.2, s * 0.2, Math.PI, 0);
      ctx.stroke();
      break;
    }
    case "s": {
      ctx.strokeStyle = "#7b8f5a";
      ctx.lineWidth = 1.2;
      for (let i = -1; i <= 1; i++) {
        ctx.beginPath();
        ctx.moveTo(cx + i * s * 0.25, cy + s * 0.2);
        ctx.lineTo(cx + i * s * 0.25, cy - s * 0.12);
        ctx.stroke();
      }
      break;
    }
    case "~":
    case "-": {
      ctx.strokeStyle = "rgba(255,255,255,0.18)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - s * 0.35, cy);
      ctx.quadraticCurveTo(cx - s * 0.17, cy - s * 0.12, cx, cy);
      ctx.quadraticCurveTo(cx + s * 0.17, cy + s * 0.12, cx + s * 0.35, cy);
      ctx.stroke();
      break;
    }
  }
  ctx.restore();
}

function drawSettlement(ctx: CanvasRenderingContext2D, size: string, cx: number, cy: number, s: number) {
  const k = size === "city" ? 0.75 : size === "town" ? 0.58 : 0.42;
  ctx.save();
  ctx.fillStyle = "rgba(0,0,0,0.4)";
  ctx.beginPath();
  ctx.ellipse(cx, cy + s * k * 0.55, s * k, s * k * 0.3, 0, 0, Math.PI * 2);
  ctx.fill();
  const drawHouse = (x: number, y: number, w: number) => {
    ctx.fillStyle = "#e9d8b4";
    ctx.fillRect(x - w / 2, y - w * 0.5, w, w * 0.7);
    ctx.fillStyle = "#9c3d2e";
    ctx.beginPath();
    ctx.moveTo(x - w * 0.62, y - w * 0.45);
    ctx.lineTo(x, y - w * 1.0);
    ctx.lineTo(x + w * 0.62, y - w * 0.45);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#2b1d10";
    ctx.lineWidth = 1;
    ctx.strokeRect(x - w / 2, y - w * 0.5, w, w * 0.7);
  };
  if (size === "city") {
    // walls + towers
    ctx.fillStyle = "#b9ad97";
    ctx.strokeStyle = "#2b1d10";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.rect(cx - s * 0.6, cy - s * 0.2, s * 1.2, s * 0.55);
    ctx.fill();
    ctx.stroke();
    for (const ox of [-0.6, 0.6]) {
      ctx.fillStyle = "#a59a85";
      ctx.fillRect(cx + ox * s - s * 0.13, cy - s * 0.5, s * 0.26, s * 0.85);
      ctx.strokeRect(cx + ox * s - s * 0.13, cy - s * 0.5, s * 0.26, s * 0.85);
    }
    drawHouse(cx, cy - s * 0.12, s * 0.42);
  } else if (size === "town") {
    drawHouse(cx - s * 0.25, cy + s * 0.1, s * 0.34);
    drawHouse(cx + s * 0.22, cy, s * 0.4);
  } else {
    drawHouse(cx, cy + s * 0.08, s * 0.36);
  }
  ctx.restore();
}

function drawPoi(ctx: CanvasRenderingContext2D, kind: string, cx: number, cy: number, s: number) {
  const glyph: Record<string, string> = { ruins: "🏛", cave: "🕳", tower: "🗼", camp: "⛺", shrine: "⛩" };
  ctx.save();
  ctx.font = `${Math.round(s * 0.9)}px serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(glyph[kind] ?? "❖", cx, cy);
  ctx.restore();
}
