"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { retailerColorByLabel } from "@/lib/retailers";
import { BrandLogo } from "./product-tile";

// A live-styled preview that cycles the kind of cross-retailer / earned-vs-bought
// "I didn't know that" each search surfaces — not a bare share number. Brands are
// chosen for reliable logos; the real pull happens when you click.
const PREVIEWS = [
  { keyword: "Protein Bars", brand: "Premier Protein", retailer: "Walmart", tag: "Cross-retailer", headline: "Owns Walmart's shelf — but barely shows on Amazon." },
  { keyword: "Energy Drinks", brand: "Monster", retailer: "Amazon", tag: "Earned vs bought", headline: "Leads Amazon — but half of it is paid placement." },
  { keyword: "Coffee", brand: "Starbucks", retailer: "Amazon", tag: "Retailers disagree", headline: "Owns Amazon coffee. A different brand owns Walmart." },
  { keyword: "Sparkling Water", brand: "LaCroix", retailer: "Amazon", tag: "Cross-retailer", headline: "Wins Amazon — but loses the Target shelf entirely." },
];

export function HeroPreview({ onPick }: { onPick: (kw: string) => void }) {
  const reduced = useReducedMotion();
  const [i, setI] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const t = setInterval(() => setI((p) => (p + 1) % PREVIEWS.length), 3400);
    return () => clearInterval(t);
  }, [reduced]);

  const p = PREVIEWS[i];

  return (
    <button
      onClick={() => onPick(p.keyword)}
      className="card-hover group relative w-full overflow-hidden rounded-3xl border border-border bg-card p-5 text-left shadow-[0_24px_70px_-40px_oklch(0.2_0_0/0.55)]"
      aria-label={`Explore ${p.keyword}`}
    >
      {/* example header — these are illustrative samples that cycle; the real
          pull happens when you run a search. Labeled "Example", not "Live". */}
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-muted-foreground/50" />
        <span className="text-[11px] font-semibold uppercase tracking-wider">
          <span className="text-muted-foreground">Example · </span>
          <span style={{ color: retailerColorByLabel(p.retailer) }}>{p.retailer}</span>
        </span>
        <span className="ml-auto inline-flex items-center gap-0.5 text-xs font-medium text-muted-foreground opacity-0 transition group-hover:opacity-100">
          Explore <ArrowUpRight className="h-3.5 w-3.5" />
        </span>
      </div>

      {/* cycling insight — keyed so the fade replays each rotation */}
      <PreviewBody key={i} p={p} />
    </button>
  );
}

function PreviewBody({ p }: { p: (typeof PREVIEWS)[number] }) {
  return (
    <div className="animate-fade-up">
      <div className="mt-4 flex items-center gap-2">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {p.keyword}
        </p>
        <span className="ml-auto shrink-0 rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-brand">
          {p.tag}
        </span>
      </div>
      <div className="mt-1.5 flex items-center gap-2.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-white ring-1 ring-black/10">
          <BrandLogo brand={p.brand} className="h-6 w-6" />
        </span>
        <div className="min-w-0 truncate text-2xl font-bold leading-tight tracking-tight">
          {p.brand}
        </div>
      </div>
      <p className="mt-3 text-[15px] font-bold leading-snug tracking-tight text-foreground">
        {p.headline}
      </p>
      <p className="mt-2 text-xs text-muted-foreground">
        Only Nimble reads this live across every retailer.
      </p>
    </div>
  );
}
