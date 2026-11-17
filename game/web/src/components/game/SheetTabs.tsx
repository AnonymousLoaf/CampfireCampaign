import { useLayoutEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { ABILITIES, type CharacterView, type CustomKind, type Item, type Spell } from "../../api/types";
import { formatMoney, signed } from "../../util/format";
import { useGame } from "./gameContext";
import { SpellBadges } from "../SpellPick";
import { RulesetContext, RulesText, Term } from "../RulesText";
import { abilityKey, skillKey } from "../../rules/glossary";
import Portrait, { PortraitEditor } from "../Portrait";
import CustomPicker from "../custom/CustomPicker";
import { KIND_LABEL } from "../custom/MyContentPanel";

type Tab = "sheet" | "inventory" | "spells" | "quests" | "npcs";

export default function SheetTabs({ viewedId, onViewed }: { viewedId: string | null; onViewed: (id: string) => void }) {
  const { view, controls, openLevelUp, run } = useGame();
  const [tab, setTab] = useState<Tab>("sheet");
  const c = viewedId ? view.characters[viewedId] : undefined;
  const editable = !!c && controls.includes(c.id);

  return (
    <div className="sheet-tabs">
      <div className="tabs small-tabs">
        <button className={tab === "sheet" ? "active" : ""} onClick={() => setTab("sheet")}>
          Sheet
        </button>
        <button className={tab === "inventory" ? "active" : ""} onClick={() => setTab("inventory")}>
          Inventory
        </button>
        {c?.spellcasting && (
          <button className={tab === "spells" ? "active" : ""} onClick={() => setTab("spells")}>
            Spells
          </button>
        )}
        <button className={tab === "quests" ? "active" : ""} onClick={() => setTab("quests")}>
          Quests {view.quests.filter((q) => q.status === "active").length > 0 && <span className="count">{view.quests.filter((q) => q.status === "active").length}</span>}
        </button>
        <button className={tab === "npcs" ? "active" : ""} onClick={() => setTab("npcs")}>
          NPCs
        </button>
      </div>
      {(tab === "sheet" || tab === "inventory" || tab === "spells") && (
        <div className="viewing-row">
          <select value={viewedId ?? ""} onChange={(e) => onViewed(e.target.value)}>
            {Object.values(view.characters).map((ch) => (
              <option key={ch.id} value={ch.id}>
                {ch.name}
                {ch.id === view.me.character_id ? " (you)" : controls.includes(ch.id) ? " (you control)" : ""}
              </option>
            ))}
          </select>
          {!editable && c && <span className="muted small">view only</span>}
        </div>
      )}
      <div className="sheet-body">
        {tab === "sheet" && c && (
          <RulesetContext.Provider value={c.ruleset}>
          <CharacterSheet
            c={c}
            onLevelUp={editable && openLevelUp ? () => openLevelUp(c.id) : undefined}
            manage={c.owner_id === view.me.user_id ? run : undefined}
          />
          </RulesetContext.Provider>
        )}
        <RulesetContext.Provider value={c?.ruleset}>
          {tab === "inventory" && c && <Inventory c={c} editable={editable} />}
          {tab === "spells" && c?.spellcasting && <Spells c={c} editable={editable} />}
        </RulesetContext.Provider>
        {tab === "quests" && (
          <div className="stack-tight">
            {view.quests.length === 0 && <div className="muted small">No quests yet.</div>}
            {view.quests.map((q, i) => (
              <div key={i} className={`quest ${q.status}`}>
                <div>
                  <strong>{q.title}</strong> <span className={`badge ${q.status === "done" ? "green" : q.status === "failed" ? "red" : "gold"}`}>{q.status}</span>
                </div>
                {q.notes && <div className="small">{q.notes}</div>}
              </div>
            ))}
          </div>
        )}
        {tab === "npcs" && (
          <div className="stack-tight">
            {view.npcs.length === 0 && <div className="muted small">You haven't met anyone notable yet.</div>}
            {view.npcs.map((n, i) => (
              <div key={i} className={`npc ${n.portrait_url ? "with-face" : ""}`}>
                {n.portrait_url && <Portrait c={{ name: n.name, class: "", color: "#5a7d9a", portrait_url: n.portrait_url }} size="big" zoomable />}
                <div className="npc-text">
                  <div>
                    <strong>{n.name}</strong> <span className="muted small">{n.role}</span> {n.attitude && <span className="badge">{n.attitude}</span>}
                  </div>
                  {n.notes && <div className="small">{n.notes}</div>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** Custom entries (homebrew / own books) of the given kinds, with a "custom" tag and, for the owner, a detach button. */
function CustomEntries({ c, kinds, manage }: { c: CharacterView; kinds: CustomKind[]; manage?: (fn: () => Promise<unknown>) => Promise<boolean> }) {
  const list = (c.custom ?? []).filter((x) => kinds.includes(x.kind));
  return (
    <>
      {list.map((x) => (
        <details key={x.entry_id} className="feature custom">
          <summary>
            {x.name}{" "}
            {x.source === "dm" ? <span className="badge tiny gold" title="Granted by the DM in play">from the DM</span> : <span className="badge tiny custom-tag">custom</span>}
            {x.kind !== "feat" && x.kind !== "feature" && <span className="muted small"> · {KIND_LABEL[x.kind] ?? x.kind}</span>}
            {x.level !== null && x.level !== undefined && x.kind === "spell" && <span className="muted small"> · {x.level === 0 ? "cantrip" : `L${x.level}`}</span>}
            {manage && x.source !== "dm" && (
              <button
                className="chip-x"
                title="Detach from this character"
                onClick={(e) => {
                  e.preventDefault();
                  void manage(() => api.detachCustom(c.id, x.entry_id));
                }}
              >
                ×
              </button>
            )}
          </summary>
          <div className="small pre"><RulesText text={x.description} /></div>
        </details>
      ))}
    </>
  );
}

export function CharacterSheet({
  c,
  onLevelUp,
  manage,
}: {
  c: CharacterView;
  onLevelUp?: () => void;
  /** Present when I own this character: portrait upload and custom content. */
  manage?: (fn: () => Promise<unknown>) => Promise<boolean>;
}) {
  const custom = c.custom ?? [];
  const has = (...k: CustomKind[]) => custom.some((x) => k.includes(x.kind));
  return (
    <div className="char-sheet">
      <div className="sheet-header">
        {manage ? (
          <PortraitEditor
            c={c}
            size="big"
            upload={(f) => manage(() => api.uploadPortrait(c.id, f))}
            remove={() => manage(() => api.removePortrait(c.id))}
            generate={(notes) => manage(() => api.generatePortrait(c.id, notes))}
          />
        ) : (
          <Portrait c={c} size="big" zoomable />
        )}
        <div className="sheet-header-name">
          <div className="sheet-name">{c.name}</div>
          {manage && <CustomPicker c={c} run={manage} />}
        </div>
      </div>
      {c.pending_level_up && (
        <div className="levelup-banner">
          <span>✦ Level {c.pending_level_up.to_level} is ready!</span>
          {onLevelUp ? (
            <button className="btn primary small" onClick={onLevelUp}>
              Level up
            </button>
          ) : (
            <span className="muted small">Its player can level up.</span>
          )}
        </div>
      )}
      <div className="muted small">
        Level {c.level} {c.race}
        {c.subrace ? ` (${c.subrace})` : ""} {c.class}
        {c.subclass ? ` — ${c.subclass}` : ""} · {c.background} · {c.alignment}
        {c.ruleset && <span className={`ruleset-badge r${c.ruleset}`}>{c.ruleset}</span>}
      </div>
      {!!c.exhaustion && c.exhaustion > 0 && (
        <div className="exhaustion-line small" title="2024 rules: each level of exhaustion is −2 to every d20 test; level 6 is death.">
          <span className="exh-pips">
            {Array.from({ length: 6 }).map((_, i) => (
              <span key={i} className={`pip ${i < (c.exhaustion ?? 0) ? "full" : ""}`} />
            ))}
          </span>
          Exhaustion {c.exhaustion} · −{2 * (c.exhaustion ?? 0)} to d20 tests
        </div>
      )}
      <div className="sheet-stats">
        <Stat label="AC" value={c.ac} />
        <Stat label="HP" value={`${c.hp}/${c.hp_max}`} />
        <Stat label="Speed" value={`${c.speed}`} />
        <Stat label="Init" value={signed(c.initiative)} />
        <Stat label="Prof" value={signed(c.prof_bonus)} />
        <Stat label="Passive" value={c.passive_perception} />
      </div>
      <div className="xp-line small">
        XP {c.xp.toLocaleString()}
        {c.xp_next ? ` / ${c.xp_next.toLocaleString()}` : " · max level"}
        <div className="xpbar">
          <div style={{ width: `${c.xp_next ? Math.min(100, (c.xp / Math.max(1, c.xp_next)) * 100) : 100}%` }} />
        </div>
      </div>
      <div className="ability-grid">
        {ABILITIES.map((k) => (
          <div key={k} className={`ability-cell ${c.save_profs.includes(k) ? "prof" : ""}`} title={`Save ${signed(c.saves[k])}`}>
            <div className="ab-name"><Term k={abilityKey(k)}>{k}</Term></div>
            <div className="ab-score">{c.abilities[k]}</div>
            <div className="ab-mod">{signed(c.mods[k])}</div>
            <div className="ab-save small">save {signed(c.saves[k])}</div>
          </div>
        ))}
      </div>
      <h4>Skills</h4>
      <div className="skill-list">
        {Object.entries(c.skills).map(([name, v]) => (
          <div key={name} className={`skill ${c.skill_profs.includes(name) ? "prof" : ""}`}>
            <span>
              {c.skill_profs.includes(name) ? "●" : "○"} <Term k={skillKey(name)}>{name}</Term>
            </span>
            <span>{signed(v)}</span>
          </div>
        ))}
      </div>
      <h4>Attacks</h4>
      {c.attacks.length === 0 && <div className="muted small">No attacks — equip a weapon.</div>}
      {c.attacks.map((a) => (
        <div key={a.id} className="attack-row small">
          <strong>
            {a.name}
            {a.mastery && (
              <span className="badge tiny mastery" title={masteryText(c, a.mastery)}>
                {a.mastery}
              </span>
            )}
          </strong>
          <span>
            {signed(a.to_hit)} to hit · {a.damage} {a.damage_type} · {a.range_ft}
            {a.long_range_ft ? `/${a.long_range_ft}` : ""} ft
          </span>
        </div>
      ))}
      {c.masteries && c.masteries.length > 0 && (
        <>
          <h4>Weapon masteries</h4>
          {c.masteries.map((m) => (
            <details key={m.weapon_key} className="feature">
              <summary>
                {m.name} <span className="badge tiny mastery">{m.mastery}</span>
              </summary>
              <div className="small"><RulesText text={m.description || MASTERY_TEXT[m.mastery] || ""} /></div>
            </details>
          ))}
        </>
      )}
      {((c.feats && c.feats.length > 0) || has("feat")) && (
        <>
          <h4>Feats</h4>
          {(c.feats ?? []).map((f) => (
            <details key={f.name} className="feature">
              <summary>{f.name}</summary>
              <div className="small pre"><RulesText text={f.description} /></div>
            </details>
          ))}
          <CustomEntries c={c} kinds={["feat"]} manage={manage} />
        </>
      )}
      {has("spell") && (
        <>
          <h4>Custom spells</h4>
          <CustomEntries c={c} kinds={["spell"]} manage={manage} />
        </>
      )}
      {c.actions && c.actions.length > 0 && (
        <>
          <h4>Combat actions</h4>
          {c.actions.map((a) => (
            <details key={a.id} className="feature">
              <summary>
                {a.name} <span className="badge tiny">{a.kind}</span>
                {a.uses && (
                  <span className="muted small">
                    {" "}
                    · {a.uses.max - a.uses.used}/{a.uses.max}
                    {a.uses.per ? ` per ${a.uses.per}` : ""}
                  </span>
                )}
              </summary>
              <div className="small pre"><RulesText text={a.description} /></div>
            </details>
          ))}
        </>
      )}
      <h4>Features</h4>
      {c.features.map((f) => (
        <details key={f.name} className="feature">
          <summary>
            {f.name}
            {f.uses && (
              <span className="muted small">
                {" "}
                · {f.uses.max - f.uses.used}/{f.uses.max} per {f.uses.per} rest
              </span>
            )}
          </summary>
          <div className="small pre"><RulesText text={f.description} /></div>
        </details>
      ))}
      {(c.race_traits ?? []).length > 0 && (
        <>
          <h4>
            {c.race} traits{" "}
            <span className="muted small">{c.race_source === "homebrew" ? "homebrew" : "Campfire Campaign"}</span>
          </h4>
          {(c.race_traits ?? []).map((t, i) => (
            <details key={`${i}-${t.name}`} className="feature">
              <summary>{t.name}</summary>
              <div className="small pre"><RulesText text={t.description} /></div>
            </details>
          ))}
        </>
      )}
      <CustomEntries c={c} kinds={["feature", "background", "species_trait"]} manage={manage} />
      {c.issues.length > 0 && (
        <>
          <h4>Import notes</h4>
          {c.issues.map((i, n) => (
            <div key={n} className="small">
              ⚠ {i.issue}
              {i.fix && i.fix !== "—" ? <> — <span className="muted">{i.fix}</span></> : null}
            </div>
          ))}
        </>
      )}
      {c.backstory && (
        <details className="feature">
          <summary>Backstory</summary>
          <div className="small pre">{c.backstory}</div>
        </details>
      )}
    </div>
  );
}

/** Short descriptions of the 2024 weapon mastery properties (fallback when the server sends none). */
const MASTERY_TEXT: Record<string, string> = {
  Vex: "Hit: you have advantage on your next attack against that target.",
  Topple: "Hit: the target makes a CON save or falls prone.",
  Sap: "Hit: the target has disadvantage on its next attack.",
  Slow: "Hit: the target's speed drops by 10 ft.",
  Push: "Hit: the target is pushed 10 ft away from you.",
  Graze: "Miss: you still deal damage equal to your ability modifier.",
  Cleave: "Hit: make one extra attack against a different adjacent enemy (once per turn).",
  Nick: "Make the extra light-weapon attack as part of the Attack action.",
};

function masteryText(c: CharacterView, mastery: string): string {
  return c.masteries?.find((m) => m.mastery === mastery)?.description || MASTERY_TEXT[mastery] || mastery;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat">
      <div className="stat-val">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function Inventory({ c, editable }: { c: CharacterView; editable: boolean }) {
  const { view, gameId, run } = useGame();
  const [giving, setGiving] = useState<Item | null>(null);
  const charParam = c.id !== view.me.character_id ? c.id : undefined;
  const inCombat = view.phase.type === "combat";
  const others = Object.values(view.characters).filter((x) => x.id !== c.id);
  const weight = c.inventory.reduce((s, i) => s + i.weight * i.qty, 0);

  return (
    <div className="inventory">
      <div className="inv-head">
        <span className="gold">💰 {formatMoney(c.gold_cp)}</span>
        <span className="muted small">Carrying {Math.round(weight * 10) / 10} lb</span>
      </div>
      {c.inventory.length === 0 && <div className="muted small">Empty pack.</div>}
      {c.inventory.map((it) => (
        <div key={it.id} className={`inv-item ${it.equipped ? "equipped" : ""}`}>
          <div className="inv-main">
            <div>
              <strong>{it.name}</strong>
              {it.qty > 1 && <span className="muted"> ×{it.qty}</span>}
              {it.equipped && <span className="badge green small">equipped</span>}
            </div>
            <div className="muted small">
              {it.category}
              {it.damage && ` · ${it.damage}`}
              {it.ac && ` · ${it.ac}`}
              {it.properties.length > 0 && ` · ${it.properties.join(", ")}`}
              {it.value_cp > 0 && ` · ${formatMoney(it.value_cp)}`}
            </div>
            {it.description && <ItemDescription text={it.description} />}
          </div>
          {editable && (
            <div className="inv-actions">
              {it.equippable && !inCombat && (
                <button className="btn tiny" onClick={() => void run(() => api.equip(gameId, it.id, !it.equipped, charParam))}>
                  {it.equipped ? "Unequip" : "Equip"}
                </button>
              )}
              {it.usable && (
                <button className="btn tiny" onClick={() => void run(() => api.useItem(gameId, it.id, undefined, charParam))}>
                  Use
                </button>
              )}
              {!inCombat && others.length > 0 && (
                <button className="btn tiny ghost" onClick={() => setGiving(giving?.id === it.id ? null : it)}>
                  Give
                </button>
              )}
            </div>
          )}
          {giving?.id === it.id && (
            <div className="give-row">
              {others.map((o) => (
                <button
                  key={o.id}
                  className="chip"
                  onClick={() => {
                    void run(() => api.give(gameId, it.id, 1, o.id, charParam));
                    setGiving(null);
                  }}
                >
                  → {o.name}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Spells({ c, editable }: { c: CharacterView; editable: boolean }) {
  const { view, gameId, run } = useGame();
  const sc = c.spellcasting!;
  const [editing, setEditing] = useState(false);
  const [chosen, setChosen] = useState<string[]>([]);
  const canPrepare = editable && !!sc.prepares && (sc.options?.length ?? 0) > 0;
  const busyPhase = view.phase.type === "combat" || view.phase.type === "dm";
  const max = sc.prepared_max ?? sc.options?.length ?? 0;
  const charParam = c.id !== view.me.character_id ? c.id : undefined;

  const startEdit = () => {
    setChosen(sc.spells.map((s) => s.index));
    setEditing(true);
  };

  return (
    <div className="spells">
      <div className="small">
        Spell save DC <strong>{sc.save_dc}</strong> · Spell attack <strong>{signed(sc.attack_bonus)}</strong> · Ability {sc.ability}
      </div>
      {sc.concentrating_on && (
        <div className="conc-line small">
          ◎ Concentrating on <strong>{sc.concentrating_on}</strong>
        </div>
      )}
      <div className="slot-row">
        {Object.entries(sc.slots).map(([lvl, s]) => (
          <div key={lvl} className="slot-group">
            <span className="small">Level {lvl}</span>
            <SlotPips max={s.max} used={s.used} />
          </div>
        ))}
        {sc.pact && (
          <div className="slot-group pact">
            <span className="small">Pact (level {sc.pact.level})</span>
            <SlotPips max={sc.pact.max} used={sc.pact.used} />
            <span className="muted tiny-text">short rest</span>
          </div>
        )}
      </div>
      <h4>Cantrips</h4>
      <div className="spell-list">{sc.cantrips.map((s) => <SpellCard key={s.index} s={s} />)}</div>
      <div className="row-between">
        <h4>
          {sc.prepares ? "Prepared spells" : sc.known ? "Spells known" : "Spells"}
          {sc.prepares && sc.prepared_max ? (
            <span className="muted small">
              {" "}
              ({sc.spells.length}/{sc.prepared_max})
            </span>
          ) : null}
        </h4>
        {canPrepare && !editing && (
          <button className="btn tiny" disabled={busyPhase} title={busyPhase ? "Not during combat" : ""} onClick={startEdit}>
            Prepare spells
          </button>
        )}
      </div>
      {editing ? (
        <div className="prepare-editor">
          <p className="muted small">
            Choose up to {max} spells{sc.spellbook ? " from your spellbook" : ""} (up to level {sc.max_spell_level ?? "?"}). {chosen.length}/{max} chosen.
          </p>
          <div className="prepare-list">
            {(sc.options ?? []).map((s) => {
              const on = chosen.includes(s.index);
              return (
                <label key={s.index} className={`prepare-item ${on ? "on" : ""}`}>
                  <input
                    type="checkbox"
                    checked={on}
                    disabled={!on && chosen.length >= max}
                    onChange={() => setChosen(on ? chosen.filter((x) => x !== s.index) : [...chosen, s.index])}
                  />
                  <span>
                    <strong>{s.name}</strong>{" "}
                    <span className="muted small">
                      L{s.level} · {s.school}
                    </span>{" "}
                    <SpellBadges s={s} />
                  </span>
                </label>
              );
            })}
          </div>
          <div className="row gap">
            <button className="btn ghost small" onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button
              className="btn primary small"
              onClick={() => void run(() => api.prepare(gameId, chosen, charParam)).then((ok) => ok && setEditing(false))}
            >
              Save prepared spells
            </button>
          </div>
        </div>
      ) : (
        <div className="spell-list">{sc.spells.map((s) => <SpellCard key={s.index} s={s} />)}</div>
      )}
      {(c.custom ?? []).some((x) => x.kind === "spell") && !editing && (
        <>
          <h4>Custom spells</h4>
          <CustomEntries c={c} kinds={["spell"]} />
        </>
      )}
      {sc.spellbook && sc.spellbook.length > 0 && !editing && (
        <details className="feature">
          <summary>Spellbook ({sc.spellbook.length})</summary>
          <div className="spell-list">{sc.spellbook.map((s) => <SpellCard key={s.index} s={s} />)}</div>
        </details>
      )}
    </div>
  );
}

function SlotPips({ max, used }: { max: number; used: number }) {
  return (
    <span className="slot-pips">
      {Array.from({ length: max }).map((_, i) => (
        <span key={i} className={`pip ${i < max - used ? "full" : ""}`} />
      ))}
    </span>
  );
}

export function SpellCard({ s }: { s: Spell }) {
  return (
    <details className="spell-card">
      <summary>
        <strong>{s.name}</strong> <span className={`kind kind-${s.kind}`}>{s.kind}</span>{" "}
        <span className="muted small">
          {s.level === 0 ? "cantrip" : `L${s.level}`} · {s.school}
          {s.range_ft ? ` · ${s.range_ft} ft` : ""}
        </span>{" "}
        <SpellBadges s={s} />
      </summary>
      <div className="small">
        {s.casting_time && <div className="muted">Casting time: {s.casting_time}</div>}
        <div className="pre">
          <RulesText text={s.description} />
        </div>
      </div>
    </details>
  );
}

/** An item's description: two lines, with the rest a click away. */
export function ItemDescription({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const [long, setLong] = useState(text.length > 140 || text.includes("\n"));
  const ref = useRef<HTMLDivElement>(null);
  // Offer "More" whenever the two-line preview actually cuts the text off (narrow panels cut short text too).
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && !open) setLong(el.scrollHeight > el.clientHeight + 1);
  }, [text, open]);
  return (
    <div className="small">
      <div ref={ref} className={open ? "pre" : "clamp"}>
        <RulesText text={text} />
      </div>
      {long && (
        <button type="button" className="link-btn small" onClick={() => setOpen(!open)}>
          {open ? "Less ▴" : "More ▾"}
        </button>
      )}
    </div>
  );
}
