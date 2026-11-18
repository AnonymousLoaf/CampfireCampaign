/** Dock layout: a tree of splits (rows/columns with sizes in %) whose leaves are panes holding one or more panel tabs. */

export type PanelId = "party" | "sheet" | "inventory" | "spells" | "journal" | "npcs" | "map" | "live" | "story" | "chat" | "composer";
export const ALL_PANELS: PanelId[] = ["party", "sheet", "inventory", "spells", "journal", "npcs", "map", "live", "story", "chat", "composer"];
/** Panels that can't be closed (you'd have no way to play). */
export const PINNED: PanelId[] = ["composer"];

export interface Pane {
  kind: "pane";
  id: string;
  tabs: PanelId[];
  active: PanelId;
}
export interface Split {
  kind: "split";
  id: string;
  dir: "row" | "col";
  sizes: number[]; // percentages, summing to 100
  children: Node[];
}
export type Node = Pane | Split;
export interface Layout {
  root: Node;
  hidden: PanelId[];
}
export type Zone = "left" | "right" | "top" | "bottom" | "center";

let seq = 0;
const uid = (p: string) => `${p}${Date.now().toString(36)}${(seq++).toString(36)}`;
const pane = (tabs: PanelId[], active?: PanelId): Pane => ({ kind: "pane", id: uid("p"), tabs, active: active ?? tabs[0] });
const split = (dir: Split["dir"], sizes: number[], children: Node[]): Split => ({ kind: "split", id: uid("s"), dir, sizes, children });

export function defaultLayout(): Layout {
  return {
    root: split("row", [21, 50, 29], [
      split("col", [36, 64], [pane(["party"]), pane(["sheet", "inventory", "spells", "journal", "npcs"])]),
      pane(["map"]),
      split("col", [70, 30], [pane(["live", "story", "chat"]), pane(["composer"])]),
    ]),
    hidden: [],
  };
}

export function panes(n: Node): Pane[] {
  return n.kind === "pane" ? [n] : n.children.flatMap(panes);
}

export function findPaneOf(root: Node, pid: PanelId): Pane | undefined {
  return panes(root).find((p) => p.tabs.includes(pid));
}

const clone = (l: Layout): Layout => JSON.parse(JSON.stringify(l)) as Layout;

/** Collapse empty panes and single-child splits; flatten a split into a parent of the same direction. */
function normalize(n: Node): Node | null {
  if (n.kind === "pane") return n.tabs.length ? n : null;
  const kids: Node[] = [];
  const sizes: number[] = [];
  n.children.forEach((c, i) => {
    const m = normalize(c);
    if (!m) return;
    if (m.kind === "split" && m.dir === n.dir) {
      m.children.forEach((cc, j) => {
        kids.push(cc);
        sizes.push((n.sizes[i] * m.sizes[j]) / 100);
      });
    } else {
      kids.push(m);
      sizes.push(n.sizes[i]);
    }
  });
  if (!kids.length) return null;
  if (kids.length === 1) return kids[0];
  const total = sizes.reduce((a, b) => a + b, 0) || 1;
  return { ...n, children: kids, sizes: sizes.map((s) => (s / total) * 100) };
}

function detach(l: Layout, pid: PanelId): void {
  for (const p of panes(l.root)) {
    const i = p.tabs.indexOf(pid);
    if (i >= 0) {
      p.tabs.splice(i, 1);
      if (p.active === pid) p.active = p.tabs[Math.max(0, i - 1)] ?? p.tabs[0];
    }
  }
  l.hidden = l.hidden.filter((h) => h !== pid);
}

function replaceNode(n: Node, id: string, f: (x: Node) => Node): Node {
  if (n.id === id) return f(n);
  if (n.kind === "pane") return n;
  return { ...n, children: n.children.map((c) => replaceNode(c, id, f)) };
}

function parentOf(n: Node, id: string): Split | null {
  if (n.kind === "pane") return null;
  for (const c of n.children) {
    if (c.id === id) return n;
    const p = parentOf(c, id);
    if (p) return p;
  }
  return null;
}

/** Move a panel next to (or into) a pane. */
export function movePanel(layout: Layout, pid: PanelId, targetPaneId: string, zone: Zone): Layout {
  const before = findPaneOf(layout.root, pid);
  if (before && before.id === targetPaneId && (zone === "center" || before.tabs.length === 1)) return layout; // no-op
  const l = clone(layout);
  detach(l, pid);
  const target = panes(l.root).find((p) => p.id === targetPaneId);
  if (!target) return layout;
  if (zone === "center") {
    target.tabs.push(pid);
    target.active = pid;
  } else {
    const dir: Split["dir"] = zone === "left" || zone === "right" ? "row" : "col";
    const first = zone === "left" || zone === "top";
    const fresh = pane([pid]);
    const parent = parentOf(l.root, target.id);
    if (parent && parent.dir === dir) {
      const i = parent.children.findIndex((c) => c.id === target.id);
      const half = parent.sizes[i] / 2;
      parent.sizes.splice(i, 1, half, half);
      parent.children.splice(first ? i : i + 1, 0, fresh);
    } else {
      l.root = replaceNode(l.root, target.id, (t) => split(dir, [50, 50], first ? [fresh, t] : [t, fresh]));
    }
  }
  l.root = normalize(l.root) ?? pane(["composer"]);
  return l;
}

/** Put a tab at a position in a pane's tab strip: reorders within a pane, or moves it in from another pane. */
export function placeTab(layout: Layout, pid: PanelId, paneId: string, index: number): Layout {
  const l = clone(layout);
  const target = panes(l.root).find((p) => p.id === paneId);
  if (!target) return layout;
  const from = target.tabs.indexOf(pid);
  if (from >= 0) {
    if (index === from || index === from + 1) return layout; // dropped where it already is
    target.tabs.splice(from, 1);
    if (from < index) index--;
  } else {
    detach(l, pid);
  }
  target.tabs.splice(Math.max(0, Math.min(index, target.tabs.length)), 0, pid);
  target.active = pid;
  l.root = normalize(l.root) ?? pane(["composer"]);
  return l;
}

export function hidePanel(layout: Layout, pid: PanelId): Layout {
  if (PINNED.includes(pid)) return layout;
  const l = clone(layout);
  detach(l, pid);
  l.hidden.push(pid);
  l.root = normalize(l.root) ?? pane(["composer"]);
  return l;
}

/** Show a hidden panel as a tab in the biggest pane (or next to a sensible neighbour). */
export function showPanel(layout: Layout, pid: PanelId): Layout {
  const l = clone(layout);
  l.hidden = l.hidden.filter((h) => h !== pid);
  if (findPaneOf(l.root, pid)) return l;
  const near: Partial<Record<PanelId, PanelId[]>> = {
    live: ["story", "chat"],
    story: ["live", "chat"],
    chat: ["live", "story"],
    party: ["sheet"],
  };
  const host =
    (near[pid] ?? ["sheet", "inventory", "journal", "npcs", "spells"]).map((n) => findPaneOf(l.root, n)).find(Boolean) ?? panes(l.root)[0];
  host.tabs.push(pid);
  host.active = pid;
  return l;
}

export function activate(layout: Layout, paneId: string, pid: PanelId): Layout {
  const l = clone(layout);
  const p = panes(l.root).find((x) => x.id === paneId);
  if (p && p.tabs.includes(pid)) p.active = pid;
  return l;
}

/** Make a panel the visible tab wherever it is (e.g. the map when a fight starts). Returns the same object if nothing changes. */
export function reveal(layout: Layout, pid: PanelId): Layout {
  const p = findPaneOf(layout.root, pid);
  if (!p || p.active === pid) return layout;
  return activate(layout, p.id, pid);
}

export function resize(layout: Layout, splitId: string, sizes: number[]): Layout {
  const l = clone(layout);
  l.root = replaceNode(l.root, splitId, (n) => (n.kind === "split" ? { ...n, sizes } : n));
  return l;
}

// ── persistence (per device) ──
const KEY = "campfire.dock.v1";

function valid(n: unknown, seen: Set<string>): n is Node {
  const x = n as Node;
  if (!x || typeof x !== "object" || typeof x.id !== "string") return false;
  if (x.kind === "pane") {
    if (!Array.isArray(x.tabs) || !x.tabs.length) return false;
    for (const t of x.tabs) {
      if (!ALL_PANELS.includes(t) || seen.has(t)) return false;
      seen.add(t);
    }
    if (!x.tabs.includes(x.active)) x.active = x.tabs[0];
    return true;
  }
  return (
    x.kind === "split" &&
    (x.dir === "row" || x.dir === "col") &&
    Array.isArray(x.children) &&
    Array.isArray(x.sizes) &&
    x.children.length === x.sizes.length &&
    x.children.length > 0 &&
    x.children.every((c) => valid(c, seen))
  );
}

export function loadLayout(): Layout {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) {
      const l = JSON.parse(raw) as Layout;
      const seen = new Set<string>();
      if (valid(l.root, seen)) {
        let out: Layout = { root: l.root, hidden: (l.hidden ?? []).filter((h) => ALL_PANELS.includes(h) && !seen.has(h)) };
        // panels added since this layout was saved show up as tabs
        for (const p of ALL_PANELS) if (!seen.has(p) && !out.hidden.includes(p)) out = showPanel(out, p);
        for (const p of PINNED) if (out.hidden.includes(p)) out = showPanel(out, p);
        return out;
      }
    }
  } catch {
    /* storage blocked or a broken layout: start fresh */
  }
  return defaultLayout();
}

export function saveLayout(l: Layout | null): void {
  try {
    if (l) window.localStorage.setItem(KEY, JSON.stringify(l));
    else window.localStorage.removeItem(KEY);
  } catch {
    /* storage blocked: the layout lasts until the page closes */
  }
}
