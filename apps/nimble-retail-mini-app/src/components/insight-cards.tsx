"use client";

import { Lightbulb, ArrowRight } from "lucide-react";
import type { InsightCard } from "@/lib/types";
import { toneStyles } from "@/lib/ui";
import { RETAILER_META, retailerColor } from "@/lib/retailers";

// Scannable insight cards: a bold takeaway (the "what"), one supporting line
// (the "why"), and the action. Insights before analytics — these lead, charts
// and tables come after.
export function InsightCards({ cards }: { cards: InsightCard[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {cards.map((c, idx) => {
        const tone = toneStyles[c.tone];
        const retailerLabel =
          c.retailer && c.retailer !== "cross"
            ? RETAILER_META[c.retailer].label
            : c.retailer === "cross"
              ? "Cross-retailer"
              : null;
        return (
          <article
            key={c.id}
            className="card-hover animate-fade-up flex flex-col overflow-hidden rounded-2xl border border-border bg-card"
            style={{ animationDelay: `${idx * 60}ms` }}
          >
            <div className={`h-1 w-full ${tone.bar}`} />
            <div className="flex flex-1 flex-col p-5">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {c.title}
                </span>
                {retailerLabel && (
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone.chip}`}
                    style={
                      c.retailer && c.retailer !== "cross"
                        ? { color: retailerColor(c.retailer) }
                        : undefined
                    }
                  >
                    {retailerLabel}
                  </span>
                )}
              </div>

              {/* Bold takeaway */}
              <p className="text-[15px] font-semibold leading-snug tracking-tight text-foreground">
                {c.what}
              </p>
              {/* One supporting line */}
              <p className="mt-1.5 text-sm leading-snug text-muted-foreground">
                {c.why}
              </p>

              {/* Action */}
              <div className={`mt-3 flex items-start gap-2 rounded-xl border p-2.5 ${tone.chip}`}>
                <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <p className="text-sm font-medium leading-snug">{c.action}</p>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}

export { ArrowRight };
