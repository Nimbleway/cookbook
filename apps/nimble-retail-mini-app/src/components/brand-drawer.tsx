"use client";

import { useEffect, useState } from "react";
import { X, TrendingUp, TrendingDown, Star } from "lucide-react";
import type { RetailerId, RetailerResult, RetailerSerpResult } from "@/lib/types";
import { RETAILER_META } from "@/lib/retailers";
import { ProductTile } from "./product-tile";

// Competitive drilldown for a single brand. Computed live from the raw rows so
// every brand click reveals genuinely new intelligence (per-retailer share,
// organic vs paid, rating edge, and a "so what").
export function BrandDrawer({
  brand,
  results,
  onClose,
  onSelectBrand,
}: {
  brand: string;
  results: RetailerResult[];
  onClose: () => void;
  onSelectBrand: (b: string) => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Grow the per-retailer bars from zero once the panel has mounted.
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setGrown(true), 60);
    return () => clearTimeout(t);
  }, []);

  const ok = results.filter(
    (r): r is Extract<RetailerResult, { status: "ok" }> => r.status === "ok",
  );
  const allRows = ok.flatMap((r) => r.results);
  const brandRows = allRows.filter((r) => r.brand === brand);

  // Per-retailer share for this brand.
  const perRetailer = ok.map((r) => {
    const rows = r.results;
    const mine = rows.filter((x) => x.brand === brand);
    return {
      retailer: r.retailer,
      share: rows.length ? Math.round((mine.length / rows.length) * 100) : 0,
      organic: mine.filter((m) => !m.sponsored).length,
      sponsored: mine.filter((m) => m.sponsored).length,
      bestRank: mine.length ? Math.min(...mine.map((m) => m.rank)) : null,
    };
  });

  const organic = brandRows.filter((r) => !r.sponsored).length;
  const sponsored = brandRows.filter((r) => r.sponsored).length;
  const avgRating = avg(brandRows.map((r) => r.rating));
  const catAvgRating = avg(allRows.map((r) => r.rating));
  const ratingEdge = avgRating && catAvgRating ? avgRating - catAvgRating : 0;

  const strongest = [...perRetailer].sort((a, b) => b.share - a.share)[0];
  const weakest = [...perRetailer].sort((a, b) => a.share - b.share)[0];
  const gap = strongest && weakest ? strongest.share - weakest.share : 0;

  // Competing brands to jump to next.
  const competitors = topBrands(allRows, brand).slice(0, 4);

  const discovery = buildDiscovery({
    brand,
    organic,
    sponsored,
    ratingEdge,
    gap,
    strongest,
    weakest,
  });

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 animate-fade-in bg-foreground/30 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside className="relative flex h-full w-[min(100vw,28rem)] animate-drawer-in flex-col overflow-y-auto bg-background shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-background/90 p-4 backdrop-blur">
          <div className="flex items-center gap-3">
            <ProductTile brand={brand} size="md" />
            <div>
              <h2 className="text-lg font-bold tracking-tight">{brand}</h2>
              <p className="text-xs text-muted-foreground">
                {brandRows.length} page-one placements analyzed
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-muted-foreground hover:bg-muted"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5 p-4">
          {/* The reveal */}
          <div className="rounded-2xl border border-brand/20 bg-brand/10 p-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand">
              <TrendingUp className="h-3.5 w-3.5" /> The insight
            </p>
            <p className="mt-1.5 text-[0.95rem] font-medium leading-snug">
              {discovery}
            </p>
          </div>

          {/* Organic vs paid */}
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Organic placements" value={organic} tone="positive" />
            <Stat label="Sponsored placements" value={sponsored} tone="warning" />
          </div>

          {/* Rating edge */}
          <div className="rounded-2xl border border-border bg-card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Quality signal
            </p>
            <div className="mt-1 flex items-center gap-2">
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              <span className="text-xl font-bold">
                {avgRating ? avgRating.toFixed(2) : "—"}
              </span>
              {ratingEdge !== 0 && (
                <span
                  className={`inline-flex items-center gap-0.5 text-xs font-medium ${
                    ratingEdge > 0 ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {ratingEdge > 0 ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : (
                    <TrendingDown className="h-3 w-3" />
                  )}
                  {ratingEdge > 0 ? "+" : ""}
                  {ratingEdge.toFixed(2)} vs category
                </span>
              )}
            </div>
          </div>

          {/* Per-retailer share */}
          <div className="rounded-2xl border border-border bg-card p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Share by retailer
            </p>
            <div className="space-y-2.5">
              {perRetailer.map((p) => (
                <div key={p.retailer} className="flex items-center gap-3">
                  <span className="w-16 shrink-0 text-sm font-medium">
                    {RETAILER_META[p.retailer].label}
                  </span>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className="grow-bar h-full rounded-full"
                      style={{
                        width: `${grown ? p.share : 0}%`,
                        background: RETAILER_META[p.retailer].color,
                      }}
                    />
                  </div>
                  <span className="w-10 shrink-0 text-right text-sm font-semibold tabular-nums">
                    {p.share}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Jump to a competitor */}
          {competitors.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Compare against
              </p>
              <div className="flex flex-wrap gap-2">
                {competitors.map((c) => (
                  <button
                    key={c}
                    onClick={() => onSelectBrand(c)}
                    className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-sm font-medium hover:border-brand/40"
                  >
                    <ProductTile brand={c} size="sm" />
                    {c}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "positive" | "warning";
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p
        className={`mt-1 text-2xl font-bold ${
          tone === "positive" ? "text-emerald-400" : "text-brand"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function avg(nums: (number | undefined)[]): number | undefined {
  const v = nums.filter((n): n is number => typeof n === "number");
  if (!v.length) return undefined;
  return v.reduce((a, b) => a + b, 0) / v.length;
}

function topBrands(rows: RetailerSerpResult[], exclude: string): string[] {
  const counts = new Map<string, number>();
  for (const r of rows) {
    if (r.brand === exclude) continue;
    counts.set(r.brand, (counts.get(r.brand) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([b]) => b);
}

function buildDiscovery(d: {
  brand: string;
  organic: number;
  sponsored: number;
  ratingEdge: number;
  gap: number;
  strongest: { retailer: RetailerId; share: number } | undefined;
  weakest: { retailer: RetailerId; share: number } | undefined;
}): string {
  if (d.gap >= 20 && d.strongest && d.weakest) {
    return `${d.brand} owns ${d.strongest.share}% of ${RETAILER_META[d.strongest.retailer].label}'s shelf but only ${d.weakest.share}% of ${RETAILER_META[d.weakest.retailer].label}'s — wide open on one retailer, locked on another.`;
  }
  if (d.organic > d.sponsored * 2 && d.organic > 0) {
    return `${d.brand} wins mostly organically (${d.organic} organic vs ${d.sponsored} paid) — it ranks on merit, not just ad spend. Hard for challengers to buy their way past.`;
  }
  if (d.sponsored > d.organic && d.sponsored > 0) {
    return `${d.brand} leans on paid placement (${d.sponsored} sponsored vs ${d.organic} organic) — its visibility could erode fast if it pulls back ad spend.`;
  }
  if (d.ratingEdge > 0.15) {
    return `${d.brand} rates +${d.ratingEdge.toFixed(2)} above the category average — shoppers love it more than its shelf share suggests. Room to convert quality into visibility.`;
  }
  if (d.ratingEdge < -0.15) {
    return `${d.brand} holds visibility despite below-average ratings — a quality gap competitors can exploit with better reviews.`;
  }
  return `${d.brand} holds a balanced position across retailers — steady organic and paid presence with no single point of failure.`;
}
