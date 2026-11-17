import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import {
  ABILITIES,
  type Ability,
  type AbilityMap,
  type AbilityRoll,
  type CreatorOptions,
  type Ruleset,
} from "../api/types";
import ErrorText, { useAction } from "../components/ErrorText";
import { abilityMod, formatMoney, signed } from "../util/format";
import { SpellPicker } from "../components/SpellPick";
import { RulesetContext, RulesText, Term } from "../components/RulesText";
import { abilityKey, skillKey } from "../rules/glossary";

const STEPS = ["Race", "Class", "Background", "Abilities", "Skills", "Equipment", "Spells", "Details", "Review"] as const;
type Step = (typeof STEPS)[number];

const COLORS = ["#c0392b", "#d68910", "#b7950b", "#229954", "#17a589", "#2e86c1", "#6c3483", "#a93226", "#7f8c8d", "#ca6f1e"];

const BASE: AbilityMap = { STR: 8, DEX: 8, CON: 8, INT: 8, WIS: 8, CHA: 8 };

/** The class list a Magic Initiate feat uses: the server's `list`, else "Magic Initiate (Cleric)" → "cleric". */
function magicInitiateList(feat: { name?: string | null; list?: string | null } | undefined | null): string | null {
  const featName = feat?.name;
  if (!featName || !/^magic initiate/i.test(featName)) return null;
  if (feat?.list) return feat.list.trim().toLowerCase();
  const m = /\(([^)]+)\)/.exec(featName);
  return (m ? m[1] : "wizard").trim().toLowerCase();
}

export default function CharacterCreator({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [ruleset, setRuleset] = useState<Ruleset>("2014");
  const [opts, setOpts] = useState<CreatorOptions | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [step, setStep] = useState<Step>("Race");

  const [race, setRace] = useState("");
  const [subrace, setSubrace] = useState<string | null>(null);
  const [cls, setCls] = useState("");
  const [background, setBackground] = useState("");
  const [method, setMethod] = useState<"standard" | "pointbuy" | "roll">("standard");
  const [assign, setAssign] = useState<Record<Ability, number | null>>({ STR: null, DEX: null, CON: null, INT: null, WIS: null, CHA: null });
  const [pointBuy, setPointBuy] = useState<AbilityMap>({ ...BASE });
  const [roll, setRoll] = useState<AbilityRoll | null>(null);
  const [rollAssign, setRollAssign] = useState<Record<Ability, number | null>>({ STR: null, DEX: null, CON: null, INT: null, WIS: null, CHA: null });
  const [skills, setSkills] = useState<string[]>([]);
  const [equipment, setEquipment] = useState("");
  const [cantrips, setCantrips] = useState<string[]>([]);
  const [spells, setSpells] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [alignment, setAlignment] = useState("True Neutral");
  const [color, setColor] = useState(COLORS[Math.floor(Math.random() * COLORS.length)]);
  const [backstory, setBackstory] = useState("");
  // M2 choices
  const [ancestry, setAncestry] = useState("");
  const [bonusAbilities, setBonusAbilities] = useState<Ability[]>([]);
  const [fightingStyle, setFightingStyle] = useState("");
  const [expertise, setExpertise] = useState<string[]>([]);
  const [subclass, setSubclass] = useState("");
  // M3 (2024) choices
  const [bgAsiMode, setBgAsiMode] = useState<"21" | "111">("21");
  const [bgPlus2, setBgPlus2] = useState<Ability | "">("");
  const [bgPlus1, setBgPlus1] = useState<Ability | "">("");
  const [masteries, setMasteries] = useState<string[]>([]);
  const [miCantrips, setMiCantrips] = useState<string[]>([]);
  const [miSpell, setMiSpell] = useState("");

  useEffect(() => {
    setOpts(null);
    setLoadErr(null);
    api
      .creatorOptions(ruleset)
      .then((o) => {
        setOpts(o);
        if (o.alignments.length && !o.alignments.includes("True Neutral")) setAlignment(o.alignments[0]);
      })
      .catch((e) => setLoadErr(e instanceof Error ? e.message : String(e)));
  }, [ruleset]);

  const is2024 = ruleset === "2024";

  /** Switching rulesets invalidates every choice made from the other ruleset's data. */
  const switchRuleset = (r: Ruleset) => {
    if (r === ruleset) return;
    setRuleset(r);
    setRace("");
    setSubrace(null);
    setCls("");
    setBackground("");
    setSkills([]);
    setEquipment("");
    setCantrips([]);
    setSpells([]);
    setAncestry("");
    setBonusAbilities([]);
    setFightingStyle("");
    setExpertise([]);
    setSubclass("");
    setBgPlus2("");
    setBgPlus1("");
    setMasteries([]);
    setMiCantrips([]);
    setMiSpell("");
    setStep("Race");
  };

  const raceObj = opts?.races.find((r) => r.index === race) ?? null;
  const subObj = raceObj?.subraces.find((s) => s.index === subrace) ?? null;
  const clsObj = opts?.classes.find((c) => c.index === cls) ?? null;
  const bgObj = opts?.backgrounds.find((b) => b.index === background) ?? null;
  const caster = clsObj?.spellcasting ?? null;
  const hasL1Spells = !!caster && (caster.cantrips_known > 0 || caster.spells_at_l1 > 0);
  const abilityChoices = raceObj?.ability_choices ?? null;
  const ancestries = raceObj?.ancestries ?? null;
  const styles = clsObj?.fighting_styles ?? null;
  const expertiseCount = clsObj?.expertise_at_l1 ?? 0;
  const l1Subclasses = clsObj && clsObj.subclass_level === 1 ? clsObj.subclasses ?? [] : [];
  // 2024
  const bgAbilities = (is2024 ? bgObj?.ability_options : null) ?? [];
  const masteryCount = is2024 ? clsObj?.weapon_mastery ?? 0 : 0;
  const masteryOptions = clsObj?.mastery_options ?? [];
  const miList = is2024 ? magicInitiateList(bgObj?.origin_feat) : null;
  const miClass = miList ? opts?.classes.find((c) => c.index === miList || c.name.toLowerCase() === miList) ?? null : null;
  const miCantripOptions = miClass?.spellcasting?.cantrips ?? [];
  const miSpellOptions = (miClass?.spellcasting?.spells ?? []).filter((s) => s.level === 1);

  const steps = STEPS.filter((s) => s !== "Spells" || hasL1Spells);
  const stepLabel = (s: Step) => (s === "Race" && is2024 ? "Species" : s);

  /** Background ability increases (2024): +2/+1 or +1/+1/+1 among the background's three abilities. */
  const bgAsi: Partial<AbilityMap> = useMemo(() => {
    if (!is2024 || bgAbilities.length === 0) return {};
    if (bgAsiMode === "111") return Object.fromEntries(bgAbilities.map((a) => [a, 1]));
    const out: Partial<AbilityMap> = {};
    if (bgPlus2) out[bgPlus2] = 2;
    if (bgPlus1 && bgPlus1 !== bgPlus2) out[bgPlus1] = 1;
    return out;
  }, [is2024, bgAbilities, bgAsiMode, bgPlus2, bgPlus1]);

  /** Bonus for an ability: racial (2014), Half-Elf free choices, and background increases (2024). */
  const bonusFor = (k: Ability) =>
    (raceObj?.ability_bonuses[k] ?? 0) +
    (subObj?.ability_bonuses[k] ?? 0) +
    (abilityChoices && bonusAbilities.includes(k) ? abilityChoices.amount : 0) +
    (bgAsi[k] ?? 0);

  const baseScores: AbilityMap | null = useMemo(() => {
    if (method === "pointbuy") return pointBuy;
    const a = method === "standard" ? assign : rollAssign;
    if (ABILITIES.some((k) => a[k] === null)) return null;
    return a as AbilityMap;
  }, [method, assign, rollAssign, pointBuy]);

  const finalScores: AbilityMap | null = useMemo(() => {
    if (!baseScores) return null;
    const out = { ...baseScores };
    for (const k of ABILITIES) out[k] += bonusFor(k);
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseScores, raceObj, subObj, bonusAbilities, bgAsi]);

  const pointCost = (v: number) => opts?.point_buy.costs[String(v)] ?? 0;
  const pointsSpent = ABILITIES.reduce((s, k) => s + pointCost(pointBuy[k]), 0);
  const budget = opts?.point_buy.budget ?? 27;

  const bgSkills = bgObj?.skills ?? [];

  const valid = (s: Step): string | null => {
    switch (s) {
      case "Race":
        if (!raceObj) return is2024 ? "Choose a species." : "Choose a race.";
        if (raceObj.subraces.length > 0 && !subObj) return is2024 ? "Choose a lineage." : "Choose a subrace.";
        if (ancestries && ancestries.length && !ancestry) return "Choose a draconic ancestry.";
        if (abilityChoices && bonusAbilities.length !== abilityChoices.count)
          return `Choose ${abilityChoices.count} abilities to raise by ${abilityChoices.amount}.`;
        return null;
      case "Class":
        if (!clsObj) return "Choose a class.";
        if (styles && styles.length && !fightingStyle) return "Choose a fighting style.";
        if (l1Subclasses.length && !subclass) return "Choose a subclass.";
        return null;
      case "Background":
        if (!bgObj) return "Choose a background.";
        if (is2024 && bgAbilities.length) {
          if (bgAsiMode === "21" && (!bgPlus2 || !bgPlus1 || bgPlus2 === bgPlus1))
            return "Pick one ability for +2 and a different one for +1.";
        }
        if (miList) {
          if (miCantrips.length !== Math.min(2, miCantripOptions.length)) return "Pick 2 Magic Initiate cantrips.";
          if (miSpellOptions.length && !miSpell) return "Pick a Magic Initiate level-1 spell.";
        }
        return null;
      case "Abilities":
        if (method === "pointbuy" && pointsSpent > budget) return "You've spent more points than your budget.";
        if (method === "roll" && !roll) return "Roll your ability scores first.";
        return baseScores ? null : "Assign a score to every ability.";
      case "Skills":
        if (!clsObj || skills.length !== clsObj.skill_choices.count) return `Pick ${clsObj?.skill_choices.count ?? 0} skills.`;
        if (expertiseCount && expertise.length !== expertiseCount) return `Pick ${expertiseCount} skills for Expertise.`;
        return null;
      case "Equipment":
        if (!(equipment || (clsObj?.equipment_options.length ?? 0) === 0)) return "Choose your starting equipment.";
        if (masteryCount > 0 && masteries.length !== Math.min(masteryCount, masteryOptions.length))
          return `Pick ${masteryCount} weapon masteries.`;
        return null;
      case "Spells":
        if (!caster) return null;
        if (cantrips.length !== caster.cantrips_known) return `Pick ${caster.cantrips_known} cantrips.`;
        if (caster.spells_at_l1 > 0 && spells.length !== caster.spells_at_l1) return `Pick ${caster.spells_at_l1} level-1 spells.`;
        return null;
      case "Details":
        return name.trim() ? null : "Give your character a name.";
      case "Review":
        return null;
    }
  };

  const idx = steps.indexOf(step);
  const err = valid(step);
  const go = (d: number) => setStep(steps[Math.max(0, Math.min(steps.length - 1, idx + d))]);

  const [doRoll, rolling, rollErr] = useAction(async () => {
    setRoll(await api.rollAbilities());
    setRollAssign({ STR: null, DEX: null, CON: null, INT: null, WIS: null, CHA: null });
  });

  const [create, creating, createErr] = useAction(async () => {
    if (!baseScores) throw new Error("Ability scores are incomplete.");
    await api.createCharacter({
      name: name.trim(),
      race,
      subrace,
      class: cls,
      background,
      ability_method: method,
      roll_id: method === "roll" ? roll?.roll_id ?? null : null,
      abilities: baseScores,
      skills,
      equipment_option: equipment,
      cantrips: caster ? cantrips : [],
      spells: caster ? spells : [],
      alignment,
      backstory,
      color,
      ...(subclass ? { subclass } : {}),
      ...(fightingStyle ? { fighting_style: fightingStyle } : {}),
      ...(expertise.length ? { expertise } : {}),
      ...(abilityChoices && bonusAbilities.length ? { bonus_abilities: bonusAbilities } : {}),
      ...(ancestry ? { ancestry } : {}),
      ...(is2024
        ? {
            ruleset,
            background_asi: bgAsi,
            masteries,
            magic_initiate: miList ? { cantrips: miCantrips, spell: miSpell } : null,
          }
        : {}),
    });
    onDone();
  });

  if (loadErr) {
    return (
      <div className="creator">
        <ErrorText error={loadErr} />
        <div className="row gap">
          {ruleset !== "2014" && (
            <button className="btn" onClick={() => switchRuleset("2014")}>
              Use 2014 rules
            </button>
          )}
          <button className="btn" onClick={onCancel}>
            Back
          </button>
        </div>
      </div>
    );
  }
  if (!opts) {
    return (
      <div className="center-screen">
        <div className="spinner" />
      </div>
    );
  }

  const toggle = (list: string[], set: (v: string[]) => void, v: string, max: number) => {
    if (list.includes(v)) set(list.filter((x) => x !== v));
    else if (list.length < max) set([...list, v]);
  };

  return (
    <RulesetContext.Provider value={ruleset}>
    <div className="creator">
      <header className="topbar">
        <div className="brand-inline">
          <span className="brand-sigil">⚔</span> New character
        </div>
        <button className="btn ghost small" onClick={onCancel}>
          Cancel
        </button>
      </header>

      <nav className="stepper">
        {steps.map((s, i) => (
          <button
            key={s}
            className={`step ${s === step ? "active" : ""} ${i < idx ? "done" : ""}`}
            onClick={() => {
              // allow jumping back, or forward only through valid steps
              if (i <= idx || steps.slice(0, i).every((p) => !valid(p))) setStep(s);
            }}
          >
            <span className="step-num">{i + 1}</span> {stepLabel(s)}
          </button>
        ))}
      </nav>

      <div className="creator-body">
        <div className="creator-main">
          {step === "Race" && (
            <div>
              <div className="ruleset-pick">
                <span className="label">Rules</span>
                <div className="seg">
                  <button className={ruleset === "2014" ? "active" : ""} onClick={() => switchRuleset("2014")}>
                    2014 (SRD 5.1)
                  </button>
                  <button className={ruleset === "2024" ? "active" : ""} onClick={() => switchRuleset("2024")}>
                    2024 (SRD 5.2)
                  </button>
                </div>
                <span className="muted small">
                  {is2024
                    ? "Ability increases come from your background; you pick weapon masteries and get an origin feat."
                    : "Ability increases come from your race."}{" "}
                  A character can only join games that use the same rules.
                </span>
              </div>
              <h2>{is2024 ? "Choose your species" : "Choose your race"}</h2>
              <div className="choice-grid">
                {opts.races.map((r) => (
                  <button
                    key={r.index}
                    className={`choice ${race === r.index ? "selected" : ""}`}
                    onClick={() => {
                      if (race !== r.index) {
                        setBonusAbilities([]);
                        setAncestry("");
                      }
                      setRace(r.index);
                      setSubrace(r.subraces.length === 1 ? r.subraces[0].index : null);
                    }}
                  >
                    <strong>{r.name}</strong>
                    <span className="muted small">
                      {Object.entries(r.ability_bonuses)
                        .map(([k, v]) => `${k} ${signed(v as number)}`)
                        .join(", ") || "—"}{" "}
                      · Speed {r.speed} ft
                    </span>
                    <span className="small">{r.traits.slice(0, 4).join(", ")}</span>
                  </button>
                ))}
              </div>
              {raceObj && raceObj.subraces.length > 0 && (
                <>
                  <h3>{is2024 ? "Lineage" : "Subrace"}</h3>
                  <div className="choice-grid">
                    {raceObj.subraces.map((s) => (
                      <button key={s.index} className={`choice ${subrace === s.index ? "selected" : ""}`} onClick={() => setSubrace(s.index)}>
                        <strong>{s.name}</strong>
                        <span className="muted small">
                          {Object.entries(s.ability_bonuses)
                            .map(([k, v]) => `${k} ${signed(v as number)}`)
                            .join(", ")}
                        </span>
                        <span className="small">{s.traits.join(", ")}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
              {abilityChoices && (
                <>
                  <h3>
                    Raise {abilityChoices.count} abilities by {abilityChoices.amount}{" "}
                    <span className="muted small">({bonusAbilities.length}/{abilityChoices.count})</span>
                  </h3>
                  <div className="chip-grid">
                    {ABILITIES.filter((k) => !abilityChoices.exclude.includes(k)).map((k) => {
                      const picked = bonusAbilities.includes(k);
                      return (
                        <button
                          key={k}
                          className={`chip ${picked ? "selected" : ""}`}
                          disabled={!picked && bonusAbilities.length >= abilityChoices.count}
                          onClick={() => setBonusAbilities(picked ? bonusAbilities.filter((x) => x !== k) : [...bonusAbilities, k])}
                        >
                          {k} +{abilityChoices.amount}
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
              {ancestries && ancestries.length > 0 && (
                <>
                  <h3>Draconic ancestry</h3>
                  <div className="chip-grid">
                    {ancestries.map((a) => (
                      <button key={a.name} className={`chip ${ancestry === a.name ? "selected" : ""}`} onClick={() => setAncestry(a.name)}>
                        {a.name} <span className="muted small">{a.damage_type}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
              {raceObj && (
                <div className="detail-box">
                  <strong>{raceObj.name}</strong> · {raceObj.size} · Languages: {raceObj.languages.join(", ")}
                  <div className="small">
                    Traits: <RulesText text={raceObj.traits.join(", ")} />
                  </div>
                </div>
              )}
            </div>
          )}

          {step === "Class" && (
            <div>
              <h2>Choose your class</h2>
              <div className="choice-grid">
                {opts.classes.map((c) => (
                  <button
                    key={c.index}
                    className={`choice ${cls === c.index ? "selected" : ""}`}
                    onClick={() => {
                      if (cls !== c.index) {
                        setCls(c.index);
                        setSkills([]);
                        setExpertise([]);
                        setFightingStyle("");
                        setSubclass(c.subclass_level === 1 && c.subclasses?.length === 1 ? c.subclasses[0].index ?? c.subclasses[0].name : "");
                        setEquipment(c.equipment_options[0]?.id ?? "");
                        setCantrips([]);
                        setSpells([]);
                      }
                    }}
                  >
                    <strong>{c.name}</strong>
                    <span className="muted small">
                      d{c.hit_die} hit die · Saves {c.saves.join(", ")}
                      {c.spellcasting ? ` · Casts with ${c.spellcasting.ability}` : ""}
                    </span>
                    <span className="small"><RulesText text={c.description} /></span>
                  </button>
                ))}
              </div>
              {clsObj && (
                <div className="detail-box">
                  <div className="small">
                    <strong>Armor:</strong> {clsObj.armor.join(", ") || "none"} · <strong>Weapons:</strong> {clsObj.weapons.join(", ")}
                  </div>
                  <h4>Level 1 features</h4>
                  {clsObj.features.map((f) => (
                    <div key={f.name} className="feature">
                      <strong>{f.name}.</strong> <span className="small"><RulesText text={f.description} /></span>
                    </div>
                  ))}
                  {clsObj.subclasses && clsObj.subclasses.length > 0 && clsObj.subclass_level !== 1 && (
                    <div className="small muted">
                      Subclass at level {clsObj.subclass_level ?? 3}: {clsObj.subclasses.map((s) => s.name).join(", ")}
                    </div>
                  )}
                </div>
              )}
              {clsObj && l1Subclasses.length > 0 && (
                <>
                  <h3>Subclass</h3>
                  <div className="choice-grid">
                    {l1Subclasses.map((s) => {
                      const id = s.index ?? s.name;
                      return (
                        <button key={id} className={`choice ${subclass === id ? "selected" : ""}`} onClick={() => setSubclass(id)}>
                          <strong>{s.name}</strong>
                          <span className="small"><RulesText text={s.description} /></span>
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
              {clsObj && styles && styles.length > 0 && (
                <>
                  <h3>Fighting style</h3>
                  <div className="choice-grid">
                    {styles.map((s) => (
                      <button key={s.name} className={`choice ${fightingStyle === s.name ? "selected" : ""}`} onClick={() => setFightingStyle(s.name)}>
                        <strong>{s.name}</strong>
                        <span className="small"><RulesText text={s.description} /></span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {step === "Background" && (
            <div>
              <h2>Choose a background</h2>
              <div className="choice-grid">
                {opts.backgrounds.map((b) => (
                  <button key={b.index} className={`choice ${background === b.index ? "selected" : ""}`} onClick={() => {
                    if (background !== b.index) {
                      setBgPlus2("");
                      setBgPlus1("");
                      setMiCantrips([]);
                      setMiSpell("");
                    }
                    setBackground(b.index);
                    setSkills((prev) => prev.filter((s) => !b.skills.includes(s)));
                  }}>
                    <strong>{b.name}</strong>
                    <span className="muted small">
                      Skills: {b.skills.join(", ")} · {formatMoney(b.gold_cp)}
                      {is2024 && b.ability_options?.length ? ` · ${b.ability_options.join(", ")}` : ""}
                    </span>
                    {is2024 && b.origin_feat && <span className="small">Origin feat: {b.origin_feat.name}</span>}
                    <span className="small"><RulesText text={b.description} /></span>
                  </button>
                ))}
              </div>
              {is2024 && bgObj && bgAbilities.length > 0 && (
                <>
                  <h3>Ability increases</h3>
                  <div className="seg">
                    <button className={bgAsiMode === "21" ? "active" : ""} onClick={() => setBgAsiMode("21")}>
                      +2 and +1
                    </button>
                    <button className={bgAsiMode === "111" ? "active" : ""} onClick={() => setBgAsiMode("111")}>
                      +1 to all three
                    </button>
                  </div>
                  {bgAsiMode === "21" ? (
                    <div className="stack-tight">
                      <div className="row gap wrap">
                        <span className="small muted asi-label">+2</span>
                        {bgAbilities.map((a) => (
                          <button key={a} className={`chip ${bgPlus2 === a ? "selected" : ""}`} onClick={() => setBgPlus2(a)}>
                            {a}
                          </button>
                        ))}
                      </div>
                      <div className="row gap wrap">
                        <span className="small muted asi-label">+1</span>
                        {bgAbilities.map((a) => (
                          <button key={a} className={`chip ${bgPlus1 === a ? "selected" : ""}`} disabled={bgPlus2 === a} onClick={() => setBgPlus1(a)}>
                            {a}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="small">+1 to {bgAbilities.join(", ")}.</p>
                  )}
                </>
              )}
              {is2024 && bgObj?.origin_feat && (
                <div className="detail-box">
                  <strong>Origin feat: {bgObj.origin_feat.name}.</strong> <span className="small"><RulesText text={bgObj.origin_feat.description} /></span>
                  {bgObj.tool && <div className="small muted">Tool proficiency: {bgObj.tool}</div>}
                </div>
              )}
              {miList && (
                <>
                  <h3>
                    Magic Initiate ({miClass?.name ?? miList}) — cantrips{" "}
                    <span className="muted small">({miCantrips.length}/2)</span>
                  </h3>
                  {miCantripOptions.length ? (
                    <SpellPicker list={miCantripOptions} chosen={miCantrips} max={2} onToggle={(i) => toggle(miCantrips, setMiCantrips, i, 2)} />
                  ) : (
                    <p className="muted small">No cantrip list available for this feat.</p>
                  )}
                  <h3>
                    Magic Initiate — level-1 spell <span className="muted small">({miSpell ? 1 : 0}/1, cast once per long rest for free)</span>
                  </h3>
                  {miSpellOptions.length ? (
                    <SpellPicker list={miSpellOptions} chosen={miSpell ? [miSpell] : []} max={1} onToggle={(i) => setMiSpell(miSpell === i ? "" : i)} />
                  ) : (
                    <p className="muted small">No level-1 spell list available for this feat.</p>
                  )}
                </>
              )}
            </div>
          )}

          {step === "Abilities" && (
            <div>
              <h2>Ability scores</h2>
              <div className="seg">
                <button className={method === "standard" ? "active" : ""} onClick={() => setMethod("standard")}>
                  Standard array
                </button>
                <button className={method === "pointbuy" ? "active" : ""} onClick={() => setMethod("pointbuy")}>
                  Point buy
                </button>
                <button className={method === "roll" ? "active" : ""} onClick={() => setMethod("roll")}>
                  Roll 4d6
                </button>
              </div>

              {method === "standard" && (
                <AssignTable
                  values={opts.standard_array}
                  assign={assign}
                  setAssign={setAssign}
                  bonus={(k) => bonusFor(k)}
                  hint="Assign each number to one ability."
                />
              )}

              {method === "pointbuy" && (
                <div>
                  <p className={`small ${pointsSpent > budget ? "error-text" : "muted"}`}>
                    Points spent: {pointsSpent} / {budget}
                  </p>
                  <table className="ability-table">
                    <tbody>
                      {ABILITIES.map((k) => {
                        const bonus = bonusFor(k);
                        const v = pointBuy[k];
                        const total = v + bonus;
                        return (
                          <tr key={k}>
                            <th><Term k={abilityKey(k)}>{k}</Term></th>
                            <td>
                              <button className="btn small" disabled={v <= opts.point_buy.min} onClick={() => setPointBuy({ ...pointBuy, [k]: v - 1 })}>
                                −
                              </button>
                              <span className="score">{v}</span>
                              <button
                                className="btn small"
                                disabled={v >= opts.point_buy.max || pointsSpent - pointCost(v) + pointCost(v + 1) > budget}
                                onClick={() => setPointBuy({ ...pointBuy, [k]: v + 1 })}
                              >
                                +
                              </button>
                            </td>
                            <td className="muted small">{bonus ? `${signed(bonus)} race` : ""}</td>
                            <td>
                              <strong>{total}</strong> <span className="muted">({signed(abilityMod(total))})</span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {method === "roll" && (
                <div>
                  <p className="muted small">
                    The server rolls 4d6 and drops the lowest die, six times. Rolls are recorded — you get one set per character.
                  </p>
                  {!roll ? (
                    <button className="btn primary" disabled={rolling} onClick={() => void doRoll()}>
                      🎲 Roll ability scores
                    </button>
                  ) : (
                    <>
                      <div className="roll-sets">
                        {roll.sets.map((s, i) => (
                          <div key={i} className="roll-set">
                            <div className="dice-row">
                              {s.rolls.map((d, j) => {
                                const droppedIdx = s.rolls.indexOf(s.dropped);
                                return (
                                  <span key={j} className={`die ${j === droppedIdx ? "dropped" : ""}`}>
                                    {d}
                                  </span>
                                );
                              })}
                            </div>
                            <div className="roll-total">{s.total}</div>
                          </div>
                        ))}
                      </div>
                      <AssignTable
                        key={roll.roll_id}
                        values={roll.sets.map((s) => s.total)}
                        assign={rollAssign}
                        setAssign={setRollAssign}
                        bonus={(k) => bonusFor(k)}
                        hint="Assign each rolled total to one ability."
                      />
                    </>
                  )}
                  <ErrorText error={rollErr} />
                </div>
              )}
            </div>
          )}

          {step === "Skills" && clsObj && (
            <div>
              <h2>Skills</h2>
              <p className="muted small">
                Choose {clsObj.skill_choices.count} from your class list. Your background already gives you{" "}
                {bgSkills.join(" and ") || "no skills"}.
              </p>
              <div className="chip-grid">
                {Object.keys(opts.skills).map((sk) => {
                  const fromBg = bgSkills.includes(sk);
                  const allowed = clsObj.skill_choices.options.includes(sk);
                  const picked = skills.includes(sk);
                  return (
                    <button
                      key={sk}
                      className={`chip ${picked ? "selected" : ""} ${fromBg ? "granted" : ""}`}
                      disabled={fromBg || !allowed || (!picked && skills.length >= clsObj.skill_choices.count)}
                      onClick={() => toggle(skills, setSkills, sk, clsObj.skill_choices.count)}
                      title={fromBg ? "From your background" : allowed ? "" : "Not on your class list"}
                    >
                      <Term k={skillKey(sk)}>{sk}</Term> <span className="muted small">{opts.skills[sk]}</span>
                      {fromBg && <span className="small"> ✓ background</span>}
                    </button>
                  );
                })}
              </div>
              <p className="small">
                {skills.length} / {clsObj.skill_choices.count} chosen
              </p>
              {expertiseCount > 0 && (
                <>
                  <h3>
                    Expertise <span className="muted small">({expertise.length}/{expertiseCount}) — double proficiency</span>
                  </h3>
                  <div className="chip-grid">
                    {[...new Set([...bgSkills, ...skills])].map((sk) => {
                      const picked = expertise.includes(sk);
                      return (
                        <button
                          key={sk}
                          className={`chip ${picked ? "selected" : ""}`}
                          disabled={!picked && expertise.length >= expertiseCount}
                          onClick={() => toggle(expertise, setExpertise, sk, expertiseCount)}
                        >
                          {sk}
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          )}

          {step === "Equipment" && clsObj && (
            <div>
              <h2>Starting equipment</h2>
              <div className="choice-grid">
                {clsObj.equipment_options.map((o) => (
                  <button key={o.id} className={`choice ${equipment === o.id ? "selected" : ""}`} onClick={() => setEquipment(o.id)}>
                    <strong>{o.label}</strong>
                    <span className="small">{o.items.join(", ")}</span>
                  </button>
                ))}
              </div>
              {bgObj && <p className="muted small">Your background also gives you {formatMoney(bgObj.gold_cp)}.</p>}
              {masteryCount > 0 && (
                <>
                  <h3>
                    Weapon mastery <span className="muted small">({masteries.length}/{masteryCount}) — special effects with these weapons</span>
                  </h3>
                  <div className="chip-grid">
                    {masteryOptions.map((m) => {
                      const picked = masteries.includes(m.weapon_key);
                      return (
                        <button
                          key={m.weapon_key}
                          className={`chip ${picked ? "selected" : ""}`}
                          disabled={!picked && masteries.length >= masteryCount}
                          onClick={() => toggle(masteries, setMasteries, m.weapon_key, masteryCount)}
                        >
                          {m.name} <span className="muted small">{m.mastery}</span>
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          )}

          {step === "Spells" && caster && (
            <div>
              <h2>Spells</h2>
              <h3>
                Cantrips ({cantrips.length}/{caster.cantrips_known})
              </h3>
              {caster.cantrips_known > 0 ? (
                <SpellPicker list={caster.cantrips} chosen={cantrips} max={caster.cantrips_known} onToggle={(i) => toggle(cantrips, setCantrips, i, caster.cantrips_known)} />
              ) : (
                <p className="muted small">Your class learns no cantrips.</p>
              )}
              {caster.spells_at_l1 > 0 ? (
                <>
                  <h3>
                    {caster.known || caster.pact ? "Spells known" : caster.prepares ? "Prepared spells" : "Spellbook"} ({spells.length}/{caster.spells_at_l1}){" "}
                    <span className="muted small">
                      {caster.pact
                        ? "— Pact Magic: few slots, back on a short rest"
                        : caster.known
                          ? "— you learn these permanently"
                          : caster.prepares
                            ? "— you can change them after each long rest"
                            : "— you prepare from your spellbook each day"}
                    </span>
                  </h3>
                  <SpellPicker list={caster.spells} chosen={spells} max={caster.spells_at_l1} onToggle={(i) => toggle(spells, setSpells, i, caster.spells_at_l1)} />
                </>
              ) : (
                <p className="muted small">You start casting levelled spells at level 2.</p>
              )}
            </div>
          )}

          {step === "Details" && (
            <div className="stack narrow">
              <h2>Details</h2>
              <label>
                Name
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Character name" autoFocus />
              </label>
              <label>
                Alignment
                <select value={alignment} onChange={(e) => setAlignment(e.target.value)}>
                  {opts.alignments.map((a) => (
                    <option key={a}>{a}</option>
                  ))}
                </select>
              </label>
              <div>
                <div className="label">Token colour</div>
                <div className="row gap wrap">
                  {COLORS.map((c) => (
                    <button key={c} className={`swatch ${color === c ? "selected" : ""}`} style={{ background: c }} onClick={() => setColor(c)} aria-label={c} />
                  ))}
                  <input type="color" value={color} onChange={(e) => setColor(e.target.value)} />
                </div>
              </div>
              <label>
                Backstory <span className="muted small">(the DM reads this)</span>
                <textarea rows={6} value={backstory} onChange={(e) => setBackstory(e.target.value)} placeholder="Where they're from, what they want, what they're running from…" />
              </label>
            </div>
          )}

          {step === "Review" && (
            <div>
              <h2>Review</h2>
              <div className="review">
                <div className="char-avatar big" style={{ background: color }}>
                  {name.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h3>{name || "Unnamed"}</h3>
                  <div className="muted">
                    Level 1 {raceObj?.name}
                    {subObj ? ` (${subObj.name})` : ""} {clsObj?.name} · {bgObj?.name} · {alignment}
                  </div>
                  <div className="small">Skills: {[...bgSkills, ...skills].join(", ")}</div>
                  {expertise.length > 0 && <div className="small">Expertise: {expertise.join(", ")}</div>}
                  {(subclass || fightingStyle || ancestry) && (
                    <div className="small">
                      {[
                        subclass && `Subclass: ${l1Subclasses.find((s) => (s.index ?? s.name) === subclass)?.name ?? subclass}`,
                        fightingStyle && `Fighting style: ${fightingStyle}`,
                        ancestry && `Ancestry: ${ancestry}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                  )}
                  <div className="small">Equipment: {clsObj?.equipment_options.find((o) => o.id === equipment)?.items.join(", ")}</div>
                  {is2024 && (
                    <div className="small">
                      {[
                        "Rules: 2024",
                        Object.keys(bgAsi).length && `Background: ${Object.entries(bgAsi).map(([k, v]) => `${k} +${v}`).join(", ")}`,
                        bgObj?.origin_feat && `Origin feat: ${bgObj.origin_feat.name}`,
                        masteries.length &&
                          `Masteries: ${masteries.map((k) => masteryOptions.find((m) => m.weapon_key === k)?.name ?? k).join(", ")}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                  )}
                  {caster && (
                    <div className="small">
                      Spells: {[...cantrips, ...spells].map((i) => [...caster.cantrips, ...caster.spells].find((s) => s.index === i)?.name ?? i).join(", ")}
                    </div>
                  )}
                </div>
              </div>
              <ErrorText error={createErr} />
            </div>
          )}
        </div>

        <aside className="creator-preview">
          <h3>Preview</h3>
          <div className="muted small">
            {raceObj?.name ?? "—"} {subObj ? `(${subObj.name})` : ""} {clsObj?.name ?? ""}
            <span className={`ruleset-badge r${ruleset}`}>{ruleset}</span>
          </div>
          <div className="ability-grid">
            {ABILITIES.map((k) => (
              <div key={k} className="ability-cell">
                <div className="ab-name"><Term k={abilityKey(k)}>{k}</Term></div>
                <div className="ab-score">{finalScores ? finalScores[k] : "–"}</div>
                <div className="ab-mod">{finalScores ? signed(abilityMod(finalScores[k])) : ""}</div>
              </div>
            ))}
          </div>
          {clsObj && finalScores && (
            <div className="small stack-tight">
              <div>
                <strong>HP</strong> {clsObj.hit_die + abilityMod(finalScores.CON)}
              </div>
              <div>
                <strong>Speed</strong> {raceObj?.speed ?? 30} ft
              </div>
              <div>
                <strong>Saves</strong> {clsObj.saves.join(", ")}
              </div>
              {caster && (
                <div>
                  <strong>Spell save DC</strong> {8 + 2 + abilityMod(finalScores[caster.ability])}
                </div>
              )}
            </div>
          )}
          <p className="muted small">AC and attacks are calculated by the server from your equipment.</p>
        </aside>
      </div>

      <footer className="creator-foot">
        <button className="btn ghost" disabled={idx === 0} onClick={() => go(-1)}>
          ← Back
        </button>
        <span className="muted small">{err}</span>
        {step === "Review" ? (
          <button className="btn primary" disabled={creating || steps.some((s) => valid(s))} onClick={() => void create()}>
            {creating ? "Creating…" : "Create character"}
          </button>
        ) : (
          <button className="btn primary" disabled={!!err} onClick={() => go(1)}>
            Next →
          </button>
        )}
      </footer>
    </div>
    </RulesetContext.Provider>
  );
}

function AssignTable({
  values,
  assign,
  setAssign,
  bonus,
  hint,
}: {
  values: number[];
  assign: Record<Ability, number | null>;
  setAssign: (a: Record<Ability, number | null>) => void;
  bonus: (k: Ability) => number;
  hint: string;
}) {
  // Track by index into `values` so duplicate numbers (e.g. two 12s from rolling) work.
  const [slots, setSlots] = useState<Record<Ability, number | null>>(() => {
    const out: Record<Ability, number | null> = { STR: null, DEX: null, CON: null, INT: null, WIS: null, CHA: null };
    const used = new Set<number>();
    for (const k of ABILITIES) {
      const v = assign[k];
      if (v === null) continue;
      const i = values.findIndex((x, n) => x === v && !used.has(n));
      if (i >= 0) {
        used.add(i);
        out[k] = i;
      }
    }
    return out;
  });

  const setSlot = (k: Ability, i: number | null) => {
    const next = { ...slots };
    if (i !== null) {
      for (const other of ABILITIES) if (next[other] === i) next[other] = null;
    }
    next[k] = i;
    setSlots(next);
    const a: Record<Ability, number | null> = { STR: null, DEX: null, CON: null, INT: null, WIS: null, CHA: null };
    for (const ab of ABILITIES) a[ab] = next[ab] === null ? null : values[next[ab] as number];
    setAssign(a);
  };

  return (
    <div>
      <p className="muted small">{hint}</p>
      <table className="ability-table">
        <tbody>
          {ABILITIES.map((k) => {
            const i = slots[k];
            const v = i === null ? null : values[i];
            const b = bonus(k);
            return (
              <tr key={k}>
                <th><Term k={abilityKey(k)}>{k}</Term></th>
                <td>
                  <select value={i === null ? "" : String(i)} onChange={(e) => setSlot(k, e.target.value === "" ? null : Number(e.target.value))}>
                    <option value="">—</option>
                    {values.map((val, n) => (
                      <option key={n} value={n}>
                        {val}
                        {Object.values(slots).includes(n) && slots[k] !== n ? " (used)" : ""}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="muted small">{b ? `${signed(b)} race` : ""}</td>
                <td>{v !== null && <><strong>{v + b}</strong> <span className="muted">({signed(abilityMod(v + b))})</span></>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
