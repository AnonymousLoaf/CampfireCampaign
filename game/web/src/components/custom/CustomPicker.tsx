import { useState } from "react";
import { api } from "../../api/client";
import type { CharacterView, CustomEntry } from "../../api/types";
import { KIND_LABEL, PRIVACY_LINE } from "./MyContentPanel";

/**
 * "Add custom…" — attach an entry from my content library to a character, or detach one.
 * `run` wraps the API call (in-game it refreshes the view and toasts errors).
 */
export default function CustomPicker({
  c,
  run,
  showAttached = false,
}: {
  c: CharacterView;
  run: (fn: () => Promise<unknown>) => Promise<boolean | unknown>;
  /** Also list what's attached, with remove buttons (the lobby card has no sheet to show them). */
  showAttached?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [lib, setLib] = useState<CustomEntry[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const attached = new Set((c.custom ?? []).map((x) => x.entry_id));

  const toggle = async () => {
    if (open) return setOpen(false);
    setOpen(true);
    setErr(null);
    try {
      setLib(await api.customList());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setLib([]);
    }
  };

  // homebrew races are picked in the character creator, not attached afterwards
  const available = (lib ?? []).filter((e) => !attached.has(e.id) && e.kind !== "race");

  return (
    <div className="custom-picker">
      {showAttached && (c.custom ?? []).length > 0 && (
        <div className="custom-attached">
          {(c.custom ?? []).map((x) => (
            <span key={x.entry_id} className="chip custom-chip" title={`${KIND_LABEL[x.kind] ?? x.kind}: ${x.description}`}>
              {x.name} <small className="muted">{KIND_LABEL[x.kind] ?? x.kind}</small>
              <button className="chip-x" title="Detach from this character" onClick={() => void run(() => api.detachCustom(c.id, x.entry_id))}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <button className="btn tiny ghost" onClick={() => void toggle()} aria-expanded={open}>
        {open ? "Close" : "Add custom…"}
      </button>
      {open && (
        <div className="custom-pop">
          <p className="muted tiny-text">{PRIVACY_LINE}</p>
          {err && <div className="error-text small">{err}</div>}
          {lib === null ? (
            <div className="spinner small" />
          ) : available.length === 0 ? (
            <div className="muted small">{lib.length ? "Everything in your content is already attached." : "Your content library is empty — add entries under My content in the lobby."}</div>
          ) : (
            <ul className="custom-pick-list">
              {available.map((e) => (
                <li key={e.id}>
                  <button
                    className="custom-pick"
                    onClick={() =>
                      void Promise.resolve(run(() => api.attachCustom(c.id, e.id))).then(() => setOpen(false))
                    }
                  >
                    <strong>{e.name}</strong> <span className="badge tiny">{KIND_LABEL[e.kind] ?? e.kind}</span>
                    {e.description && <div className="muted tiny-text clamp">{e.description}</div>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
