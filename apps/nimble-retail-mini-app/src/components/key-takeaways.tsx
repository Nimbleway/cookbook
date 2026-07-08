"use client";

import { Zap } from "lucide-react";
import type { InsightCard } from "@/lib/types";
import { toneStyles } from "@/lib/ui";

// Three punchy one-liners pulled from the top insight cards — so the report
// LEADS with its conclusions (insights first), right under the hero.
export function KeyTakeaways({ cards }: { cards: InsightCard[] }) {
  const top = cards.slice(0, 3);
  if (!top.length) return null;

  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <Zap className="h-3.5 w-3.5 text-brand" />
        The 3 things to know
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {top.map((c, i) => {
          const tone = toneStyles[c.tone];
          return (
            <div
              key={c.id}
              className="animate-fade-up relative overflow-hidden rounded-2xl border border-border bg-card p-4"
              style={{ animationDelay: `${i * 70}ms` }}
            >
              <span className={`absolute left-0 top-0 h-full w-1 ${tone.bar}`} />
              <span className="text-2xl font-bold tabular-nums text-foreground/15">
                0{i + 1}
              </span>
              <p className="mt-1 text-sm font-semibold leading-snug tracking-tight">
                {c.what}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
