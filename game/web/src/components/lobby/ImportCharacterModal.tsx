import { useState } from "react";
import { api } from "../../api/client";
import type { CharacterView, Issue, Ruleset } from "../../api/types";
import { KIND_LABEL } from "../custom/MyContentPanel";
import Modal from "../Modal";
import ErrorText, { useAction } from "../ErrorText";
import CharacterCard from "./CharacterCard";

export default function ImportCharacterModal({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [source, setSource] = useState("");
  const [result, setResult] = useState<{ character: CharacterView; issues: Issue[]; ruleset?: Ruleset } | null>(null);
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
          {(() => {
            const rs = result.ruleset ?? result.character.ruleset ?? "2014";
            return (
              <div className="import-ruleset small">
                Imported as <span className={`ruleset-badge r${rs}`}>{rs}</span>{" "}
                <span className="muted">
                  {rs === "2024" ? "rules (5.5 / SRD 5.2) — it can join 2024 games." : "rules (SRD 5.1) — it can join 2014 games."}
                </span>
              </div>
            );
          })()}
          {(result.character.custom?.length ?? 0) > 0 && (
            <div>
              <div className="label">Kept as custom entries (the DM reads their text):</div>
              <ul className="import-custom">
                {result.character.custom!.map((x) => (
                  <li key={x.entry_id}>
                    <strong>{x.name}</strong> <span className="badge tiny custom-tag">{KIND_LABEL[x.kind] ?? x.kind}</span>
                  </li>
                ))}
              </ul>
              <p className="muted tiny-text">These came from your D&amp;D Beyond sheet and aren't in the game's rules tables. They're private to you.</p>
            </div>
          )}
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
