"use client";

import { Loader2 } from "lucide-react";
import type { RetailerId } from "@/lib/types";
import { RETAILER_META, ALL_RETAILERS } from "@/lib/retailers";

// Progressive loading: shows which retailers have landed vs are still streaming.
export function RetailerProgress({
  pending,
  arrived,
}: {
  pending: RetailerId[];
  arrived: RetailerId[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {ALL_RETAILERS.map((r) => {
        const isArrived = arrived.includes(r);
        const isPending = pending.includes(r);
        return (
          <span
            key={r}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition ${
              isArrived
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : "border-border bg-card text-muted-foreground"
            }`}
          >
            {isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: RETAILER_META[r].color }}
              />
            )}
            {RETAILER_META[r].label}
            {isArrived ? " ✓" : isPending ? "…" : ""}
          </span>
        );
      })}
    </div>
  );
}

export function HeroSkeleton() {
  return (
    <div className="rounded-3xl border border-border bg-card p-8">
      <div className="skeleton h-4 w-48 rounded" />
      <div className="skeleton mt-4 h-14 w-72 rounded-lg" />
      <div className="skeleton mt-4 h-4 w-full max-w-md rounded" />
      <div className="skeleton mt-6 h-16 w-full rounded-2xl" />
    </div>
  );
}

export function KpiSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="rounded-2xl border border-border bg-card p-4">
          <div className="skeleton h-3 w-20 rounded" />
          <div className="skeleton mt-3 h-7 w-16 rounded" />
        </div>
      ))}
    </div>
  );
}
