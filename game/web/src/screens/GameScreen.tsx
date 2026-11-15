import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { GameView, Me, TravelTo } from "../api/types";
import { subscribe } from "../api/ws";
import { navigate } from "../router";
import { GameContext, controlsOf, type GameCtx } from "../components/game/gameContext";
import GameHeader from "../components/game/GameHeader";
import PartyPanel from "../components/game/PartyPanel";
import StoryFeed from "../components/game/StoryFeed";
import SheetTabs from "../components/game/SheetTabs";
import ShopModal from "../components/game/ShopModal";
import HostSettingsModal from "../components/game/HostSettingsModal";
import TvLinkModal from "../components/game/TvLinkModal";
import { CombatComposer, CombatTurnBanner, ExplorationComposer, RollComposer, ShopComposer } from "../components/game/Composer";
import WorldMap from "../maps/WorldMap";
import BattleMap from "../maps/BattleMap";
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
  const [modal, setModal] = useState<null | "shop" | "settings" | "tv">(null);
  const [levelUpFor, setLevelUpFor] = useState<string | null>(null);
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
  // Keep the acting character valid.
  useEffect(() => {
    if (!actingId || !controls.includes(actingId)) setActingId(view.me.character_id && controls.includes(view.me.character_id) ? view.me.character_id : controls[0] ?? null);
  }, [controls, actingId, view.me.character_id]);

  // Auto-switch map tab when combat starts / ends (on phones, jump to the map when a fight starts).
  const hasEncounter = !!view.encounter;
  useEffect(() => {
    setMapTab(hasEncounter ? "battle" : "world");
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

  // Combat is typed: whoever's turn it is describes what they do. Track only whose turn it is.
  const enc = view.encounter;
  const myTurn = !!enc && view.phase.type === "combat" && enc.my_turn && !!enc.my_token_id;

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

  // Individual initiative: follow whichever of my characters is up.
  useEffect(() => {
    const cid = enc?.tokens.find((t) => t.id === enc.turn.actor_id)?.character_id;
    if (cid && cid !== actingId && controls.includes(cid)) setActingId(cid);
  }, [enc?.turn.actor_id, actingId, controls]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // My own token on the battle map (for "N ft from you" on the info card).
  const viewerTokenId = enc?.tokens.find((t) => t.kind === "pc" && t.character_id === (actingId ?? view.me.character_id))?.id ?? null;
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
        return enc ? <CombatComposer /> : null;
      case "dm":
        return (
          <div className="composer">
            {enc && <CombatTurnBanner writing />}
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
                <BattleMap encounter={enc} portraits={portraits} actorTokenId={enc.turn.actor_id} viewerTokenId={viewerTokenId} interactive />
              )}
            </div>
    </section>
  );

  const mobileTabs: { id: MobileTab; label: string; icon: string; badge?: number | string }[] = [
    { id: "story", label: "Story", icon: "📜", badge: (view.me.unseen_count ?? 0) > 0 ? view.me.unseen_count : undefined },
    { id: "map", label: enc ? "Battle" : "Map", icon: enc ? "⚔" : "🗺", badge: myTurn ? "!" : undefined },
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
