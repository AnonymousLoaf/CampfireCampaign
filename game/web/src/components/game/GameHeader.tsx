import { useState, type ReactNode } from "react";
import { api } from "../../api/client";
import { navigate } from "../../router";
import { PHASE_LABEL, formatCountdown, useNow } from "../../util/format";
import { useGame } from "./gameContext";
import InviteByEmail from "./InviteByEmail";
import PlotPicker from "./PlotPicker";

export default function GameHeader({ onSettings, onTv, extra }: { onSettings: () => void; onTv: () => void; extra?: ReactNode }) {
  const { view, gameId, run } = useGame();
  const now = useNow(1000);
  const [liveMenu, setLiveMenu] = useState(false);
  const [more, setMore] = useState(false); // phones: the header's extra buttons
  const p = view.phase;
  const s = view.game.settings;
  const host = view.me.is_host;
  const cd = formatCountdown(p.deadline, now);
  const busy = view.dm.busy || p.type === "dm";

  return (
    <header className="game-header">
      <button className="icon-btn" title="Back to lobby" onClick={() => navigate({ name: "lobby" })}>
        ←
      </button>
      <div className="game-title">
        <h1>{view.game.name}</h1>
        <div className="muted small">
          {view.location?.name && <>📍 {view.location.name} · </>}
          {view.scene && (
            <>
              Day {view.scene.day}, {view.scene.time_of_day}
              {view.scene.weather ? ` · ${view.scene.weather}` : ""}
            </>
          )}
        </div>
      </div>

      <div className="phase-cluster">
        <span className={`phase-pill ${p.type}`}>{PHASE_LABEL[p.type] ?? p.type}</span>
        {p.deadline && p.type !== "dm" && p.type !== "lobby" && (
          <span className={`countdown ${cd === "overdue" ? "overdue" : ""}`} title={new Date(p.deadline).toLocaleString()}>
            ⏳ {cd}
          </span>
        )}
        {s.live && <span className="live-pill">● LIVE</span>}
        {s.input_mode === "single" && <span className="badge">One speaker</span>}
        {busy && (
          <span className="dm-busy">
            <span className="spinner tiny" /> The DM is writing…
          </span>
        )}
      </div>

      <button className="icon-btn header-more" aria-expanded={more} title="More" onClick={() => setMore((v) => !v)}>
        ⋯
      </button>
      <div className={`header-actions ${more ? "open" : ""}`}>
        {view.game.status === "lobby" && (
          <span className="invite">
            Invite code <code className="code big">{view.game.invite_code}</code>
          </span>
        )}
        {view.game.status === "lobby" && view.me.role !== "spectator" && <InviteByEmail gameId={gameId} />}
        {view.game.status === "lobby" && (host ? <PlotPicker /> : view.has_plot && <span className="badge" title="The host wrote this campaign's story. Only the DM knows it.">📜 Custom plot</span>)}
        {host && view.game.status === "lobby" && (
          <button className="btn primary keep" onClick={() => void run(() => api.start(gameId))}>
            Start game
          </button>
        )}
        {host && view.game.status === "active" && (
          <div className="live-toggle">
            {s.live ? (
              <button className="btn live-on" onClick={() => void run(() => api.patchSettings(gameId, { live: false }))}>
                End live session
              </button>
            ) : (
              <button className="btn live" onClick={() => setLiveMenu((v) => !v)}>
                ● Start live session
              </button>
            )}
            {liveMenu && !s.live && (
              <div className="popover" onMouseLeave={() => setLiveMenu(false)}>
                <div className="small muted">Everyone's together now — rounds use a {s.live_timer_minutes}-minute timer.</div>
                <button
                  className="btn small"
                  onClick={() => {
                    setLiveMenu(false);
                    void run(() => api.patchSettings(gameId, { live: true }));
                  }}
                >
                  Start — everyone acts
                </button>
                <button
                  className="btn small"
                  onClick={() => {
                    setLiveMenu(false);
                    void run(() => api.patchSettings(gameId, { live: true, input_mode: "single" }));
                  }}
                >
                  Start — one table speaker
                </button>
              </div>
            )}
          </div>
        )}
        {host && p.error && (
          <button className="btn danger small keep" onClick={() => void run(() => api.retryDm(gameId))} title={p.error}>
            Retry DM
          </button>
        )}
        {host && view.game.status === "active" && ["exploration", "roll", "shop", "combat"].includes(p.type) && (
          <button
            className="btn ghost small"
            title="Resolve this phase now; the timeout rule applies to anyone who hasn't acted"
            onClick={() => {
              if (window.confirm("Resolve this phase now? Anyone who hasn't acted is handled by the timeout rule.")) void run(() => api.forceResolve(gameId));
            }}
          >
            Force resolve
          </button>
        )}
        {extra}
        {host && (
          <>
            <button className="btn ghost small" onClick={onTv} title="Big-screen view for a TV">
              📺 TV view
            </button>
            <button className="icon-btn" onClick={onSettings} title="Game settings">
              ⚙<span className="menu-label"> Settings</span>
            </button>
          </>
        )}
      </div>
    </header>
  );
}
