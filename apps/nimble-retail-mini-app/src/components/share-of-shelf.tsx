"use client";

import { useState } from "react";
import { ChevronRight, Crown } from "lucide-react";
import type { BrandShare } from "@/lib/types";
import { ProductTile } from "./product-tile";
import { useInView } from "@/lib/use-in-view";
import { useCountUp } from "@/lib/use-count-up";

// The category-share centerpiece, brought up into Act 1. Ranked bars with real
// logos; the leader is emphasized ("owns the shelf"). Every row is clickable →
// brand drilldown. Reuses BrandShare from the insight engine.
export function ShareOfShelf({
  keyword,
  brands,
  onSelect,
  selectedBrand,
  highlightBrand,
}: {
  keyword: string;
  brands: BrandShare[];
  onSelect: (brand: string) => void;
  selectedBrand?: string | null;
  highlightBrand?: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const [ref, inView] = useInView<HTMLDivElement>();
  if (!brands.length) return null;

  const leader = brands[0];
  const max = leader.share || 1;
  // Challengers keep their TRUE rank (index+1). If the user's highlighted brand
  // sits below the visible cut, surface it anyway so they can always see it.
  const challengers = brands
    .map((b, i) => ({ b, rank: i + 1 }))
    .slice(1, expanded ? 8 : 5);
  if (highlightBrand) {
    const hiIdx = brands.findIndex((b) => b.brand === highlightBrand);
    if (hiIdx > 0 && !challengers.some((c) => c.rank === hiIdx + 1)) {
      challengers.push({ b: brands[hiIdx], rank: hiIdx + 1 });
    }
  }
  const isActive = (name: string) =>
    selectedBrand === name || highlightBrand === name;

  return (
    <div className="rounded-3xl border border-border bg-card p-5 sm:p-6">
      <div className="mb-4 flex items-baseline justify-between gap-2">
        <h3 className="text-lg font-bold tracking-tight">
          Who owns{" "}
          <span className="capitalize">{keyword}</span>?
        </h3>
        <span className="shrink-0 text-xs font-medium text-muted-foreground">
          share of page one
        </span>
      </div>

      <div ref={ref} className="space-y-2.5">
        {/* Leader — emphasized */}
        <LeaderRow brand={leader} inView={inView} active={isActive(leader.brand)} onSelect={onSelect} />

        {/* Challengers */}
        <div className="divide-y divide-border/60">
          {challengers.map(({ b, rank }) => (
            <BrandRow
              key={b.brand}
              brand={b}
              rank={rank}
              max={max}
              inView={inView}
              active={isActive(b.brand)}
              onSelect={onSelect}
            />
          ))}
        </div>
      </div>

      {brands.length > 6 && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="mt-3 text-sm font-medium text-brand hover:underline"
        >
          {expanded ? "Show less" : `+ ${brands.length - 6} more brands`}
        </button>
      )}
    </div>
  );
}

function LeaderRow({
  brand: b,
  inView,
  active,
  onSelect,
}: {
  brand: BrandShare;
  inView: boolean;
  active: boolean;
  onSelect: (brand: string) => void;
}) {
  const pct = Math.round(b.share * 100);
  const count = useCountUp(pct, { durationMs: 1100, enabled: inView });
  const organicPct = b.count ? (b.organicCount / b.count) * 100 : 0;
  return (
    <button
      onClick={() => onSelect(b.brand)}
      className={`card-hover group flex w-full items-center gap-3 rounded-2xl border p-3 text-left sm:gap-4 ${
        active ? "border-brand/50 bg-brand/10" : "border-border bg-secondary/40"
      }`}
    >
      <ProductTile brand={b.brand} size="md" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-base font-bold tracking-tight">{b.brand}</span>
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-gold px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-black">
            <Crown className="h-3 w-3" /> owns the shelf
          </span>
        </div>
        <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="grow-bar h-full rounded-full"
            style={{
              width: inView ? "100%" : "0%",
              background: `linear-gradient(90deg, var(--gold-deep) ${organicPct}%, var(--brand-2) ${organicPct}%)`,
            }}
          />
        </div>
        <div className="mt-1 text-[11px] text-muted-foreground">
          {b.organicCount} organic · {b.sponsoredCount} sponsored · avg rank {b.avgRank}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="text-3xl font-bold leading-none tabular-nums sm:text-4xl">{count}%</div>
      </div>
    </button>
  );
}

function BrandRow({
  brand: b,
  rank,
  max,
  inView,
  active,
  onSelect,
}: {
  brand: BrandShare;
  rank: number;
  max: number;
  inView: boolean;
  active: boolean;
  onSelect: (brand: string) => void;
}) {
  const pct = Math.round(b.share * 100);
  const count = useCountUp(pct, { durationMs: 900, enabled: inView });
  const organicPct = b.count ? (b.organicCount / b.count) * 100 : 0;
  return (
    <button
      onClick={() => onSelect(b.brand)}
      className={`group flex w-full items-center gap-3 rounded-lg px-1 py-2.5 text-left transition ${
        active ? "bg-brand/10" : "hover:bg-muted/50"
      }`}
    >
      <span className="w-4 shrink-0 text-sm font-semibold text-muted-foreground">{rank}</span>
      <ProductTile brand={b.brand} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-medium">{b.brand}</span>
          <span className="shrink-0 text-sm font-semibold tabular-nums">{count}%</span>
        </div>
        <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="grow-bar h-full rounded-full"
            style={{
              width: inView ? `${(b.share / max) * 100}%` : "0%",
              background: `linear-gradient(90deg, var(--gold-deep) ${organicPct}%, var(--brand-2) ${organicPct}%)`,
            }}
          />
        </div>
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5" />
    </button>
  );
}
