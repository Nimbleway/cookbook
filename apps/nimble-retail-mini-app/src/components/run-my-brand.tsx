"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  Crown,
  ArrowRight,
  ArrowUpRight,
  Lightbulb,
  EyeOff,
  DoorOpen,
} from "lucide-react";
import type { InsightPayload } from "@/lib/types";
import { analyzeBrand } from "@/lib/brand-analysis";
import { BrandLogo } from "./product-tile";
import { SignalChip } from "./signal-chip";
import { useLeadModal } from "./lead-modal";

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

// "Run My Brand" — the personalization hook, promoted directly below the
// verdict. The output is CONSULTATIVE, not a metrics dump: Visibility Score,
// Category Leader, Gap to Leader, Biggest Opportunity, and a Recommended Action.
export function RunMyBrand({
  insights,
  onMatch,
  onRun,
  onOpenBrand,
  initialBrand,
}: {
  insights: InsightPayload;
  onMatch: (brand: string | null) => void;
  onRun?: (term: string) => void; // the brand the user ran, matched or not
  onOpenBrand: (brand: string) => void;
  initialBrand?: string | null; // brand-intent search → auto-run its scorecard
}) {
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState<string | null>(null);
  // Claude-sharpened signature, tagged with the brand it's for (so it's only
  // applied to the matching result and never needs a sync reset).
  const [refined, setRefined] = useState<{ brand: string; headline: string; detail: string } | null>(null);

  const { brandShare: brands, keyword } = insights;
  const leader = brands[0];
  const picks = useMemo(() => brands.slice(0, 4), [brands]);

  const result = useMemo(
    () => (searched ? analyzeBrand(insights, searched) : null),
    [searched, insights],
  );

  const run = (term: string) => {
    const t = term.trim();
    if (!t) return;
    setQuery(t);
    setSearched(t);
    onRun?.(t);
    const q = norm(t);
    const hit = brands.find(
      (b) => norm(b.brand) === q || norm(b.brand).includes(q) || q.includes(norm(b.brand)),
    );
    onMatch(hit ? hit.brand : null);
  };

  // Brand-intent search auto-runs the scorecard once (e.g. searched "Quest" →
  // ran the Protein Bars shelf → show Quest's position immediately).
  const ranInitial = useRef(false);
  useEffect(() => {
    if (ranInitial.current || !initialBrand) return;
    ranInitial.current = true;
    run(initialBrand);
  }, [initialBrand]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sharpen the deterministic signature with Claude. Tagged by brand; setState
  // lives in the async callback, never the effect body.
  const foundBrand = result?.found ? result.brand : null;
  useEffect(() => {
    if (!foundBrand) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/brand-signature", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ payload: insights, brand: foundBrand }),
        });
        if (!res.ok) return;
        const d = (await res.json()) as { headline?: string; detail?: string };
        if (!cancelled && d.headline?.trim()) {
          setRefined({ brand: foundBrand, headline: d.headline.trim(), detail: (d.detail || "").trim() });
        }
      } catch {
        /* deterministic signature already shown */
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [foundBrand, insights.collectedAt]);

  if (!brands.length) return null;

  // The signature to show: Claude's if it's for this exact brand, else the
  // deterministic one computed in analyzeBrand.
  const sig =
    result?.found && refined && refined.brand === result.brand
      ? { headline: refined.headline, detail: refined.detail }
      : result?.found
        ? result.signature
        : null;

  return (
    <section className="animate-fade-up rounded-3xl border border-brand/25 bg-gradient-to-br from-brand/10 to-card p-5 sm:p-6">
      <div className="flex items-start gap-2">
        <div className="flex flex-1 items-center gap-2">
          <Search className="h-4 w-4 text-brand" />
          <h3 className="text-base font-bold tracking-tight sm:text-lg">
            Is your brand winning this shelf?
          </h3>
        </div>
        <SignalChip category="competition" className="hidden shrink-0 sm:inline-flex" />
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Type your brand — see exactly where you stand on the live{" "}
        <span className="font-medium capitalize text-foreground">{keyword}</span>{" "}
        shelf, or who&apos;s taking the space if you&apos;re not on it yet.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(query);
        }}
        className="mt-4 flex items-center gap-2 rounded-2xl border border-border bg-background p-1.5"
      >
        <Search className="ml-2 h-4 w-4 shrink-0 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type your brand…"
          className="h-9 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground/70"
          aria-label="Run my brand"
        />
        <button
          type="submit"
          className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl bg-gold px-3.5 text-sm font-semibold text-background transition active:scale-[0.98]"
        >
          Run my brand
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground/80">
          Don&apos;t have one handy? Try:
        </span>
        {picks.map((p) => (
          <button
            key={p.brand}
            onClick={() => run(p.brand)}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card py-1 pl-1.5 pr-3 text-xs font-medium text-muted-foreground transition hover:border-brand/40 hover:text-foreground"
          >
            <span className="flex h-5 w-5 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-black/10">
              <BrandLogo brand={p.brand} className="h-3.5 w-3.5 object-contain" />
            </span>
            {p.brand}
          </button>
        ))}
      </div>

      {result?.found && (
        <div className="mt-4 animate-fade-up">
          {/* The brand's SIGNATURE leads — the one thing that makes its story
              different from every other brand's. Then the supporting scorecard. */}
          {sig && (
            <div className="mb-3 rounded-2xl border border-brand/30 bg-brand/[0.08] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-brand">
                {result.brand}&apos;s signature
              </p>
              <p className="mt-1 text-base font-bold leading-snug tracking-tight sm:text-lg">
                {sig.headline}
              </p>
              {sig.detail && (
                <p className="mt-1 text-sm leading-snug text-muted-foreground">{sig.detail}</p>
              )}
            </div>
          )}

          {/* Consultative scorecard — four reads, then the action */}
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <Stat label="Share of shelf">
              <span className="text-2xl font-bold tabular-nums sm:text-3xl">{result.score}%</span>
              <Sub>of page one · #{result.rank} of {result.total} brands</Sub>
            </Stat>
            <Stat label="Category leader">
              {result.isLeader ? (
                <span className="inline-flex items-center gap-1 text-lg font-bold">
                  You <Crown className="h-4 w-4 text-brand" />
                </span>
              ) : (
                <span className="truncate text-lg font-bold">{leader.brand}</span>
              )}
              <Sub>{result.leaderPct}% of page one</Sub>
            </Stat>
            <Stat label="Behind the leader">
              {result.isLeader ? (
                <span className="text-lg font-bold text-emerald-300">Leading</span>
              ) : (
                <span className="text-2xl font-bold tabular-nums sm:text-3xl">+{result.gap}<span className="text-sm font-semibold text-muted-foreground"> pts</span></span>
              )}
              <Sub>{result.isLeader ? "ahead of #2" : "behind #1"}</Sub>
            </Stat>
            <Stat label="The opening">
              <span className="text-sm font-semibold leading-snug text-brand">{result.opportunity}</span>
            </Stat>
          </div>

          {/* No generic "takeaway" line here — the signature above already
              carries the brand-specific insight + so-what. */}
          <button
            onClick={() => onOpenBrand(result.brand)}
            className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline"
          >
            See {result.brand}&apos;s full breakdown
            <ArrowRight className="h-3.5 w-3.5" />
          </button>

          {/* Even when you're winning, there's a reason to talk: every market. */}
          <BrandCta
            headline={<>See {result.brand} in every market, live.</>}
            sub={
              <>
                This is national. We&apos;ll track {result.brand} by retailer, city, or store —
                and alert you when it moves.
              </>
            }
          />
        </div>
      )}

      {result && !result.found && (
        <div className="mt-4 animate-fade-up">
          {/* The absence IS the finding — designed as a real scorecard, equal
              weight to the "found" case, not an error state. */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-semibold text-amber-300">
              <EyeOff className="h-3.5 w-3.5" />
              Not on page one
            </span>
          </div>
          <p className="mt-2.5 text-base font-bold leading-snug tracking-tight sm:text-lg">
            <span className="capitalize">{result.brand.trim()}</span> isn&apos;t visible on the{" "}
            <span className="capitalize">{keyword}</span>{" "}
            shelf — here&apos;s the space you&apos;d be fighting for.
          </p>

          {/* Quantified absence — what the empty slot costs you */}
          <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <Stat label="Brands competing">
              <span className="text-2xl font-bold tabular-nums sm:text-3xl">{result.competitors}</span>
              <Sub>holding page one right now</Sub>
            </Stat>
            <Stat label="Top-3 grip">
              <span className="text-2xl font-bold tabular-nums sm:text-3xl">
                {result.topThreeShare}
                <span className="text-sm font-semibold text-muted-foreground">%</span>
              </span>
              <Sub>locked by the leaders</Sub>
            </Stat>
            <Stat label="Paid slots">
              <span className="text-2xl font-bold tabular-nums sm:text-3xl">
                {result.sponsoredPct}
                <span className="text-sm font-semibold text-muted-foreground">%</span>
              </span>
              <Sub>are sponsored placements</Sub>
            </Stat>
            <Stat label="Entry price band">
              {result.priceBand ? (
                <>
                  <span className="text-lg font-bold tabular-nums sm:text-xl">
                    ${result.priceBand.low.toFixed(2)}–${result.priceBand.high.toFixed(2)}
                  </span>
                  <Sub>per unit on page one</Sub>
                </>
              ) : (
                <>
                  <span className="text-lg font-bold">—</span>
                  <Sub>no price data on this pull</Sub>
                </>
              )}
            </Stat>
          </div>

          {/* The opening — most fragmented shelf = cheapest door */}
          {result.winnableRetailer && (
            <div className="mt-3 flex items-start gap-2.5 rounded-2xl border border-emerald-500/25 bg-emerald-500/10 p-3.5">
              <DoorOpen className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-300">
                  Most open shelf
                </p>
                <p className="mt-0.5 text-sm leading-snug text-foreground">
                  <span className="font-semibold">{result.winnableRetailer.label}</span> — its leader{" "}
                  <span className="font-semibold">{result.winnableRetailer.leaderBrand}</span> holds
                  just {result.winnableRetailer.leaderPct}% of page one. The cheapest door to break in.
                </p>
              </div>
            </div>
          )}

          {/* Recommended action — same consultative payoff as the found case */}
          <div className="mt-3 flex items-start gap-2.5 rounded-2xl border border-brand/25 bg-brand/10 p-3.5">
            <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-brand">
                The takeaway
              </p>
              <p className="mt-0.5 text-sm leading-snug text-foreground">{result.action}</p>
            </div>
          </div>

          {/* The bandage — the absence is the highest-intent moment, so it ends
              in a conversation, not a tip. Personalized, deterministic, instant. */}
          <BrandCta
            headline={
              <>
                Want to get <span className="capitalize">{result.brand.trim()}</span> onto this
                shelf?
              </>
            }
            sub={
              result.winnableRetailer ? (
                <>
                  We&apos;ll map where you&apos;re missing across every retailer — and why{" "}
                  {result.winnableRetailer.label} is the place to start.
                </>
              ) : (
                <>We&apos;ll map where you&apos;re missing across every retailer and market.</>
              )
            }
          />
        </div>
      )}
    </section>
  );
}

// The conversion bandage shown inside a brand result — a single, confident,
// personalized ask that turns the "aha" into a reason to talk to Nimble. No AI
// call: it must be instant and reliable at the conversion peak.
function BrandCta({
  headline,
  sub,
}: {
  headline: React.ReactNode;
  sub: React.ReactNode;
}) {
  const { open } = useLeadModal();
  return (
    <button
      onClick={() => open()}
      className="mt-3 flex w-full items-center justify-between gap-3 rounded-2xl border border-brand/30 bg-brand/[0.06] p-3.5 text-left transition hover:border-brand/50 active:scale-[0.99]"
    >
      <div className="min-w-0">
        <p className="text-sm font-bold leading-snug tracking-tight text-foreground">
          {headline}
        </p>
        <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{sub}</p>
      </div>
      <span className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-gold px-3.5 py-2 text-sm font-semibold text-background">
        Get my brand&apos;s review
        <ArrowUpRight className="h-4 w-4" />
      </span>
    </button>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-1">{children}</div>
    </div>
  );
}

function Sub({ children }: { children: React.ReactNode }) {
  return <p className="mt-0.5 w-full text-[11px] text-muted-foreground">{children}</p>;
}
