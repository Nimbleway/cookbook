"use client";

import type { InsightPayload } from "@/lib/types";
import { ProductImage } from "./product-tile";
import { useCountUp } from "@/lib/use-count-up";
import { retailerColorByLabel } from "@/lib/retailers";
import { heroCopy } from "@/lib/hero-copy";
import { SignalChip } from "./signal-chip";

// Compact answer hero. Headline/eyebrow/subline adapt to search INTENT
// (category / brand / keyword) via heroCopy — deterministic, instant. Kept
// small on purpose so the cross-retailer matrix lands near the fold.
export function HeroInsight({
  insights,
  live,
  focusBrand,
}: {
  insights: InsightPayload;
  live: boolean;
  focusBrand?: string | null;
}) {
  const hero = insights.heroInsight;
  const copy = heroCopy(insights, focusBrand);
  const share = useCountUp(hero.share, { durationMs: 1100 });
  const pulledAt = new Date(insights.collectedAt).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
  // The actual #1 SKU for the winning brand → show its real product photo.
  const topSku = insights.results
    .filter((r) => r.brand === hero.brand)
    .sort((a, b) => a.rank - b.rank)[0];

  return (
    <section className="animate-fade-up rounded-3xl border border-border bg-card p-5 shadow-[0_20px_70px_-40px_oklch(0.2_0_0/0.5)] sm:p-7">
      {/* Loud freshness proof — the credibility signal, hero-level not a caption */}
      <div className="mb-3 flex items-center gap-2">
        {live ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-emerald-300">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            Live · pulled {pulledAt}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-amber-300">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            Sample shelf
          </span>
        )}
        <SignalChip category="competition" className="hidden sm:inline-flex" />
      </div>

      {/* Intent-adaptive headline leads; eyebrow frames it; the brand+% is the anchor. */}
      <p className="mb-3 max-w-3xl text-balance text-xl font-bold leading-[1.14] tracking-tight sm:text-2xl">
        {copy.headline}
      </p>

      <p className="text-xs font-medium uppercase tracking-wider text-brand">
        {copy.eyebrow}
      </p>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="hidden sm:block">
          <ProductImage
            brand={hero.brand}
            imageUrl={topSku?.imageUrl}
            title={topSku?.productTitle}
            size="lg"
            href={topSku?.productUrl}
          />
        </div>
        <div className="text-[1.75rem] font-bold leading-none tracking-tight sm:text-5xl">
          {hero.brand}
        </div>
        <div className="text-lg font-semibold text-muted-foreground sm:text-2xl">
          <span className="text-gradient tabular-nums">{share}%</span>
          {hero.retailerLabel ? (
            <>
              {" of "}
              <span style={{ color: retailerColorByLabel(hero.retailerLabel) }}>
                {hero.retailerLabel}
              </span>
              {"’s shelf"}
            </>
          ) : (
            " of page one"
          )}
        </div>
      </div>

      <p className="mt-3 max-w-2xl text-base text-foreground/80">{copy.subline}</p>
    </section>
  );
}
