"use client";

import { Flame, TrendingUp } from "lucide-react";
import type { TopSeller } from "@/lib/types";
import { RETAILER_META } from "@/lib/retailers";
import { ProductPhoto } from "./product-tile";

// "Selling right now" — the signal a static report can never show. Reads like a
// live feed, not a chart. The "#N on shelf" tag vs sales order is the aha:
// what's selling isn't always what's most visible.
export function SellingNow({ topSelling }: { topSelling: TopSeller[] }) {
  if (!topSelling.length) return null;

  return (
    <section className="animate-fade-up overflow-hidden rounded-3xl border border-border bg-[oklch(0.17_0_0)] text-white">
      <div className="flex items-center gap-2 border-b border-white/10 px-5 py-3.5">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose-500" />
        </span>
        <Flame className="h-4 w-4 text-amber-400" />
        <h3 className="font-semibold tracking-tight">Selling right now</h3>
        <span className="ml-auto text-xs text-white/50">
          live purchase velocity · this month
        </span>
      </div>

      <div className="flex gap-3 overflow-x-auto p-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {topSelling.map((t, i) => {
          const beatsVisibility = t.visibilityRank > i + 1;
          return (
            <div
              key={`${t.retailer}-${t.productTitle}-${i}`}
              className="flex w-56 shrink-0 flex-col gap-2 rounded-2xl bg-white/[0.06] p-3.5 ring-1 ring-white/10"
            >
              {/* Product photo as the focal point (real image when live) */}
              <div className="relative">
                <div className="h-32 overflow-hidden rounded-xl bg-white">
                  <ProductPhoto
                    brand={t.brand}
                    imageUrl={t.imageUrl}
                    title={t.productTitle}
                    href={t.productUrl}
                  />
                </div>
                <span className="absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-black/70 text-xs font-bold text-white">
                  {i + 1}
                </span>
              </div>

              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-semibold">{t.brand}</span>
                <span
                  className="flex shrink-0 items-center gap-1 text-[11px]"
                  style={{ color: RETAILER_META[t.retailer].color }}
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: RETAILER_META[t.retailer].color }}
                  />
                  {RETAILER_META[t.retailer].label}
                </span>
              </div>

              <p className="line-clamp-2 text-xs text-white/60">
                {t.productTitle}
              </p>

              <div className="mt-auto flex items-end justify-between">
                <div>
                  <div className="text-lg font-bold leading-none text-amber-300">
                    {t.recentSales.replace(/ bought.*/, "")}
                  </div>
                  <div className="text-[10px] uppercase tracking-wide text-white/40">
                    bought / mo
                  </div>
                </div>
                <span
                  className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                    beatsVisibility
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "bg-white/10 text-white/50"
                  }`}
                  title="Position on the shelf vs its sales rank"
                >
                  {beatsVisibility && <TrendingUp className="h-3 w-3" />}#
                  {t.visibilityRank} on shelf
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
