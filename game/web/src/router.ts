import { useEffect, useState } from "react";

export type Route =
  | { name: "lobby" }
  | { name: "join"; code: string }
  | { name: "game"; id: string }
  | { name: "create-character" }
  | { name: "tv"; token: string };

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, "");
  const parts = h.split("/").filter(Boolean);
  if (parts[0] === "game" && parts[1]) return { name: "game", id: decodeURIComponent(parts[1]) };
  if (parts[0] === "tv" && parts[1]) return { name: "tv", token: decodeURIComponent(parts[1]) };
  if (parts[0] === "join" && parts[1]) return { name: "join", code: decodeURIComponent(parts[1]) };
  if (parts[0] === "create-character") return { name: "create-character" };
  return { name: "lobby" };
}

export function navigate(route: Route) {
  let hash = "#/";
  if (route.name === "game") hash = `#/game/${encodeURIComponent(route.id)}`;
  if (route.name === "create-character") hash = "#/create-character";
  if (route.name === "tv") hash = `#/tv/${encodeURIComponent(route.token)}`;
  if (route.name === "join") hash = `#/join/${encodeURIComponent(route.code)}`;
  if (window.location.hash !== hash) window.location.hash = hash;
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}
