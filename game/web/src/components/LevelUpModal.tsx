import { useState } from "react";
import { ABILITIES, type Ability, type CharacterView, type LevelUpBody, type Spell } from "../api/types";
import Modal from "./Modal";
import ErrorText from "./ErrorText";
import { signed } from "../util/format";

/**
 * Level-up wizard for one character's `pending_level_up` offer.
 * `submit` posts the choices (in-game or from the lobby) and resolves to {hp_gained, level}.
 */
export default function LevelUpModal({
  character,
  submit,
  onClose,
}: {
  character: CharacterView;
  submit: (body: LevelUpBody) => Promise<{ hp_gained?: number; level?: number }>;
  onClose: () => void;
}) {
  // Keep the offer we opened with: after confirming, the refreshed view no longer has it, but we still show the result.
  const [openedOffer] = useState(character.pending_level_up);
  const offer = character.pending_level_up ?? openedOffer;
  const [hpMethod, setHpMethod] = useState<"average" | "roll">("average");
  const [asiMode, setAsiMode] = useState<"two" | "split">("two");
  const [asiOne, setAsiOne] = useState<Ability | "">("");
  const [asiSplit, setAsiSplit] = useState<Ability[]>([]);
  const [subclass, setSubclass] = useState("");
  const [style, setStyle] = useState("");
  const [expertise, setExpertise] = useState<string[]>([]);
  const [cantrips, setCantrips] = useState<string[]>([]);
  const [spells, setSpells] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<{ hp_gained?: number; level?: number } | null>(null);

  if (!offer) {
    return (
      <Modal title="Level up" onClose={onClose}>
        <p className="muted">{character.name} has no level-up waiting.</p>
      </Modal>
    );
  }

  const capped = (k: Ability, plus: number) => character.abilities[k] + plus > 20;
  const asi: Partial<Record<Ability, number>> | null = !offer.asi
    ? null
    : asiMode === "two"
      ? asiOne
        ? { [asiOne]: 2 }
        : null
      : asiSplit.length === 2
        ? { [asiSplit[0]]: 1, [asiSplit[1]]: 1 }
        : null;

  const problems: string[] = [];
  if (offer.asi && !asi) problems.push(asiMode === "two" ? "Pick an ability to raise by 2." : "Pick two abilities to raise by 1.");
  if (offer.subclass_options?.length && !subclass) problems.push("Choose a subclass.");
  if (offer.fighting_style_options?.length && !style) problems.push("Choose a fighting style.");
  if (offer.expertise && expertise.length !== offer.expertise) problems.push(`Pick ${offer.expertise} skills for Expertise.`);
  if (offer.cantrips && cantrips.length !== Math.min(offer.cantrips, offer.cantrip_options.length))
    problems.push(`Pick ${offer.cantrips} new cantrip${offer.cantrips > 1 ? "s" : ""}.`);
  if (offer.spells && spells.length !== Math.min(offer.spells, offer.spell_options.length))
    problems.push(`Pick ${offer.spells} new spell${offer.spells > 1 ? "s" : ""}.`);

  const toggle = (list: string[], set: (v: string[]) => void, v: string, max: number) => {
    if (list.includes(v)) set(list.filter((x) => x !== v));
    else if (list.length < max) set([...list, v]);
  };

  const confirm = async () => {
    setBusy(true);
    setErr(null);
    try {
      const body: LevelUpBody = { hp_method: hpMethod, asi };
      if (subclass) body.subclass = subclass;
      if (style) body.fighting_style = style;
      if (expertise.length) body.expertise = expertise;
      if (cantrips.length) body.cantrips = cantrips;
      if (spells.length) body.spells = spells;
      const r = await submit(body);
      setResult(r ?? {});
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <Modal title={`${character.name} reached level ${result.level ?? offer.to_level}!`} onClose={onClose} footer={<button className="btn primary" onClick={onClose}>Onward</button>}>
        <div className="levelup-done">
          <div className="big-num">✦ Level {result.level ?? offer.to_level}</div>
          {typeof result.hp_gained === "number" && <p>+{result.hp_gained} maximum hit points.</p>}
          {offer.features.length > 0 && (
            <ul className="small">
              {offer.features.map((f) => (
                <li key={f.name}>
                  <strong>{f.name}</strong>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      title={`Level up: ${character.name} → level ${offer.to_level}`}
      onClose={onClose}
      wide
      footer={
        <>
          <span className="muted small grow">{problems[0] ?? ""}</span>
          <button className="btn ghost" onClick={onClose}>
            Later
          </button>
          <button className="btn primary" disabled={busy || problems.length > 0} onClick={() => void confirm()}>
            {busy ? "Levelling…" : `Become level ${offer.to_level}`}
          </button>
        </>
      }
    >
      <div className="levelup">
        <section>
          <h3>Hit points</h3>
          <div className="seg">
            <button className={hpMethod === "average" ? "active" : ""} onClick={() => setHpMethod("average")}>
              Take the average (+{offer.hp_average + offer.con_mod})
            </button>
            <button className={hpMethod === "roll" ? "active" : ""} onClick={() => setHpMethod("roll")}>
              Roll 1d{offer.hit_die} {signed(offer.con_mod)}
            </button>
          </div>
          <p className="muted small">Rolling can do better or worse than the average; the server rolls and you keep the result (minimum 1).</p>
        </section>

        {offer.features.length > 0 && (
          <section>
            <h3>New at level {offer.to_level}</h3>
            {offer.features.map((f) => (
              <div key={f.name} className="feature">
                <strong>{f.name}.</strong> <span className="small">{f.description}</span>
              </div>
            ))}
          </section>
        )}

        {offer.asi && (
          <section>
            <h3>Ability Score Improvement</h3>
            <div className="seg">
              <button className={asiMode === "two" ? "active" : ""} onClick={() => setAsiMode("two")}>
                +2 to one ability
              </button>
              <button className={asiMode === "split" ? "active" : ""} onClick={() => setAsiMode("split")}>
                +1 to two abilities
              </button>
            </div>
            <div className="chip-grid">
              {ABILITIES.map((k) => {
                const picked = asiMode === "two" ? asiOne === k : asiSplit.includes(k);
                const over = capped(k, asiMode === "two" ? 2 : 1);
                return (
                  <button
                    key={k}
                    className={`chip ${picked ? "selected" : ""}`}
                    disabled={over || (asiMode === "split" && !picked && asiSplit.length >= 2)}
                    title={over ? "Can't go above 20" : ""}
                    onClick={() => {
                      if (asiMode === "two") setAsiOne(picked ? "" : k);
                      else setAsiSplit(picked ? asiSplit.filter((x) => x !== k) : [...asiSplit, k]);
                    }}
                  >
                    {k} {character.abilities[k]}
                    {picked ? ` → ${character.abilities[k] + (asiMode === "two" ? 2 : 1)}` : ""}
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {offer.subclass_options && offer.subclass_options.length > 0 && (
          <section>
            <h3>Subclass</h3>
            <div className="choice-grid">
              {offer.subclass_options.map((s) => {
                const id = s.index ?? s.name;
                return (
                  <button key={id} className={`choice ${subclass === id ? "selected" : ""}`} onClick={() => setSubclass(id)}>
                    <strong>{s.name}</strong>
                    <span className="small">{s.description}</span>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {offer.fighting_style_options && offer.fighting_style_options.length > 0 && (
          <section>
            <h3>Fighting style</h3>
            <div className="choice-grid">
              {offer.fighting_style_options.map((s) => (
                <button key={s.name} className={`choice ${style === s.name ? "selected" : ""}`} onClick={() => setStyle(s.name)}>
                  <strong>{s.name}</strong>
                  <span className="small">{s.description}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {offer.expertise > 0 && (
          <section>
            <h3>
              Expertise <span className="muted small">({expertise.length}/{offer.expertise})</span>
            </h3>
            <div className="chip-grid">
              {offer.expertise_options.map((sk) => {
                const picked = expertise.includes(sk);
                return (
                  <button
                    key={sk}
                    className={`chip ${picked ? "selected" : ""}`}
                    disabled={!picked && expertise.length >= offer.expertise}
                    onClick={() => toggle(expertise, setExpertise, sk, offer.expertise)}
                  >
                    {sk}
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {offer.cantrips > 0 && (
          <section>
            <h3>
              New cantrips <span className="muted small">({cantrips.length}/{offer.cantrips})</span>
            </h3>
            <SpellChoices list={offer.cantrip_options} chosen={cantrips} max={offer.cantrips} onToggle={(i) => toggle(cantrips, setCantrips, i, offer.cantrips)} />
          </section>
        )}

        {offer.spells > 0 && (
          <section>
            <h3>
              New spells <span className="muted small">({spells.length}/{offer.spells}) · up to level {offer.max_spell_level}</span>
            </h3>
            <SpellChoices list={offer.spell_options} chosen={spells} max={offer.spells} onToggle={(i) => toggle(spells, setSpells, i, offer.spells)} />
          </section>
        )}
        <ErrorText error={err} />
      </div>
    </Modal>
  );
}

function SpellChoices({ list, chosen, max, onToggle }: { list: Spell[]; chosen: string[]; max: number; onToggle: (i: string) => void }) {
  if (!list.length) return <p className="muted small">No new options available.</p>;
  return (
    <div className="spell-pick-grid">
      {list.map((s) => {
        const picked = chosen.includes(s.index);
        return (
          <button key={s.index} className={`spell-card pick ${picked ? "selected" : ""}`} disabled={!picked && chosen.length >= max} onClick={() => onToggle(s.index)}>
            <div className="spell-head">
              <strong>{s.name}</strong>
              <span className={`kind kind-${s.kind}`}>{s.kind}</span>
            </div>
            <div className="muted small">
              {s.level === 0 ? "cantrip" : `level ${s.level}`} · {s.school}
              {s.range_ft ? ` · ${s.range_ft} ft` : ""}
              <SpellBadges s={s} />
            </div>
            <div className="small clamp">{s.description}</div>
          </button>
        );
      })}
    </div>
  );
}

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

/** A small "Level up!" button for any character with a pending offer. */
export function LevelUpBadge({ character, onClick }: { character: CharacterView; onClick: () => void }) {
  if (!character.pending_level_up) return null;
  return (
    <button
      className="levelup-badge"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      title={`Level ${character.pending_level_up.to_level} is ready`}
    >
      ✦ Level up!
    </button>
  );
}
