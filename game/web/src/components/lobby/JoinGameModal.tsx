import { useState } from "react";
import { api } from "../../api/client";
import type { CharacterView } from "../../api/types";
import Modal from "../Modal";
import ErrorText, { useAction } from "../ErrorText";
import CharacterPicker from "./CharacterPicker";

export default function JoinGameModal({
  characters,
  initialCode,
  onClose,
  onJoined,
}: {
  characters: CharacterView[];
  initialCode?: string;
  onClose: () => void;
  onJoined: (id: string) => void;
}) {
  const [code, setCode] = useState(initialCode ?? "");
  const [mode, setMode] = useState<"play" | "watch">("play");
  const [charId, setCharId] = useState(characters[0]?.id ?? "");
  const [join, busy, error] = useAction(async () => {
    const res = mode === "watch" ? await api.spectateGame(code.trim()) : await api.joinGame(code.trim(), charId);
    onJoined(res.id);
  });

  return (
    <Modal
      title="Join a game"
      onClose={onClose}
      footer={
        <>
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn primary"
            disabled={busy || !code.trim() || (mode === "play" && !charId)}
            onClick={() => void join()}
          >
            {mode === "watch" ? "Watch" : "Join"}
          </button>
        </>
      }
    >
      <div className="stack">
        <label>
          Invite code
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. K7Q2XD" autoFocus />
        </label>
        <div className="seg">
          <button className={mode === "play" ? "active" : ""} onClick={() => setMode("play")}>
            Play a character
          </button>
          <button className={mode === "watch" ? "active" : ""} onClick={() => setMode("watch")}>
            Just watch
          </button>
        </div>
        {mode === "play" ? (
          <>
            <CharacterPicker characters={characters} value={charId} onChange={setCharId} />
            <p className="muted small">Your character must use the same rules (2014 or 2024) as the game.</p>
          </>
        ) : (
          <p className="muted small">
            Spectators see the whole game — story, maps and the party — but can't act. No character needed.
          </p>
        )}
        <ErrorText error={error} />
      </div>
    </Modal>
  );
}
