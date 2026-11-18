import { useRef, useState, type ReactNode } from "react";
import { PINNED, activate, hidePanel, movePanel, placeTab, resize, type Layout, type Node, type Pane, type PanelId, type Split, type Zone } from "./layout";

export interface PanelDef {
  title: string;
  icon: string;
  badge?: number | string;
  /** Extra class on the panel body (e.g. one that brings the old column styling). */
  bodyClass?: string;
  render: () => ReactNode;
}

const MIN_PCT = 8;
const DND_TYPE = "application/x-campfire-panel";

/** Docked, resizable panes. Drag a tab onto another pane's edge to split it out, or onto its middle to join it. */
export default function Dock({ layout, onChange, panels }: { layout: Layout; onChange: (l: Layout) => void; panels: Record<PanelId, PanelDef> }) {
  const [dragging, setDragging] = useState<PanelId | null>(null);
  const ctx: DockCtx = { layout, onChange, panels, dragging, setDragging };
  return (
    <div className={`dock ${dragging ? "dragging" : ""}`}>
      <NodeView node={layout.root} ctx={ctx} />
    </div>
  );
}

interface DockCtx {
  layout: Layout;
  onChange: (l: Layout) => void;
  panels: Record<PanelId, PanelDef>;
  dragging: PanelId | null;
  setDragging: (p: PanelId | null) => void;
}

function NodeView({ node, ctx }: { node: Node; ctx: DockCtx }) {
  return node.kind === "pane" ? <PaneView pane={node} ctx={ctx} /> : <SplitView split={node} ctx={ctx} />;
}

function SplitView({ split, ctx }: { split: Split; ctx: DockCtx }) {
  const ref = useRef<HTMLDivElement>(null);
  const startDrag = (i: number, e: React.PointerEvent) => {
    const el = ref.current;
    if (!el) return;
    e.preventDefault();
    const rect = el.getBoundingClientRect();
    const total = split.dir === "row" ? rect.width : rect.height;
    const start = split.dir === "row" ? e.clientX : e.clientY;
    const sizes = [...split.sizes];
    const pair = sizes[i] + sizes[i + 1];
    const handle = e.currentTarget as HTMLElement;
    handle.setPointerCapture(e.pointerId);
    document.body.classList.add(split.dir === "row" ? "resizing-col" : "resizing-row");
    let latest = sizes;
    const move = (ev: PointerEvent) => {
      const d = (((split.dir === "row" ? ev.clientX : ev.clientY) - start) / total) * 100;
      const a = Math.min(pair - MIN_PCT, Math.max(MIN_PCT, sizes[i] + d));
      latest = [...sizes];
      latest[i] = a;
      latest[i + 1] = pair - a;
      // live feedback without re-rendering the whole game on every pixel
      const kids = el.children;
      let k = 0;
      for (const c of Array.from(kids)) {
        if ((c as HTMLElement).dataset.dockChild !== undefined) {
          (c as HTMLElement).style.flexBasis = `${latest[k]}%`;
          k++;
        }
      }
    };
    const up = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
      handle.removeEventListener("pointercancel", up);
      document.body.classList.remove("resizing-col", "resizing-row");
      ctx.onChange(resize(ctx.layout, split.id, latest));
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
    handle.addEventListener("pointercancel", up);
  };
  const kids: ReactNode[] = [];
  split.children.forEach((c, i) => {
    if (i > 0)
      kids.push(
        <div
          key={`h${c.id}`}
          className={`dock-handle dir-${split.dir}`}
          role="separator"
          aria-orientation={split.dir === "row" ? "vertical" : "horizontal"}
          title="Drag to resize"
          onPointerDown={(e) => startDrag(i - 1, e)}
          onDoubleClick={() => {
            const pair = split.sizes[i - 1] + split.sizes[i];
            const s = [...split.sizes];
            s[i - 1] = pair / 2;
            s[i] = pair / 2;
            ctx.onChange(resize(ctx.layout, split.id, s));
          }}
        />,
      );
    kids.push(
      <div key={c.id} data-dock-child="" className="dock-cell" style={{ flexBasis: `${split.sizes[i]}%` }}>
        <NodeView node={c} ctx={ctx} />
      </div>,
    );
  });
  return (
    <div ref={ref} className={`dock-split dir-${split.dir}`}>
      {kids}
    </div>
  );
}

function zoneAt(e: React.DragEvent, el: HTMLElement): Zone {
  const r = el.getBoundingClientRect();
  const x = (e.clientX - r.left) / r.width;
  const y = (e.clientY - r.top) / r.height;
  const edges: [Zone, number][] = [
    ["left", x],
    ["right", 1 - x],
    ["top", y],
    ["bottom", 1 - y],
  ];
  const [z, d] = edges.reduce((a, b) => (b[1] < a[1] ? b : a));
  return d < 0.25 ? z : "center";
}

function PaneView({ pane, ctx }: { pane: Pane; ctx: DockCtx }) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [zone, setZone] = useState<Zone | null>(null);
  const [slot, setSlot] = useState<number | null>(null); // where a dragged tab would land in this strip
  const def = ctx.panels[pane.active];
  const isDragging = !!ctx.dragging;
  const drop = (z: Zone) => {
    const pid = ctx.dragging;
    ctx.setDragging(null);
    setZone(null);
    if (pid) ctx.onChange(movePanel(ctx.layout, pid, pane.id, z));
  };
  return (
    <div className="dock-pane">
      <div
        className="dock-tabs"
        onDragOver={(e) => {
          if (!isDragging) return;
          e.preventDefault();
          if (slot !== pane.tabs.length) setSlot(pane.tabs.length); // empty space after the last tab
        }}
        onDragLeave={(e) => {
          if (!(e.relatedTarget instanceof window.Node && e.currentTarget.contains(e.relatedTarget))) setSlot(null);
        }}
        onDrop={(e) => {
          e.preventDefault();
          const pid = ctx.dragging;
          const at = slot ?? pane.tabs.length;
          ctx.setDragging(null);
          setSlot(null);
          if (pid) ctx.onChange(placeTab(ctx.layout, pid, pane.id, at));
        }}
      >
        {pane.tabs.map((t, i) => {
          const d = ctx.panels[t];
          return (
            <button
              key={t}
              className={`dock-tab ${t === pane.active ? "active" : ""} ${slot === i ? "drop-before" : ""} ${
                slot === i + 1 && i === pane.tabs.length - 1 ? "drop-after" : ""
              }`}
              draggable
              title="Drag to move: between tabs to reorder, onto another pane's edge to give it its own space, or onto its middle to add it as a tab"
              onDragOver={(e) => {
                if (!isDragging) return;
                e.preventDefault();
                e.stopPropagation();
                const r = e.currentTarget.getBoundingClientRect();
                const s = e.clientX < r.left + r.width / 2 ? i : i + 1;
                if (s !== slot) setSlot(s);
              }}
              onClick={() => ctx.onChange(activate(ctx.layout, pane.id, t))}
              onDragStart={(e) => {
                e.dataTransfer.setData(DND_TYPE, t);
                e.dataTransfer.setData("text/plain", d.title);
                e.dataTransfer.effectAllowed = "move";
                // let the drag image render before the overlays appear
                window.setTimeout(() => ctx.setDragging(t), 0);
              }}
              onDragEnd={() => {
                ctx.setDragging(null);
                setSlot(null);
              }}
            >
              <span className="dock-tab-icon">{d.icon}</span>
              <span className="dock-tab-title">{d.title}</span>
              {d.badge !== undefined && <span className="count">{d.badge}</span>}
              {!PINNED.includes(t) && (
                <span
                  className="dock-tab-x"
                  role="button"
                  title={`Close ${d.title} (bring it back from Layout)`}
                  onClick={(e) => {
                    e.stopPropagation();
                    ctx.onChange(hidePanel(ctx.layout, t));
                  }}
                >
                  ×
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div ref={bodyRef} className={`dock-body ${def?.bodyClass ?? ""}`}>
        {def?.render()}
        {isDragging && (
          <div
            className="dock-drop"
            onDragOver={(e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
              const z = zoneAt(e, e.currentTarget);
              if (z !== zone) setZone(z);
            }}
            onDragLeave={() => setZone(null)}
            onDrop={(e) => {
              e.preventDefault();
              drop(zoneAt(e, e.currentTarget));
            }}
          >
            {zone && <div className={`dock-drop-preview ${zone}`} />}
          </div>
        )}
      </div>
    </div>
  );
}
