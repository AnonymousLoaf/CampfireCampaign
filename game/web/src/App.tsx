import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api/client";
import type { Me } from "./api/types";
import { navigate, useRoute } from "./router";
import AuthScreen from "./screens/AuthScreen";
import LobbyScreen from "./screens/LobbyScreen";
import CharacterCreator from "./screens/CharacterCreator";
import GameScreen from "./screens/GameScreen";
import TvScreen from "./screens/TvScreen";

export default function App() {
  const route = useRoute();
  // The TV view needs no login.
  if (route.name === "tv") return <TvScreen key={route.token} token={route.token} />;
  return <SignedInApp />;
}

function SignedInApp() {
  const route = useRoute();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);

  const loadMe = useCallback(async () => {
    try {
      setMe(await api.me());
      setBootError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setMe(null);
      else setBootError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  if (loading) {
    return (
      <div className="center-screen">
        <div className="spinner" />
      </div>
    );
  }

  if (!me) {
    return (
      <>
        {bootError && <div className="banner error">Can't reach the game server: {bootError}</div>}
        <AuthScreen onSignedIn={setMe} />
      </>
    );
  }

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      setMe(null);
      navigate({ name: "lobby" });
    }
  };

  if (route.name === "game") return <GameScreen key={route.id} gameId={route.id} me={me} />;
  if (route.name === "create-character")
    return <CharacterCreator onDone={() => navigate({ name: "lobby" })} onCancel={() => navigate({ name: "lobby" })} />;
  return <LobbyScreen me={me} onMeChange={setMe} onLogout={logout} />;
}
