import type { CharacterView, GameView } from "../../api/types";
import { initials } from "../../util/format";
import { LevelUpBadge } from "../LevelUpModal";

/** "until Fri 18:00", "until they're back" — or null when the member isn't away. */
export function awayLabel(until: string | null | undefined): string | null {
  if (!until) return null;
  const d = new Date(until);
  if (Number.isNaN(d.getTime())) return "away";
  if (d.getTime() < Date.now()) return null;
  if (d.getFullYear() > new Date().getFullYear() + 5) return "away until they're back";
  return `away until ${d.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`;
}

export function HpBar({ hp, max, temp = 0 }: { hp: number; max: number; temp?: number }) {
  const frac = max > 0 ? Math.max(0, Math.min(1, hp / max)) : 0;
  const cls = frac > 0.5 ? "good" : frac > 0.25 ? "warn" : "bad";
  return (
    <div className="hpbar" title={`${hp}/${max} HP${temp ? ` (+${temp} temp)` : ""}`}>
      <div className={`hpbar-fill ${cls}`} style={{ width: `${frac * 100}%` }} />
      <span className="hpbar-text">
        {hp}/{max}
        {temp ? ` +${temp}` : ""}
      </span>
    </div>
  );
}

export function memberStatus(view: GameView, userId: string): { label: string; cls: string } {
  const m = view.members.find((x) => x.user_id === userId);
  const p = view.phase;
  if (!m) return { label: "", cls: "" };
  if (p.type === "shop") return m.ready ? { label: "Ready", cls: "ok" } : { label: "Shopping", cls: "wait" };
  if (p.waiting_on.includes(userId)) return { label: "Waiting", cls: "wait" };
  if (p.type === "exploration" || p.type === "roll" || p.type === "combat")
    return m.has_acted ? { label: "Done", cls: "ok" } : { label: "—", cls: "muted" };
  return { label: "", cls: "" };
}

export default function PartyPanel({
  view,
  selectedId,
  onSelect,
  onNudge,
  controls = [],
  onLevelUp,
  readOnly = false,
}: {
  view: GameView;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNudge?: (userId: string) => void;
  controls?: string[];
  onLevelUp?: (characterId: string) => void;
  /** TV view: show level-up as a passive tag instead of a button. */
  readOnly?: boolean;
}) {
  const chars: { c: CharacterView; userId: string; name: string }[] = [];
  for (const m of view.members) {
    if (m.character_id && view.characters[m.character_id]) chars.push({ c: view.characters[m.character_id], userId: m.user_id, name: m.display_name });
  }
  // Characters not tied to a member (e.g. AI companions) — show them too.
  for (const c of Object.values(view.characters)) {
    if (!chars.some((x) => x.c.id === c.id)) chars.push({ c, userId: c.owner_id, name: "" });
  }

  return (
    <div className="party-panel">
      <h3 className="panel-title">Party</h3>
      {chars.map(({ c, userId, name }) => {
        const st = memberStatus(view, userId);
        const isMe = c.id === view.me.character_id;
        const away = awayLabel(view.members.find((m) => m.user_id === userId)?.away_until);
        return (
          <div key={c.id} className={`party-card ${selectedId === c.id ? "selected" : ""} ${c.down ? "down" : ""} ${c.dead ? "dead" : ""}`} onClick={() => onSelect(c.id)}>
            <div className="party-card-top">
              <span className="char-avatar small" style={{ background: c.color }}>
                {initials(c.name)}
              </span>
              <div className="party-card-name">
                <div>
                  <strong>{c.name}</strong> {isMe && <span className="muted small">(you)</span>}
                </div>
                <div className="muted small">
                  L{c.level} {c.class}
                  {name && ` · ${name}`}
                </div>
              </div>
              <div className="party-card-ac" title="Armor Class">
                <span>{c.ac}</span>
              </div>
            </div>
            <HpBar hp={c.hp} max={c.hp_max} temp={c.temp_hp} />
            <div className="party-card-foot">
              <div className="cond-list">
                {c.dead && <span className="cond bad">Dead</span>}
                {c.down && !c.dead && (
                  <span className="cond bad">
                    Down · saves {c.death_saves.success}✓ {c.death_saves.fail}✗
                  </span>
                )}
                {c.conditions.map((x) => (
                  <span key={x} className="cond">
                    {x}
                  </span>
                ))}
                {away && (
                  <span className="cond away" title="The AI plays this character cautiously while they're away">
                    ✈ {away}
                  </span>
                )}
                {!!c.exhaustion && c.exhaustion > 0 && <span className="cond bad">Exhaustion {c.exhaustion}</span>}
                {c.inspiration && <span className="cond gold">Inspired</span>}
                {c.spellcasting?.concentrating_on && <span className="cond conc" title="Concentrating">◎ {c.spellcasting.concentrating_on}</span>}
                {c.pending_level_up &&
                  (onLevelUp && controls.includes(c.id) && !readOnly ? (
                    <LevelUpBadge character={c} onClick={() => onLevelUp(c.id)} />
                  ) : (
                    <span className="cond gold">✦ Level {c.pending_level_up.to_level} ready</span>
                  ))}
              </div>
              {st.label && <span className={`status ${st.cls}`}>{st.label}</span>}
              {onNudge && st.cls === "wait" && userId !== view.me.user_id && (
                <button
                  className="link small"
                  onClick={(e) => {
                    e.stopPropagation();
                    onNudge(userId);
                  }}
                  title="Send a reminder"
                >
                  nudge
                </button>
              )}
            </div>
          </div>
        );
      })}
      {view.members.some((m) => m.role === "spectator") && (
        <div className="spectator-list muted small">
          👁 Watching: {view.members.filter((m) => m.role === "spectator").map((m) => m.display_name).join(", ")}
        </div>
      )}
    </div>
  );
}
