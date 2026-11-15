import { useState } from "react";
import { api } from "../../api/client";
import type { Me } from "../../api/types";
import ErrorText, { useAction } from "../ErrorText";

export default function SettingsPanel({ me, onMeChange }: { me: Me; onMeChange: (m: Me) => void }) {
  const [key, setKey] = useState("");
  const [save, saving, saveErr] = useAction(async () => {
    onMeChange(await api.setApiKey(key.trim()));
    setKey("");
  });
  const [remove, removing, removeErr] = useAction(async () => {
    onMeChange(await api.removeApiKey());
  });

  return (
    <section className="panel settings-panel">
      <div className="panel-head">
        <h2>Settings</h2>
      </div>
      <h3>Claude API key</h3>
      <p className="muted small">
        Games you host can use this key to run the AI Dungeon Master. It's stored encrypted on the server and never shown
        again — only the last 4 characters.
      </p>
      {me.has_api_key ? (
        <div className="row gap center">
          <span className="key-chip">•••• {me.api_key_last4}</span>
          <button className="btn ghost small danger" disabled={removing} onClick={() => void remove()}>
            Remove key
          </button>
        </div>
      ) : (
        <div className="muted small">No key saved.</div>
      )}
      <form
        className="row gap"
        onSubmit={(e) => {
          e.preventDefault();
          if (key.trim()) void save();
        }}
      >
        <input
          type="password"
          placeholder={me.has_api_key ? "Replace with a new key" : "sk-ant-…"}
          value={key}
          onChange={(e) => setKey(e.target.value)}
          className="grow"
          autoComplete="off"
        />
        <button className="btn" disabled={saving || !key.trim()}>
          Save
        </button>
      </form>
      <ErrorText error={saveErr || removeErr} />
    </section>
  );
}
