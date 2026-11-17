import { api } from "../../api/client";
import type { CharacterView } from "../../api/types";
import { formatMoney } from "../../util/format";
import { LevelUpBadge } from "../LevelUpModal";
import Portrait, { PortraitEditor } from "../Portrait";
import CustomPicker from "../custom/CustomPicker";

export default function CharacterCard({
  c,
  onDelete,
  onLeaveGame,
  onLevelUp,
  onChanged,
}: {
  c: CharacterView;
  onDelete?: () => void;
  /** The character is in someone else's game: take it out (the character keeps its progress). */
  onLeaveGame?: () => void;
  onLevelUp?: () => void;
  /** When set, the card offers portrait upload/remove and custom content (my own characters in the lobby). */
  onChanged?: () => void;
}) {
  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      return true;
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      onChanged?.();
    }
  };
  return (
    <div className="char-card">
      {onChanged ? (
        <PortraitEditor
          c={c}
          size=""
          upload={async (f) => {
            await api.uploadPortrait(c.id, f);
            onChanged();
          }}
          remove={async () => {
            await api.removePortrait(c.id);
            onChanged();
          }}
        />
      ) : (
        <Portrait c={c} />
      )}
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
          {!onChanged && (c.custom?.length ?? 0) > 0 && <span className="badge">{c.custom!.length} custom</span>}
        </div>
        {onChanged && <CustomPicker c={c} run={run} showAttached />}
      </div>
      {(onDelete || onLeaveGame) && (
        <div className="char-card-actions">
          {onDelete && (
            <button className="icon-btn danger" title="Delete character" onClick={onDelete}>
              🗑
            </button>
          )}
          {onLeaveGame && (
            <button className="btn ghost small" title={`Take ${c.name} out of their campaign`} onClick={onLeaveGame}>
              Leave game
            </button>
          )}
        </div>
      )}
    </div>
  );
}
