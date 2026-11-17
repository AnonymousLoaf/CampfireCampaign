import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Me } from "../api/types";
import ErrorText from "../components/ErrorText";

export default function AuthScreen({ onSignedIn }: { onSignedIn: (me: Me) => void }) {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me =
        tab === "login"
          ? await api.login(username.trim(), password)
          : await api.register(username.trim(), password, displayName.trim() || username.trim());
      onSignedIn(me);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="brand">
          <span className="brand-sigil">⚔</span>
          <h1>Campfire Campaign</h1>
          <p className="muted">A campaign that keeps going — play together, or on your own time.</p>
        </div>
        <div className="tabs">
          <button className={tab === "login" ? "active" : ""} onClick={() => setTab("login")}>
            Sign in
          </button>
          <button className={tab === "register" ? "active" : ""} onClick={() => setTab("register")}>
            Create account
          </button>
        </div>
        <form onSubmit={submit} className="stack">
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
          </label>
          {tab === "register" && (
            <label>
              Display name
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="What the party calls you"
              />
            </label>
          )}
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={tab === "login" ? "current-password" : "new-password"}
              required
            />
          </label>
          <ErrorText error={error} />
          <button className="btn primary" disabled={busy}>
            {busy ? "…" : tab === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
