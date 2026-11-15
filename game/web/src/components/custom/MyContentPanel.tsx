import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import type { CustomEntry, CustomEntryInput, CustomKind } from "../../api/types";
import ErrorText, { useAction } from "../ErrorText";

export const KIND_LABEL: Record<CustomKind, string> = {
  feat: "Feat",
  feature: "Class / subclass feature",
  spell: "Spell",
  item: "Item",
  background: "Background",
  species_trait: "Species trait",
};
const KINDS = Object.keys(KIND_LABEL) as CustomKind[];
const SCHOOLS = ["Abjuration", "Conjuration", "Divination", "Enchantment", "Evocation", "Illusion", "Necromancy", "Transmutation"];

export const PRIVACY_LINE =
  "Private to you — for homebrew, or content from books you own. The DM reads these in your games; they're never shared anywhere else.";

type Draft = {
  kind: CustomKind;
  name: string;
  description: string;
  level: string;
  // spell
  school: string;
  casting_time: string;
  range: string;
  concentration: boolean;
  // item
  value_gp: string;
  weight: string;
  category: string;
  // background
  skills: string;
  tool: string;
};

const EMPTY: Draft = {
  kind: "feat",
  name: "",
  description: "",
  level: "",
  school: "Evocation",
  casting_time: "1 action",
  range: "",
  concentration: false,
  value_gp: "",
  weight: "",
  category: "Gear",
  skills: "",
  tool: "",
};

function toDraft(e: CustomEntry): Draft {
  const d = (e.data ?? {}) as Record<string, unknown>;
  const s = (k: string, dflt = "") => (d[k] === undefined || d[k] === null ? dflt : String(d[k]));
  return {
    ...EMPTY,
    kind: e.kind,
    name: e.name,
    description: e.description,
    level: e.level === null || e.level === undefined ? s("level") : String(e.level),
    school: s("school", "Evocation"),
    casting_time: s("casting_time", "1 action"),
    range: s("range"),
    concentration: d.concentration === true,
    value_gp: s("value_gp"),
    weight: s("weight"),
    category: s("category", "Gear"),
    skills: Array.isArray(d.skills) ? (d.skills as unknown[]).map(String).join(", ") : s("skills"),
    tool: s("tool"),
  };
}

function num(s: string): number | null {
  if (s.trim() === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function toInput(d: Draft): CustomEntryInput {
  const level = num(d.level);
  const base: CustomEntryInput = { kind: d.kind, name: d.name.trim(), description: d.description.trim(), level };
  if (d.kind === "spell")
    base.data = { level: level ?? 0, school: d.school, casting_time: d.casting_time.trim(), range: d.range.trim(), concentration: d.concentration };
  else if (d.kind === "item") base.data = { value_gp: num(d.value_gp) ?? 0, weight: num(d.weight) ?? 0, category: d.category.trim() || "Gear" };
  else if (d.kind === "background")
    base.data = {
      skills: d.skills
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
      tool: d.tool.trim(),
    };
  else base.data = {};
  return base;
}

/** Lobby section: my custom content library (list, create/edit, delete). */
export default function MyContentPanel() {
  const [entries, setEntries] = useState<CustomEntry[] | null>(null);
  const [editing, setEditing] = useState<{ id: string | null; draft: Draft } | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setEntries(await api.customList());
      setLoadErr(null);
    } catch (e) {
      setLoadErr(e instanceof Error ? e.message : String(e));
      setEntries([]);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const [save, saving, saveErr] = useAction(async () => {
    if (!editing) return;
    const body = toInput(editing.draft);
    if (editing.id) await api.customUpdate(editing.id, body);
    else await api.customCreate(body);
    setEditing(null);
    await load();
  });
  const [remove, , removeErr] = useAction(async (id: string) => {
    await api.customDelete(id);
    await load();
  });

  const d = editing?.draft;
  const setD = (patch: Partial<Draft>) => setEditing((e) => (e ? { ...e, draft: { ...e.draft, ...patch } } : e));

  return (
    <section className="panel my-content">
      <div className="panel-head">
        <h2>My content</h2>
        {!editing && (
          <button className="btn" onClick={() => setEditing({ id: null, draft: { ...EMPTY } })}>
            New entry
          </button>
        )}
      </div>
      <p className="muted small">{PRIVACY_LINE} Attach entries to a character from its card or sheet.</p>
      <ErrorText error={loadErr || removeErr} />

      {editing && d && (
        <form
          className="custom-form stack-tight"
          onSubmit={(e) => {
            e.preventDefault();
            if (d.name.trim()) void save();
          }}
        >
          <div className="row gap wrap">
            <label className="field">
              <span className="label">Kind</span>
              <select value={d.kind} onChange={(e) => setD({ kind: e.target.value as CustomKind })}>
                {KINDS.map((k) => (
                  <option key={k} value={k}>
                    {KIND_LABEL[k]}
                  </option>
                ))}
              </select>
            </label>
            <label className="field grow">
              <span className="label">Name</span>
              <input value={d.name} onChange={(e) => setD({ name: e.target.value })} maxLength={80} required />
            </label>
            {d.kind !== "item" && d.kind !== "background" && (
              <label className="field narrow">
                <span className="label">{d.kind === "spell" ? "Spell level" : "Level"}</span>
                <input type="number" min={0} max={20} value={d.level} placeholder={d.kind === "spell" ? "0 = cantrip" : "optional"} onChange={(e) => setD({ level: e.target.value })} />
              </label>
            )}
          </div>

          {d.kind === "spell" && (
            <div className="row gap wrap">
              <label className="field">
                <span className="label">School</span>
                <select value={d.school} onChange={(e) => setD({ school: e.target.value })}>
                  {SCHOOLS.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="label">Casting time</span>
                <input value={d.casting_time} onChange={(e) => setD({ casting_time: e.target.value })} />
              </label>
              <label className="field">
                <span className="label">Range</span>
                <input value={d.range} placeholder="60 feet" onChange={(e) => setD({ range: e.target.value })} />
              </label>
              <label className="toggle">
                <input type="checkbox" checked={d.concentration} onChange={(e) => setD({ concentration: e.target.checked })} />
                <span>Concentration</span>
              </label>
            </div>
          )}
          {d.kind === "item" && (
            <div className="row gap wrap">
              <label className="field">
                <span className="label">Value (gp)</span>
                <input type="number" min={0} step="any" value={d.value_gp} onChange={(e) => setD({ value_gp: e.target.value })} />
              </label>
              <label className="field">
                <span className="label">Weight (lb)</span>
                <input type="number" min={0} step="any" value={d.weight} onChange={(e) => setD({ weight: e.target.value })} />
              </label>
              <label className="field">
                <span className="label">Category</span>
                <input value={d.category} onChange={(e) => setD({ category: e.target.value })} placeholder="Gear, Weapon, Wondrous item…" />
              </label>
            </div>
          )}
          {d.kind === "background" && (
            <div className="row gap wrap">
              <label className="field grow">
                <span className="label">Skills (comma separated)</span>
                <input value={d.skills} placeholder="Insight, Religion" onChange={(e) => setD({ skills: e.target.value })} />
              </label>
              <label className="field">
                <span className="label">Tool</span>
                <input value={d.tool} placeholder="Calligrapher's supplies" onChange={(e) => setD({ tool: e.target.value })} />
              </label>
            </div>
          )}

          <label className="field">
            <span className="label">Description (the DM rules from this text)</span>
            <textarea rows={5} value={d.description} onChange={(e) => setD({ description: e.target.value })} maxLength={4000} />
          </label>
          <ErrorText error={saveErr} />
          <div className="row gap">
            <button type="button" className="btn ghost small" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button className="btn primary small" disabled={saving || !d.name.trim()}>
              {saving ? "Saving…" : editing.id ? "Save changes" : "Add to my content"}
            </button>
          </div>
        </form>
      )}

      {entries === null ? (
        <div className="spinner" />
      ) : entries.length === 0 && !editing ? (
        <div className="empty">No custom content yet.</div>
      ) : (
        <ul className="custom-list">
          {entries.map((e) => (
            <li key={e.id} className="custom-row">
              <details>
                <summary>
                  <strong>{e.name}</strong> <span className={`badge tiny kind-${e.kind}`}>{KIND_LABEL[e.kind] ?? e.kind}</span>
                  {e.level !== null && e.level !== undefined && <span className="muted small"> · {e.kind === "spell" ? (e.level === 0 ? "cantrip" : `L${e.level}`) : `level ${e.level}`}</span>}
                </summary>
                <div className="small pre">{e.description || <span className="muted">No description.</span>}</div>
              </details>
              <div className="row gap">
                <button className="btn tiny ghost" onClick={() => setEditing({ id: e.id, draft: toDraft(e) })}>
                  Edit
                </button>
                <button
                  className="btn tiny ghost danger"
                  onClick={() => {
                    if (window.confirm(`Delete "${e.name}" from your content?`)) void remove(e.id);
                  }}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
