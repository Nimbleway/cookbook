import type { InsightTone } from "./types";

export function fmtPrice(n?: number): string {
  if (n === undefined) return "—";
  return `$${n.toFixed(2)}`;
}

export function fmtCount(n?: number): string {
  if (n === undefined) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return `${n}`;
}

// Tailwind class sets per insight tone. Centralized so every surface agrees.
export const toneStyles: Record<
  InsightTone,
  { chip: string; bar: string; text: string; dot: string }
> = {
  positive: {
    chip: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
    bar: "bg-emerald-500",
    text: "text-emerald-300",
    dot: "bg-emerald-400",
  },
  warning: {
    chip: "bg-orange-500/10 text-orange-300 border-orange-500/30",
    bar: "bg-orange-500",
    text: "text-orange-300",
    dot: "bg-orange-400",
  },
  opportunity: {
    chip: "bg-brand/10 text-brand border-brand/30",
    bar: "bg-gold",
    text: "text-brand",
    dot: "bg-brand",
  },
  neutral: {
    chip: "bg-white/5 text-muted-foreground border-border",
    bar: "bg-muted-foreground/50",
    text: "text-muted-foreground",
    dot: "bg-muted-foreground",
  },
};
