import { useEffect, useState } from "react";
import { HoverInfo, RulesText, Term } from "../RulesText";
import { SpellDetails } from "../SpellPick";
import { api } from "../../api/client";
import type { Attack, CharacterView, Encounter, PendingRoll, RestKind } from "../../api/types";
import { useGame } from "./gameContext";

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

export function ExplorationComposer() {
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
    await run(() => api.submitAction(gameId, text.trim(), null, rest));
    setBusy(false);
  };
  const canSubmit = !!text.trim() || !!rest;
  const restRule = view.game.settings.rest_rule;
  const restHint =
    restRule === "gritty" ? { short: "8 hours", long: "7 days" } : restRule === "epic" ? { short: "5 min", long: "1 hour" } : { short: "1 hour", long: "8 hours" };

  return (
    <div className="composer">
      {view.phase.prompt && <div className="dm-prompt">{view.phase.prompt}</div>}
      <Others />
      {single && <div className="speaker-note">🗣 Acting for the whole party</div>}
      {!single && !!view.phase.spotlight?.length && view.me.user_id && !view.phase.waiting_on.includes(view.me.user_id) && !mine && (
        <div className="speaker-note">
          🎯 The DM is waiting on {view.phase.spotlight.join(" and ")}. You can still add an action if you like.
        </div>
      )}
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
        <span className="muted small">Want to travel? Say where — "we take the east road to the next town." Click the map to see what you know about a place.</span>
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
      {mine && (
        <div className="ok-text small">
          ✓ Your action is in{mine.edited ? " (edited — others see that it changed)" : ""}. You can change it until the round resolves.
        </div>
      )}
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
            {s.text || <em className="muted">{s.rest ? "(rest)" : "(no words)"}</em>}
            {s.rest && <span className="muted small"> · {s.rest === "short" ? "☕ short rest" : "🌙 long rest"}</span>}
            {s.edited && (
              <span className="edited-tag" title={s.updated_at ? `Edited ${new Date(s.updated_at).toLocaleString()}` : "Edited"}>
                edited
              </span>
            )}
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
      {view.encounter && <CombatTurnBanner />}
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
              {!r.result && <RollNeed r={r} saveDc={c?.spellcasting?.save_dc} />}
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
                  {r.result.hit === true && <span className="badge green">Hit</span>}
                  {r.result.hit === false && <span className="badge red">Miss</span>}
                  {r.result.lines && r.result.lines.length > 0 && (
                    <div className="roll-lines small">
                      {r.result.lines.map((l, i) => (
                        <div key={i}>{l}</div>
                      ))}
                    </div>
                  )}
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

/** What a roll needs to succeed, told the way a DM at the table would. */
function RollNeed({ r, saveDc }: { r: PendingRoll; saveDc?: number }) {
  const bonus = r.bonus ?? 0;
  const add = bonus ? ` ${bonus > 0 ? "+" : "−"} ${Math.abs(bonus)}` : "";
  const adv =
    r.advantage === "advantage" ? " You roll two d20s and keep the higher." : r.advantage === "disadvantage" ? " You roll two d20s and keep the lower." : "";
  if (r.dc !== null) {
    const die = r.dc - bonus;
    return (
      <div className="roll-need small">
        You need a total of <strong>{r.dc}</strong> or more (d20{add}) —{" "}
        {die <= 1 ? (
          <>you can't fail this one.</>
        ) : die > 20 ? (
          <>even a 20 on the die falls short.</>
        ) : (
          <>
            a <strong>{die}</strong> or higher on the die.
          </>
        )}
        {adv}
      </div>
    );
  }
  if (r.check === "combat" && bonus) {
    return (
      <div className="roll-need small">
        d20{add} to hit. You hit if the total meets the target's <Term k="armor-class">Armor Class</Term> — the DM keeps that number to
        themselves, as at the table. A natural 20 always hits (a <Term k="critical-hit">critical hit</Term>); a natural 1 always misses.{adv}
      </div>
    );
  }
  if (r.check === "combat") {
    return (
      <div className="roll-need small">
        {saveDc ? (
          <>
            The target makes a <Term k="saving-throw">saving throw</Term> against your <Term k="spell-save-dc">spell save DC</Term> of{" "}
            <strong>{saveDc}</strong>; your roll is the spell's damage or effect.
          </>
        ) : (
          <>Your roll decides how well it works.</>
        )}
      </div>
    );
  }
  return null;
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


// ── Combat: you type what your character does; the DM resolves it with real rolls ──

const COMBAT_QUICK = [
  { label: "Attack", text: "I attack " },
  { label: "Move", text: "I move " },
  { label: "Cast", text: "I cast " },
  { label: "Dodge", text: "I take the Dodge action, " },
  { label: "Help", text: "I help " },
  { label: "Use item", text: "I use my " },
];

/** "Round 2 · Goblin 1's turn", and who the game is waiting for. */
export function CombatTurnBanner({ writing = false }: { writing?: boolean }) {
  const { view } = useGame();
  const enc = view.encounter;
  if (!enc) return null;
  const actor = enc.tokens.find((t) => t.id === enc.turn.actor_id) ?? null;
  const mine = !writing && enc.my_turn && !!enc.my_token_id && view.phase.type === "combat";
  const who = actor ? `${actor.name}'s turn` : "";
  return (
    <div className={`turn-banner ${mine ? "mine" : ""}`}>
      Round {enc.round}
      {who ? ` · ${who}` : ""}
      {writing && <span className="muted"> · the DM is writing…</span>}
    </div>
  );
}

export function CombatComposer() {
  const { view, gameId, run, acting } = useGame();
  const enc = view.encounter!;
  const single = view.game.settings.input_mode === "single";
  const actor = enc.tokens.find((t) => t.id === enc.turn.actor_id) ?? null;
  const myTok = enc.my_turn && enc.my_token_id ? enc.tokens.find((t) => t.id === enc.my_token_id) ?? null : null;
  const me = myTok?.character_id ? view.characters[myTok.character_id] : undefined;
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  // A fresh box for every turn.
  useEffect(() => {
    setText("");
  }, [view.phase.id, enc.turn.actor_id]);

  const submit = async () => {
    if (!text.trim()) return;
    setBusy(true);
    const ok = await run(() => api.submitAction(gameId, text.trim(), null, null));
    setBusy(false);
    if (ok) setText("");
  };

  const waiting = (() => {
    if (!actor) return "Waiting for the next turn…";
    if (actor.kind === "monster") return `${actor.name} is acting…`;
    const c = actor.character_id ? view.characters[actor.character_id] : undefined;
    if (single) return `Waiting for ${speakerName(view)} to say what ${actor.name} does…`;
    const m = view.members.find((x) => x.character_id === actor.character_id);
    return `Waiting for ${c?.name ?? actor.name}${m ? ` (${m.display_name})` : ""} to act…`;
  })();

  if (!myTok || !me) {
    const ref = acting ?? (view.me.character_id ? view.characters[view.me.character_id] : undefined);
    return (
      <div className="composer combat">
        <CombatTurnBanner />
        <div className="muted small">
          {acting?.down ? "You're down — the dice decide your fate at the start of your turn. " : ""}
          {waiting} You'll be notified when it's your turn.
        </div>
        {ref && <CombatReference c={ref} budget={null} collapsed />}
      </div>
    );
  }

  return (
    <div className="composer combat">
      <div className="turn-banner mine">
        Round {enc.round} · Your turn, {me.name}: describe what you do
      </div>
      {view.phase.prompt && <div className="dm-prompt">{view.phase.prompt}</div>}
      {single && <div className="speaker-note">🗣 You're typing for {me.name}</div>}
      <div className="quick-chips">
        {COMBAT_QUICK.map((q) => (
          <button key={q.label} className="chip" onClick={() => setText((t) => (t.trim() ? `${t.trim()} ${q.text}` : q.text))}>
            {q.label}
          </button>
        ))}
      </div>
      <textarea
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={`What does ${me.name} do? e.g. "I duck behind the cart and throw a dagger at the orc's head."`}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void submit();
        }}
      />
      <div className="composer-row">
        <span className="muted small">Your action, bonus action and movement — the DM moves your token and asks for rolls.</span>
        <div className="grow" />
        <button className="btn primary" disabled={busy || !text.trim()} onClick={() => void submit()}>
          Submit action
        </button>
      </div>
      <CombatReference c={me} budget={enc.budget} />
    </div>
  );
}

/** A read-only cheat sheet of what the character can do. Nothing here is clickable: you type what you use. */
export function CombatReference({ c, budget, collapsed = false }: { c: CharacterView; budget: Encounter["budget"]; collapsed?: boolean }) {
  const sc = c.spellcasting;
  const slotText = sc
    ? [
        ...Object.entries(sc.slots)
          .filter(([, v]) => v.max > 0)
          .sort(([a], [b]) => Number(a) - Number(b))
          .map(([lvl, v]) => `L${lvl} ${v.max - v.used}/${v.max}`),
        ...(sc.pact ? [`Pact L${sc.pact.level} ${sc.pact.max - sc.pact.used}/${sc.pact.max}`] : []),
      ].join(" · ")
    : "";
  const leveled = (sc?.spells ?? []).slice().sort((a, b) => a.level - b.level || a.name.localeCompare(b.name));
  const actions = c.actions ?? [];
  const actionNames = new Set(actions.map((a) => a.name.toLowerCase()));
  const otherFeatures = c.features.filter((f) => f.uses && !actionNames.has(f.name.toLowerCase()));
  const range = (a: Attack) =>
    a.kind === "melee" && !a.long_range_ft ? `${a.range_ft} ft` : a.long_range_ft ? `${a.range_ft}/${a.long_range_ft} ft` : `${a.range_ft} ft`;
  const body = (
    <div className="combat-ref">
      <div className="budget">
        <span className="ref-chip">Speed {c.speed} ft</span>
        {budget && (
          <>
            <span className={`budget-chip ${budget.move_ft > 0 ? "" : "used"}`}>🥾 {budget.move_ft} ft left</span>
            <span className={`budget-chip ${budget.action ? "" : "used"}`}>Action</span>
            {budget.attacks_left !== undefined && budget.attacks_left > 0 && !budget.action && (
              <span className="budget-chip">{budget.attacks_left} attack{budget.attacks_left > 1 ? "s" : ""} left</span>
            )}
            <span className={`budget-chip ${budget.bonus ? "" : "used"}`}>Bonus action</span>
            {budget.reaction !== undefined && <span className={`budget-chip ${budget.reaction ? "" : "used"}`}>Reaction</span>}
          </>
        )}
        <span className="ref-chip">AC {c.ac}</span>
        <span className="ref-chip">
          HP {c.hp}/{c.hp_max}
        </span>
      </div>
      {c.attacks.length > 0 && (
        <div className="ref-section">
          <div className="ref-label">Weapons</div>
          {c.attacks.map((a) => (
            <div key={a.id} className="ref-row">
              <strong>{a.name}</strong>
              <span>
                {a.to_hit >= 0 ? "+" : ""}
                {a.to_hit} to hit · {a.damage} {a.damage_type} · {range(a)}
                {a.mastery ? ` · ${a.mastery}` : ""}
              </span>
            </div>
          ))}
        </div>
      )}
      {sc && (sc.cantrips.length > 0 || leveled.length > 0) && (
        <div className="ref-section">
          <div className="ref-label">
            Spells <span className="muted">· DC {sc.save_dc} · +{sc.attack_bonus} to hit{slotText ? ` · slots ${slotText}` : ""}</span>
          </div>
          {sc.cantrips.length > 0 && (
            <div className="ref-row">
              <span className="muted">Cantrips</span>
              <span>
                {sc.cantrips.map((s, i) => (
                  <span key={s.index}>
                    {i > 0 && ", "}
                    <HoverInfo info={<SpellDetails s={s} />} wide>
                      {s.name}
                    </HoverInfo>
                  </span>
                ))}
              </span>
            </div>
          )}
          {leveled.length > 0 && (
            <div className="ref-row">
              <span className="muted">Prepared</span>
              <span>
                {leveled.map((s, i) => (
                  <span key={s.index}>
                    {i > 0 && ", "}
                    <HoverInfo info={<SpellDetails s={s} />} wide>
                      {s.name} ({s.level})
                    </HoverInfo>
                  </span>
                ))}
              </span>
            </div>
          )}
        </div>
      )}
      {(actions.length > 0 || otherFeatures.length > 0) && (
        <div className="ref-section">
          <div className="ref-label">Features</div>
          <div className="ref-feats">
            {actions.map((a) => (
              <HoverInfo key={a.id} className={`ref-chip ${a.available ? "" : "used"}`} info={<FeatureInfo name={a.name} text={a.description} />}>
                {a.name}
                <span className="muted">
                  {" "}
                  · {a.kind === "bonus" ? "bonus" : a.kind}
                  {a.uses ? ` · ${a.uses.max - a.uses.used}/${a.uses.max}` : ""}
                </span>
              </HoverInfo>
            ))}
            {otherFeatures.map((f) => (
              <HoverInfo key={f.name} className="ref-chip" info={<FeatureInfo name={f.name} text={f.description} />}>
                {f.name}
                {f.uses && (
                  <span className="muted">
                    {" "}
                    · {f.uses.max - f.uses.used}/{f.uses.max}
                  </span>
                )}
              </HoverInfo>
            ))}
          </div>
        </div>
      )}
    </div>
  );
  if (collapsed) {
    return (
      <details className="combat-ref-wrap">
        <summary className="small">What {c.name} can do</summary>
        {body}
      </details>
    );
  }
  return body;
}
function FeatureInfo({ name, text }: { name: string; text: string }) {
  return (
    <>
      <div className="rules-pop-title">{name}</div>
      <div className="pre">
        <RulesText text={text} />
      </div>
    </>
  );
}
