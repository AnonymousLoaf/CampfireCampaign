import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { CampaignStats, CharacterView } from "../../api/types";
import { formatMoney } from "../../util/format";
import Modal from "../Modal";
import Portrait from "../Portrait";
import { useGame } from "./gameContext";
import { Paragraphs } from "./StoryFeed";

type Award = { key: keyof CampaignStats; title: string; what: (n: number) => string };
const AWARDS: Award[] = [
  { key: "kills", title: "Slayer", what: (n) => `${n} foe${n === 1 ? "" : "s"} felled` },
  { key: "damage_dealt", title: "Heavy Hitter", what: (n) => `${n} damage dealt` },
  { key: "crits", title: "Deadeye", what: (n) => `${n} critical hit${n === 1 ? "" : "s"}` },
  { key: "damage_taken", title: "Shield of the Party", what: (n) => `${n} damage taken` },
  { key: "downs", title: "Back from the Brink", what: (n) => `dropped ${n} time${n === 1 ? "" : "s"} and got back up` },
  { key: "nat1", title: "Cursed Dice", what: (n) => `${n} natural 1${n === 1 ? "" : "s"}` },
  { key: "gold_cp", title: "Coin Magnet", what: (n) => `${formatMoney(n)} earned` },
];

/** Who wins each award: the single highest (ties go to nobody unless everyone is tied at the top). */
function awardsFor(ids: string[], stats: Record<string, CampaignStats>): Record<string, { title: string; text: string }[]> {
  const out: Record<string, { title: string; text: string }[]> = {};
  for (const a of AWARDS) {
    const vals = ids.map((id) => [id, stats[id]?.[a.key] ?? 0] as const).filter(([, v]) => v > 0);
    if (!vals.length) continue;
    const top = Math.max(...vals.map(([, v]) => v));
    const winners = vals.filter(([, v]) => v === top);
    if (winners.length !== 1) continue;
    (out[winners[0][0]] ??= []).push({ title: a.title, text: a.what(top) });
  }
  return out;
}

function StatChips({ s }: { s: CampaignStats }) {
  const hitRate = s.attacks ? Math.round(((s.hits ?? 0) / s.attacks) * 100) : null;
  const chips: [string, string | number][] = [
    ["Foes felled", s.kills ?? 0],
    ["Damage dealt", s.damage_dealt ?? 0],
    ["Hit rate", hitRate === null ? "—" : `${hitRate}%`],
    ["Crits", s.crits ?? 0],
    ["Natural 20s", s.nat20 ?? 0],
    ["Natural 1s", s.nat1 ?? 0],
    ["Damage taken", s.damage_taken ?? 0],
    ["Times dropped", s.downs ?? 0],
    ["Gold earned", s.gold_cp ? formatMoney(s.gold_cp) : "—"],
  ];
  return (
    <div className="ep-stats">
      {chips.map(([k, v]) => (
        <div key={k} className="ep-stat">
          <div className="ep-stat-val">{v}</div>
          <div className="ep-stat-label">{k}</div>
        </div>
      ))}
    </div>
  );
}

export function EpilogueModal({ onClose }: { onClose: () => void }) {
  const { view } = useGame();
  const ep = view.epilogue;
  if (!ep || ep.status !== "done") return null;
  const heroes = Object.values(view.characters);
  const awards = awardsFor(
    heroes.map((c) => c.id),
    ep.stats,
  );
  const p = ep.party ?? {};
  return (
    <Modal title={ep.title || "Epilogue"} wide onClose={onClose}>
      <div className="epilogue">
        <div className="ep-party-line muted small">
          {p.days ?? "?"} day{p.days === 1 ? "" : "s"} on the road · {p.quests_done ?? 0} quest{p.quests_done === 1 ? "" : "s"} completed
          {p.quests_failed ? ` · ${p.quests_failed} failed` : ""} · {p.npcs_met ?? 0} people met
          {p.places ? ` · ${p.places} places found` : ""}
        </div>
        <div className="ep-text">
          <Paragraphs text={ep.text ?? ""} />
        </div>
        <h3 className="ep-heroes-h">The heroes</h3>
        <div className="ep-heroes">
          {heroes.map((c) => (
            <HeroCard key={c.id} c={c} fate={ep.characters[c.id]} stats={ep.stats[c.id] ?? {}} awards={awards[c.id] ?? []} />
          ))}
        </div>
      </div>
    </Modal>
  );
}

function HeroCard({ c, fate, stats, awards }: { c: CharacterView; fate?: string; stats: CampaignStats; awards: { title: string; text: string }[] }) {
  return (
    <div className={`ep-hero ${c.dead ? "fallen" : ""}`}>
      <div className="ep-hero-head">
        <Portrait c={c} size="big" zoomable />
        <div>
          <div className="ep-hero-name">
            {c.name} {c.dead && <span className="badge red">fallen</span>}
          </div>
          <div className="muted small">
            Level {c.level} {c.race} {c.class}
          </div>
          {awards.length > 0 && (
            <div className="ep-awards">
              {awards.map((a) => (
                <span key={a.title} className="ep-award" title={a.text}>
                  🏆 {a.title}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      {fate && (
        <div className="ep-fate">
          <Paragraphs text={fate} />
        </div>
      )}
      <StatChips s={stats} />
    </div>
  );
}

/** Banner and button for the epilogue: the host can close a finished story; everyone can reread the ending. */
export function EpilogueBar({ onOpen }: { onOpen: () => void }) {
  const { view, gameId, run } = useGame();
  const ep = view.epilogue;
  const host = view.me.is_host;
  if (ep?.status === "done") {
    return (
      <div className="epilogue-bar done">
        <span>📜 The campaign has ended: {ep.title}</span>
        <button className="btn small primary" onClick={onOpen}>
          Read the epilogue
        </button>
      </div>
    );
  }
  if (ep?.status === "writing") {
    return (
      <div className="epilogue-bar">
        <span className="spinner tiny" /> The DM is writing the epilogue…
      </div>
    );
  }
  if (!host || view.game.status !== "active") return null;
  if (!view.story_complete && ep?.status !== "error") return null;
  return (
    <div className="epilogue-bar">
      <span>{ep?.status === "error" ? `The epilogue couldn't be written: ${ep.error ?? ""}` : "✦ The story has reached its end."}</span>
      <button className="btn small primary" disabled={!!view.encounter} onClick={() => void endCampaign(gameId, run)}>
        {ep?.status === "error" ? "Try again" : "End campaign & write the epilogue"}
      </button>
    </div>
  );
}

export async function endCampaign(gameId: string, run: (fn: () => Promise<unknown>) => Promise<boolean>) {
  if (
    !window.confirm(
      "End the campaign? The DM writes an epilogue for the world and each hero, with everyone's stats, and the game is over: no more turns.",
    )
  )
    return false;
  return run(() => api.endCampaign(gameId));
}

/** Open the epilogue once, the first time this device sees it. */
export function useEpilogueAutoOpen(gameId: string, done: boolean, open: () => void) {
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    if (!done || checked) return;
    setChecked(true);
    const key = `campfire.epilogueSeen.${gameId}`;
    try {
      if (window.localStorage.getItem(key)) return;
      window.localStorage.setItem(key, "1");
    } catch {
      /* storage blocked: just show it */
    }
    open();
  }, [done, checked, gameId, open]);
}
