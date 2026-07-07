"use client";

import {
  PackageX,
  Tag,
  Megaphone,
  Trophy,
  RefreshCw,
  Radio,
} from "lucide-react";
import type { InsightPayload, RightNowFact, SearchMode } from "@/lib/types";

// "What we see right now" — strictly point-in-time facts from the CURRENT pull
// (availability, promotions, paid penetration, leader gap). No movement, trends,
// deltas, or comparisons to a prior pull — there is no historical snapshot. The
// "Refresh Live Data" button performs a genuine Nimble re-fetch and then shows
// only a timestamp ("Last refreshed 2:17 PM").

const KIND_ICON: Record<RightNowFact["kind"], typeof PackageX> = {
  availability: PackageX,
  promo: Tag,
  sponsored: Megaphone,
  leader: Trophy,
};

const TONE_TEXT: Record<string, string> = {
  positive: "text-emerald-300",
  opportunity: "text-amber-300",
  warning: "text-orange-300",
  neutral: "text-white/70",
};

export function WhatWeSeeNow({
  insights,
  mode,
  refreshing,
  preview,
  onRefresh,
}: {
  insights: InsightPayload;
  mode: SearchMode;
  refreshing: boolean;
  preview: boolean;
  onRefresh: () => void;
}) {
  const facts = insights.rightNow.facts;
  const isLive = mode === "live";

  // Honest status line — a timestamp once live data is in, nothing implying history.
  const stamp = (() => {
    if (refreshing) return "Refreshing…";
    if (preview) return "Pulling live…";
    if (isLive) {
      const t = new Date(insights.collectedAt).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      });
      return `Last refreshed ${t}`;
    }
    return "Indexed sample";
  })();

  return (
    <section className="overflow-hidden rounded-3xl border border-border bg-[oklch(0.16_0_0)] text-white">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-white/10 px-4 py-3 sm:px-5">
        <Radio className="h-4 w-4 text-brand" />
        <h3 className="text-sm font-semibold tracking-tight sm:text-base">
          What we see right now
        </h3>
        <span className="ml-auto inline-flex items-center gap-1.5 font-mono text-xs text-white/55">
          {refreshing && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
          {stamp}
        </span>
      </div>

      <div className="space-y-3 p-4 sm:p-5">
        <p className="text-[13px] leading-relaxed text-white/60">
          Exactly what a shopper sees on these shelves right now.
        </p>

        {facts.length > 0 ? (
          <ul className="space-y-2.5">
            {facts.map((f) => {
              const Icon = KIND_ICON[f.kind];
              return (
                <li key={f.id} className="flex items-start gap-2.5 text-sm">
                  <Icon
                    className={`mt-0.5 h-4 w-4 shrink-0 ${TONE_TEXT[f.tone] ?? "text-white/70"}`}
                  />
                  <span className="leading-snug">
                    <span className="font-semibold text-white">{f.value}</span>
                    {f.detail && (
                      <span className="text-white/55"> — {f.detail}</span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-white/50">
            No standout availability or pricing signals on this shelf right now.
          </p>
        )}

        {/* Genuine re-fetch — live mode only. */}
        {isLive && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="bg-gold inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-background transition active:scale-[0.98] disabled:opacity-70"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        )}
      </div>
    </section>
  );
}
