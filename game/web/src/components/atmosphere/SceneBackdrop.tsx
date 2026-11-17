import { useEffect, useRef, useState } from "react";
import { isNight, weatherKind } from "../../util/sound";

type Scene = { type?: string; time_of_day?: string; weather?: string; hour?: number } | null | undefined;

/** Base colours per place: [top, bottom, accent]. */
const PALETTE: Record<string, [string, string, string]> = {
  town: ["#3b3428", "#1f1a14", "#c9a25a"],
  tavern: ["#4a2c17", "#1e120a", "#e08a3a"],
  wilderness: ["#2f3b26", "#171d12", "#9bb06a"],
  forest: ["#1f3320", "#0c160d", "#6fa05a"],
  dungeon: ["#25232a", "#0d0c10", "#7d6fa8"],
  cave: ["#2a2622", "#0e0c0a", "#8a7a66"],
  ruins: ["#3a3730", "#17150f", "#b3a27a"],
  road: ["#3a3324", "#1a160e", "#c2a86a"],
  castle: ["#2e2f38", "#121318", "#a3a8c8"],
  temple: ["#36301f", "#16130b", "#e6cf7a"],
  swamp: ["#25321f", "#0e140c", "#7f9a5a"],
  mountain: ["#323842", "#14171c", "#b5c2d4"],
  coast: ["#1f3240", "#0b141b", "#7fb6d0"],
  camp: ["#33301f", "#15130b", "#e0943a"],
};

/** Texture overlays (CSS backgrounds) that hint at the place. */
const TEXTURE: Record<string, string> = {
  tavern: "repeating-linear-gradient(90deg, rgba(0,0,0,0.12) 0 2px, transparent 2px 46px)",
  dungeon: "repeating-linear-gradient(0deg, rgba(0,0,0,0.18) 0 2px, transparent 2px 32px), repeating-linear-gradient(90deg, rgba(0,0,0,0.12) 0 2px, transparent 2px 64px)",
  castle: "repeating-linear-gradient(0deg, rgba(0,0,0,0.15) 0 2px, transparent 2px 28px), repeating-linear-gradient(90deg, rgba(0,0,0,0.1) 0 2px, transparent 2px 56px)",
  cave: "radial-gradient(ellipse at 20% 0%, rgba(0,0,0,0.35), transparent 50%), radial-gradient(ellipse at 80% 100%, rgba(0,0,0,0.4), transparent 55%)",
  forest: "radial-gradient(circle at 15% 20%, rgba(120,170,90,0.10), transparent 30%), radial-gradient(circle at 70% 60%, rgba(120,170,90,0.08), transparent 35%)",
  swamp: "radial-gradient(ellipse at 50% 100%, rgba(120,150,110,0.18), transparent 60%)",
  coast: "repeating-linear-gradient(170deg, rgba(255,255,255,0.03) 0 3px, transparent 3px 22px)",
  ruins: "repeating-linear-gradient(45deg, rgba(0,0,0,0.08) 0 3px, transparent 3px 40px)",
  temple: "radial-gradient(circle at 50% 0%, rgba(255,230,160,0.14), transparent 55%)",
};

/** Tint by time of day: overlay colour + opacity. */
function timeTint(hour?: number, tod?: string): string {
  const h = typeof hour === "number" ? hour : todHour(tod);
  if (h < 5 || h >= 21) return "rgba(10, 18, 48, 0.55)"; // night
  if (h < 7) return "rgba(200, 110, 90, 0.22)"; // dawn
  if (h < 17) return "rgba(255, 240, 210, 0.04)"; // day
  if (h < 19) return "rgba(230, 120, 60, 0.20)"; // golden hour
  return "rgba(70, 40, 90, 0.38)"; // dusk
}

export function todHour(tod?: string): number {
  const s = (tod || "").toLowerCase();
  if (s.includes("dawn")) return 6;
  if (s.includes("morning")) return 9;
  if (s.includes("noon") || s.includes("midday")) return 12;
  if (s.includes("afternoon")) return 15;
  if (s.includes("dusk") || s.includes("sunset")) return 19;
  if (s.includes("evening")) return 20;
  if (s.includes("night")) return 23;
  return 10;
}

function computeStyle(scene: Scene, terrain?: string | null, art?: string | null): { key: string; background: string } {
  const type = (terrain || scene?.type || "road").toLowerCase();
  const [top, bottom, accent] = PALETTE[type] ?? PALETTE.road;
  const w = weatherKind(scene?.weather);
  const indoor = ["tavern", "dungeon", "cave"].includes(type);
  const tint = indoor ? "rgba(0,0,0,0)" : timeTint(scene?.hour, scene?.time_of_day);
  const weatherVeil =
    indoor ? "transparent" : w === "fog" ? "rgba(200,205,210,0.16)" : w === "storm" ? "rgba(20,24,34,0.35)" : w === "rain" || w === "overcast" ? "rgba(60,70,85,0.22)" : w === "snow" ? "rgba(220,230,240,0.10)" : "transparent";
  const glow = indoor && (type === "tavern") ? `radial-gradient(ellipse at 50% 110%, ${accent}40, transparent 60%)` : `radial-gradient(ellipse at 50% -10%, ${accent}26, transparent 60%)`;
  const layers = [
    `linear-gradient(${tint}, ${tint})`,
    `linear-gradient(${weatherVeil}, ${weatherVeil})`,
    TEXTURE[type] ?? "none",
    glow,
    ...(art ? ["linear-gradient(rgba(10, 8, 6, 0.45), rgba(10, 8, 6, 0.7))", `url("${art}") center / cover no-repeat`] : []),
    `linear-gradient(180deg, ${top}, ${bottom})`,
  ].filter((x) => x !== "none");
  const key = `${type}|${w}|${indoor ? "in" : timeTint(scene?.hour, scene?.time_of_day)}|${art ?? ""}`;
  return { key, background: layers.join(", ") };
}

/**
 * A scene-reactive background (gradient, texture, vignette) that cross-fades when the place, weather or
 * time changes. Sits behind its parent's content (parent needs position: relative).
 */
export default function SceneBackdrop({
  scene,
  terrain,
  subtle = false,
  art,
}: {
  scene: Scene;
  terrain?: string | null;
  subtle?: boolean;
  /** A painted picture of the scene, drawn under the tint. */
  art?: string | null;
}) {
  const next = computeStyle(scene, terrain, art);
  const [layers, setLayers] = useState<{ key: string; background: string; id: number }[]>(() => [{ ...next, id: 0 }]);
  const n = useRef(0);

  useEffect(() => {
    setLayers((ls) => (ls[ls.length - 1]?.key === next.key ? ls : [...ls.slice(-1), { ...next, id: ++n.current }]));
    const t = window.setTimeout(() => setLayers((ls) => ls.slice(-1)), 1600);
    return () => window.clearTimeout(t);
  }, [next.key]); // eslint-disable-line react-hooks/exhaustive-deps

  const night = isNight(scene?.hour, scene?.time_of_day);
  return (
    <div className={`scene-backdrop ${subtle ? "subtle" : ""} ${night ? "night" : ""}`} aria-hidden>
      {layers.map((l, i) => (
        <div key={l.id} className={`scene-layer ${i === layers.length - 1 && layers.length > 1 ? "entering" : ""}`} style={{ background: l.background }} />
      ))}
      <div className="scene-vignette" />
    </div>
  );
}
