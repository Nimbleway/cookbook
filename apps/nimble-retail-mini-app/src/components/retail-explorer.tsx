"use client";

import { useState } from "react";
import { ChevronDown, Star, Table2 } from "lucide-react";
import type { RetailerSerpResult } from "@/lib/types";
import { RETAILER_META } from "@/lib/retailers";
import { fmtPrice, fmtCount } from "@/lib/ui";
import { ProductTile } from "./product-tile";

// Secondary section — analytics AFTER insights. Collapsed by default so the
// experience never opens on a table.
export function RetailExplorer({ rows }: { rows: RetailerSerpResult[] }) {
  const [open, setOpen] = useState(false);
  const [onlySponsored, setOnlySponsored] = useState(false);

  const filtered = (onlySponsored ? rows.filter((r) => r.sponsored) : rows)
    .slice()
    .sort((a, b) => a.rank - b.rank);

  return (
    <div className="rounded-2xl border border-border bg-card">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 p-5"
      >
        <span className="flex items-center gap-2 font-semibold tracking-tight">
          <Table2 className="h-4 w-4 text-muted-foreground" />
          Explore the raw shelf
          <span className="text-sm font-normal text-muted-foreground">
            {rows.length} products
          </span>
        </span>
        <ChevronDown
          className={`h-5 w-5 text-muted-foreground transition ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* grid-rows 0fr→1fr gives a smooth height animation without measuring */}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div className="border-t border-border">
            <div className="flex items-center gap-2 px-5 py-3">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={onlySponsored}
                onChange={(e) => setOnlySponsored(e.target.checked)}
                className="h-4 w-4 rounded accent-[var(--brand)]"
              />
              Sponsored only
            </label>
          </div>
          <div className="max-h-[28rem] overflow-auto">
            <table className="w-full min-w-[34rem] text-sm">
              <thead className="sticky top-0 bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground backdrop-blur">
                <tr>
                  <th className="px-4 py-2 font-medium">#</th>
                  <th className="px-4 py-2 font-medium">Product</th>
                  <th className="px-4 py-2 font-medium">Retailer</th>
                  <th className="px-4 py-2 text-right font-medium">Price</th>
                  <th className="px-4 py-2 text-right font-medium">Rating</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filtered.map((r, i) => (
                  <tr key={`${r.retailer}-${r.rank}-${i}`} className="hover:bg-muted/30">
                    <td className="px-4 py-2 align-middle text-muted-foreground tabular-nums">
                      {r.rank}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2.5">
                        <ProductTile brand={r.brand} imageUrl={r.imageUrl} size="md" href={r.productUrl} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="truncate font-medium">{r.brandRaw ?? r.brand}</span>
                            {r.sponsored && (
                              <span className="shrink-0 rounded bg-brand/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-brand">
                                Ad
                              </span>
                            )}
                          </div>
                          <p className="line-clamp-1 max-w-xs text-xs text-muted-foreground">
                            {r.productTitle}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2 align-middle">
                      <span
                        className="inline-flex items-center gap-1.5 text-xs font-medium"
                        style={{ color: RETAILER_META[r.retailer].color }}
                      >
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ background: RETAILER_META[r.retailer].color }}
                        />
                        {RETAILER_META[r.retailer].label}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right align-middle tabular-nums">
                      {fmtPrice(r.price)}
                    </td>
                    <td className="px-4 py-2 text-right align-middle">
                      <span className="inline-flex items-center gap-1 tabular-nums">
                        <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                        {r.rating?.toFixed(1) ?? "—"}
                        <span className="text-xs text-muted-foreground">
                          ({fmtCount(r.reviewCount)})
                        </span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </div>
        </div>
      </div>
    </div>
  );
}
