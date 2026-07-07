import { Swords, Sparkles, AlertTriangle, GitCompare, Activity } from "lucide-react";
import type { FindingKind } from "@/lib/types";

// ─── Executive signal categories ─────────────────────────────────────────────
// Every analysis maps to ONE of five categories a VP grasps instantly. The chip
// is the 5-second tell — it says "this is a Risk / an Opportunity / …" before a
// single number is read. This is the de-dashboarding primitive.
export type SignalCategory =
  | "competition"
  | "opportunity"
  | "risk"
  | "difference"
  | "monitoring";

const MAP: Record<
  SignalCategory,
  { label: string; Icon: typeof Swords; cls: string }
> = {
  competition: {
    label: "Competition",
    Icon: Swords,
    cls: "text-amber-300 border-amber-500/25 bg-amber-500/[0.12]",
  },
  opportunity: {
    label: "Opportunity",
    Icon: Sparkles,
    cls: "text-emerald-300 border-emerald-500/25 bg-emerald-500/[0.12]",
  },
  risk: {
    label: "Risk",
    Icon: AlertTriangle,
    cls: "text-orange-300 border-orange-500/25 bg-orange-500/[0.12]",
  },
  difference: {
    label: "Difference",
    Icon: GitCompare,
    cls: "text-brand border-brand/30 bg-brand/[0.10]",
  },
  monitoring: {
    label: "Monitoring",
    Icon: Activity,
    cls: "text-sky-300 border-sky-500/25 bg-sky-500/[0.12]",
  },
};

export function SignalChip({
  category,
  className,
}: {
  category: SignalCategory;
  className?: string;
}) {
  const m = MAP[category];
  const Icon = m.Icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${m.cls} ${className ?? ""}`}
    >
      <Icon className="h-3 w-3" />
      {m.label}
    </span>
  );
}

// Map each "3 things we found" finding to a signal category, so every takeaway
// reads as Competition / Opportunity / Risk / Difference.
export function findingSignalCategory(kind: FindingKind): SignalCategory {
  switch (kind) {
    case "leaders":
    case "price":
      return "difference";
    case "sponsored":
    case "promo":
      return "risk";
    case "availability":
    case "stockout":
    case "fragmentation":
      return "opportunity";
    case "demand":
    case "dominance":
      return "competition";
    default:
      return "competition";
  }
}
