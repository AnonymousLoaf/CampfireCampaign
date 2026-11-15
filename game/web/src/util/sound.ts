/**
 * Synthesized game audio (Web Audio API, no sound files).
 *
 * Browsers only allow audio after a user gesture, so nothing plays until `unlock()` runs from a click.
 * Ambience is a set of looping layers (wind, rain, fire…) cross-faded as the scene changes; effects are
 * short one-shots triggered by new log entries.
 */
import { getPrefs, onPrefs, setPrefs } from "./prefs";

export type AmbienceLayer = "wind" | "rain" | "storm" | "fire" | "tavern" | "cave" | "water" | "night";
export type Effect =
  | "sword"
  | "arrow"
  | "magic"
  | "thud"
  | "crit"
  | "heal"
  | "coins"
  | "dice"
  | "door"
  | "toll"
  | "whoosh";

type Layer = { gain: GainNode; stop: () => void; level: number };

let ac: AudioContext | null = null;
let master: GainNode | null = null;
let ambBus: GainNode | null = null;
let fxBus: GainNode | null = null;
let noiseBuf: AudioBuffer | null = null;
let brownBuf: AudioBuffer | null = null;
const layers = new Map<AmbienceLayer, Layer>();
let wanted: Partial<Record<AmbienceLayer, number>> = {};
const unlockListeners = new Set<(on: boolean) => void>();

export function soundSupported(): boolean {
  return typeof window !== "undefined" && !!(window.AudioContext || (window as unknown as { webkitAudioContext?: unknown }).webkitAudioContext);
}

export function isUnlocked(): boolean {
  return !!ac && ac.state === "running";
}

export function onUnlockChange(fn: (on: boolean) => void): () => void {
  unlockListeners.add(fn);
  return () => unlockListeners.delete(fn);
}

/** Call from a user gesture (click/tap). Remembers the choice so later visits unlock on the first tap. */
export function unlock(): void {
  if (!soundSupported()) return;
  try {
    if (!ac) {
      const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      ac = new Ctor();
      master = ac.createGain();
      master.connect(ac.destination);
      ambBus = ac.createGain();
      fxBus = ac.createGain();
      ambBus.connect(master);
      fxBus.connect(master);
      noiseBuf = makeNoise(ac, false);
      brownBuf = makeNoise(ac, true);
      applyPrefs();
      ac.addEventListener("statechange", () => unlockListeners.forEach((l) => l(isUnlocked())));
    }
    void ac.resume().then(() => {
      unlockListeners.forEach((l) => l(isUnlocked()));
      syncLayers();
    });
    if (!getPrefs().soundOn) setPrefs({ soundOn: true });
  } catch {
    /* audio unavailable */
  }
}

/** Turn sound off for this device (and silence everything). */
export function disableSound(): void {
  setPrefs({ soundOn: false });
  for (const k of [...layers.keys()]) dropLayer(k);
  void ac?.suspend().then(() => unlockListeners.forEach((l) => l(false)));
}

// If the player switched sound on before, the first tap anywhere brings it back.
if (typeof window !== "undefined") {
  const auto = () => {
    if (getPrefs().soundOn && !isUnlocked()) unlock();
  };
  window.addEventListener("pointerdown", auto, { capture: true });
  window.addEventListener("keydown", auto, { capture: true });
}

function applyPrefs() {
  if (!ac || !master || !ambBus || !fxBus) return;
  const p = getPrefs();
  const t = ac.currentTime;
  master.gain.setTargetAtTime(p.volume * 0.9, t, 0.05);
  ambBus.gain.setTargetAtTime(p.ambience ? 0.55 : 0, t, 0.3);
  fxBus.gain.setTargetAtTime(p.effects ? 1 : 0, t, 0.05);
}
onPrefs(applyPrefs);

function makeNoise(ctx: AudioContext, brown: boolean): AudioBuffer {
  const len = ctx.sampleRate * 3;
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const d = buf.getChannelData(0);
  let last = 0;
  for (let i = 0; i < len; i++) {
    const w = Math.random() * 2 - 1;
    if (brown) {
      last = (last + 0.02 * w) / 1.02;
      d[i] = last * 3.5;
    } else d[i] = w;
  }
  return buf;
}

function noiseSrc(brown = false): AudioBufferSourceNode {
  const s = ac!.createBufferSource();
  s.buffer = brown ? brownBuf : noiseBuf;
  s.loop = true;
  s.loopStart = Math.random() * 2;
  return s;
}

function filter(type: BiquadFilterType, freq: number, q = 1): BiquadFilterNode {
  const f = ac!.createBiquadFilter();
  f.type = type;
  f.frequency.value = freq;
  f.Q.value = q;
  return f;
}

function gainNode(v: number): GainNode {
  const g = ac!.createGain();
  g.gain.value = v;
  return g;
}

function lfo(freq: number, depth: number, target: AudioParam): OscillatorNode {
  const o = ac!.createOscillator();
  o.frequency.value = freq;
  const g = gainNode(depth);
  o.connect(g).connect(target);
  o.start();
  return o;
}

/** Repeats `fn` at random intervals (ms) until stopped. */
function every(min: number, max: number, fn: () => void): () => void {
  let id = 0;
  let live = true;
  const tick = () => {
    if (!live) return;
    if (isUnlocked()) fn();
    id = window.setTimeout(tick, min + Math.random() * (max - min));
  };
  id = window.setTimeout(tick, min * Math.random());
  return () => {
    live = false;
    window.clearTimeout(id);
  };
}

// ---------- ambience layers ----------

function buildLayer(kind: AmbienceLayer, out: GainNode): () => void {
  const ctx = ac!;
  const nodes: AudioScheduledSourceNode[] = [];
  const timers: (() => void)[] = [];
  const start = (n: AudioScheduledSourceNode) => {
    n.start();
    nodes.push(n);
  };

  switch (kind) {
    case "wind": {
      const n = noiseSrc(true);
      const bp = filter("bandpass", 500, 0.8);
      const g = gainNode(0.6);
      n.connect(bp).connect(g).connect(out);
      nodes.push(lfo(0.08, 260, bp.frequency));
      nodes.push(lfo(0.13, 0.35, g.gain));
      start(n);
      break;
    }
    case "rain":
    case "storm": {
      const heavy = kind === "storm";
      const n = noiseSrc();
      const hp = filter("highpass", 900);
      const lp = filter("lowpass", heavy ? 5000 : 7000);
      const g = gainNode(heavy ? 0.32 : 0.2);
      n.connect(hp).connect(lp).connect(g).connect(out);
      start(n);
      const r = noiseSrc(true);
      const rg = gainNode(heavy ? 0.5 : 0.25);
      r.connect(filter("lowpass", 400)).connect(rg).connect(out);
      start(r);
      // individual drops on the roof/leaves
      timers.push(every(heavy ? 40 : 90, heavy ? 120 : 260, () => ping(out, 2500 + Math.random() * 3000, 0.012, 0.04, "sine")));
      if (heavy) timers.push(every(9000, 22000, () => thunder(out)));
      break;
    }
    case "fire": {
      const n = noiseSrc(true);
      const g = gainNode(0.55);
      n.connect(filter("lowpass", 600)).connect(g).connect(out);
      nodes.push(lfo(0.6, 0.15, g.gain));
      start(n);
      timers.push(every(30, 220, () => crackle(out)));
      break;
    }
    case "tavern": {
      // A murmur of voices: noise through shifting vowel-like formants.
      for (const f0 of [350, 650, 1100]) {
        const n = noiseSrc();
        const bp = filter("bandpass", f0, 6);
        const g = gainNode(0.08);
        n.connect(bp).connect(g).connect(out);
        nodes.push(lfo(0.3 + Math.random() * 0.5, f0 * 0.25, bp.frequency));
        nodes.push(lfo(0.7 + Math.random() * 0.9, 0.06, g.gain));
        start(n);
      }
      timers.push(every(2500, 7000, () => ping(out, 2200 + Math.random() * 1600, 0.05, 0.25, "triangle"))); // mugs clink
      timers.push(every(40, 200, () => crackle(out, 0.5))); // the hearth
      break;
    }
    case "cave": {
      const n = noiseSrc(true);
      n.connect(filter("lowpass", 160)).connect(gainNode(0.5)).connect(out);
      start(n);
      const delay = ctx.createDelay(1.5);
      delay.delayTime.value = 0.33;
      const fb = gainNode(0.38);
      delay.connect(fb).connect(delay);
      delay.connect(out);
      timers.push(every(900, 3200, () => drip(out, delay)));
      break;
    }
    case "water": {
      const n = noiseSrc(true);
      const lp = filter("lowpass", 700);
      const g = gainNode(0.35);
      n.connect(lp).connect(g).connect(out);
      nodes.push(lfo(0.14, 0.3, g.gain));
      nodes.push(lfo(0.11, 300, lp.frequency));
      start(n);
      break;
    }
    case "night": {
      timers.push(every(350, 1600, () => cricket(out)));
      break;
    }
  }
  return () => {
    for (const n of nodes) {
      try {
        n.stop();
      } catch {
        /* already stopped */
      }
    }
    timers.forEach((t) => t());
  };
}

function ping(out: AudioNode, freq: number, vol: number, dur: number, type: OscillatorType) {
  const ctx = ac!;
  const t = ctx.currentTime;
  const o = ctx.createOscillator();
  o.type = type;
  o.frequency.value = freq;
  const g = gainNode(0);
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(vol, t + 0.004);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(out);
  o.start(t);
  o.stop(t + dur + 0.05);
}

function burst(out: AudioNode, opts: { at?: number; dur: number; vol: number; type?: BiquadFilterType; freq: number; q?: number; brown?: boolean; attack?: number }) {
  const ctx = ac!;
  const t = opts.at ?? ctx.currentTime;
  const s = ctx.createBufferSource();
  s.buffer = opts.brown ? brownBuf : noiseBuf;
  s.loopStart = 0;
  const f = filter(opts.type ?? "bandpass", opts.freq, opts.q ?? 1);
  const g = gainNode(0);
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(opts.vol, t + (opts.attack ?? 0.003));
  g.gain.exponentialRampToValueAtTime(0.0001, t + opts.dur);
  s.connect(f).connect(g).connect(out);
  s.start(t, Math.random() * 2);
  s.stop(t + opts.dur + 0.05);
  return f;
}

function crackle(out: AudioNode, scale = 1) {
  burst(out, { dur: 0.01 + Math.random() * 0.03, vol: (0.1 + Math.random() * 0.25) * scale, type: "highpass", freq: 1500 + Math.random() * 2500 });
}

function drip(out: AudioNode, wet: AudioNode) {
  const ctx = ac!;
  const t = ctx.currentTime;
  const o = ctx.createOscillator();
  o.type = "sine";
  const f = 900 + Math.random() * 900;
  o.frequency.setValueAtTime(f, t);
  o.frequency.exponentialRampToValueAtTime(f * 0.45, t + 0.08);
  const g = gainNode(0);
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(0.18, t + 0.005);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);
  o.connect(g);
  g.connect(out);
  g.connect(wet);
  o.start(t);
  o.stop(t + 0.2);
}

function cricket(out: AudioNode) {
  const ctx = ac!;
  const t0 = ctx.currentTime;
  const f = 4200 + Math.random() * 800;
  const pulses = 2 + Math.floor(Math.random() * 3);
  for (let i = 0; i < pulses; i++) {
    const t = t0 + i * 0.07;
    const o = ctx.createOscillator();
    o.frequency.value = f;
    const g = gainNode(0);
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.025, t + 0.01);
    g.gain.linearRampToValueAtTime(0, t + 0.045);
    o.connect(g).connect(out);
    o.start(t);
    o.stop(t + 0.06);
  }
}

function thunder(out: AudioNode) {
  const ctx = ac!;
  const t = ctx.currentTime;
  burst(out, { at: t, dur: 3.5, vol: 0.9, type: "lowpass", freq: 140, brown: true, attack: 0.08 });
  burst(out, { at: t + 0.05, dur: 1.2, vol: 0.4, type: "lowpass", freq: 400, attack: 0.02 });
}

const LEVELS: Record<AmbienceLayer, number> = { wind: 0.55, rain: 0.8, storm: 1, fire: 0.7, tavern: 0.8, cave: 0.8, water: 0.7, night: 0.8 };

/** Sets the wanted ambience (layer → relative level 0..1). Layers fade in/out over ~2 s. */
export function setAmbience(want: Partial<Record<AmbienceLayer, number>>): void {
  wanted = want;
  syncLayers();
}

function syncLayers() {
  if (!ac || !ambBus || !isUnlocked()) return;
  const t = ac.currentTime;
  for (const [k, lvl] of Object.entries(wanted) as [AmbienceLayer, number][]) {
    const target = lvl * LEVELS[k];
    let l = layers.get(k);
    if (!l) {
      const g = gainNode(0);
      g.connect(ambBus);
      l = { gain: g, stop: buildLayer(k, g), level: 0 };
      layers.set(k, l);
    }
    l.level = target;
    l.gain.gain.cancelScheduledValues(t);
    l.gain.gain.setTargetAtTime(target, t, 0.7);
  }
  for (const k of [...layers.keys()]) if (!(k in wanted)) dropLayer(k);
}

function dropLayer(k: AmbienceLayer) {
  const l = layers.get(k);
  if (!l || !ac) return;
  layers.delete(k);
  l.gain.gain.setTargetAtTime(0, ac.currentTime, 0.6);
  window.setTimeout(() => {
    l.stop();
    l.gain.disconnect();
  }, 3500);
}

// ---------- one-shot effects ----------

export function play(fx: Effect): void {
  if (!ac || !fxBus || !isUnlocked() || !getPrefs().effects) return;
  const ctx = ac;
  const out = fxBus;
  const t = ctx.currentTime;
  switch (fx) {
    case "sword": {
      // metallic clang: inharmonic partials + a bright scrape
      for (const [f, v] of [
        [1250, 0.18],
        [1870, 0.12],
        [2960, 0.09],
        [4130, 0.06],
      ] as const) {
        const o = ctx.createOscillator();
        o.type = "triangle";
        o.frequency.value = f * (0.97 + Math.random() * 0.06);
        const g = gainNode(0);
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(v, t + 0.002);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.5 + Math.random() * 0.3);
        o.connect(g).connect(out);
        o.start(t);
        o.stop(t + 0.9);
      }
      burst(out, { dur: 0.18, vol: 0.35, type: "highpass", freq: 3000 });
      break;
    }
    case "arrow": {
      const f = burst(out, { dur: 0.22, vol: 0.25, type: "bandpass", freq: 900, q: 3, attack: 0.05 });
      f.frequency.setValueAtTime(600, t);
      f.frequency.exponentialRampToValueAtTime(3500, t + 0.2);
      const o = ctx.createOscillator();
      o.frequency.setValueAtTime(180, t + 0.22);
      o.frequency.exponentialRampToValueAtTime(70, t + 0.32);
      const g = gainNode(0);
      g.gain.setValueAtTime(0, t + 0.22);
      g.gain.linearRampToValueAtTime(0.5, t + 0.225);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.4);
      o.connect(g).connect(out);
      o.start(t + 0.22);
      o.stop(t + 0.45);
      burst(out, { at: t + 0.22, dur: 0.06, vol: 0.3, type: "lowpass", freq: 1200 });
      break;
    }
    case "whoosh": {
      const f = burst(out, { dur: 0.3, vol: 0.16, type: "bandpass", freq: 700, q: 2, attack: 0.1 });
      f.frequency.setValueAtTime(400, t);
      f.frequency.exponentialRampToValueAtTime(1800, t + 0.28);
      break;
    }
    case "magic": {
      const delay = ctx.createDelay(1);
      delay.delayTime.value = 0.12;
      const fb = gainNode(0.45);
      delay.connect(fb).connect(delay);
      delay.connect(out);
      [880, 1108, 1318, 1760, 2217].forEach((f, i) => {
        const at = t + i * 0.045;
        const o = ctx.createOscillator();
        o.type = "sine";
        o.frequency.value = f;
        const g = gainNode(0);
        g.gain.setValueAtTime(0, at);
        g.gain.linearRampToValueAtTime(0.07, at + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, at + 0.6);
        o.connect(g);
        g.connect(out);
        g.connect(delay);
        lfo(9, 6, o.frequency);
        o.start(at);
        o.stop(at + 0.7);
      });
      const f = burst(out, { dur: 0.6, vol: 0.08, type: "bandpass", freq: 4000, q: 4, attack: 0.15 });
      f.frequency.exponentialRampToValueAtTime(8000, t + 0.6);
      window.setTimeout(() => delay.disconnect(), 3000);
      break;
    }
    case "thud": {
      const o = ctx.createOscillator();
      o.frequency.setValueAtTime(120, t);
      o.frequency.exponentialRampToValueAtTime(40, t + 0.25);
      const g = gainNode(0);
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.8, t + 0.005);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.35);
      o.connect(g).connect(out);
      o.start(t);
      o.stop(t + 0.4);
      burst(out, { dur: 0.15, vol: 0.4, type: "lowpass", freq: 500, brown: true });
      break;
    }
    case "crit": {
      // short brassy fanfare
      [
        [392, 0],
        [523, 0.09],
        [784, 0.18],
      ].forEach(([f, d]) => {
        const at = t + d;
        for (const det of [-6, 6]) {
          const o = ctx.createOscillator();
          o.type = "sawtooth";
          o.frequency.value = f;
          o.detune.value = det;
          const lp = filter("lowpass", 2200);
          const g = gainNode(0);
          g.gain.setValueAtTime(0, at);
          g.gain.linearRampToValueAtTime(0.07, at + 0.02);
          g.gain.setValueAtTime(0.07, at + (d === 0.18 ? 0.35 : 0.08));
          g.gain.exponentialRampToValueAtTime(0.0001, at + (d === 0.18 ? 0.9 : 0.2));
          o.connect(lp).connect(g).connect(out);
          o.start(at);
          o.stop(at + 1);
        }
      });
      break;
    }
    case "heal": {
      [1046, 1318, 1568, 2093].forEach((f, i) => bell(out, f, t + i * 0.08, 0.08, 1.2));
      break;
    }
    case "coins": {
      for (let i = 0; i < 7; i++) {
        const at = t + i * (0.04 + Math.random() * 0.05);
        const o = ctx.createOscillator();
        o.type = "triangle";
        o.frequency.value = 3200 + Math.random() * 2600;
        const g = gainNode(0);
        g.gain.setValueAtTime(0, at);
        g.gain.linearRampToValueAtTime(0.06, at + 0.002);
        g.gain.exponentialRampToValueAtTime(0.0001, at + 0.18);
        o.connect(g).connect(out);
        o.start(at);
        o.stop(at + 0.2);
      }
      break;
    }
    case "dice": {
      let at = t;
      for (let i = 0; i < 9; i++) {
        at += 0.03 + Math.random() * (0.04 + i * 0.012);
        burst(out, { at, dur: 0.025, vol: 0.25 * (1 - i / 12), type: "bandpass", freq: 1800 + Math.random() * 2200, q: 2 });
      }
      break;
    }
    case "door": {
      const o = ctx.createOscillator();
      o.type = "sawtooth";
      o.frequency.setValueAtTime(90, t);
      o.frequency.linearRampToValueAtTime(140, t + 0.4);
      o.frequency.linearRampToValueAtTime(70, t + 1.1);
      lfo(23, 25, o.frequency);
      const bp = filter("bandpass", 900, 5);
      const g = gainNode(0);
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.12, t + 0.15);
      g.gain.linearRampToValueAtTime(0.08, t + 0.9);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 1.2);
      o.connect(bp).connect(g).connect(out);
      o.start(t);
      o.stop(t + 1.3);
      break;
    }
    case "toll": {
      bell(out, 196, t, 0.28, 4.5);
      bell(out, 196, t + 2.2, 0.2, 4);
      break;
    }
  }
}

function bell(out: AudioNode, f: number, at: number, vol: number, dur: number) {
  const ctx = ac!;
  for (const [ratio, v] of [
    [1, 1],
    [2.76, 0.45],
    [5.4, 0.25],
    [8.93, 0.12],
  ] as const) {
    const o = ctx.createOscillator();
    o.type = "sine";
    o.frequency.value = f * ratio;
    const g = gainNode(0);
    g.gain.setValueAtTime(0, at);
    g.gain.linearRampToValueAtTime(vol * v, at + 0.004);
    g.gain.exponentialRampToValueAtTime(0.0001, at + dur / ratio ** 0.4);
    o.connect(g).connect(out);
    o.start(at);
    o.stop(at + dur + 0.1);
  }
}

// ---------- mapping game state → sound ----------

const INDOOR = new Set(["tavern", "dungeon", "cave", "castle", "temple"]);

export function ambienceFor(scene: { type?: string; time_of_day?: string; weather?: string; hour?: number } | null, terrain?: string | null): Partial<Record<AmbienceLayer, number>> {
  if (!scene && !terrain) return {};
  const type = (terrain || scene?.type || "").toLowerCase();
  const w = weatherKind(scene?.weather);
  const night = isNight(scene?.hour, scene?.time_of_day);
  const out: Partial<Record<AmbienceLayer, number>> = {};
  switch (type) {
    case "tavern":
      out.tavern = 1;
      out.fire = 0.6;
      break;
    case "dungeon":
    case "cave":
      out.cave = 1;
      break;
    case "ruins":
      out.wind = 0.6;
      out.cave = 0.4;
      break;
    case "castle":
    case "temple":
      out.fire = 0.4;
      out.cave = 0.3;
      break;
    case "coast":
      out.water = 1;
      out.wind = 0.5;
      break;
    case "swamp":
      out.water = 0.6;
      break;
    case "camp":
      out.fire = 1;
      out.wind = 0.3;
      break;
    case "town":
      out.wind = 0.3;
      out.tavern = 0.25;
      break;
    default: // wilderness, forest, road, mountain
      out.wind = type === "mountain" ? 1 : 0.6;
  }
  const indoor = INDOOR.has(type);
  if (!indoor) {
    if (w === "storm") out.storm = 1;
    else if (w === "rain") out.rain = 1;
    if (w === "wind" || w === "snow" || w === "storm") out.wind = Math.max(out.wind ?? 0, 1);
    if (night && (w === "clear" || w === "overcast") && type !== "town" && type !== "coast") out.night = 1;
  }
  return out;
}

export type WeatherKind = "clear" | "overcast" | "rain" | "storm" | "snow" | "fog" | "wind";

export function weatherKind(text?: string | null): WeatherKind {
  const s = (text || "").toLowerCase();
  if (/storm|thunder|lightning|tempest/.test(s)) return "storm";
  if (/snow|blizzard|sleet|flurr/.test(s)) return "snow";
  if (/rain|drizzle|shower|downpour/.test(s)) return "rain";
  if (/fog|mist|haze|murk/.test(s)) return "fog";
  if (/wind|gust|gale|breez/.test(s)) return "wind";
  if (/overcast|cloud|grey|gray|gloom/.test(s)) return "overcast";
  return "clear";
}

export function isNight(hour?: number | null, tod?: string | null): boolean {
  if (typeof hour === "number") return hour < 6 || hour >= 20;
  return /night|midnight/.test((tod || "").toLowerCase());
}

const RANGED = /\b(bow|longbow|shortbow|crossbow|arrow|bolt|sling|dart|javelin|blowgun|thrown)\b/i;
const MAGIC = /\b(fire|cold|lightning|radiant|necrotic|force|psychic|thunder|acid|spell|eldritch|ray|blast|missile|flame|frost|chill|sacred|smite|bolt of)\b/i;
const BLUNT = /\b(bite|claw|claws|slam|tail|fist|unarmed|club|greatclub|maul|warhammer|light hammer|mace|morningstar|flail|hooves|gore|tentacle|quarterstaff|staff)\b/i;

/** Picks a sound for a combat log line (text + data from the server). */
export function combatEffect(text: string, data: Record<string, unknown> | null): Effect[] {
  const d = data ?? {};
  const out: Effect[] = [];
  if (typeof d.heal === "number" && d.heal > 0) out.push("heal");
  if (d.hit === true) {
    const weapon = /\bwith (.+?):/i.exec(text)?.[1] ?? "";
    const probe = `${weapon} ${String(d.damage_type ?? "")} ${String(d.attack ?? "")}`;
    if (MAGIC.test(probe) || (!weapon && MAGIC.test(text))) out.push("magic");
    else if (RANGED.test(probe)) out.push("arrow");
    else if (BLUNT.test(probe)) out.push("thud");
    else out.push("sword");
    if (d.crit === true) out.push("crit");
  } else if (d.hit === false) out.push("whoosh");
  else if (!out.length && /\b(takes \d+ (fire|cold|lightning|radiant|necrotic|force|psychic|thunder|acid))\b/i.test(text)) out.push("magic");
  if (/\b(falls|dies|is slain|is killed|collapses, dead)\b/i.test(text)) out.push("toll");
  return out;
}
