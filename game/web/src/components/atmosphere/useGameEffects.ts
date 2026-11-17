import { useEffect, useRef } from "react";
import type { GameView, LogEntry } from "../../api/types";
import { ambienceFor, combatEffect, play, setAmbience, type Effect } from "../../util/sound";
import { enqueue } from "../../util/tts";
import { getPrefs } from "../../util/prefs";
import { showDice } from "../DiceRoller";

type RollData = {
  roll?: { natural?: number; total?: number; modifier?: number; rolls?: number[]; advantage?: string };
  dc?: number | null;
  character_id?: string;
};

/**
 * Reacts to NEW log entries only (never replays history on load): sound effects, the dice overlay,
 * and auto-read of narration. Also keeps the ambience in step with the scene.
 */
export function useGameEffects(view: GameView, opts: { tv?: boolean } = {}) {
  const seen = useRef<{ game: string; ids: Set<string>; maxNum: number } | null>(null);

  // Ambience follows the scene (or the battle map's terrain during a fight).
  const terrain = view.encounter?.terrain ?? null;
  const sc = view.scene;
  useEffect(() => {
    setAmbience(ambienceFor(sc, terrain));
  }, [sc?.type, sc?.weather, sc?.hour, sc?.time_of_day, terrain]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => setAmbience({}), []);

  useEffect(() => {
    const log = view.log;
    const gid = view.game.id;
    if (!seen.current || seen.current.game !== gid) {
      // First sight of this game: everything already here is history.
      seen.current = { game: gid, ids: new Set(log.map((e) => String(e.id))), maxNum: maxNumeric(log) };
      return;
    }
    const s = seen.current;
    const fresh = log.filter((e) => {
      const k = String(e.id);
      if (s.ids.has(k)) return false;
      const n = Number(e.id);
      // Older entries that scroll into the window (e.g. after a reconnect) aren't news.
      return !(Number.isFinite(n) && n <= s.maxNum);
    });
    for (const e of log) s.ids.add(String(e.id));
    s.maxNum = Math.max(s.maxNum, maxNumeric(log));
    if (!fresh.length) return;

    const prefs = getPrefs();
    const sounds: Effect[] = [];
    for (const e of fresh) {
      const d = (e.data ?? null) as Record<string, unknown> | null;
      switch (e.kind) {
        case "roll": {
          sounds.push("dice");
          const rd = (d ?? {}) as RollData;
          const r = rd.roll;
          if (r && typeof r.natural === "number" && typeof r.total === "number") {
            const c = rd.character_id ? view.characters[rd.character_id] : undefined;
            const dc = typeof rd.dc === "number" ? rd.dc : null;
            showDice({
              natural: r.natural,
              total: r.total,
              modifier: r.modifier,
              rolls: r.rolls,
              advantage: r.advantage,
              dc,
              success: dc !== null ? r.total >= dc : null,
              label: rollLabel(e.text, c?.name),
              who: c?.name,
              color: c?.color,
            });
          }
          if (r?.natural === 20) sounds.push("crit");
          break;
        }
        case "combat": {
          sounds.push(...combatEffect(e.text, d));
          // A player's own attack roll (typed combat: they clicked Roll) gets the dice too.
          const cd = (d ?? {}) as { attacker?: string; roll?: RollData["roll"]; hit?: boolean; attack?: string; damage?: number };
          const r = cd.roll;
          if (cd.attacker?.startsWith("pc-") && r && typeof r.natural === "number" && typeof r.total === "number") {
            const c = view.characters[cd.attacker.slice(3)];
            showDice({
              kind: "attack",
              natural: r.natural,
              total: r.total,
              modifier: r.modifier,
              rolls: r.rolls,
              advantage: r.advantage,
              dc: null,
              success: typeof cd.hit === "boolean" ? cd.hit : null,
              label: cd.attack ? `${cd.attack}${cd.hit && cd.damage ? ` · ${cd.damage} damage` : ""}` : "Attack",
              who: c?.name,
              color: c?.color,
            });
          }
          break;
        }
        case "event":
        case "system":
          if (/\b(loot|gold|gp|coins?|treasure|buys?|sells?|sold|bought|purse)\b/i.test(e.text)) sounds.push("coins");
          if (/\b(falls|dies|is slain|has died)\b/i.test(e.text)) sounds.push("toll");
          if (/\b(regains?|heals?)\b.*\bHP\b/i.test(e.text)) sounds.push("heal");
          if (/\bdoors?\b.*\b(open|opens|creak|creaks|swings)\b|\b(open|opens|creaks)\b.*\bdoors?\b/i.test(e.text)) sounds.push("door");
          break;
        case "narration":
          if (/\bdoors?\b[^.]*\b(creak|creaks|groans|swings open)\b/i.test(e.text)) sounds.push("door");
          if ((opts.tv ? prefs.tvAutoRead : prefs.autoRead) && e.text.trim()) enqueue(String(e.id), e.text);
          break;
      }
    }
    // Stagger so a whole monster round doesn't play as one crash.
    sounds.slice(0, 10).forEach((fx, i) => window.setTimeout(() => play(fx), i * 260));
  }, [view.log, view.game.id]); // eslint-disable-line react-hooks/exhaustive-deps
}

function maxNumeric(log: LogEntry[]): number {
  let m = -Infinity;
  for (const e of log) {
    const n = Number(e.id);
    if (Number.isFinite(n) && n > m) m = n;
  }
  return m;
}

/** "Aria — Perception: 14 vs DC 12 — success." → "Perception" */
function rollLabel(text: string, name?: string): string {
  let t = text.split(":")[0] ?? "";
  if (name && t.startsWith(name)) t = t.slice(name.length).replace(/^\s*[—-]\s*/, "");
  return t.trim().slice(0, 60);
}
