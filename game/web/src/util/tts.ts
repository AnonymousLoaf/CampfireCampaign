/** Spoken narration: the server's voiced audio (Kokoro, a voice per character) when there is some, else the
 * browser's built-in speech synthesis. */
import { useEffect, useState } from "react";
import { getPrefs } from "./prefs";

type Item = { id: string; text: string; audio?: string | null };

let speakingId: string | null = null;
let player: HTMLAudioElement | null = null;
const queue: Item[] = [];
const listeners = new Set<(id: string | null) => void>();

export function ttsSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";
}

function emit() {
  listeners.forEach((l) => l(speakingId));
}

export function englishVoices(): SpeechSynthesisVoice[] {
  if (!ttsSupported()) return [];
  return window.speechSynthesis.getVoices().filter((v) => /^en([-_]|$)/i.test(v.lang));
}

function pickVoice(): SpeechSynthesisVoice | undefined {
  const all = englishVoices();
  const want = getPrefs().voice;
  return (want && all.find((v) => v.voiceURI === want)) || all.find((v) => v.default) || all[0];
}

/** Split long narration into sentence groups — some browsers cut off utterances longer than ~15 s. */
function chunks(text: string): string[] {
  const clean = text.replace(/[*_#>`]/g, "").replace(/\s+/g, " ").trim();
  const sentences = clean.match(/[^.!?…]+[.!?…]+["”’)]*\s*|[^.!?…]+$/g) ?? [clean];
  const out: string[] = [];
  let cur = "";
  for (const s of sentences) {
    if ((cur + s).length > 220 && cur) {
      out.push(cur.trim());
      cur = "";
    }
    cur += s;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

function done(item: Item) {
  if (speakingId !== item.id) return;
  speakingId = null;
  emit();
  const next = queue.shift();
  if (next) speakNow(next);
}

function speakNow(item: Item) {
  if (item.audio) {
    // the server's voiced narration
    speakingId = item.id;
    emit();
    if (!player) player = new Audio();
    player.src = item.audio;
    player.playbackRate = getPrefs().rate || 1;
    player.onended = () => done(item);
    player.onerror = () => {
      // the audio didn't load: read the text with the browser's voice instead
      if (speakingId === item.id && ttsSupported()) speakNow({ id: item.id, text: item.text });
      else done(item);
    };
    player.play().catch(() => done(item)); // blocked until the page has had a tap: skip quietly
    return;
  }
  if (!ttsSupported()) return;
  const synth = window.speechSynthesis;
  const parts = chunks(item.text);
  const voice = pickVoice();
  const rate = getPrefs().rate;
  speakingId = item.id;
  emit();
  parts.forEach((p, i) => {
    const u = new SpeechSynthesisUtterance(p);
    if (voice) {
      u.voice = voice;
      u.lang = voice.lang;
    } else u.lang = "en-US";
    u.rate = rate;
    if (i === parts.length - 1) {
      u.onend = () => {
        if (speakingId !== item.id) return;
        speakingId = null;
        emit();
        const next = queue.shift();
        if (next) speakNow(next);
      };
    }
    u.onerror = () => {
      if (speakingId === item.id && i === parts.length - 1) {
        speakingId = null;
        emit();
      }
    };
    synth.speak(u);
  });
}

function busy(): boolean {
  return speakingId !== null || (ttsSupported() && window.speechSynthesis.speaking);
}

function hush() {
  if (player) {
    player.onended = player.onerror = null;
    player.pause();
  }
  if (ttsSupported()) window.speechSynthesis.cancel();
}

/** Speak now, interrupting anything playing. `audio`: the server's voiced version, when there is one. */
export function speak(id: string, text: string, audio?: string | null): void {
  if (!audio && !ttsSupported()) return;
  queue.length = 0;
  speakingId = null;
  hush();
  speakNow({ id, text, audio });
}

/** Speak after whatever is currently being read (used for auto-read of new narration). */
export function enqueue(id: string, text: string, audio?: string | null): void {
  if (!audio && !ttsSupported()) return;
  if (!busy()) speakNow({ id, text, audio });
  else queue.push({ id, text, audio });
}

export function stopSpeaking(): void {
  queue.length = 0;
  speakingId = null;
  hush();
  emit();
}

/** Whether anything can speak here: the browser's voice, or audio files (the server's voices). */
export function canSpeak(): boolean {
  return ttsSupported() || typeof Audio !== "undefined";
}

export function useSpeakingId(): string | null {
  const [id, setId] = useState(speakingId);
  useEffect(() => {
    listeners.add(setId);
    return () => {
      listeners.delete(setId);
    };
  }, []);
  return id;
}

/** English voices, re-read when the browser finishes loading them. */
export function useVoices(): SpeechSynthesisVoice[] {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>(() => englishVoices());
  useEffect(() => {
    if (!ttsSupported()) return;
    const upd = () => setVoices(englishVoices());
    upd();
    window.speechSynthesis.addEventListener("voiceschanged", upd);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", upd);
  }, []);
  return voices;
}
