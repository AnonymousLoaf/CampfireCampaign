import { useEffect, useState } from "react";

export function formatMoney(cp: number): string {
  const neg = cp < 0;
  let n = Math.abs(Math.round(cp));
  const gp = Math.floor(n / 100);
  n -= gp * 100;
  const sp = Math.floor(n / 10);
  const c = n - sp * 10;
  const parts: string[] = [];
  if (gp) parts.push(`${gp.toLocaleString()} gp`);
  if (sp) parts.push(`${sp} sp`);
  if (c || parts.length === 0) parts.push(`${c} cp`);
  return (neg ? "-" : "") + parts.join(" ");
}

export function formatCountdown(deadline: string | null, now: number = Date.now()): string {
  if (!deadline) return "no deadline";
  const ms = new Date(deadline).getTime() - now;
  if (Number.isNaN(ms)) return "";
  if (ms <= 0) return "overdue";
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec.toString().padStart(2, "0")}s`;
  return `${sec}s`;
}

export function signed(n: number): string {
  return n >= 0 ? `+${n}` : `${n}`;
}

export function abilityMod(score: number): number {
  return Math.floor((score - 10) / 2);
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function timeAgo(ts: string): string {
  const ms = Date.now() - new Date(ts).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/** Re-renders every `ms` so countdowns tick. */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(t);
  }, [ms]);
  return now;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export const PHASE_LABEL: Record<string, string> = {
  lobby: "Gathering the party",
  exploration: "Exploration",
  roll: "Rolls needed",
  shop: "Shopping",
  combat: "Combat",
  dm: "The DM is writing…",
  ended: "Campaign over",
};
