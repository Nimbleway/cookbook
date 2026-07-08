"use client";

import { GitCompare, Scale, Radio, MapPin, Zap, ArrowUpRight } from "lucide-react";
import { useLeadModal } from "./lead-modal";

// Compact "what your reports miss" rail — sits in the hero's right column on
// desktop (above the live example) to back up the headline, and stacks under
// the hook on mobile. Tight one-liners, not a big band.
const PAINS = [
  { Icon: GitCompare, label: "Cross-retailer, side by side", line: "Amazon, Walmart & Target — one shelf, three stories." },
  { Icon: Scale, label: "Earned vs bought", line: "Who's winning on merit vs renting it with ads." },
  { Icon: Radio, label: "Live, not last week", line: "Price, rank & stock — pulled the moment you ask." },
  { Icon: MapPin, label: "Every market", line: "The national shelf hides how it shifts by city & store." },
  { Icon: Zap, label: "Retailer data, fast", line: "Any category — the full live picture in seconds." },
];

export function LandingPains() {
  const { open } = useLeadModal();
  return (
    <div className="animate-fade-up rounded-2xl border border-border bg-card/60 p-5 text-left">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand">
        What your data misses
      </p>
      <ul className="mt-3 space-y-3">
        {PAINS.map(({ Icon, label, line }) => (
          <li key={label} className="flex gap-3">
            <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand">
              <Icon className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-bold leading-snug">{label}</p>
              <p className="text-xs leading-snug text-muted-foreground">{line}</p>
            </div>
          </li>
        ))}
      </ul>
      <button
        onClick={() => open()}
        className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-gold px-3.5 py-2 text-sm font-bold text-background transition active:scale-[0.98]"
      >
        Get in touch for more data
        <ArrowUpRight className="h-4 w-4" />
      </button>
    </div>
  );
}
