import { useEffect, useState } from "react";

/** Per-device preferences (sound, narration voice). Kept in localStorage; never sent to the server. */
export interface DevicePrefs {
  volume: number; // 0..1 master
  ambience: boolean;
  effects: boolean;
  autoRead: boolean;
  tvAutoRead: boolean;
  voice: string; // voiceURI, "" = browser default English voice
  rate: number; // 0.6..1.6
  dice: boolean; // animated dice overlay
  diceMotion: "auto" | "always"; // "always": roll the dice even when the device asks for reduced motion
  soundOn: boolean; // the player switched sound on (browsers still need a tap each visit)
}

const KEY = "dnd.devicePrefs.v1";
const DEFAULTS: DevicePrefs = {
  volume: 0.6,
  ambience: true,
  effects: true,
  autoRead: false,
  tvAutoRead: false,
  voice: "",
  rate: 1,
  dice: true,
  diceMotion: "auto",
  soundOn: false,
};

let current: DevicePrefs = load();
const listeners = new Set<(p: DevicePrefs) => void>();

function load(): DevicePrefs {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<DevicePrefs>) };
  } catch {
    /* private mode / blocked storage */
  }
  return { ...DEFAULTS };
}

export function getPrefs(): DevicePrefs {
  return current;
}

export function setPrefs(patch: Partial<DevicePrefs>): void {
  current = { ...current, ...patch };
  try {
    window.localStorage.setItem(KEY, JSON.stringify(current));
  } catch {
    /* ignore */
  }
  for (const l of listeners) l(current);
}

export function onPrefs(fn: (p: DevicePrefs) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function usePrefs(): [DevicePrefs, (patch: Partial<DevicePrefs>) => void] {
  const [p, setP] = useState(current);
  useEffect(() => onPrefs(setP), []);
  return [p, setPrefs];
}

export function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}
