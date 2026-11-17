import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Me, Meta } from "../../api/types";
import ErrorText, { useAction } from "../ErrorText";
import { disablePush, enablePush, pushSubscribed, pushSupported } from "../../util/push";
import { AudioSettings } from "../atmosphere/AudioControls";

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

      <XaiKeySettings me={me} onMeChange={onMeChange} />

      <NotificationSettings me={me} onMeChange={onMeChange} />

      <h3>Sound &amp; narration</h3>
      <p className="muted small">
        Ambience and effects are synthesized in your browser; narration is read by your browser's built-in voices. Nothing
        is downloaded or sent anywhere.
      </p>
      <AudioSettings />
    </section>
  );
}

function NotificationSettings({ me, onMeChange }: { me: Me; onMeChange: (m: Me) => void }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [email, setEmail] = useState(me.email ?? "");
  const [remind, setRemind] = useState(me.notify?.remind_minutes ?? 60);
  const [subscribed, setSubscribed] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const supported = pushSupported();

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
    void pushSubscribed().then(setSubscribed);
  }, []);

  useEffect(() => {
    setEmail(me.email ?? "");
    setRemind(me.notify?.remind_minutes ?? 60);
  }, [me.email, me.notify?.remind_minutes]);

  const emailAvail = meta?.email_available ?? false;
  const pushAvail = meta?.push_available ?? false;
  const notify = me.notify ?? { email: false, push: false, remind_minutes: 60 };

  const [patch, patching, patchErr] = useAction(async (p: Parameters<typeof api.setNotifications>[0]) => {
    onMeChange(await api.setNotifications(p));
    setMsg("Saved.");
  });
  const [enable, enabling, enableErr] = useAction(async () => {
    await enablePush();
    setSubscribed(true);
    if (!notify.push) onMeChange(await api.setNotifications({ notify_push: true }));
    setMsg("This device will get notifications.");
  });
  const [disable, disabling, disableErr] = useAction(async () => {
    await disablePush();
    setSubscribed(false);
    setMsg("This device won't get notifications any more.");
  });
  const [test, testing, testErr] = useAction(async () => {
    await api.pushTest();
    setMsg("Test sent — it should arrive in a few seconds.");
  });

  return (
    <div className="notify-settings">
      <h3>Notifications</h3>
      <p className="muted small">
        Get told when it's your move, when the DM replies, and shortly before your deadline. Nothing is sent during a live
        session.
      </p>

      <div className={`notify-block ${pushAvail ? "" : "disabled"}`}>
        <div className="row-between">
          <strong>Push notifications</strong>
          <label className="toggle">
            <input
              type="checkbox"
              checked={notify.push}
              disabled={!pushAvail || patching}
              onChange={(e) => void patch({ notify_push: e.target.checked })}
            />
            <span>{notify.push ? "On" : "Off"}</span>
          </label>
        </div>
        {!pushAvail && <div className="muted small">The server can't send push notifications (push support isn't installed).</div>}
        {pushAvail && !supported && (
          <div className="muted small">
            This browser can't receive push here. Push needs a secure connection: open the game over HTTPS, or as
            http://localhost on the computer running the server.
          </div>
        )}
        {pushAvail && supported && (
          <div className="row gap wrap">
            {subscribed ? (
              <>
                <span className="badge green">This device is subscribed</span>
                <button className="btn small" disabled={testing} onClick={() => void test()}>
                  Send test
                </button>
                <button className="btn ghost small" disabled={disabling} onClick={() => void disable()}>
                  Turn off on this device
                </button>
              </>
            ) : (
              <button className="btn primary small" disabled={enabling} onClick={() => void enable()}>
                Enable notifications on this device
              </button>
            )}
          </div>
        )}
      </div>

      <div className={`notify-block ${emailAvail ? "" : "disabled"}`}>
        <div className="row-between">
          <strong>Email</strong>
          <label className="toggle">
            <input
              type="checkbox"
              checked={notify.email}
              disabled={!emailAvail || patching || !(me.email || email)}
              onChange={(e) => void patch({ notify_email: e.target.checked, ...(email !== (me.email ?? "") ? { email } : {}) })}
            />
            <span>{notify.email ? "On" : "Off"}</span>
          </label>
        </div>
        {!emailAvail && <div className="muted small">Email isn't set up on this server (the host needs to configure SMTP).</div>}
        <form
          className="row gap"
          onSubmit={(e) => {
            e.preventDefault();
            void patch({ email: email.trim() || null });
          }}
        >
          <input
            type="email"
            className="grow"
            placeholder="you@example.com"
            value={email}
            disabled={!emailAvail}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button className="btn small" disabled={!emailAvail || patching || email === (me.email ?? "")}>
            Save email
          </button>
        </form>
      </div>

      <div className={`notify-block ${pushAvail ? "" : "disabled"}`}>
        <div className="row-between">
          <strong>Chat messages</strong>
          <label className="toggle">
            <input
              type="checkbox"
              checked={!!notify.chat}
              disabled={!pushAvail || patching}
              onChange={(e) => void patch({ notify_chat: e.target.checked })}
            />
            <span>{notify.chat ? "On" : "Off"}</span>
          </label>
        </div>
        <div className="muted small">
          A push when someone posts in a game's chat while you don't have it open — at most one every 10 minutes per game.
        </div>
      </div>

      <div className="notify-block">
        <label className="row gap center wrap">
          <span>Remind me</span>
          <select
            value={remind}
            onChange={(e) => {
              const v = Number(e.target.value);
              setRemind(v);
              void patch({ remind_minutes: v });
            }}
          >
            {[0, 15, 30, 60, 120, 240, 720].map((m) => (
              <option key={m} value={m}>
                {m === 0 ? "never" : m < 60 ? `${m} minutes` : `${m / 60} hour${m > 60 ? "s" : ""}`}
              </option>
            ))}
          </select>
          <span>before my deadline</span>
        </label>
      </div>
      {msg && <div className="small muted">{msg}</div>}
      <ErrorText error={patchErr || enableErr || disableErr || testErr} />
    </div>
  );
}

function XaiKeySettings({ me, onMeChange }: { me: Me; onMeChange: (m: Me) => void }) {
  const [key, setKey] = useState("");
  const [save, saving, saveErr] = useAction(async () => {
    onMeChange(await api.setXaiKey(key.trim()));
    setKey("");
  });
  const [remove, removing, removeErr] = useAction(async () => {
    onMeChange(await api.removeXaiKey());
  });
  return (
    <>
      <h3>Grok (xAI) API key</h3>
      <p className="muted small">
        Games you host use it to paint scenes, monsters and NPCs, and you can paint character portraits with it. Stored
        encrypted on the server and never shown again, only the last 4 characters.
      </p>
      {me.has_xai_key ? (
        <div className="row gap center">
          <span className="key-chip">•••• {me.xai_key_last4}</span>
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
          placeholder={me.has_xai_key ? "Replace with a new key" : "xai-…"}
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
    </>
  );
}
