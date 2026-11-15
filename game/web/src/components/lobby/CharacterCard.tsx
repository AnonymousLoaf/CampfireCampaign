import type { CharacterView } from "../../api/types";
import { formatMoney, initials } from "../../util/format";
import { LevelUpBadge } from "../LevelUpModal";

export default function CharacterCard({ c, onDelete, onLevelUp }: { c: CharacterView; onDelete?: () => void; onLevelUp?: () => void }) {
  return (
    <div className="char-card">
      <div className="char-avatar" style={{ background: c.color || "#777" }}>
        {initials(c.name)}
      </div>
      <div className="char-card-body">
        <div className="char-name">
          {c.name}
          <span className={`ruleset-badge r${c.ruleset ?? "2014"}`}>{c.ruleset ?? "2014"}</span>
        </div>
        <div className="muted small">
          Level {c.level} {c.race}
          {c.subrace ? ` (${c.subrace})` : ""} {c.class}
        </div>
        <div className="char-stats small">
          <span>HP {c.hp}/{c.hp_max}</span>
          <span>AC {c.ac}</span>
          <span>{formatMoney(c.gold_cp)}</span>
        </div>
        <div className="row gap small">
          {c.source === "ddb" && <span className="badge">D&amp;D Beyond</span>}
          {c.game_id ? <span className="badge blue">In a game</span> : <span className="badge green">Available</span>}
          {c.issues?.length > 0 && <span className="badge red">{c.issues.length} issue{c.issues.length > 1 ? "s" : ""}</span>}
          {onLevelUp && <LevelUpBadge character={c} onClick={onLevelUp} />}
        </div>
      </div>
      {onDelete && (
        <button className="icon-btn danger" title="Delete character" onClick={onDelete}>
          🗑
        </button>
      )}
    </div>
  );
}
