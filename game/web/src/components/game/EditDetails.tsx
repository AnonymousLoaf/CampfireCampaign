import { useState } from "react";
import { api } from "../../api/client";
import type { CharacterView } from "../../api/types";
import ErrorText, { useAction } from "../ErrorText";
import Modal from "../Modal";

export const ALIGNMENTS = [
  "Lawful Good",
  "Neutral Good",
  "Chaotic Good",
  "Lawful Neutral",
  "True Neutral",
  "Chaotic Neutral",
  "Lawful Evil",
  "Neutral Evil",
  "Chaotic Evil",
];

/** A player's own character: name, alignment, token colour and backstory can change any time. Rules stay as built. */
export default function EditDetails({ c, onClose, onSaved }: { c: CharacterView; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(c.name);
  const [alignment, setAlignment] = useState(c.alignment || "True Neutral");
  const [color, setColor] = useState(c.color || "#c9a227");
  const [backstory, setBackstory] = useState(c.backstory || "");
  const [save, saving, error] = useAction(async () => {
    await api.editDetails(c.id, { name: name.trim(), alignment, color, backstory });
    onSaved();
    onClose();
  });
  return (
    <Modal
      title={`Edit ${c.name}`}
      onClose={onClose}
      footer={
        <>
          <ErrorText error={error} />
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={saving || !name.trim()} onClick={() => void save()}>
            {saving ? "Saving…" : "Save"}
          </button>
        </>
      }
    >
      <div className="stack">
        <label className="field">
          <span className="label">Name</span>
          <input value={name} maxLength={40} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">
          <span className="label">Alignment</span>
          <select value={alignment} onChange={(e) => setAlignment(e.target.value)}>
            {ALIGNMENTS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="label">Token colour</span>
          <input type="color" value={color} onChange={(e) => setColor(e.target.value)} />
        </label>
        <label className="field">
          <span className="label">Backstory</span>
          <textarea rows={7} maxLength={4000} value={backstory} onChange={(e) => setBackstory(e.target.value)} />
        </label>
        <div className="muted small">
          Race, class, ability scores and other rules choices stay as built; they change through levelling up.
        </div>
      </div>
    </Modal>
  );
}
