import { useState } from "react";
import { ALL_PANELS, PINNED, defaultLayout, findPaneOf, hidePanel, showPanel, type Layout, type PanelId } from "./layout";
import type { PanelDef } from "./Dock";

/** Header menu: show or hide panels, and reset to the standard layout. */
export default function LayoutMenu({ layout, onChange, panels }: { layout: Layout; onChange: (l: Layout) => void; panels: Record<PanelId, PanelDef> }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="layout-menu">
      <button className="btn ghost small" aria-expanded={open} onClick={() => setOpen((v) => !v)} title="Choose and arrange your panels">
        ▦ Layout
      </button>
      {open && (
        <div className="popover layout-pop" onMouseLeave={() => setOpen(false)}>
          <div className="small muted">
            Drag a panel's tab onto the edge of another panel to give it its own space, or onto its middle to stack them as tabs.
            Drag the gaps between panels to resize. Saved on this device.
          </div>
          <div className="layout-list">
            {ALL_PANELS.map((p) => {
              const shown = !!findPaneOf(layout.root, p);
              return (
                <label key={p} className={`toggle ${PINNED.includes(p) ? "pinned" : ""}`}>
                  <input
                    type="checkbox"
                    checked={shown}
                    disabled={PINNED.includes(p)}
                    onChange={() => onChange(shown ? hidePanel(layout, p) : showPanel(layout, p))}
                  />
                  <span>
                    {panels[p].icon} {panels[p].title}
                  </span>
                </label>
              );
            })}
          </div>
          <button
            className="btn small"
            onClick={() => {
              onChange(defaultLayout());
              setOpen(false);
            }}
          >
            Reset to standard layout
          </button>
        </div>
      )}
    </div>
  );
}
