import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { CharacterView, GameSummary, Me, Meta } from "../api/types";
import { subscribe } from "../api/ws";
import { navigate } from "../router";
import { PHASE_LABEL, formatCountdown, useNow } from "../util/format";
import ErrorText from "../components/ErrorText";
import CreateGameModal from "../components/lobby/CreateGameModal";
import JoinGameModal from "../components/lobby/JoinGameModal";
import ImportCharacterModal from "../components/lobby/ImportCharacterModal";
import CharacterCard from "../components/lobby/CharacterCard";
import LevelUpModal from "../components/LevelUpModal";
import SettingsPanel from "../components/lobby/SettingsPanel";
import MyContentPanel from "../components/custom/MyContentPanel";

export default function LobbyScreen({
  me,
  onMeChange,
  onLogout,
}: {
  me: Me;
  onMeChange: (m: Me) => void;
  onLogout: () => void;
}) {
  const [games, setGames] = useState<GameSummary[] | null>(null);
  const [characters, setCharacters] = useState<CharacterView[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<null | "create" | "join" | "import">(null);
  const [levelUpFor, setLevelUpFor] = useState<string | null>(null);
  const levelUpChar = levelUpFor ? characters?.find((c) => c.id === levelUpFor) : undefined;
  const now = useNow(1000);

  const load = useCallback(async () => {
    try {
      const [g, c, m] = await Promise.all([api.games(), api.characters(), api.meta()]);
      setGames(g);
      setCharacters(c);
      setMeta(m);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
    return subscribe("lobby", () => void load());
  }, [load]);

  const deleteCharacter = async (id: string) => {
    if (!window.confirm("Delete this character? This can't be undone.")) return;
    try {
      await api.deleteCharacter(id);
      void load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const freeCharacters = (characters ?? []).filter((c) => !c.game_id);

  return (
    <div className="lobby">
      <header className="topbar">
        <div className="brand-inline">
          <span className="brand-sigil">⚔</span> Async D&amp;D
        </div>
        <div className="topbar-right">
          <span className="muted">Signed in as {me.display_name}</span>
          <button className="btn ghost small" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </header>

      <ErrorText error={error} />

      <main className="lobby-grid">
        <section className="panel">
          <div className="panel-head">
            <h2>Your games</h2>
            <div className="row gap">
              <button className="btn" onClick={() => setModal("join")}>
                Join with code
              </button>
              <button className="btn primary" onClick={() => setModal("create")}>
                New game
              </button>
            </div>
          </div>
          {games === null ? (
            <div className="spinner" />
          ) : games.length === 0 ? (
            <div className="empty">
              No games yet. Start one and send your friends the invite code, or join theirs.
            </div>
          ) : (
            <ul className="game-list">
              {games.map((g) => (
                <li key={g.id} className={`game-row ${g.my_turn ? "my-turn" : ""}`} onClick={() => navigate({ name: "game", id: g.id })}>
                  <div className="game-row-main">
                    <div className="game-name">
                      {g.name}
                      {g.my_turn && <span className="badge gold">Your move</span>}
                    </div>
                    <div className="muted small">
                      Hosted by {g.host_name} · {g.player_count}/{g.max_players} players
                      {g.status === "lobby" && (
                        <>
                          {" "}
                          · invite code <code className="code">{g.invite_code}</code>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="game-row-side">
                    <span className={`status-pill ${g.status}`}>
                      {g.status === "active" ? PHASE_LABEL[g.phase_type ?? "exploration"] ?? g.phase_type : g.status === "lobby" ? "Lobby" : "Ended"}
                    </span>
                    {g.status === "active" && g.deadline && (
                      <span className={`countdown ${formatCountdown(g.deadline, now) === "overdue" ? "overdue" : ""}`}>
                        ⏳ {formatCountdown(g.deadline, now)}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Your characters</h2>
            <div className="row gap">
              <button className="btn" onClick={() => setModal("import")}>
                Import from D&amp;D Beyond
              </button>
              <button className="btn primary" onClick={() => navigate({ name: "create-character" })}>
                Create character
              </button>
            </div>
          </div>
          {characters === null ? (
            <div className="spinner" />
          ) : characters.length === 0 ? (
            <div className="empty">You need a character to create or join a game.</div>
          ) : (
            <div className="char-grid">
              {characters.map((c) => (
                <CharacterCard
                  key={c.id}
                  c={c}
                  onDelete={c.game_id ? undefined : () => deleteCharacter(c.id)}
                  onLevelUp={c.game_id ? undefined : () => setLevelUpFor(c.id)}
                  onChanged={() => void load()}
                />
              ))}
            </div>
          )}
        </section>

        <MyContentPanel />

        <SettingsPanel me={me} onMeChange={(m) => { onMeChange(m); void load(); }} />
      </main>

      {levelUpChar && (
        <LevelUpModal
          character={levelUpChar}
          submit={async (body) => {
            const r = await api.levelUpCharacter(levelUpChar.id, body);
            void load();
            return r;
          }}
          onClose={() => setLevelUpFor(null)}
        />
      )}
      {modal === "create" && meta && (
        <CreateGameModal
          meta={meta}
          characters={freeCharacters}
          onClose={() => setModal(null)}
          onCreated={(id) => navigate({ name: "game", id })}
        />
      )}
      {modal === "join" && (
        <JoinGameModal characters={freeCharacters} onClose={() => setModal(null)} onJoined={(id) => navigate({ name: "game", id })} />
      )}
      {modal === "import" && (
        <ImportCharacterModal
          onClose={() => setModal(null)}
          onImported={() => {
            void load();
          }}
        />
      )}
    </div>
  );
}
