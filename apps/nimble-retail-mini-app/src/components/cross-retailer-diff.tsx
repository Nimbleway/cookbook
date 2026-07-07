"use client";

import { Sparkles, ArrowRight } from "lucide-react";
import type { RetailerDifference, CrossRetailerMatrix } from "@/lib/types";
import { RETAILER_META, ALL_RETAILERS } from "@/lib/retailers";
import { SignalChip } from "./signal-chip";

// "What Changes Across Retailers?" — the centerpiece differentiator. The
// side-by-side matrix IS the proof and leads directly: every metric laid out
// across Amazon, Walmart & Target, with the diverging rows highlighted so the
// takeaway is instant — "I didn't realize they looked this different."
// Point-in-time only.

export function CrossRetailerDiff({
  matrix,
}: {
  differences: RetailerDifference[];
  matrix?: CrossRetailerMatrix;
}) {
  const showMatrix = matrix && matrix.retailers.length >= 2 && matrix.rows.length > 0;
  if (!showMatrix) return null;
  const missing = ALL_RETAILERS.filter((r) => !matrix!.retailers.includes(r));

  return (
    <section className="animate-fade-up overflow-hidden rounded-3xl border border-border bg-[oklch(0.16_0_0)] text-white">
      {/* Section header — given hero weight */}
      <div className="flex items-start gap-2 border-b border-white/10 bg-gradient-to-r from-brand/15 to-transparent px-5 py-4 sm:px-6">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-brand" />
            <h3 className="text-lg font-bold tracking-tight sm:text-xl">
              What changes across retailers?
            </h3>
          </div>
          <p className="mt-1 text-sm text-white/55">
            Same category. Three different shelves. Right now.
          </p>
        </div>
        <SignalChip category="difference" className="hidden shrink-0 sm:inline-flex" />
      </div>

      <div className="px-5 py-5 sm:px-6">
        {/* The side-by-side proof — shown directly. Diverging rows are flagged
            (gold dot + note) so the surprises read at a glance. */}
        <Matrix matrix={matrix!} />
        {missing.length > 0 && (
          <p className="mt-2 text-xs text-white/45">
            {missing.map((r) => RETAILER_META[r].label).join(" & ")} didn&apos;t respond this
            pull — showing{" "}
            {matrix!.retailers.map((r) => RETAILER_META[r].label).join(" & ")}.
          </p>
        )}

        <p className="mt-4 inline-flex items-center gap-1.5 text-xs font-medium text-brand">
          <ArrowRight className="h-3.5 w-3.5" />
          One pull, every retailer — only Nimble reads them side by side, live.
        </p>
      </div>
    </section>
  );
}

function Matrix({ matrix }: { matrix: CrossRetailerMatrix }) {
  const { retailers, rows } = matrix;
  // 1 label column + N retailer columns. Inline style because N is dynamic.
  const gridCols = `minmax(104px,1.2fr) repeat(${retailers.length}, minmax(0,1fr))`;

  return (
    <div className="overflow-hidden rounded-2xl ring-1 ring-white/10">
      {/* Header — retailer names in their brand colors */}
      <div
        className="grid items-center gap-x-2 border-b border-white/10 bg-white/[0.03] px-3 py-2.5 sm:px-4"
        style={{ gridTemplateColumns: gridCols }}
      >
        <span className="text-[10px] font-semibold uppercase tracking-wider text-white/35">
          Metric
        </span>
        {retailers.map((rt) => (
          <span
            key={rt}
            className="text-center text-xs font-bold tracking-tight sm:text-sm"
            style={{ color: RETAILER_META[rt].color }}
          >
            {RETAILER_META[rt].label}
          </span>
        ))}
      </div>

      {/* Rows */}
      {rows.map((row, i) => (
        <div
          key={row.id}
          className={`grid items-center gap-x-2 px-3 py-2.5 sm:px-4 ${
            i > 0 ? "border-t border-white/[0.06]" : ""
          } ${row.diverges ? "bg-brand/[0.07]" : ""}`}
          style={{ gridTemplateColumns: gridCols }}
        >
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-medium uppercase leading-tight tracking-wide text-white/55 sm:text-xs">
                {row.label}
              </span>
              {row.diverges && (
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand"
                  aria-label="differs across retailers"
                />
              )}
            </div>
            {row.diverges && row.note && (
              <span className="mt-0.5 inline-block text-[11px] font-semibold leading-tight text-brand">
                ◄ {row.note}
              </span>
            )}
          </div>
          {retailers.map((rt) => (
            <span
              key={rt}
              className={`truncate text-center text-xs tabular-nums sm:text-sm ${
                row.diverges ? "font-bold text-white" : "font-medium text-white/85"
              }`}
              title={row.values[rt] ?? "—"}
            >
              {row.values[rt] ?? "—"}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}
