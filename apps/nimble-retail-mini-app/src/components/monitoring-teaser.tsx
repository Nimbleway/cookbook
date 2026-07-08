"use client";

import { useEffect, useState } from "react";
import { Lock, CalendarClock, ArrowRight, Activity } from "lucide-react";
import type { InsightPayload } from "@/lib/types";
import { SignalChip } from "./signal-chip";
import { useLeadModal } from "./lead-modal";

// ─── Track this over time (capability teaser) ────────────────────────────────
// We have NO history and never fake it. This panel communicates that Nimble
// MONITORS the shelf over time: the charts are visibly locked/illustrative
// (blurred, no numbers), while the "today's first data point" line shows REAL
// current values. Claude adds a forward-looking "what we'd watch" line; a
// deterministic fallback always renders so the booth never depends on the call.
export function MonitoringTeaser({ insights }: { insights: InsightPayload }) {
  const { open } = useLeadModal();
  const leader = insights.brandShare[0];
  const shareOfShelf = leader ? Math.round(leader.share * 100) : 0;
  const shareOfVoice = insights.paidOrganic.sponsoredPct;
  const retailerCount = insights.retailers.length;

  // Deterministic "what we'd watch" — Claude may enrich it.
  const fallbackWatch =
    shareOfVoice >= 40
      ? `We'd watch share of voice weekly — with ${shareOfVoice}% of this shelf paid, leadership flips on ad spend before anything else.`
      : leader
        ? `We'd track ${leader.brand}'s share of shelf and any new sponsored pressure — the first things to move on this shelf.`
        : `We'd track share of shelf and sponsored pressure here week over week.`;
  const [watch, setWatch] = useState(fallbackWatch);

  // Keyed on the shelf by the parent → state resets without a sync setState.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/monitoring", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ payload: insights }),
        });
        if (!res.ok) return;
        const data = (await res.json()) as { watch?: string };
        if (!cancelled && data.watch?.trim()) setWatch(data.watch.trim());
      } catch {
        /* enrichment only */
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [insights.keyword, insights.collectedAt]);

  return (
    <section className="overflow-hidden rounded-3xl border border-border bg-card">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border bg-gradient-to-r from-brand/10 to-transparent px-5 py-4 sm:px-6">
        <Activity className="h-4 w-4 text-brand" />
        <div className="flex-1">
          <h3 className="text-lg font-bold tracking-tight sm:text-xl">Track this over time</h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            This is today. The shelf moves daily — Nimble watches it so your reports don&apos;t go stale.
          </p>
        </div>
        <SignalChip category="monitoring" className="hidden shrink-0 sm:inline-flex" />
      </div>

      <div className="space-y-5 px-5 py-5 sm:px-6">
        {/* Locked, illustrative charts — visibly NOT real data */}
        <div className="relative overflow-hidden rounded-2xl border border-border bg-[oklch(0.16_0_0)] p-5 sm:p-6">
          <div className="grid gap-5 sm:grid-cols-2">
            <LockedChart label="Share of shelf" points={SHELF_POINTS} />
            <LockedChart label="Share of voice (paid)" points={VOICE_POINTS} />
          </div>
          {/* Lock overlay */}
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 bg-[oklch(0.16_0_0)]/30 backdrop-blur-[1px]">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-black/50 px-3 py-1.5 text-xs font-semibold text-white">
              <Lock className="h-3.5 w-3.5 text-brand" />
              Live tracking starts when you do
            </span>
            <span className="text-[10px] font-medium uppercase tracking-wide text-white/40">
              Illustrative — Nimble plots your first point from today
            </span>
          </div>
        </div>

        {/* Today's REAL starting point */}
        <div className="rounded-2xl border border-brand/20 bg-brand/[0.05] px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-brand">
            Today&apos;s first data point
          </p>
          <p className="mt-1 text-sm">
            {leader ? (
              <>
                <span className="font-bold">{leader.brand}</span> holds{" "}
                <span className="font-bold tabular-nums">{shareOfShelf}%</span> share of shelf ·{" "}
                <span className="font-bold tabular-nums">{shareOfVoice}%</span> share of voice is
                paid
                {retailerCount > 1 ? <> · across {retailerCount} retailers</> : null}.
              </>
            ) : (
              <>Captured live — the baseline Nimble would track forward from here.</>
            )}
          </p>
        </div>

        {/* What Nimble tracks */}
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/70">
            What Nimble tracks, day over day
          </p>
          <div className="flex flex-wrap gap-2">
            {["Share of shelf", "Share of voice", "Price", "Availability", "Search rank"].map(
              (m) => (
                <span
                  key={m}
                  className="rounded-full border border-border bg-secondary px-3 py-1 text-xs font-medium text-foreground"
                >
                  {m}
                </span>
              ),
            )}
          </div>
        </div>

        {/* Claude "what we'd watch" + CTA */}
        <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">{watch}</p>
          <button
            onClick={() => open({ keyword: insights.keyword })}
            className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-xl bg-gold px-4 py-2.5 text-sm font-semibold text-background transition active:scale-[0.98] sm:self-auto"
          >
            <CalendarClock className="h-4 w-4" />
            Start tracking this shelf
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </section>
  );
}

// Fixed, decorative trend shapes (NOT data) in a 0..300 x / 0..100 y space —
// the data line is blurred over a crisp grid so it reads as a real chart that's
// simply locked.
const SHELF_POINTS = "0,75 38,68 76,71 114,55 152,59 190,43 228,47 266,31 300,27";
const VOICE_POINTS = "0,54 38,61 76,45 114,53 152,34 190,43 228,26 266,34 300,21";

function LockedChart({ label, points }: { label: string; points: string }) {
  const area = `0,100 ${points} 300,100`;
  return (
    <div className="select-none">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-white/40">
        {label}
      </p>
      <svg
        viewBox="0 0 300 100"
        className="h-28 w-full sm:h-36"
        preserveAspectRatio="none"
        aria-hidden
      >
        {/* Crisp grid */}
        <g stroke="oklch(1 0 0 / 0.08)" strokeWidth="1">
          {[20, 40, 60, 80].map((y) => (
            <line key={`h${y}`} x1="0" y1={y} x2="300" y2={y} />
          ))}
          {[50, 100, 150, 200, 250].map((x) => (
            <line key={`v${x}`} x1={x} y1="0" x2={x} y2="100" />
          ))}
        </g>
        {/* Blurred data line + area — illustrative only */}
        <g style={{ filter: "blur(2.5px)" }}>
          <polygon points={area} fill="oklch(0.72 0.17 95 / 0.12)" />
          <polyline
            points={points}
            fill="none"
            stroke="oklch(0.72 0.17 95)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.85"
          />
        </g>
      </svg>
    </div>
  );
}
