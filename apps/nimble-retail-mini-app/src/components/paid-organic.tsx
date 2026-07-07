"use client";

import { useEffect, useState } from "react";
import { Scale, Sprout, Megaphone, ArrowRight } from "lucide-react";
import type { InsightPayload } from "@/lib/types";
import { RETAILER_META } from "@/lib/retailers";
import { BrandLogo } from "./product-tile";
import { SignalChip } from "./signal-chip";

// ─── Earned vs Bought ────────────────────────────────────────────────────────
// Are brands winning because they EARNED visibility or BOUGHT it? Every number
// is deterministic (from the sponsored flag — our most reliable signal). The
// verdict line shows the engine's deterministic copy instantly, then swaps in
// Claude's interpretation when it returns. Claude is enrichment, never required.
export function PaidOrganic({ insights }: { insights: InsightPayload }) {
  const po = insights.paidOrganic;
  const [verdict, setVerdict] = useState(po.verdict);
  const [soWhat, setSoWhat] = useState(po.soWhat);

  // Try to enrich the deterministic verdict with Claude's read. The component
  // is keyed on the shelf by the parent, so state resets on a new search
  // without a synchronous setState here. setState lives in the async callback.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/paid-organic", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ payload: insights }),
        });
        if (!res.ok) return; // 503/502 → keep deterministic copy
        const data = (await res.json()) as { verdict?: string; soWhat?: string };
        if (cancelled) return;
        if (data.verdict?.trim()) setVerdict(data.verdict.trim());
        if (data.soWhat?.trim()) setSoWhat(data.soWhat.trim());
      } catch {
        /* enrichment only — deterministic copy already shown */
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [insights.keyword, insights.collectedAt]);

  if (po.dependence.length === 0) return null;

  const goAsk = () =>
    document.getElementById("ask-nimble")?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <section className="overflow-hidden rounded-3xl border border-border bg-card">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border bg-gradient-to-r from-brand/10 to-transparent px-5 py-4 sm:px-6">
        <Scale className="h-4 w-4 text-brand" />
        <div className="flex-1">
          <h3 className="text-lg font-bold tracking-tight sm:text-xl">Earned vs bought</h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Who&apos;s winning on merit — and who&apos;s buying the shelf
          </p>
        </div>
        <SignalChip category="risk" className="hidden shrink-0 sm:inline-flex" />
      </div>

      <div className="space-y-5 px-5 py-5 sm:px-6">
        {/* The verdict — deterministic, swapped for Claude's read when it lands */}
        <p className="text-pretty text-base font-bold leading-snug tracking-tight sm:text-lg">
          {verdict}
        </p>

        {/* Two-card contrast: earned vs bought leaders */}
        <div className="grid gap-3 sm:grid-cols-2">
          {po.organicLeader && (
            <ContrastCard
              tone="earned"
              icon={Sprout}
              kicker="Earned the most"
              brand={po.organicLeader.brand}
              detail={`${po.organicLeader.organicCount} organic slot${po.organicLeader.organicCount === 1 ? "" : "s"} — won, not bought`}
            />
          )}
          {po.paidLeader && (
            <ContrastCard
              tone="bought"
              icon={Megaphone}
              kicker="Bought the most"
              brand={po.paidLeader.brand}
              detail={`${po.paidLeader.sponsoredCount} sponsored placement${po.paidLeader.sponsoredCount === 1 ? "" : "s"}`}
            />
          )}
        </div>

        {/* Pay-to-play by retailer — the ONE number (retailer-level paid
            pressure is the statistically robust signal; per-brand dependence
            bars were dropped as small-n noise). */}
        {po.byRetailer.length >= 2 && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-2xl border border-border bg-secondary/40 px-4 py-3">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/70">
              Paid placement by shelf
            </span>
            {po.byRetailer.map((r) => (
              <span key={r.retailer} className="inline-flex items-center gap-1.5 text-sm">
                <span
                  className="font-semibold"
                  style={{ color: RETAILER_META[r.retailer].color }}
                >
                  {RETAILER_META[r.retailer].label}
                </span>
                <span className="font-bold tabular-nums">{r.sponsoredPct}%</span>
              </span>
            ))}
          </div>
        )}

        {/* So-what + CTA */}
        <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">{soWhat}</p>
          <button
            onClick={goAsk}
            className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-full border border-brand/30 bg-brand/[0.06] px-3.5 py-2 text-xs font-semibold text-brand transition hover:border-brand/50 sm:self-auto"
          >
            Ask about paid pressure
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </section>
  );
}

function ContrastCard({
  tone,
  icon: Icon,
  kicker,
  brand,
  detail,
}: {
  tone: "earned" | "bought";
  icon: typeof Sprout;
  kicker: string;
  brand: string;
  detail: string;
}) {
  const accent =
    tone === "earned"
      ? "border-emerald-500/30 bg-emerald-500/[0.06]"
      : "border-amber-500/30 bg-amber-500/[0.06]";
  const iconColor = tone === "earned" ? "text-emerald-400" : "text-amber-400";
  return (
    <div className={`rounded-2xl border p-4 ${accent}`}>
      <div className="flex items-center gap-1.5">
        <Icon className={`h-3.5 w-3.5 ${iconColor}`} />
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">
          {kicker}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-black/10">
          <BrandLogo brand={brand} className="h-4 w-4 object-contain" />
        </span>
        <span className="truncate text-lg font-bold tracking-tight">{brand}</span>
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">{detail}</p>
    </div>
  );
}

