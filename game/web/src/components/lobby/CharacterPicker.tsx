import type { CharacterView } from "../../api/types";
import { navigate } from "../../router";
import { initials } from "../../util/format";

export default function CharacterPicker({
  characters,
  value,
  onChange,
}: {
  characters: CharacterView[];
  value: string;
  onChange: (id: string) => void;
}) {
  if (characters.length === 0) {
    return (
      <div className="empty small">
        You have no free characters (each character can be in one game at a time).{" "}
        <button className="link" onClick={() => navigate({ name: "create-character" })}>
          Create one
        </button>
        .
      </div>
    );
  }
  return (
    <div>
      <div className="label">Play as</div>
      <div className="picker-list">
        {characters.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`picker-item ${value === c.id ? "selected" : ""}`}
            onClick={() => onChange(c.id)}
          >
            <span className="char-avatar tiny" style={{ background: c.color || "#777" }}>
              {initials(c.name)}
            </span>
            <span>
              <strong>{c.name}</strong>
              <span className="muted small">
                {" "}
                · L{c.level} {c.race} {c.class}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
