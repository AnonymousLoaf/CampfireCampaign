import type { CharacterView, Ruleset } from "../../api/types";
import { navigate } from "../../router";
import { initials } from "../../util/format";

/** Characters without a ruleset predate M3 and are 2014 characters. */
export const rulesetOf = (c: CharacterView): Ruleset => c.ruleset ?? "2014";

export default function CharacterPicker({
  characters,
  value,
  onChange,
  ruleset,
}: {
  characters: CharacterView[];
  value: string;
  onChange: (id: string) => void;
  /** Only offer characters made for this ruleset (when known). */
  ruleset?: Ruleset;
}) {
  const list = ruleset ? characters.filter((c) => rulesetOf(c) === ruleset) : characters;
  if (list.length === 0) {
    return (
      <div className="empty small">
        {ruleset && characters.length > 0
          ? `None of your free characters use the ${ruleset} rules. `
          : "You have no free characters (each character can be in one game at a time). "}
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
        {list.map((c) => (
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
              <span className={`ruleset-badge r${rulesetOf(c)}`}>{rulesetOf(c)}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
