"use client";

import type { Kpi } from "@/lib/types";
import { toneStyles } from "@/lib/ui";
import { useCountUp } from "@/lib/use-count-up";

export function KpiRow({ kpis }: { kpis: Kpi[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {kpis.map((k, idx) => {
        const tone = toneStyles[k.tone ?? "neutral"];
        return (
          <div
            key={k.id}
            className="animate-fade-up rounded-2xl border border-border bg-card p-4"
            style={{ animationDelay: `${idx * 60}ms` }}
          >
            <div className="flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {k.label}
              </p>
            </div>
            <p className="mt-2 truncate text-xl font-bold tracking-tight tabular-nums sm:text-2xl">
              <KpiValue value={k.value} />
            </p>
            {k.sub && (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {k.sub}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Counts up the leading number of a KPI value (e.g. "44%" → 0→44 + "%"),
// rendering non-numeric values (brand names) unchanged.
function KpiValue({ value }: { value: string }) {
  const match = value.match(/^(\d+(?:\.\d+)?)(.*)$/);
  const target = match ? parseFloat(match[1]) : 0;
  const decimals = match && match[1].includes(".") ? 1 : 0;
  const n = useCountUp(target, { durationMs: 850, decimals, enabled: Boolean(match) });
  if (!match) return <>{value}</>;
  return (
    <>
      {decimals ? n.toFixed(decimals) : n}
      {match[2]}
    </>
  );
}
