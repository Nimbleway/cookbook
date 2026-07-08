"use client";

import { MapPin, Lock, ArrowUpRight } from "lucide-react";
import type { InsightPayload } from "@/lib/types";
import { perItemPrice, median } from "@/lib/insight-engine";
import { BrandLogo } from "./product-tile";
import { SignalChip } from "./signal-chip";
import { useLeadModal } from "./lead-modal";

// "Retail Intelligence Is Local" — a CAPABILITY TEASER laid out as a market
// comparison table (rhymes with the cross-retailer matrix). The National column
// is REAL (this pull); the city columns are explicitly LOCKED, never fabricated.
// The point: the same analysis runs for any market — worth a conversation.
const CITIES = ["New York", "Los Angeles", "Chicago"];
const CITY_ABBR: Record<string, string> = {
  "New York": "NYC",
  "Los Angeles": "LA",
  "Chicago": "CHI",
};

export function LocalizationTeaser({ insights }: { insights: InsightPayload }) {
  const { open } = useLeadModal();
  const top = insights.brandShare[0];
  if (!top) return null;

  // National facts — all from THIS pull, aggregated across retailers.
  const rows = insights.results;
  const perUnit = rows.map(perItemPrice).filter((p): p is number => p !== null);
  const med = median(perUnit); // median per-unit — outlier-proof
  const avgPrice = med !== null ? `$${med.toFixed(2)}` : "—";
  const sponsoredPct = rows.length
    ? `${Math.round((rows.filter((r) => r.sponsored).length / rows.length) * 100)}%`
    : "—";

  const gridCols = `minmax(92px,1.1fr) 1.3fr repeat(${CITIES.length}, minmax(0,1fr))`;

  return (
    <section className="animate-fade-up overflow-hidden rounded-3xl border border-border bg-card">
      <div className="flex items-start gap-2 border-b border-border bg-gradient-to-r from-brand/10 to-transparent px-5 py-4 sm:px-6">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-brand" />
            <h3 className="text-lg font-bold tracking-tight sm:text-xl">
              Retail intelligence is local
            </h3>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            The same shelf looks different city to city. This is national — any market is a
            conversation away.
          </p>
        </div>
        <SignalChip category="difference" className="hidden shrink-0 sm:inline-flex" />
      </div>

      <div className="p-5 sm:p-6">
        <div className="overflow-hidden rounded-2xl border border-border">
          {/* Header — National (live) + locked cities */}
          <div
            className="grid items-center gap-x-2 border-b border-border bg-secondary/40 px-3 py-2.5 sm:px-4"
            style={{ gridTemplateColumns: gridCols }}
          >
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Metric
            </span>
            <span className="inline-flex items-center gap-1.5 text-xs font-bold tracking-tight text-brand sm:text-sm">
              National
              <span className="rounded-full bg-brand/15 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-brand">
                live
              </span>
            </span>
            {CITIES.map((c) => (
              <span
                key={c}
                className="text-center text-xs font-semibold tracking-tight text-muted-foreground/70 sm:text-sm"
                title={c}
              >
                <span className="sm:hidden">{CITY_ABBR[c] ?? c}</span>
                <span className="hidden sm:inline">{c}</span>
              </span>
            ))}
          </div>

          <Row label="Top brand" gridCols={gridCols}>
            <span className="flex min-w-0 items-center gap-1.5">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-black/10">
                <BrandLogo brand={top.brand} className="h-3.5 w-3.5 object-contain" />
              </span>
              <span className="truncate text-sm font-semibold">{top.brand}</span>
              <span className="shrink-0 text-xs font-semibold tabular-nums text-muted-foreground">
                {Math.round(top.share * 100)}%
              </span>
            </span>
          </Row>
          <Row label="Typical price" gridCols={gridCols}>
            <span className="text-sm font-semibold tabular-nums">{avgPrice}</span>
          </Row>
          <Row label="Sponsored" gridCols={gridCols}>
            <span className="text-sm font-semibold tabular-nums">{sponsoredPct}</span>
          </Row>
        </div>
      </div>

      <div className="border-t border-border px-5 py-4 sm:px-6">
        <button
          onClick={() => open({ keyword: insights.keyword })}
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:underline"
        >
          Unlock any market — see your brand by city, store by store
          <ArrowUpRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </section>
  );
}

// A metric row: label · real National value · locked city cells.
function Row({
  label,
  gridCols,
  children,
}: {
  label: string;
  gridCols: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="grid items-center gap-x-2 border-b border-border px-3 py-2.5 last:border-b-0 sm:px-4"
      style={{ gridTemplateColumns: gridCols }}
    >
      <span className="truncate text-[11px] font-medium uppercase tracking-wide text-muted-foreground sm:text-xs">
        {label}
      </span>
      <div className="min-w-0">{children}</div>
      {CITIES.map((c) => (
        <span key={c} className="flex justify-center" aria-label={`${c} locked`}>
          <Lock className="h-3.5 w-3.5 text-muted-foreground/45" />
        </span>
      ))}
    </div>
  );
}
