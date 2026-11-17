/** Spoken narration: the audio the host PC makes with Kokoro, a voice per character. There's no fallback to
 * the browser's own speech: a narration without voiced audio simply isn't read. */
import { useEffect, useState } from "react";
import { getPrefs } from "./prefs";

type Item = { id: string; audio: string };

let speakingId: string | null = null;
let player: HTMLAudioElement | null = null;
const queue: Item[] = [];
const listeners = new Set<(id: string | null) => void>();

/** Whether this browser can play the voiced narration. */
export function canSpeak(): boolean {
  return typeof window !== "undefined" && typeof Audio !== "undefined";
}

function emit() {
  listeners.forEach((l) => l(speakingId));
}

function done(item: Item) {
  if (speakingId !== item.id) return;
  speakingId = null;
  emit();
  const next = queue.shift();
  if (next) speakNow(next);
}

function speakNow(item: Item) {
  speakingId = item.id;
  emit();
  if (!player) player = new Audio();
  player.src = item.audio;
  player.playbackRate = getPrefs().rate || 1;
  player.onended = () => done(item);
  player.onerror = () => done(item);
  player.play().catch(() => done(item)); // blocked until the page has had a tap: skip quietly
}

function hush() {
  if (player) {
    player.onended = player.onerror = null;
    player.pause();
  }
}

/** Play a narration now, interrupting anything playing. */
export function speak(id: string, audio: string): void {
  if (!canSpeak()) return;
  queue.length = 0;
  speakingId = null;
  hush();
  speakNow({ id, audio });
}

/** Play after whatever is currently being read (auto-read of new narration). */
export function enqueue(id: string, audio: string): void {
  if (!canSpeak()) return;
  if (speakingId === null) speakNow({ id, audio });
  else queue.push({ id, audio });
}

export function stopSpeaking(): void {
  queue.length = 0;
  speakingId = null;
  hush();
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
