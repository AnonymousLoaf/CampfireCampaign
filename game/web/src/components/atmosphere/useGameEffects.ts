import { useEffect, useRef } from "react";
import type { GameView, LogEntry } from "../../api/types";
import { ambienceFor, combatEffect, play, setAmbience, type Effect } from "../../util/sound";
import { enqueue } from "../../util/tts";
import { getPrefs } from "../../util/prefs";
import { showDice } from "../DiceRoller";

type RollData = {
  roll?: { natural?: number | null; total?: number; modifier?: number; rolls?: number[]; advantage?: string; notation?: string };
  dc?: number | null;
  character_id?: string;
  /** Spell dice outside a fight: the total with the spellcasting bonus, and "healing" or "<type> damage". */
  spell_total?: number;
  bonus?: number;
  what?: string;
};

/** "2d8+3" → 8 (the die size), or 0. */
function sidesOf(notation?: string): number {
  const m = /d(\d+)/.exec(notation ?? "");
  return m ? Number(m[1]) : 0;
}

/**
 * Reacts to NEW log entries only (never replays history on load): sound effects, the dice overlay,
 * and auto-read of narration. Also keeps the ambience in step with the scene.
 */
export function useGameEffects(view: GameView, opts: { tv?: boolean } = {}) {
  const seen = useRef<{ game: string; ids: Set<string>; maxNum: number } | null>(null);
  // new narrations waiting for the host PC's voiced audio: id → give-up timer
  const waiting = useRef(new Map<string, { timer: number }>());
  useEffect(() => {
    if (!waiting.current.size) return;
    for (const e of view.log) {
      const w = waiting.current.get(String(e.id));
      const audio = (e.data as { audio?: string } | null)?.audio;
      if (w && audio) {
        window.clearTimeout(w.timer);
        waiting.current.delete(String(e.id));
        enqueue(String(e.id), audio);
      }
    }
  }, [view.log]);
  useEffect(() => () => waiting.current.forEach((w) => window.clearTimeout(w.timer)), []);

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
          if (r && typeof r.natural !== "number" && r.notation && r.rolls?.length && sidesOf(r.notation)) {
            // a spell's healing or damage dice (Cure Wounds' 2d8…)
            const c = rd.character_id ? view.characters[rd.character_id] : undefined;
            const sides = sidesOf(r.notation);
            showDice({
              kind: rd.what === "healing" ? "heal" : "damage",
              dice: r.rolls.map((v) => ({ sides, value: v })),
              total: rd.spell_total ?? r.total ?? 0,
              modifier: rd.bonus ?? r.modifier,
              label: rollLabel(e.text, c?.name),
              who: c?.name,
              color: c?.color,
            });
          }
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
          const cd = (d ?? {}) as {
            attacker?: string;
            target?: string;
            roll?: RollData["roll"];
            hit?: boolean;
            attack?: string;
            damage?: number;
            damage_dice?: { sides: number; value: number }[];
            heal?: number;
            /** the second click of an attack: its d20 was shown on the first */
            damage_only?: boolean;
          };
          const r = cd.roll;
          // healing in a fight (Cure Wounds on an ally): its dice roll too
          if (typeof cd.heal === "number" && r && r.notation && r.rolls?.length && sidesOf(r.notation)) {
            const t = cd.target?.startsWith("pc-") ? view.characters[cd.target.slice(3)] : undefined;
            const sides = sidesOf(r.notation);
            showDice({
              kind: "heal",
              dice: r.rolls.map((v) => ({ sides, value: v })),
              total: r.total ?? cd.heal,
              modifier: r.modifier,
              label: t ? `${t.name} is healed` : "Healing",
              color: t?.color,
            });
          }
          if (cd.attacker?.startsWith("pc-") && r && typeof r.natural === "number" && typeof r.total === "number") {
            const c = view.characters[cd.attacker.slice(3)];
            if (!cd.damage_only)
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
            // then the damage dice, thrown after the attack lands
            if (cd.hit && cd.damage_dice?.length && typeof cd.damage === "number") {
              showDice({
                kind: "damage",
                dice: cd.damage_dice,
                total: cd.damage,
                label: `${cd.attack ?? "Attack"} damage`,
                who: c?.name,
                color: c?.color,
              });
            }
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
          if ((opts.tv ? prefs.tvAutoRead : prefs.autoRead) && e.text.trim()) {
            const id = String(e.id);
            const audio = (e.data as { audio?: string } | null)?.audio;
            if (audio) enqueue(id, audio);
            else if (view.game.settings.voices !== false) {
              // the host PC voices it in a few seconds; past a minute it's old news, so it isn't read
              const timer = window.setTimeout(() => waiting.current.delete(id), 60000);
              waiting.current.set(id, { timer });
            }
          }
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
