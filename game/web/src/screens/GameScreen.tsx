import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { GameView, Me, Token, TravelTo } from "../api/types";
import { subscribe } from "../api/ws";
import { navigate } from "../router";
import { GameContext, controlsOf, useGame, type GameCtx } from "../components/game/gameContext";
import GameHeader from "../components/game/GameHeader";
import PartyPanel from "../components/game/PartyPanel";
import StoryFeed from "../components/game/StoryFeed";
import SheetTabs from "../components/game/SheetTabs";
import ShopModal from "../components/game/ShopModal";
import HostSettingsModal from "../components/game/HostSettingsModal";
import TvLinkModal from "../components/game/TvLinkModal";
import { CombatComposer, ExplorationComposer, RollComposer, ShopComposer, type Armed, type CombatState } from "../components/game/Composer";
import WorldMap from "../maps/WorldMap";
import BattleMap, { type Aim } from "../maps/BattleMap";
import LevelUpModal from "../components/LevelUpModal";
import AwayControl from "../components/game/AwayControl";
import CatchUp from "../components/game/CatchUp";
import StoryHistory from "../components/game/StoryHistory";
import { useIsMobile } from "../util/useMedia";
import SceneBackdrop from "../components/atmosphere/SceneBackdrop";
import SkyStrip from "../components/atmosphere/SkyStrip";
import { AutoReadToggle, SoundChip } from "../components/atmosphere/AudioControls";
import { useGameEffects } from "../components/atmosphere/useGameEffects";
import DiceRoller from "../components/DiceRoller";

type MobileTab = "story" | "map" | "party" | "sheet";

export default function GameScreen({ gameId, me }: { gameId: string; me: Me }) {
  const [view, setView] = useState<GameView | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | undefined>(undefined);
  // The character I'm acting as — the server computes combat moves/targets for it.
  const actingRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    try {
      const v = await api.view(gameId, actingRef.current);
      setView(v);
      setLoadErr(null);
    } catch (e) {
      setLoadErr(e instanceof Error ? e.message : String(e));
    }
  }, [gameId]);

  useEffect(() => {
    void load();
    return subscribe(gameId, () => void load());
  }, [gameId, load]);

  const showToast = (msg: string) => {
    setToast(msg);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 5000);
  };

  const run = useCallback(
    async (fn: () => Promise<unknown>) => {
      try {
        await fn();
        void load();
        return true;
      } catch (e) {
        showToast(e instanceof Error ? e.message : String(e));
        void load();
        return false;
      }
    },
    [load],
  );

  if (loadErr && !view) {
    return (
      <div className="center-screen stack">
        <div className="error-text">{loadErr}</div>
        <button className="btn" onClick={() => navigate({ name: "lobby" })}>
          Back to lobby
        </button>
      </div>
    );
  }
  if (!view) {
    return (
      <div className="center-screen">
        <div className="spinner" />
      </div>
    );
  }
  return (
    <GameLoaded
      view={view}
      gameId={gameId}
      me={me}
      run={run}
      refresh={() => void load()}
      toast={toast}
      clearToast={() => setToast(null)}
      onActingChange={(id) => {
        if (actingRef.current !== id) {
          actingRef.current = id;
          void load();
        }
      }}
    />
  );
}

function GameLoaded({
  view,
  gameId,
  run,
  refresh,
  toast,
  clearToast,
  onActingChange,
}: {
  view: GameView;
  gameId: string;
  me: Me;
  run: GameCtx["run"];
  refresh: () => void;
  toast: string | null;
  clearToast: () => void;
  onActingChange: (id: string | null) => void;
}) {
  const controls = useMemo(() => controlsOf(view), [view]);
  const [actingId, setActingId] = useState<string | null>(view.me.character_id ?? controls[0] ?? null);
  const [viewedId, setViewedId] = useState<string | null>(view.me.character_id ?? Object.keys(view.characters)[0] ?? null);
  const [mapTab, setMapTab] = useState<"world" | "battle">(view.encounter ? "battle" : "world");
  const [destination, setDestination] = useState<TravelTo>(null);
  const [destLabel, setDestLabel] = useState<string | null>(null);
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);
  const [targetMenu, setTargetMenu] = useState<{ token: Token; x: number; y: number } | null>(null);
  const [modal, setModal] = useState<null | "shop" | "settings" | "tv">(null);
  const [levelUpFor, setLevelUpFor] = useState<string | null>(null);
  const [armed, setArmedState] = useState<Armed | null>(null);
  const [aimPoint, setAimPoint] = useState<[number, number] | null>(null);
  const isMobile = useIsMobile();
  const [mobileTab, setMobileTab] = useState<MobileTab>("story");
  const [feedTab, setFeedTab] = useState<"live" | "story">("live");
  const spectator = view.me.role === "spectator";
  useGameEffects(view);
  const portraits = useMemo(() => {
    const m: Record<string, string | null | undefined> = {};
    for (const c of Object.values(view.characters)) m[c.id] = c.portrait_url;
    return m;
  }, [view.characters]);

  // Mark the log read up to the newest entry (once per new entry).
  const markedRef = useRef<string | number | null>(null);
  const newestId = view.log.length ? view.log[view.log.length - 1].id : null;
  const markSeen = (force = false) => {
    if (newestId === null || !view.me.user_id) return;
    if (!force && ((view.me.unseen_count ?? 0) <= 0 || markedRef.current === newestId)) return;
    markedRef.current = newestId;
    api
      .seen(gameId, newestId)
      .then(() => refresh())
      .catch(() => {
        markedRef.current = null;
      });
  };
  const setArmed = (a: Armed | null) => {
    setArmedState(a);
    setAimPoint(null);
    if (a) {
      setSelectedTargetId(null);
      setTargetMenu(null);
    }
  };

  // Keep the acting character valid.
  useEffect(() => {
    if (!actingId || !controls.includes(actingId)) setActingId(view.me.character_id && controls.includes(view.me.character_id) ? view.me.character_id : controls[0] ?? null);
  }, [controls, actingId, view.me.character_id]);

  // Auto-switch map tab when combat starts / ends (on phones, jump to the map when a fight starts).
  const hasEncounter = !!view.encounter;
  useEffect(() => {
    setMapTab(hasEncounter ? "battle" : "world");
    setSelectedTargetId(null);
    setTargetMenu(null);
    if (hasEncounter && isMobile && !spectator) setMobileTab("map");
  }, [hasEncounter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Open the shop automatically when a shop phase starts.
  const lastShopPhase = useRef<string | null>(null);
  useEffect(() => {
    if (view.phase.type === "shop" && lastShopPhase.current !== view.phase.id) {
      lastShopPhase.current = view.phase.id;
      setModal("shop");
    }
    if (view.phase.type !== "shop" && modal === "shop" && !view.shop) setModal(null);
  }, [view.phase.type, view.phase.id, view.shop, modal]);

  // Clear a travel destination once a new phase opens.
  useEffect(() => {
    setDestination(view.phase.my_submission?.travel_to ?? null);
    if (!view.phase.my_submission?.travel_to) setDestLabel(null);
  }, [view.phase.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Combat: which token I act with, and what it can do.
  const enc = view.encounter;
  const combat: CombatState = useMemo(() => {
    const empty: CombatState = { activeToken: null, canAct: false, reachable: [], targets: [], budget: null };
    if (!enc || view.phase.type !== "combat") return empty;
    const mine = enc.tokens.filter((t) => t.kind === "pc" && t.character_id && controls.includes(t.character_id));
    let active: Token | null = null;
    if (enc.mode === "classic") {
      active = mine.find((t) => t.id === enc.turn.actor_id) ?? mine.find((t) => t.character_id === actingId) ?? null;
    } else {
      active = mine.find((t) => t.character_id === actingId) ?? mine.find((t) => t.id === enc.my_token_id) ?? null;
    }
    // The server computes moves/targets/budget for the character I'm acting as (my_token_id).
    const canAct = !!active && enc.my_turn && enc.my_token_id === active.id;
    if (!active || !canAct) return { ...empty, activeToken: active };
    return { activeToken: active, canAct, reachable: enc.reachable, targets: enc.targets, budget: enc.budget };
  }, [enc, view.phase.type, controls, actingId]);

  // Tell the loader who I'm acting as, so the next view is computed for that character.
  useEffect(() => {
    onActingChange(actingId);
  }, [actingId]); // eslint-disable-line react-hooks/exhaustive-deps

  // When the character I'm acting as is done, follow the server to the next one I control that can act.
  useEffect(() => {
    if (!enc || !enc.my_turn || !enc.my_token_id) return;
    const t = enc.tokens.find((x) => x.id === enc.my_token_id);
    if (t?.character_id && t.character_id !== actingId && controls.includes(t.character_id)) setActingId(t.character_id);
  }, [enc?.my_token_id, enc?.my_turn]); // eslint-disable-line react-hooks/exhaustive-deps

  // In classic initiative, follow whichever of my characters is up.
  useEffect(() => {
    const cid = combat.activeToken?.character_id;
    if (enc?.mode === "classic" && cid && cid !== actingId && controls.includes(cid)) setActingId(cid);
  }, [combat.activeToken, enc?.mode, actingId, controls]);

  const ctx: GameCtx = {
    view,
    gameId,
    controls,
    actingId,
    acting: actingId ? view.characters[actingId] : undefined,
    setActingId: (id) => {
      setActingId(id);
      setViewedId(id);
    },
    charParam: actingId && actingId !== view.me.character_id ? actingId : undefined,
    run,
    refresh,
    openLevelUp: (id) => setLevelUpFor(id),
  };

  // Drop any half-finished aim when the turn, round or acting character changes.
  const aimKey = `${view.phase.id}|${enc?.round}|${enc?.turn.actor_id}|${enc?.turn.side}|${combat.activeToken?.id}|${combat.canAct}`;
  useEffect(() => {
    setArmedState(null);
    setAimPoint(null);
  }, [aimKey]);

  const aim: Aim | null = (() => {
    const tok = combat.activeToken;
    if (!armed || !tok || !combat.canAct) return null;
    if (armed.kind === "spell")
      return { mode: "point", origin: [tok.x, tok.y], area: armed.ps.area, range_ft: armed.ps.range_ft, point: aimPoint };
    const a = armed.action;
    if (a.target === "point") return { mode: "point", origin: [tok.x, tok.y], area: null, range_ft: a.range_ft, point: aimPoint };
    return { mode: "token", origin: [tok.x, tok.y], area: null, range_ft: a.range_ft, point: null, tokenFilter: a.target === "ally" ? "ally" : "enemy", actorKind: tok.kind };
  })();

  const selectedTarget = enc?.tokens.find((t) => t.id === selectedTargetId) ?? null;
  const canPickTravel = view.phase.type === "exploration" && (view.game.settings.input_mode !== "single" || !!view.me.is_speaker || (view.me.is_host && !view.game.settings.speaker_id));

  const composer = (() => {
    if (spectator) {
      return (
        <div className="composer spectating">
          <div className="muted">👁 You're spectating — you can follow everything, but only the players act.</div>
        </div>
      );
    }
    switch (view.phase.type) {
      case "lobby":
        return (
          <div className="composer">
            <div className="muted">
              Waiting for players. Share the invite code <code className="code">{view.game.invite_code}</code>.{" "}
              {view.me.is_host ? "Start the game when everyone's in." : "The host will start the game."}
            </div>
          </div>
        );
      case "exploration":
        return (
          <ExplorationComposer
            destination={destination}
            destinationLabel={destLabel}
            clearDestination={() => {
              setDestination(null);
              setDestLabel(null);
            }}
          />
        );
      case "roll":
        return <RollComposer />;
      case "shop":
        return <ShopComposer onOpenShop={() => setModal("shop")} />;
      case "combat":
        return enc ? (
          <CombatComposer
            combat={combat}
            selectedTarget={selectedTarget}
            clearTarget={() => {
              setSelectedTargetId(null);
              setTargetMenu(null);
            }}
            armed={aim ? armed : null}
            setArmed={setArmed}
            aimPoint={aimPoint}
          />
        ) : null;
      case "dm":
        return (
          <div className="composer">
            <div className="log-writing">
              <span className="quill">✒</span> The DM is writing… you'll be notified when it's your move.
            </div>
            {view.phase.error && <div className="error-text small">DM error: {view.phase.error}</div>}
          </div>
        );
      case "ended":
        return (
          <div className="composer">
            <div className="muted">This campaign has ended.</div>
          </div>
        );
    }
  })();

  const actingChar = actingId ? view.characters[actingId] : undefined;

  const partyEl = (
    <>
      <PartyPanel
        view={view}
        selectedId={viewedId}
        onSelect={(id) => {
          setViewedId(id);
          if (isMobile) setMobileTab("sheet");
        }}
        onNudge={view.me.is_host ? (uid) => void run(() => api.nudge(gameId, uid)) : undefined}
        controls={controls}
        onLevelUp={(id) => setLevelUpFor(id)}
      />
      <AwayControl />
    </>
  );
  const sheetEl = <SheetTabs viewedId={viewedId} onViewed={setViewedId} />;
  const feedBusy = view.dm.busy || view.phase.type === "dm";
  const feedEl = (
    <div className="feed-wrap atmos">
      <SceneBackdrop scene={view.scene} terrain={enc?.terrain ?? null} />
      <div className="feed-sky">
        <SkyStrip scene={enc ? { ...view.scene, type: enc.terrain } : view.scene} height={isMobile ? 40 : 52} />
        <div className="feed-sky-overlay">
          <span className="sky-caption">
            {view.scene ? `Day ${view.scene.day} · ${view.scene.time_of_day}${view.scene.weather ? ` · ${view.scene.weather}` : ""}` : ""}
          </span>
          <span className="row gap center">
            <AutoReadToggle />
            <SoundChip />
          </span>
        </div>
      </div>
      <div className="tabs small-tabs feed-tabs">
        <button className={feedTab === "live" ? "active" : ""} onClick={() => setFeedTab("live")}>
          Live
          {(view.me.unseen_count ?? 0) > 0 && <span className="count">{view.me.unseen_count}</span>}
        </button>
        <button className={feedTab === "story" ? "active" : ""} onClick={() => setFeedTab("story")}>
          Story so far
        </button>
      </div>
      {feedTab === "live" ? (
        <>
          <CatchUp onMarkRead={() => markSeen(true)} />
          <StoryFeed
            log={view.log}
            busy={feedBusy}
            lastSeenId={view.me.last_seen_id ?? null}
            onAtBottom={() => markSeen()}
          />
        </>
      ) : (
        <div className="story-feed">
          <StoryHistory />
        </div>
      )}
    </div>
  );

  const mapEl = (
    <section className="game-center">
            <div className="tabs map-tabs">
              <button className={mapTab === "world" ? "active" : ""} onClick={() => setMapTab("world")}>
                🗺 World map
              </button>
              <button className={mapTab === "battle" ? "active" : ""} disabled={!enc} onClick={() => setMapTab("battle")}>
                ⚔ Battle map{enc ? ` · round ${enc.round}` : ""}
              </button>
              {view.shop && (
                <button onClick={() => setModal("shop")} className="shop-tab">
                  🛒 {view.shop.name}
                </button>
              )}
            </div>
            <div className="map-area">
              {mapTab === "world" &&
                (view.world ? (
                  <WorldMap
                    world={view.world}
                    destination={destination}
                    locationName={view.location?.name}
                    interactive
                    onPick={
                      canPickTravel
                        ? (t, label) => {
                            setDestination(t);
                            setDestLabel(label);
                          }
                        : undefined
                    }
                  />
                ) : (
                  <div className="map-empty muted">The world map appears when the game starts.</div>
                ))}
              {mapTab === "battle" && enc && (
                <>
                  <BattleMap
                    encounter={enc}
                    portraits={portraits}
                    reachable={combat.canAct && (!combat.budget || combat.budget.move_ft > 0) ? combat.reachable : []}
                    targets={combat.canAct ? combat.targets : []}
                    actorTokenId={enc.turn.actor_id ?? combat.activeToken?.id ?? null}
                    selectedTargetId={selectedTargetId}
                    interactive={!spectator}
                    onMove={(x, y) => void run(() => api.move(gameId, x, y, ctx.charParam))}
                    onTarget={(tok, at) => {
                      setSelectedTargetId(tok.id);
                      setTargetMenu({ token: tok, x: at.x, y: at.y });
                    }}
                    aim={aim}
                    onAimPoint={(x, y) => setAimPoint([x, y])}
                    onAimToken={(tok) => {
                      if (armed?.kind !== "feature") return;
                      const a = armed.action;
                      void run(() => api.feature(gameId, a.id, { target_id: tok.id }, ctx.charParam)).then((ok) => ok && setArmed(null));
                    }}
                  />
                  {targetMenu && actingChar && (
                    <TargetMenu
                      token={targetMenu.token}
                      x={targetMenu.x}
                      y={targetMenu.y}
                      combat={combat}
                      onClose={() => setTargetMenu(null)}
                      onAttack={(attackId) =>
                        void run(() => api.attack(gameId, attackId, targetMenu.token.id, ctx.charParam)).then(() => {
                          setTargetMenu(null);
                          setSelectedTargetId(null);
                        })
                      }
                      onCast={(spell) =>
                        void run(() => api.cast(gameId, spell, targetMenu.token.id, undefined, ctx.charParam)).then(() => {
                          setTargetMenu(null);
                          setSelectedTargetId(null);
                        })
                      }
                    />
                  )}
                </>
              )}
            </div>
    </section>
  );

  const mobileTabs: { id: MobileTab; label: string; icon: string; badge?: number | string }[] = [
    { id: "story", label: "Story", icon: "📜", badge: (view.me.unseen_count ?? 0) > 0 ? view.me.unseen_count : undefined },
    { id: "map", label: enc ? "Battle" : "Map", icon: enc ? "⚔" : "🗺", badge: combat.canAct ? "!" : undefined },
    { id: "party", label: "Party", icon: "👥" },
    {
      id: "sheet",
      label: "Sheet",
      icon: "📋",
      badge: controls.some((id) => view.characters[id]?.pending_level_up) ? "✦" : undefined,
    },
  ];

  return (
    <GameContext.Provider value={ctx}>
      <div className={`game-screen atmos ${isMobile ? "mobile" : ""}`}>
        <SceneBackdrop scene={view.scene} terrain={enc?.terrain ?? null} subtle />
        <GameHeader onSettings={() => setModal("settings")} onTv={() => setModal("tv")} />
        {view.phase.error && (
          <div className="banner error">
            The DM ran into a problem: {view.phase.error} {view.me.is_host ? "— use Retry DM in the header." : "— the host can retry."}
          </div>
        )}
        {spectator && <div className="banner spectating">👁 Spectating — you can watch everything, but can't act.</div>}
        {isMobile ? (
          <>
            <div className={`mobile-body mtab-${mobileTab}`}>
              {mobileTab === "story" && <section className="game-right">{feedEl}</section>}
              {mobileTab === "map" && mapEl}
              {mobileTab === "party" && <aside className="game-left">{partyEl}</aside>}
              {mobileTab === "sheet" && <aside className="game-left">{sheetEl}</aside>}
            </div>
            <div className="mobile-composer">{composer}</div>
            <nav className="mobile-tabbar">
              {mobileTabs.map((t) => (
                <button key={t.id} className={mobileTab === t.id ? "active" : ""} onClick={() => setMobileTab(t.id)}>
                  <span className="mt-icon">{t.icon}</span>
                  <span className="mt-label">{t.label}</span>
                  {t.badge !== undefined && <span className="mt-badge">{t.badge}</span>}
                </button>
              ))}
            </nav>
          </>
        ) : (
          <div className="game-grid">
            <aside className="game-left">
              {partyEl}
              {sheetEl}
            </aside>
            {mapEl}
            <section className="game-right">
              {feedEl}
              {composer}
            </section>
          </div>
        )}

        {modal === "shop" && <ShopModal onClose={() => setModal(null)} />}
        {modal === "settings" && <HostSettingsModal onClose={() => setModal(null)} />}
        {modal === "tv" && <TvLinkModal onClose={() => setModal(null)} />}
        {levelUpFor && view.characters[levelUpFor] && (
          <LevelUpModal
            character={view.characters[levelUpFor]}
            submit={async (body) => {
              const r = await api.levelUp(gameId, levelUpFor !== view.me.character_id ? { ...body, character_id: levelUpFor } : body);
              refresh();
              return r;
            }}
            onClose={() => setLevelUpFor(null)}
          />
        )}
        {toast && (
          <div className="toast" onClick={clearToast}>
            {toast}
          </div>
        )}
        <DiceRoller />
      </div>
    </GameContext.Provider>
  );
}

function TargetMenu({
  token,
  x,
  y,
  combat,
  onClose,
  onAttack,
  onCast,
}: {
  token: Token;
  x: number;
  y: number;
  combat: CombatState;
  onClose: () => void;
  onAttack: (id: string) => void;
  onCast: (index: string) => void;
}) {
  const { view, acting } = useGame();
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: Math.max(8, x + 12), top: Math.max(8, y - 10) });
  // Keep the menu inside the map: flip to the left of the cursor near the right edge, lift it near the bottom.
  useLayoutEffect(() => {
    const el = menuRef.current;
    const parent = el?.offsetParent as HTMLElement | null;
    if (!el || !parent) return;
    let left = x + 12;
    let top = y - 10;
    if (left + el.offsetWidth > parent.clientWidth - 8) left = x - 12 - el.offsetWidth;
    if (top + el.offsetHeight > parent.clientHeight - 8) top = parent.clientHeight - 8 - el.offsetHeight;
    setPos({ left: Math.max(8, left), top: Math.max(8, top) });
  }, [x, y]);
  const t = combat.targets.find((z) => z.token_id === token.id);
  if (!t || !acting) return null;
  const actionUsed = combat.budget ? !combat.budget.action : false;
  const spells = [...(acting.spellcasting?.cantrips ?? []), ...(acting.spellcasting?.spells ?? [])];
  return (
    <div className="target-menu" ref={menuRef} style={pos} onMouseLeave={onClose}>
      <div className="target-menu-head">
        <strong>{token.name}</strong>
        <button className="icon-btn tiny" onClick={onClose}>
          ✕
        </button>
      </div>
      {actionUsed && <div className="muted small">Action used this turn.</div>}
      {t.attack_ids.map((id) => {
        const a = acting.attacks.find((z) => z.id === id);
        if (!a) return null;
        return (
          <button key={id} className="menu-item" disabled={actionUsed} onClick={() => onAttack(id)}>
            ⚔ {a.name} <span className="muted small">{a.to_hit >= 0 ? "+" : ""}{a.to_hit} · {a.damage}</span>
          </button>
        );
      })}
      {t.spell_indexes.map((idx) => {
        const s = spells.find((z) => z.index === idx);
        if (!s) return null;
        return (
          <button key={idx} className="menu-item" disabled={actionUsed} onClick={() => onCast(idx)}>
            ✧ {s.name} <span className="muted small">{s.level === 0 ? "cantrip" : `L${s.level}`}</span>
          </button>
        );
      })}
      {t.attack_ids.length === 0 && t.spell_indexes.length === 0 && <div className="muted small">Nothing reaches {token.name} from here.</div>}
      <div className="muted small">{view.encounter?.tokens.find((z) => z.id === token.id)?.hp_state}</div>
    </div>
  );
}
