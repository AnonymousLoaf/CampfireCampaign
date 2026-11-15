import { useState } from "react";
import { api } from "../../api/client";
import type { CharacterView } from "../../api/types";
import Modal from "../Modal";
import ErrorText, { useAction } from "../ErrorText";
import CharacterPicker from "./CharacterPicker";

export default function JoinGameModal({
  characters,
  onClose,
  onJoined,
}: {
  characters: CharacterView[];
  onClose: () => void;
  onJoined: (id: string) => void;
}) {
  const [code, setCode] = useState("");
  const [charId, setCharId] = useState(characters[0]?.id ?? "");
  const [join, busy, error] = useAction(async () => {
    const res = await api.joinGame(code.trim(), charId);
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
          <button className="btn primary" disabled={busy || !code.trim() || !charId} onClick={() => void join()}>
            Join
          </button>
        </>
      }
    >
      <div className="stack">
        <label>
          Invite code
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. K7Q2XD" autoFocus />
        </label>
        <CharacterPicker characters={characters} value={charId} onChange={setCharId} />
        <ErrorText error={error} />
      </div>
    </Modal>
  );
}
