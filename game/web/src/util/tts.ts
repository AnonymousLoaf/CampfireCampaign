/** Spoken narration with the browser's built-in speech synthesis (free, no key). */
import { useEffect, useState } from "react";
import { getPrefs } from "./prefs";

type Item = { id: string; text: string };

let speakingId: string | null = null;
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

function speakNow(item: Item) {
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

/** Speak now, interrupting anything playing. */
export function speak(id: string, text: string): void {
  if (!ttsSupported()) return;
  queue.length = 0;
  speakingId = null;
  window.speechSynthesis.cancel();
  speakNow({ id, text });
}

/** Speak after whatever is currently being read (used for auto-read of new narration). */
export function enqueue(id: string, text: string): void {
  if (!ttsSupported()) return;
  if (speakingId === null && !window.speechSynthesis.speaking) speakNow({ id, text });
  else queue.push({ id, text });
}

export function stopSpeaking(): void {
  if (!ttsSupported()) return;
  queue.length = 0;
  speakingId = null;
  window.speechSynthesis.cancel();
  emit();
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
