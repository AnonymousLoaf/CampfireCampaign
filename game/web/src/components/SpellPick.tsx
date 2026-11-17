import { useState } from "react";
import type { Spell } from "../api/types";
import { RulesText, useHoverPop } from "./RulesText";

export function SpellBadges({ s }: { s: Spell }) {
  return (
    <>
      {s.concentration && <span className="badge tiny" title="Concentration">C</span>}
      {s.ritual && <span className="badge tiny" title="Ritual">R</span>}
      {s.area && (
        <span className="badge tiny" title="Area of effect">
          {s.area.size_ft} ft {s.area.shape}
        </span>
      )}
    </>
  );
}

/** One line of spell facts: level, school, casting time, range, concentration, ritual. */
export function SpellFacts({ s }: { s: Spell }) {
  return (
    <div className="muted small">
      {s.level === 0 ? "Cantrip" : `Level ${s.level}`} · {s.school}
      {s.casting_time ? ` · ${s.casting_time}` : ""}
      {s.range_ft ? ` · ${s.range_ft} ft` : ""}
      {s.concentration ? " · concentration" : ""}
      {s.ritual ? " · ritual" : ""}
    </div>
  );
}

/** The full write-up of a spell, with rules keywords explained on hover. */
export function SpellDetails({ s }: { s: Spell }) {
  return (
    <div className="spell-details">
      <div className="rules-pop-title">
        {s.name} <span className={`kind kind-${s.kind}`}>{s.kind}</span>
      </div>
      <SpellFacts s={s} />
      <div className="pre">
        <RulesText text={s.description} />
      </div>
    </div>
  );
}

/** A grid of spells to choose from: each card previews the spell; hover or "More" shows all of it. */
export function SpellPicker({ list, chosen, max, onToggle }: { list: Spell[]; chosen: string[]; max: number; onToggle: (i: string) => void }) {
  return (
    <div className="spell-pick-grid">
      {list.map((s) => (
        <SpellPickCard
          key={s.index}
          s={s}
          picked={chosen.includes(s.index)}
          disabled={!chosen.includes(s.index) && chosen.length >= max}
          onToggle={() => onToggle(s.index)}
        />
      ))}
    </div>
  );
}

function SpellPickCard({ s, picked, disabled, onToggle }: { s: Spell; picked: boolean; disabled: boolean; onToggle: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const pop = useHoverPop<HTMLDivElement>({ openDelay: 450, placement: "side" });
  const act = () => {
    if (!disabled) onToggle();
  };
  return (
    <>
      <div
        {...pop.anchorProps}
        role="button"
        tabIndex={0}
        aria-pressed={picked}
        aria-disabled={disabled}
        className={`spell-card pick ${picked ? "selected" : ""} ${disabled ? "disabled" : ""}`}
        onClick={act}
        onKeyDown={(e) => {
          if (e.target !== e.currentTarget) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            act();
          }
        }}
      >
        <div className="spell-head">
          <strong>{s.name}</strong>
          <span className={`kind kind-${s.kind}`}>{s.kind}</span>
        </div>
        <div className="muted small">
          {s.level === 0 ? "cantrip" : `level ${s.level}`} · {s.school}
          {s.range_ft ? ` · ${s.range_ft} ft` : ""}
          {s.combat ? " · combat" : ""} <SpellBadges s={s} />
        </div>
        <div className={`small ${expanded ? "pre" : "clamp3"}`}>{expanded ? <RulesText text={s.description} /> : s.description}</div>
        <button
          type="button"
          className="link-btn small"
          onClick={(e) => {
            e.stopPropagation();
            pop.setOpen(false);
            setExpanded(!expanded);
          }}
        >
          {expanded ? "Less ▴" : "More ▾"}
        </button>
      </div>
      {!expanded && pop.render(<SpellDetails s={s} />, "wide")}
    </>
  );
}
