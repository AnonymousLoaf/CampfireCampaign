import { createContext, useContext } from "react";
import type { CharacterView, GameView } from "../../api/types";

export interface GameCtx {
  view: GameView;
  gameId: string;
  /** Characters I may act for (my own, or the whole party in single-speaker mode). */
  controls: string[];
  /** The character I'm currently acting as. */
  actingId: string | null;
  acting: CharacterView | undefined;
  setActingId: (id: string) => void;
  /** character_id to send in shop/inventory/combat bodies — undefined when acting as myself. */
  charParam: string | undefined;
  /** Runs an API call, shows its error as a toast, refreshes the view. Resolves true on success. */
  run: (fn: () => Promise<unknown>) => Promise<boolean>;
  refresh: () => void;
  /** Opens the level-up wizard for a character I control. */
  openLevelUp?: (characterId: string) => void;
}

export const GameContext = createContext<GameCtx | null>(null);

export function useGame(): GameCtx {
  const g = useContext(GameContext);
  if (!g) throw new Error("useGame outside GameContext");
  return g;
}

export function controlsOf(view: GameView): string[] {
  if (view.me.controls && view.me.controls.length) return view.me.controls;
  return view.me.character_id ? [view.me.character_id] : [];
}
