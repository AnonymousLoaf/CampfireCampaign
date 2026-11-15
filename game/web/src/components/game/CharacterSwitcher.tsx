import { initials } from "../../util/format";
import { useGame } from "./gameContext";

/** Shown only when I control more than one character (single-speaker mode). */
export default function CharacterSwitcher({ label = "Acting as", ids }: { label?: string; ids?: string[] }) {
  const { view, controls, actingId, setActingId } = useGame();
  const list = ids ?? controls;
  if (list.length <= 1) return null;
  return (
    <div className="char-switcher">
      <span className="muted small">{label}</span>
      {list.map((id) => {
        const c = view.characters[id];
        if (!c) return null;
        return (
          <button
            key={id}
            className={`switch-chip ${actingId === id ? "selected" : ""}`}
            onClick={() => setActingId(id)}
            title={`${c.name} — HP ${c.hp}/${c.hp_max}`}
          >
            <span className="char-avatar tiny" style={{ background: c.color }}>
              {initials(c.name)}
            </span>
            {c.name}
          </button>
        );
      })}
    </div>
  );
}
