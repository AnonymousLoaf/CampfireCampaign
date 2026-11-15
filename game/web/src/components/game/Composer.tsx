import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { ClassAction, Encounter, PointSpell, RestKind, Spell, Token, TravelTo } from "../../api/types";
import { useGame } from "./gameContext";
import CharacterSwitcher from "./CharacterSwitcher";

const QUICK = [
  { label: "Talk", text: "I talk to " },
  { label: "Search", text: "I search the area carefully for " },
  { label: "Sneak", text: "I try to sneak " },
  { label: "Use item", text: "I use my " },
  { label: "Cast", text: "I cast " },
  { label: "Rest", text: "We make camp and take a short rest." },
  { label: "Shop", text: "I head to the market to browse the shops." },
];

function speakerName(view: ReturnType<typeof useGame>["view"]): string {
  const id = view.game.settings.speaker_id ?? view.game.host_id;
  return view.members.find((m) => m.user_id === id)?.display_name ?? "The host";
}

export function ExplorationComposer({
  destination,
  destinationLabel,
  clearDestination,
}: {
  destination: TravelTo;
  destinationLabel: string | null;
  clearDestination: () => void;
}) {
  const { view, gameId, run } = useGame();
  const single = view.game.settings.input_mode === "single";
  const isSpeaker = !!view.me.is_speaker || (single && view.me.is_host && !view.game.settings.speaker_id);
  const mine = view.phase.my_submission;
  const [text, setText] = useState(mine?.text ?? "");
  const [rest, setRest] = useState<RestKind>(mine?.rest ?? null);
  const [busy, setBusy] = useState(false);

  // When a new phase opens, reset the box to whatever the server has for me.
  useEffect(() => {
    setText(view.phase.my_submission?.text ?? "");
    setRest(view.phase.my_submission?.rest ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view.phase.id]);

  if (single && !isSpeaker) {
    return (
      <div className="composer">
        {view.phase.prompt && <div className="dm-prompt">{view.phase.prompt}</div>}
        <div className="muted">
          <strong>{speakerName(view)}</strong> is the table speaker and acts for the whole party. You can follow along here.
        </div>
        <Others />
      </div>
    );
  }

  const submit = async () => {
    setBusy(true);
    await run(() => api.submitAction(gameId, text.trim(), destination, rest));
    setBusy(false);
  };
  const canSubmit = !!text.trim() || !!destination || !!rest;
  const restRule = view.game.settings.rest_rule;
  const restHint =
    restRule === "gritty" ? { short: "8 hours", long: "7 days" } : restRule === "epic" ? { short: "5 min", long: "1 hour" } : { short: "1 hour", long: "8 hours" };

  return (
    <div className="composer">
      {view.phase.prompt && <div className="dm-prompt">{view.phase.prompt}</div>}
      <Others />
      {single && <div className="speaker-note">🗣 Acting for the whole party</div>}
      <div className="quick-chips">
        {QUICK.filter((q) => q.label !== "Rest").map((q) => (
          <button key={q.label} className="chip" onClick={() => setText((t) => (t.trim() ? `${t.trim()} ${q.text}` : q.text))}>
            {q.label}
          </button>
        ))}
        <span className="chip-sep" />
        <button
          className={`chip rest ${rest === "short" ? "selected" : ""}`}
          title={`Vote for a short rest (${restHint.short}): spend hit dice, recover short-rest features`}
          onClick={() => setRest(rest === "short" ? null : "short")}
        >
          ☕ Short rest
        </button>
        <button
          className={`chip rest ${rest === "long" ? "selected" : ""}`}
          title={`Vote for a long rest (${restHint.long}): full HP, spell slots and features`}
          onClick={() => setRest(rest === "long" ? null : "long")}
        >
          🌙 Long rest
        </button>
      </div>
      {rest && (
        <div className="small muted">
          You're voting for a {rest} rest ({rest === "short" ? restHint.short : restHint.long}). {single ? "The party rests when you submit." : "It happens if most of the party agrees."}
        </div>
      )}
      <textarea
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={single ? "What does the party do?" : "What does your character do?"}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && canSubmit) void submit();
        }}
      />
      <div className="composer-row">
        {destination ? (
          <span className="dest-chip">
            🧭 Travel to {destinationLabel ?? "selected hex"}
            <button className="icon-btn tiny" onClick={clearDestination} aria-label="Clear destination">
              ✕
            </button>
          </span>
        ) : (
          <span className="muted small">Tip: click the map to propose a travel destination.</span>
        )}
        <div className="grow" />
        {mine && (
          <button className="btn ghost small" disabled={busy} onClick={() => void run(() => api.withdrawAction(gameId))}>
            Withdraw
          </button>
        )}
        <button className="btn primary" disabled={busy || !canSubmit} onClick={() => void submit()}>
          {mine ? "Update action" : "Submit action"}
        </button>
      </div>
      {mine && <div className="ok-text small">✓ Your action is in. You can change it until the round resolves.</div>}
    </div>
  );
}

function Others() {
  const { view } = useGame();
  const others = view.phase.submissions_visible.filter((s) => s.user_id !== view.me.user_id);
  if (!others.length) return null;
  return (
    <div className="others">
      {others.map((s) => {
        const m = view.members.find((x) => x.user_id === s.user_id);
        const c = m?.character_id ? view.characters[m.character_id] : undefined;
        return (
          <div key={s.user_id} className="other-action">
            <strong style={{ color: c?.color }}>{c?.name ?? m?.display_name ?? "Someone"}:</strong>{" "}
            {s.text || <em className="muted">{s.rest ? "(rest)" : "(travel only)"}</em>}
            {s.travel_to && <span className="muted small"> · 🧭 travel</span>}
            {s.rest && <span className="muted small"> · {s.rest === "short" ? "☕ short rest" : "🌙 long rest"}</span>}
          </div>
        );
      })}
    </div>
  );
}

export function RollComposer() {
  const { view, gameId, run, controls } = useGame();
  const rolls = view.phase.pending_rolls;
  return (
    <div className="composer">
      {view.phase.prompt && <div className="dm-prompt">{view.phase.prompt}</div>}
      <div className="roll-list">
        {rolls.map((r) => {
          const c = view.characters[r.character_id];
          const canRoll = !r.result && (r.user_id === view.me.user_id || controls.includes(r.character_id));
          return (
            <div key={r.id} className={`roll-req ${r.result ? "done" : ""}`}>
              <div className="roll-req-head">
                <span className="char-dot" style={{ background: c?.color }} />
                <strong>{c?.name ?? "?"}</strong>
                <span>{r.label}</span>
                {r.dc !== null && <span className="badge">DC {r.dc}</span>}
                {r.advantage !== "normal" && <span className={`badge ${r.advantage === "advantage" ? "green" : "red"}`}>{r.advantage}</span>}
              </div>
              {r.result ? (
                <div className="roll-result">
                  <span className="dice-row inline">
                    {r.result.rolls.map((d, i) => (
                      <span key={i} className={`die ${d === 20 ? "crit" : d === 1 ? "fumble" : ""}`}>
                        {d}
                      </span>
                    ))}
                  </span>
                  <span>
                    {r.result.modifier >= 0 ? "+" : ""}
                    {r.result.modifier} = <strong className="big-num">{r.result.total}</strong>
                  </span>
                  {r.result.success === true && <span className="badge green">Success</span>}
                  {r.result.success === false && <span className="badge red">Fail</span>}
                </div>
              ) : canRoll ? (
                <button className="btn primary big" onClick={() => void run(() => api.roll(gameId, r.id))}>
                  🎲 Roll
                </button>
              ) : (
                <span className="muted small">Waiting for {view.members.find((m) => m.user_id === r.user_id)?.display_name ?? "player"}…</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ShopComposer({ onOpenShop }: { onOpenShop: () => void }) {
  const { view, gameId, run } = useGame();
  const meReady = view.members.find((m) => m.user_id === view.me.user_id)?.ready ?? false;
  return (
    <div className="composer">
      {view.phase.prompt && <div className="dm-prompt">{view.phase.prompt}</div>}
      <div className="composer-row">
        <button className="btn primary" onClick={onOpenShop}>
          🛒 Open {view.shop?.name ?? "the shop"}
        </button>
        <div className="grow" />
        <label className="toggle">
          <input type="checkbox" checked={meReady} onChange={(e) => void run(() => api.ready(gameId, e.target.checked))} />
          <span>I'm ready</span>
        </label>
      </div>
      <ReadyList />
    </div>
  );
}

export function ReadyList() {
  const { view } = useGame();
  return (
    <div className="ready-list">
      {view.members.map((m) => {
        const c = m.character_id ? view.characters[m.character_id] : undefined;
        return (
          <span key={m.user_id} className={`ready-pill ${m.ready ? "ok" : ""}`}>
            {m.ready ? "✓" : "…"} {c?.name ?? m.display_name}
          </span>
        );
      })}
    </div>
  );
}

export interface CombatState {
  activeToken: Token | null;
  canAct: boolean;
  reachable: [number, number][];
  targets: Encounter["targets"];
  budget: Encounter["budget"];
}

/** Something waiting for a map click: an area spell's point, or a class feature's target. */
export type Armed =
  | { kind: "spell"; spell: Spell; ps: PointSpell; slot?: number }
  | { kind: "feature"; action: ClassAction };

export function CombatComposer({
  combat,
  selectedTarget,
  clearTarget,
  armed,
  setArmed,
  aimPoint,
}: {
  combat: CombatState;
  selectedTarget: Token | null;
  clearTarget: () => void;
  armed?: Armed | null;
  setArmed?: (a: Armed | null) => void;
  aimPoint?: [number, number] | null;
}) {
  const { view, gameId, run, acting, charParam, controls } = useGame();
  const enc = view.encounter!;
  const [custom, setCustom] = useState("");
  const [slot, setSlot] = useState<Record<string, number>>({});

  const turnText = (() => {
    if (enc.mode === "side") return enc.turn.side === "party" ? "The party's turn" : "The monsters are acting…";
    const t = enc.tokens.find((x) => x.id === enc.turn.actor_id);
    return t ? `${t.name}'s turn` : "";
  })();

  if (!combat.canAct || !combat.activeToken || !acting) {
    return (
      <div className="composer">
        <div className="turn-banner">
          Round {enc.round} · {turnText}
        </div>
        <div className="muted small">
          {acting?.down ? "You're down — the dice will decide your fate at the start of your turn." : "Waiting for your turn. You'll be notified."}
        </div>
      </div>
    );
  }

  const tgt = selectedTarget ? combat.targets.find((t) => t.token_id === selectedTarget.id) : undefined;
  const b = combat.budget;
  const attacksLeft = b?.attacks_left;
  const actionUsed = b ? !b.action : false;
  // With Extra Attack the action stays "open" until every attack is used.
  const canAttack = attacksLeft !== undefined ? attacksLeft > 0 : !actionUsed;
  const spells: Spell[] = [...(acting.spellcasting?.cantrips ?? []), ...(acting.spellcasting?.spells ?? [])].filter(
    (s) => s.combat || s.target === "point" || (s.target === "self" && !!s.area),
  );
  const classActions = acting.actions ?? [];
  // M1 servers have no `actions`; keep the old Second Wind button for them.
  const hasSecondWind =
    classActions.length === 0 && acting.features.some((f) => f.name.toLowerCase() === "second wind" && (!f.uses || f.uses.used < f.uses.max));
  const pointSpells = enc.point_spells ?? [];

  const slotsFor = (s: Spell): number[] => {
    if (s.level === 0 || !acting.spellcasting) return [];
    const regular = Object.entries(acting.spellcasting.slots)
      .filter(([lvl, v]) => Number(lvl) >= s.level && v.used < v.max)
      .map(([lvl]) => Number(lvl));
    const pact = acting.spellcasting.pact;
    if (pact && pact.level >= s.level && pact.used < pact.max && !regular.includes(pact.level)) regular.push(pact.level);
    return regular.sort((a, c) => a - c);
  };

  const castable = (s: Spell) => {
    if (s.level > 0 && slotsFor(s).length === 0) return { ok: false, why: "No spell slots left" };
    if (s.target === "point") {
      if (!pointSpells.some((p) => p.spell_index === s.index)) return { ok: false, why: "Can't cast that right now" };
      return { ok: true, why: "" };
    }
    if (s.target === "self" || s.target === "none") return { ok: true, why: "" };
    if (s.kind === "utility") return { ok: true, why: "" };
    if (s.kind === "heal" || s.target === "ally") return { ok: true, why: "" }; // can target self without a selection
    if (!selectedTarget) return { ok: false, why: "Select a target on the map" };
    if (!tgt?.spell_indexes.includes(s.index)) return { ok: false, why: "Out of range or not a valid target" };
    return { ok: true, why: "" };
  };

  const cast = (s: Spell) => {
    const lvl = s.level > 0 ? slot[s.index] ?? slotsFor(s)[0] : undefined;
    if (s.target === "point" && setArmed) {
      const ps = pointSpells.find((p) => p.spell_index === s.index);
      if (ps) {
        setArmed({ kind: "spell", spell: s, ps, slot: lvl });
        return;
      }
    }
    if (s.target === "self" || s.target === "none") {
      void run(() => api.cast(gameId, s.index, undefined, lvl, charParam)).then((ok) => ok && clearTarget());
      return;
    }
    const target = s.kind === "heal" || s.target === "ally" ? selectedTarget?.id ?? combat.activeToken!.id : selectedTarget?.id;
    void run(() => api.cast(gameId, s.index, target, lvl, charParam)).then((ok) => ok && clearTarget());
  };

  const budgetFor = (a: ClassAction) => {
    if (!b) return true;
    if (a.kind === "action") return b.action;
    if (a.kind === "bonus") return b.bonus;
    if (a.kind === "reaction") return b.reaction !== false;
    return true;
  };

  const triggerFeature = (a: ClassAction) => {
    if ((a.target === "enemy" || a.target === "ally" || a.target === "point") && setArmed) {
      setArmed({ kind: "feature", action: a });
      return;
    }
    void run(() => api.feature(gameId, a.id, {}, charParam));
  };

  const confirmAim = () => {
    if (!armed || !aimPoint) return;
    const [x, y] = aimPoint;
    const call =
      armed.kind === "spell"
        ? () => api.castAt(gameId, armed.spell.index, x, y, armed.slot, charParam)
        : () => api.feature(gameId, armed.action.id, { x, y }, charParam);
    void run(call).then((ok) => ok && setArmed?.(null));
  };

  return (
    <div className="composer combat">
      <div className="turn-banner mine">
        Round {enc.round} · Your move{controls.length > 1 ? ` as ${acting.name}` : ""}
      </div>
      {enc.mode === "side" && <CharacterSwitcher label="Act with" ids={controls.filter((id) => enc.tokens.some((t) => t.character_id === id && t.hp_state !== "dead"))} />}
      <div className="budget">
        {b ? (
          <>
            <span className={`budget-chip ${b.move_ft > 0 ? "" : "used"}`}>🥾 {b.move_ft} ft</span>
            <span className={`budget-chip ${b.action ? "" : "used"}`}>⚔ Action</span>
            {attacksLeft !== undefined && attacksLeft > 0 && b.action && <span className="budget-chip">🗡 {attacksLeft} attack{attacksLeft > 1 ? "s" : ""} left</span>}
            <span className={`budget-chip ${b.bonus ? "" : "used"}`}>✦ Bonus</span>
            {b.reaction !== undefined && <span className={`budget-chip ${b.reaction ? "" : "used"}`}>↺ Reaction</span>}
          </>
        ) : (
          <span className="muted small">Speed {acting.speed} ft</span>
        )}
        <span className="muted small">Click a blue square to move, a red-ringed creature to target.</span>
      </div>

      {armed && (
        <div className="aim-banner">
          {armed.kind === "spell" ? (
            <>
              🎯 Aiming <strong>{armed.spell.name}</strong>
              {armed.ps.area ? ` (${armed.ps.area.size_ft} ft ${armed.ps.area.shape})` : ""} — click a square within {armed.ps.range_ft} ft
            </>
          ) : armed.action.target === "point" ? (
            <>
              🎯 <strong>{armed.action.name}</strong> — click a square
              {armed.action.range_ft ? ` within ${armed.action.range_ft} ft` : ""}
            </>
          ) : (
            <>
              🎯 <strong>{armed.action.name}</strong> — click {armed.action.target === "ally" ? "an ally" : "an enemy"}
              {armed.action.range_ft ? ` within ${armed.action.range_ft} ft` : ""}
            </>
          )}
          <div className="grow" />
          {aimPoint && (armed.kind === "spell" || armed.action.target === "point") && (
            <button className="btn primary small" onClick={confirmAim}>
              {armed.kind === "spell" ? "Cast here" : "Use here"}
            </button>
          )}
          <button className="btn ghost small" onClick={() => setArmed?.(null)}>
            Cancel
          </button>
        </div>
      )}

      <div className="target-line">
        {selectedTarget ? (
          <>
            🎯 Target: <strong>{selectedTarget.name}</strong>
            <button className="icon-btn tiny" onClick={clearTarget}>
              ✕
            </button>
          </>
        ) : (
          <span className="muted small">No target selected.</span>
        )}
      </div>

      <div className="action-grid">
        {acting.attacks.map((a) => {
          const ok = !!selectedTarget && !!tgt?.attack_ids.includes(a.id) && canAttack;
          // "Attack 2 of 2" when Extra Attack gives more than one attack per action.
          const total = attacksLeft !== undefined && b?.action ? Math.max(attacksLeft, 1) : undefined;
          return (
            <button
              key={a.id}
              className="btn action"
              disabled={!ok}
              title={!selectedTarget ? "Select a target on the map" : !tgt?.attack_ids.includes(a.id) ? "Out of range" : !canAttack ? "No attacks left this turn" : ""}
              onClick={() => void run(() => api.attack(gameId, a.id, selectedTarget!.id, charParam)).then((r) => r && attacksLeft !== undefined && attacksLeft > 1 ? undefined : r && clearTarget())}
            >
              <strong>{a.name}</strong>
              <span className="small">
                {a.to_hit >= 0 ? "+" : ""}
                {a.to_hit} · {a.damage} {a.damage_type}
                {total && total > 1 ? ` · ${total} left` : ""}
              </span>
            </button>
          );
        })}
        {spells.map((s) => {
          const c = castable(s);
          const slots = slotsFor(s);
          const needsBonus = s.casting_time?.toLowerCase().includes("bonus");
          const spent = needsBonus ? (b ? !b.bonus : false) : actionUsed;
          const isArmed = armed?.kind === "spell" && armed.spell.index === s.index;
          return (
            <div key={s.index} className="spell-action">
              <button className={`btn action spell ${isArmed ? "armed" : ""}`} disabled={!c.ok || spent} title={c.why || s.description} onClick={() => cast(s)}>
                <strong>✧ {s.name}</strong>
                <span className="small">
                  {s.level === 0 ? "cantrip" : `level ${s.level}`} · {s.area ? `${s.area.size_ft} ft ${s.area.shape}` : s.kind}
                  {s.concentration ? " · conc." : ""}
                </span>
              </button>
              {slots.length > 1 && (
                <select className="slot-select" value={slot[s.index] ?? slots[0]} onChange={(e) => setSlot({ ...slot, [s.index]: Number(e.target.value) })}>
                  {slots.map((l) => (
                    <option key={l} value={l}>
                      slot {l}
                    </option>
                  ))}
                </select>
              )}
            </div>
          );
        })}
      </div>

      {classActions.length > 0 && (
        <div className="feature-actions">
          {(["action", "bonus", "reaction", "free"] as const).map((kind) => {
            const list = classActions.filter((a) => a.kind === kind);
            if (!list.length) return null;
            return (
              <div key={kind} className="feature-group">
                <span className="feature-group-label">{kind === "bonus" ? "Bonus" : kind === "free" ? "Free" : kind === "reaction" ? "Reaction" : "Action"}</span>
                {list.map((a) => {
                  const usable = a.available && budgetFor(a);
                  const isArmed = armed?.kind === "feature" && armed.action.id === a.id;
                  return (
                    <button
                      key={a.id}
                      className={`btn small feature-btn ${isArmed ? "armed" : ""}`}
                      disabled={!usable}
                      title={!a.available ? `${a.name} isn't available right now` : !budgetFor(a) ? `No ${kind} left this turn` : a.description}
                      onClick={() => triggerFeature(a)}
                    >
                      {a.name}
                      {a.uses && (
                        <span className="muted small">
                          {" "}
                          {a.uses.max - a.uses.used}/{a.uses.max}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      <div className="composer-row wrap">
        <button className="btn small" disabled={actionUsed} onClick={() => void run(() => api.act(gameId, "dodge", undefined, charParam))}>
          🛡 Dodge
        </button>
        <button className="btn small" disabled={actionUsed} onClick={() => void run(() => api.act(gameId, "dash", undefined, charParam))}>
          💨 Dash
        </button>
        <button className="btn small" disabled={actionUsed} onClick={() => void run(() => api.act(gameId, "disengage", undefined, charParam))}>
          ↩ Disengage
        </button>
        {hasSecondWind && (
          <button className="btn small" disabled={b ? !b.bonus : false} onClick={() => void run(() => api.act(gameId, "second_wind", undefined, charParam))}>
            ❤ Second Wind
          </button>
        )}
      </div>
      <div className="composer-row">
        <input className="grow" value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="Something else? Describe it for the DM…" />
        <button
          className="btn small"
          disabled={!custom.trim()}
          onClick={() => void run(() => api.act(gameId, "custom", custom.trim(), charParam)).then((ok) => ok && setCustom(""))}
        >
          Do it
        </button>
      </div>
      <div className="composer-row">
        <div className="grow" />
        <button className="btn primary" onClick={() => void run(() => api.endTurn(gameId, charParam)).then((ok) => ok && clearTarget())}>
          End turn
        </button>
      </div>
    </div>
  );
}
