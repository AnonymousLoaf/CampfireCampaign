import { useEffect, useRef } from "react";
import { weatherKind, type WeatherKind } from "../../util/sound";
import { prefersReducedMotion } from "../../util/prefs";
import { todHour } from "./SceneBackdrop";

type Scene = { type?: string; time_of_day?: string; weather?: string; hour?: number; day?: number } | null | undefined;

const INDOOR = new Set(["tavern", "dungeon", "cave"]);

type Cloud = { x: number; y: number; w: number; s: number };
type Drop = { x: number; y: number; v: number; r: number };

/** Sky colours [top, horizon] for an hour (fractional). */
function skyColors(h: number, w: WeatherKind): [string, string] {
  const stops: [number, [number, number, number], [number, number, number]][] = [
    [0, [8, 12, 30], [22, 28, 58]],
    [5, [14, 18, 44], [60, 44, 80]],
    [6.5, [70, 80, 140], [240, 150, 110]],
    [8, [80, 140, 210], [190, 215, 235]],
    [12, [60, 130, 215], [170, 210, 240]],
    [17, [80, 130, 200], [230, 190, 140]],
    [19, [70, 50, 110], [240, 120, 70]],
    [20.5, [20, 22, 56], [70, 50, 90]],
    [24, [8, 12, 30], [22, 28, 58]],
  ];
  let i = 0;
  while (i < stops.length - 2 && h >= stops[i + 1][0]) i++;
  const [h0, t0, b0] = stops[i];
  const [h1, t1, b1] = stops[i + 1];
  const f = Math.max(0, Math.min(1, (h - h0) / (h1 - h0)));
  const mix = (a: number[], b: number[]) => a.map((x, k) => Math.round(x + (b[k] - x) * f));
  let top = mix(t0, t1);
  let bot = mix(b0, b1);
  if (w === "overcast" || w === "rain" || w === "storm" || w === "snow" || w === "fog") {
    const grey = w === "storm" ? 0.7 : 0.5;
    const g = (c: number[]) => {
      const avg = (c[0] + c[1] + c[2]) / 3;
      return c.map((x) => Math.round(x + (avg - x) * grey) * (w === "storm" ? 0.7 : 0.92));
    };
    top = g(top);
    bot = g(bot);
  }
  return [`rgb(${top.join(",")})`, `rgb(${bot.join(",")})`];
}

/**
 * Animated sky: sun/moon on an arc by hour, stars at night, clouds and rain/snow/fog from the weather text.
 * Indoors it shows a dim strip with the time instead. Honours prefers-reduced-motion (one still frame).
 */
export default function SkyStrip({ scene, height = 56, className = "" }: { scene: Scene; height?: number; className?: string }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const target = useRef({ hour: 10, w: "clear" as WeatherKind, indoor: false });
  const hourType = scene?.type ?? "";
  const hour = typeof scene?.hour === "number" ? scene.hour : todHour(scene?.time_of_day);
  target.current = { hour, w: weatherKind(scene?.weather), indoor: INDOOR.has(hourType.toLowerCase()) };

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const reduced = prefersReducedMotion();
    let raf = 0;
    let shownHour = target.current.hour;
    let last = performance.now();
    let flash = 0;
    const clouds: Cloud[] = [];
    const drops: Drop[] = [];
    const stars = Array.from({ length: 60 }, () => ({ x: Math.random(), y: Math.random() * 0.8, p: Math.random() * Math.PI * 2, s: 0.5 + Math.random() }));

    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const rect = cv.getBoundingClientRect();
      cv.width = Math.max(1, Math.round(rect.width * dpr));
      cv.height = Math.max(1, Math.round(rect.height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    ro?.observe(cv);

    const frame = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const W = cv.clientWidth;
      const H = cv.clientHeight;
      const { hour: th, w, indoor } = target.current;
      // Ease the displayed hour toward the scene's hour (the long way round past midnight is fine).
      let diff = th - shownHour;
      if (diff < -12) diff += 24;
      if (diff > 12) diff -= 24;
      shownHour = reduced ? th : (shownHour + diff * Math.min(1, dt * 1.5) + 24) % 24;
      const h = shownHour;

      if (indoor) {
        const g = ctx.createLinearGradient(0, 0, 0, H);
        g.addColorStop(0, "#1a140e");
        g.addColorStop(1, "#2a1d12");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, W, H);
        // warm flicker of torchlight
        const fl = reduced ? 0.5 : 0.5 + 0.25 * Math.sin(now / 130) * Math.sin(now / 370);
        const rg = ctx.createRadialGradient(W * 0.5, H * 1.4, 4, W * 0.5, H * 1.4, W * 0.6);
        rg.addColorStop(0, `rgba(255,150,60,${0.25 + fl * 0.15})`);
        rg.addColorStop(1, "rgba(255,150,60,0)");
        ctx.fillStyle = rg;
        ctx.fillRect(0, 0, W, H);
        if (!reduced) raf = requestAnimationFrame(frame);
        return;
      }

      const [top, bot] = skyColors(h, w);
      const g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, top);
      g.addColorStop(1, bot);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);

      const nightAmt = h < 5 || h > 20.5 ? 1 : h < 6.5 ? (6.5 - h) / 1.5 : h > 19 ? (h - 19) / 1.5 : 0;
      const cloudy = w === "overcast" || w === "rain" || w === "storm" || w === "snow" || w === "fog";

      // Stars.
      if (nightAmt > 0) {
        for (const s of stars) {
          const tw = reduced ? 0.7 : 0.55 + 0.45 * Math.sin(now / 600 + s.p);
          ctx.fillStyle = `rgba(255,255,240,${nightAmt * tw * (cloudy ? 0.25 : 0.9)})`;
          ctx.fillRect(s.x * W, s.y * H, s.s, s.s);
        }
      }

      // Sun (6–18) / moon (18–6) on an arc.
      const arcY = (t: number) => H * 0.92 - Math.sin(Math.PI * t) * H * 0.72;
      const day = h >= 6 && h < 18;
      const t = day ? (h - 6) / 12 : ((h + 6) % 24) / 12;
      const bx = W * (0.06 + t * 0.88);
      const by = arcY(t);
      if (day) {
        const glow = ctx.createRadialGradient(bx, by, 2, bx, by, H * 0.6);
        glow.addColorStop(0, `rgba(255,236,170,${cloudy ? 0.25 : 0.55})`);
        glow.addColorStop(1, "rgba(255,236,170,0)");
        ctx.fillStyle = glow;
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = cloudy ? "rgba(255,245,215,0.55)" : h < 7.5 || h > 16.5 ? "#ffc27a" : "#fff3c4";
        ctx.beginPath();
        ctx.arc(bx, by, Math.max(5, H * 0.13), 0, Math.PI * 2);
        ctx.fill();
      } else {
        const r = Math.max(4, H * 0.11);
        ctx.fillStyle = `rgba(235,235,215,${cloudy ? 0.35 : 0.95})`;
        ctx.beginPath();
        ctx.arc(bx, by, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = top; // crescent bite
        ctx.beginPath();
        ctx.arc(bx + r * 0.45, by - r * 0.2, r * 0.9, 0, Math.PI * 2);
        ctx.fill();
      }

      // Clouds.
      const wantClouds = w === "clear" ? 2 : w === "wind" ? 4 : w === "fog" ? 3 : w === "overcast" ? 9 : w === "snow" ? 8 : 10;
      while (clouds.length < wantClouds) clouds.push({ x: Math.random() * W, y: Math.random() * H * 0.55, w: 40 + Math.random() * 90, s: 4 + Math.random() * 8 });
      if (clouds.length > wantClouds) clouds.length = wantClouds;
      const speed = w === "wind" || w === "storm" ? 4 : 1;
      const shade = w === "storm" ? "rgba(55,58,70,0.85)" : cloudy ? "rgba(150,155,165,0.7)" : nightAmt > 0.5 ? "rgba(90,95,120,0.45)" : "rgba(255,255,255,0.75)";
      ctx.fillStyle = shade;
      for (const c of clouds) {
        if (!reduced) c.x += c.s * speed * dt;
        if (c.x - c.w > W) c.x = -c.w;
        const r = c.w / 4;
        ctx.beginPath();
        ctx.arc(c.x, c.y + r, r, 0, Math.PI * 2);
        ctx.arc(c.x + r * 1.3, c.y + r * 0.6, r * 1.3, 0, Math.PI * 2);
        ctx.arc(c.x + r * 2.6, c.y + r, r, 0, Math.PI * 2);
        ctx.fill();
      }

      // Rain / snow.
      const wantDrops = w === "storm" ? 140 : w === "rain" ? 80 : w === "snow" ? 60 : 0;
      while (drops.length < wantDrops) drops.push({ x: Math.random() * W, y: Math.random() * H, v: 0.6 + Math.random() * 0.6, r: 0.8 + Math.random() * 1.4 });
      if (drops.length > wantDrops) drops.length = wantDrops;
      if (wantDrops) {
        if (w === "snow") {
          ctx.fillStyle = "rgba(255,255,255,0.85)";
          for (const d of drops) {
            if (!reduced) {
              d.y += d.v * 18 * dt;
              d.x += Math.sin(now / 900 + d.r * 5) * 8 * dt;
            }
            if (d.y > H) {
              d.y = -2;
              d.x = Math.random() * W;
            }
            ctx.beginPath();
            ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
            ctx.fill();
          }
        } else {
          ctx.strokeStyle = "rgba(190,210,235,0.55)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          for (const d of drops) {
            if (!reduced) {
              d.y += d.v * 160 * dt;
              d.x -= d.v * 40 * dt;
            }
            if (d.y > H) {
              d.y = -6;
              d.x = Math.random() * (W + 40);
            }
            ctx.moveTo(d.x, d.y);
            ctx.lineTo(d.x - 2.5, d.y + 7);
          }
          ctx.stroke();
        }
      }

      // Fog bands.
      if (w === "fog") {
        for (let i = 0; i < 3; i++) {
          const y = H * (0.35 + i * 0.25);
          const off = reduced ? 0 : (now / (60 + i * 25)) % W;
          const fg = ctx.createLinearGradient(0, y - 10, 0, y + 10);
          fg.addColorStop(0, "rgba(220,225,230,0)");
          fg.addColorStop(0.5, "rgba(220,225,230,0.35)");
          fg.addColorStop(1, "rgba(220,225,230,0)");
          ctx.fillStyle = fg;
          ctx.fillRect(-W + off, y - 10, W * 2, 20);
        }
      }

      // Lightning.
      if (w === "storm" && !reduced) {
        if (flash <= 0 && Math.random() < dt * 0.08) flash = 0.35;
        if (flash > 0) {
          ctx.fillStyle = `rgba(230,235,255,${flash})`;
          ctx.fillRect(0, 0, W, H);
          flash -= dt;
        }
      }

      if (!reduced) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    // Reduced motion: still redraw when the scene changes (cheap: one frame every few seconds).
    const still = reduced ? window.setInterval(() => requestAnimationFrame(frame), 3000) : 0;
    return () => {
      cancelAnimationFrame(raf);
      if (still) window.clearInterval(still);
      ro?.disconnect();
    };
  }, []);

  const label = scene ? `${scene.time_of_day ?? ""}${scene.weather ? `, ${scene.weather}` : ""}` : "";
  return <canvas ref={ref} className={`sky-strip ${className}`} style={{ height }} role="img" aria-label={label ? `Sky: ${label}` : "Sky"} />;
}
