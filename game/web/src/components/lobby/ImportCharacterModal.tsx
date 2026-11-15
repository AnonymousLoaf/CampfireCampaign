import { useState } from "react";
import { api } from "../../api/client";
import type { CharacterView, Issue } from "../../api/types";
import Modal from "../Modal";
import ErrorText, { useAction } from "../ErrorText";
import CharacterCard from "./CharacterCard";

export default function ImportCharacterModal({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [source, setSource] = useState("");
  const [result, setResult] = useState<{ character: CharacterView; issues: Issue[] } | null>(null);
  const [run, busy, error] = useAction(async () => {
    const res = await api.importCharacter(source.trim());
    setResult(res);
    onImported();
  });

  return (
    <Modal
      title="Import from D&D Beyond"
      onClose={onClose}
      footer={
        result ? (
          <button className="btn primary" onClick={onClose}>
            Done
          </button>
        ) : (
          <>
            <button className="btn ghost" onClick={onClose}>
              Cancel
            </button>
            <button className="btn primary" disabled={busy || !source.trim()} onClick={() => void run()}>
              {busy ? "Importing…" : "Import"}
            </button>
          </>
        )
      }
    >
      {!result ? (
        <div className="stack">
          <p className="muted small">
            Paste your character's link (e.g. <code>https://www.dndbeyond.com/characters/12345678</code>). The character's
            sharing must be set to <strong>Public</strong> on D&amp;D Beyond (Character → Manage → Sharing). If it's
            private, open the character JSON in a signed-in browser and paste the whole JSON text here instead.
          </p>
          <textarea rows={6} value={source} onChange={(e) => setSource(e.target.value)} placeholder="Link, id, or character JSON" />
          <p className="muted small">D&amp;D Beyond has no official API, so this may stop working without notice.</p>
          <ErrorText error={error} />
        </div>
      ) : (
        <div className="stack">
          <CharacterCard c={result.character} />
          {result.issues.length === 0 ? (
            <div className="ok-text">No problems found — ready to play.</div>
          ) : (
            <div>
              <div className="label">Fix these on D&amp;D Beyond before you play:</div>
              <ul className="issue-list">
                {result.issues.map((i, n) => (
                  <li key={n}>
                    <strong>{i.issue}</strong>
                    <div className="muted small">{i.fix}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
