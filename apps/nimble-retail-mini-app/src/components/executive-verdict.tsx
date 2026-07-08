"use client";

import type { Finding } from "@/lib/types";
import { toneStyles } from "@/lib/ui";
import { SignalChip, findingSignalCategory } from "./signal-chip";

// "3 things we found" — the most surprising things on this shelf, in plain
// voice. No what/why-it-matters/recommended-action scaffold; each card leads
// with its executive signal category + the finding. Exactly 3 (engine-ranked).

export function ThreeThings({ findings }: { findings: Finding[] }) {
  if (!findings.length) return null;

  return (
    <section className="animate-fade-up">
      <div className="mb-3 flex items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          3 things we found
        </span>
        <span className="h-px flex-1 bg-border" />
        <span className="hidden text-[11px] font-medium text-muted-foreground sm:inline">
          live · Amazon · Walmart · Target
        </span>
      </div>

      {/* Mobile: horizontal snap-scroll so the 3 cards don't push the
          cross-retailer centerpiece far down the page. Desktop: 3-up grid. */}
      <div className="-mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-1 sm:gap-4 md:mx-0 md:grid md:grid-cols-3 md:overflow-visible md:px-0 md:pb-0 [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden [scrollbar-width:none]">
        {findings.map((f, i) => (
          <div key={f.id} className="w-[80%] shrink-0 snap-start md:w-auto md:shrink">
            <FindingCard f={f} n={i + 1} />
          </div>
        ))}
      </div>
    </section>
  );
}

function FindingCard({ f, n }: { f: Finding; n: number }) {
  const tone = toneStyles[f.tone];
  return (
    <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card">
      <div className={`h-1 w-full ${tone.bar}`} />
      <div className="flex flex-1 flex-col p-4 sm:p-5">
        <div className="mb-2.5 flex items-center justify-between gap-2">
          <SignalChip category={findingSignalCategory(f.kind)} />
          <span className="text-sm font-bold tabular-nums text-muted-foreground/70">
            {n}
          </span>
        </div>

        {/* The surprising finding */}
        <p className="text-base font-bold leading-snug tracking-tight text-foreground">
          {f.headline}
        </p>
        {/* Why it's interesting — plain voice, no label */}
        <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
          {f.why}
        </p>
      </div>
    </article>
  );
}
