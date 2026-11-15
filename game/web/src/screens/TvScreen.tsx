import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { ABILITIES, type CharacterView, type GameView } from "../api/types";
import { subscribe } from "../api/ws";
import WorldMap from "../maps/WorldMap";
import BattleMap from "../maps/BattleMap";
import { HpBar } from "../components/game/PartyPanel";
import { LogItem } from "../components/game/StoryFeed";
import { PHASE_LABEL, formatCountdown, formatMoney, signed, useNow } from "../util/format";
import Portrait from "../components/Portrait";
import DiceRoller from "../components/DiceRoller";
import SceneBackdrop from "../components/atmosphere/SceneBackdrop";
import SkyStrip from "../components/atmosphere/SkyStrip";
import { AutoReadToggle, SoundChip } from "../components/atmosphere/AudioControls";
import { useGameEffects } from "../components/atmosphere/useGameEffects";

export default function TvScreen({ token }: { token: string }) {
  const [view, setView] = useState<GameView | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setView(await api.tvView(token));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [token]);

  useEffect(() => {
    void load();
    const unsub = subscribe({ tv: token }, () => void load());
    // Safety net in case the socket is blocked on the TV's network.
    const poll = window.setInterval(() => void load(), 30000);
    return () => {
      unsub();
      window.clearInterval(poll);
    };
  }, [token, load]);

  if (!view) {
    return (
      <div className="tv center-screen">
        {error ? <div className="tv-error">This TV link isn't working: {error}</div> : <div className="spinner" />}
      </div>
    );
  }
  return <TvLayout view={view} />;
}

function TvLayout({ view }: { view: GameView }) {
  const now = useNow(1000);
  const p = view.phase;
  const enc = view.encounter;
  const narrations = view.log.filter((e) => e.kind === "narration");
  const latest = narrations[narrations.length - 1];
  const recent = view.log.slice(-6).filter((e) => e.kind !== "narration");
  const chars = Object.values(view.characters);
  useGameEffects(view, { tv: true });
  const portraits = useMemo(() => {
    const m: Record<string, string | null | undefined> = {};
    for (const c of chars) m[c.id] = c.portrait_url;
    return m;
  }, [view.characters]); // eslint-disable-line react-hooks/exhaustive-deps

  const whoseTurn = (() => {
    // During a fight (including rolls and while the DM writes), show whose turn it is in initiative order.
    if (enc && p.type !== "lobby" && p.type !== "ended") {
      if (enc.mode === "side" && !enc.turn.actor_id) return enc.turn.side === "party" ? "The party's turn" : "The monsters act";
      const t = enc.tokens.find((x) => x.id === enc.turn.actor_id);
      return t ? `Round ${enc.round} · ${t.name}'s turn` : `Round ${enc.round}`;
    }
    if (p.waiting_on.length) {
      const names = p.waiting_on
        .map((uid) => {
          const m = view.members.find((x) => x.user_id === uid);
          const c = m?.character_id ? view.characters[m.character_id] : undefined;
          return c?.name ?? m?.display_name;
        })
        .filter(Boolean);
      return names.length ? `Waiting on ${names.join(", ")}` : "";
    }
    return "";
  })();

  return (
    <div className="tv atmos">
      <SceneBackdrop scene={view.scene} terrain={enc?.terrain ?? null} />
      <header className="tv-header">
        <SkyStrip scene={enc ? { ...view.scene, type: enc.terrain } : view.scene} height={96} className="tv-sky" />
        <div className="tv-header-text">
          <div className="tv-title">{view.game.name}</div>
          <div className="tv-sub">
            {view.location?.name && <>📍 {view.location.name}</>}
            {view.scene && (
              <>
                {" "}
                · Day {view.scene.day}, {view.scene.time_of_day}
                {view.scene.weather ? ` · ${view.scene.weather}` : ""}
              </>
            )}
          </div>
        </div>
        <div className="tv-phase">
          {view.game.settings.live && <span className="live-pill big">● LIVE</span>}
          <span className={`phase-pill big ${p.type}`}>{PHASE_LABEL[p.type] ?? p.type}</span>
          {whoseTurn && <span className="tv-turn">{whoseTurn}</span>}
          {p.deadline && p.type !== "dm" && <span className="tv-countdown">⏳ {formatCountdown(p.deadline, now)}</span>}
          <AutoReadToggle tv />
          <SoundChip tv />
        </div>
      </header>

      <div className="tv-grid">
        <section className="tv-map">
          {enc ? (
            <BattleMap encounter={enc} interactive={false} actorTokenId={enc.turn.actor_id} portraits={portraits} />
          ) : view.world ? (
            <WorldMap world={view.world} interactive={false} autoFit locationName={view.location?.name} />
          ) : (
            <div className="map-empty">The adventure is about to begin…</div>
          )}
        </section>

        <section className="tv-side">
          {p.type === "dm" || view.dm.busy ? (
            <div className="tv-writing">
              <span className="quill">✒</span> The Dungeon Master is writing…
            </div>
          ) : null}

          {p.type === "shop" && view.shop ? (
            <div className="tv-shop">
              <h2>{view.shop.name}</h2>
              <div className="tv-shop-list">
                {view.shop.stock.slice(0, 24).map((s) => (
                  <div key={s.key} className="tv-shop-item">
                    <span>
                      {s.name}
                      {s.rarity && <small className="muted"> · {s.rarity}</small>}
                      {(s.service || s.category === "Service") && <small className="muted"> · service</small>}
                    </span>
                    <span className="price">{formatMoney(s.price_cp)}</span>
                  </div>
                ))}
              </div>
              <div className="tv-ready">
                {view.members.map((m) => {
                  const c = m.character_id ? view.characters[m.character_id] : undefined;
                  return (
                    <span key={m.user_id} className={`ready-pill big ${m.ready ? "ok" : ""}`}>
                      {m.ready ? "✓" : "…"} {c?.name ?? m.display_name}
                    </span>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="tv-narration">
              {latest ? <Typewriter key={String(latest.id)} text={latest.text} /> : <p className="muted">The story hasn't begun yet.</p>}
            </div>
          )}

          {p.prompt && p.type !== "dm" && <div className="tv-prompt">{p.prompt}</div>}

          {p.pending_rolls.length > 0 && (
            <div className="tv-rolls">
              {p.pending_rolls.map((r) => {
                const c = view.characters[r.character_id];
                return (
                  <div key={r.id} className={`tv-roll ${r.result ? (r.result.success === false ? "fail" : "done") : ""}`}>
                    <span className="char-dot big" style={{ background: c?.color }} />
                    <span className="tv-roll-label">
                      <strong>{c?.name}</strong> — {r.label}
                      {r.dc !== null ? ` (DC ${r.dc})` : ""}
                    </span>
                    {r.result ? (
                      <span className="tv-roll-result">
                        🎲 {r.result.rolls.join(", ")} {signed(r.result.modifier)} = <strong>{r.result.total}</strong>
                        {r.result.success === true && " ✓"}
                        {r.result.success === false && " ✗"}
                      </span>
                    ) : (
                      <span className="muted">rolling…</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {recent.length > 0 && (
            <div className="tv-recent">
              {recent.map((e) => (
                <LogItem key={e.id} e={e} speak={false} />
              ))}
            </div>
          )}
        </section>
      </div>

      <footer className="tv-party">
        {chars.map((c) => (
          <TvCard key={c.id} c={c} active={!!enc && enc.tokens.some((t) => t.character_id === c.id && t.id === enc.turn.actor_id)} />
        ))}
      </footer>
      <DiceRoller variant="tv" />
    </div>
  );
}

function TvCard({ c, active }: { c: CharacterView; active: boolean }) {
  const sc = c.spellcasting;
  return (
    <div className={`tv-card ${active ? "active" : ""} ${c.down ? "down" : ""} ${c.dead ? "dead" : ""}`}>
      <div className="tv-card-top">
        <Portrait c={c} size="big" />
        <div className="tv-card-name">
          <div className="tv-name">{c.name}</div>
          <div className="muted">
            L{c.level} {c.race} {c.class}
          </div>
        </div>
        <div className="tv-ac">
          <span>{c.ac}</span>
          <small>AC</small>
        </div>
      </div>
      <HpBar hp={c.hp} max={c.hp_max} temp={c.temp_hp} />
      <div className="tv-abilities">
        {ABILITIES.map((k) => (
          <span key={k}>
            <small>{k}</small> {signed(c.mods[k])}
          </span>
        ))}
      </div>
      {sc && (Object.keys(sc.slots).length > 0 || sc.pact) && (
        <div className="tv-slots">
          {Object.entries(sc.slots).map(([lvl, s]) => (
            <span key={lvl} className="slot-group">
              <small>L{lvl}</small>
              <span className="slot-pips">
                {Array.from({ length: s.max }).map((_, i) => (
                  <span key={i} className={`pip ${i < s.max - s.used ? "full" : ""}`} />
                ))}
              </span>
            </span>
          ))}
          {sc.pact && (
            <span className="slot-group pact">
              <small>Pact L{sc.pact.level}</small>
              <span className="slot-pips">
                {Array.from({ length: sc.pact.max }).map((_, i) => (
                  <span key={i} className={`pip ${i < sc.pact!.max - sc.pact!.used ? "full" : ""}`} />
                ))}
              </span>
            </span>
          )}
        </div>
      )}
      <div className="cond-list">
        {c.pending_level_up && <span className="cond gold">✦ Level {c.pending_level_up.to_level} ready</span>}
        {sc?.concentrating_on && <span className="cond conc">◎ {sc.concentrating_on}</span>}
        {c.dead && <span className="cond bad">Dead</span>}
        {c.down && !c.dead && <span className="cond bad">Down</span>}
        {c.conditions.map((x) => (
          <span key={x} className="cond">
            {x}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Reveals text progressively, like the DM is speaking. */
function Typewriter({ text }: { text: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    const step = Math.max(1, Math.round(text.length / 400)); // long narrations reveal faster
    const t = window.setInterval(() => {
      setN((prev) => {
        if (prev >= text.length) {
          window.clearInterval(t);
          return prev;
        }
        return Math.min(text.length, prev + step);
      });
    }, 22);
    return () => window.clearInterval(t);
  }, [text]);
  const shown = text.slice(0, n);
  const paras = shown.split(/\n{2,}/);
  return (
    <div className="typewriter">
      {paras.map((p, i) => (
        <p key={i}>
          {p}
          {i === paras.length - 1 && n < text.length && <span className="caret">▍</span>}
        </p>
      ))}
    </div>
  );
}
