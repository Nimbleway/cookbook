"use client";

import { useMemo, useState } from "react";
import { ArrowLeft, Radio, ChevronDown, BarChart3, ArrowUpRight, Layers } from "lucide-react";
import type { InsightPayload, RetailerResult } from "@/lib/types";
import type { SearchState } from "@/lib/use-search";
import { buildInsights } from "@/lib/insight-engine";
import { ALL_RETAILERS, RETAILER_META } from "@/lib/retailers";
import { HeroInsight } from "./hero-insight";
import { RetailerTabs, type RetailerSelection } from "./retailer-tabs";
import { ShareOfShelf } from "./share-of-shelf";
import { RunMyBrand } from "./run-my-brand";
import { ThreeThings } from "./executive-verdict";
import { CrossRetailerDiff } from "./cross-retailer-diff";
import { PaidOrganic } from "./paid-organic";
import { MonitoringTeaser } from "./monitoring-teaser";
import { classifyIntent } from "@/lib/intent";
import { LocalizationTeaser } from "./localization-teaser";
import { WhatWeSeeNow } from "./what-we-see-now";
import { BrandDrawer } from "./brand-drawer";
import { AskTheData } from "./ask-the-data";
import { SellingNow } from "./selling-now";
import { ScanProgress } from "./scan-progress";
import { Reveal } from "./reveal";
import { ResultsNav } from "./results-nav";
import { useLeadModal } from "./lead-modal";

// Section nav as the 5 executive questions of a guided category review — NOT a
// feature-tab list. Each anchors a zone of the page; the intermediate sections
// (takeaways, ask, report, numbers) live under the preceding question as
// scrollable content/actions, not tabs.
const NAV_SECTIONS = [
  { id: "retailer-differences", label: "Across retailers" },
  { id: "paid-organic", label: "Earned vs bought" },
  { id: "run-my-brand", label: "My brand" },
  { id: "localization", label: "By market" },
  { id: "monitoring", label: "Over time" },
];

export function ResultsExperience({
  state,
  onReset,
  onRefresh,
}: {
  state: SearchState;
  onReset: () => void;
  onRefresh: () => void;
}) {
  // Drilldown state resets automatically: the parent remounts this component
  // with key={keyword} on each new search.
  const [selectedRetailer, setSelectedRetailer] =
    useState<RetailerSelection>("all");
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  // The "find your brand" highlight — visual only, decoupled from the drawer.
  const [highlightBrand, setHighlightBrand] = useState<string | null>(null);
  // The brand the prospect actually ran (matched or not) — personalizes the
  // take-home report, including the absence diagnostic when it's not on shelf.
  const [ranBrand, setRanBrand] = useState<string | null>(null);
  const { open: openLeadModal } = useLeadModal();
  // The numbers are proof-on-demand (collapsed so the story leads). Ask Nimble
  // stays visible — it's now a structured decision tool, the live proof of
  // Nimble + Claude, so we don't bury it.
  const [showData, setShowData] = useState(false);

  // Running a brand that matches the shelf opens the evidence so the
  // Share-of-Shelf highlight is actually visible.
  const handleBrandMatch = (brand: string | null) => {
    setHighlightBrand(brand);
    if (brand) setShowData(true);
  };

  // Click a retailer → recompute the entire view for that shelf.
  const displayInsights: InsightPayload | null = useMemo(() => {
    if (!state.insights) return null;
    if (selectedRetailer === "all") return state.insights;
    const filtered = state.retailerResults.filter(
      (r) => r.retailer === selectedRetailer,
    );
    return filtered.length ? buildInsights(state.keyword, filtered) : state.insights;
  }, [state.insights, state.retailerResults, selectedRetailer, state.keyword]);


  return (
    <section className="mx-auto max-w-5xl px-4 pb-28 pt-5 sm:pt-8 lg:pb-16">
      {/* Top bar */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button
          onClick={onReset}
          className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-muted-foreground transition hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          New search
        </button>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          {/* During the pull, this carries the status; once the answer lands,
              the loud freshness badge in the hero takes over (no redundancy). */}
          {!displayInsights && (
            <DataStateBadge state={state} />
          )}
        </div>
      </div>

      <h2 className="mb-1 text-xl font-bold tracking-tight sm:text-2xl">
        {state.focusBrand ? (
          <>
            <span className="capitalize">{state.focusBrand}</span>
            <span className="font-semibold text-muted-foreground">
              {" "}· across the <span className="capitalize">{state.keyword}</span> shelf
            </span>
          </>
        ) : classifyIntent(state.keyword).kind === "category" ? (
          <>
            <span className="text-muted-foreground">Category:</span>{" "}
            <span className="capitalize">{state.keyword}</span>
          </>
        ) : (
          <>
            <span className="text-muted-foreground">Live results for</span>{" "}
            <span className="capitalize">&ldquo;{state.keyword}&rdquo;</span>
          </>
        )}
      </h2>
      <p className="mb-4 text-sm text-muted-foreground">
        {state.mode === "live" ? (
          <>
            Results generated from live{" "}
            {(state.preview ? ALL_RETAILERS : (displayInsights?.retailers ?? ALL_RETAILERS))
              .map((r) => RETAILER_META[r].label)
              .join(", ")
              .replace(/, ([^,]*)$/, " & $1")}{" "}
            search results — powered by <span className="font-semibold text-foreground">Nimble</span>.
            {displayInsights && displayInsights.failedRetailers.length > 0 && (
              <span className="text-muted-foreground/80">
                {" "}({displayInsights.failedRetailers
                  .map((r) => RETAILER_META[r].label)
                  .join(", ")}{" "}
                didn&apos;t respond this pull.)
              </span>
            )}
          </>
        ) : (
          <>
            Indexed sample across Amazon, Walmart &amp; Target — connect Nimble to
            pull this shelf live.
          </>
        )}
      </p>

      {/* Fraction-of-the-data frame — sets the expectation up front (this is a
          sample). The actual CTA lives once, in the closing banner below. */}
      {displayInsights && (
        <div className="mb-5 flex items-start gap-2 text-sm leading-snug text-muted-foreground">
          <Layers className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
          <p>
            <span className="font-semibold text-foreground">
              You&apos;re seeing a small sample of what Nimble tracks
            </span>{" "}
            — a fraction of the live retail data available for any brand, on any retailer.
          </p>
        </div>
      )}

      {/* Section nav — sticky tab bar that tucks under the header on scroll.
          Only once there's a report to navigate. */}
      {displayInsights && (
        <ResultsNav sections={NAV_SECTIONS} category={state.keyword} brand={state.focusBrand} />
      )}

      {/* Live scan — shown until the REAL shelf lands. The prospect watches
          Amazon/Walmart/Target arrive one by one; no mock answer is shown. */}
      {!displayInsights &&
        (state.status === "loading" || state.status === "partial") && (
          <div className="mb-5">
            <ScanProgress mode={state.mode} retailerResults={state.retailerResults} />
          </div>
        )}

      {/* ── ① THE ANSWER (compact hero) ── */}
      {displayInsights && (
        <HeroInsight
          insights={displayInsights}
          live={state.mode === "live"}
          focusBrand={state.focusBrand}
        />
      )}

      {/* ── ② WHAT'S DIFFERENT ACROSS RETAILERS — the differentiator LEADS ──
          Moved directly under the answer so the strongest Nimble story (and the
          biggest "they don't tell the same story" aha) lands near the fold. */}
      {displayInsights && displayInsights.crossRetailer.length > 0 && (
        <div id="retailer-differences" className="mt-8 scroll-mt-32">
          <LeadIn>Most teams assume the shelf looks the same everywhere. It doesn&apos;t.</LeadIn>
          <CrossRetailerDiff
            differences={displayInsights.crossRetailer}
            matrix={displayInsights.crossRetailerMatrix}
          />
        </div>
      )}

      {/* ── ②b EARNED vs BOUGHT — paired with cross-retailer; the second
          differentiated surprise: who wins on merit vs who buys the shelf. ── */}
      {displayInsights && displayInsights.paidOrganic.dependence.length > 0 && (
        <Reveal>
          <div id="paid-organic" className="mt-12 scroll-mt-32">
            <LeadIn>But are they winning it — or buying it?</LeadIn>
            <PaidOrganic
              key={`po-${displayInsights.keyword}-${displayInsights.collectedAt}`}
              insights={displayInsights}
            />
          </div>
        </Reveal>
      )}

      {/* ── ③ TOP TAKEAWAYS — the "so what" of the difference, with actions ── */}
      {displayInsights && (
        <Reveal>
          <div id="top-takeaways" className="mt-12 scroll-mt-32">
            <ThreeThings findings={displayInsights.findings} />
          </div>
        </Reveal>
      )}

      {/* ── ④ RUN MY BRAND (now make it personal) ── */}
      {displayInsights && (
        <Reveal delayMs={40}>
          <div id="run-my-brand" className="mt-12 scroll-mt-32">
            <LeadIn>So where does your brand actually stand?</LeadIn>
            <RunMyBrand
              insights={displayInsights}
              onMatch={handleBrandMatch}
              onRun={setRanBrand}
              onOpenBrand={setSelectedBrand}
              initialBrand={state.focusBrand}
            />
          </div>
        </Reveal>
      )}

      {/* ── ⑤ RETAIL INTELLIGENCE IS LOCAL — the same shelf shifts by market ── */}
      {displayInsights && (
        <Reveal delayMs={60}>
          <div id="localization" className="mt-12 scroll-mt-32">
            <LeadIn>And that&apos;s just national.</LeadIn>
            <LocalizationTeaser insights={displayInsights} />
          </div>
        </Reveal>
      )}

      {/* ── ⑥ ASK NIMBLE — the follow-up layer, after the core story ── */}
      {displayInsights && (
        <Reveal>
          <div id="ask-nimble" className="mt-12 scroll-mt-32">
            <LeadIn>Still curious? Ask a follow-up about this shelf.</LeadIn>
            <AskTheData insights={displayInsights} />
          </div>
        </Reveal>
      )}

      {/* ── ⑦ TRACK OVER TIME — capability teaser; bridge into the CTA ── */}
      {displayInsights && (
        <Reveal>
          <div id="monitoring" className="mt-12 scroll-mt-32">
            <LeadIn>This is one snapshot. The real value is watching it move.</LeadIn>
            <MonitoringTeaser
              key={`mon-${displayInsights.keyword}-${displayInsights.collectedAt}`}
              insights={displayInsights}
            />
          </div>
        </Reveal>
      )}


      {/* ── ⑧ SUPPORTING EVIDENCE — the numbers, collapsed; raw shelf inside ── */}
      {displayInsights && (
        <Reveal>
          <div id="the-numbers" className="mt-12 space-y-4 scroll-mt-32 sm:space-y-5">
            <button
              onClick={() => setShowData((s) => !s)}
              aria-expanded={showData}
              className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border bg-card px-4 py-3.5 text-left transition hover:border-brand/40"
            >
              <span className="flex items-center gap-2.5">
                <BarChart3 className="h-4 w-4 text-brand" />
                <span className="text-sm font-semibold">
                  {showData ? "Hide the numbers" : "Want the numbers behind this?"}
                </span>
                <span className="hidden text-xs text-muted-foreground sm:inline">
                  share of shelf · what we see right now · what&apos;s selling
                </span>
              </span>
              <ChevronDown
                className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
                  showData ? "rotate-180" : ""
                }`}
              />
            </button>

            {showData && (
              <div className="animate-fade-up space-y-4 sm:space-y-5">
                {state.retailerResults.length > 0 && (
                  <RetailerTabs
                    results={state.retailerResults}
                    selected={selectedRetailer}
                    onSelect={(r) => {
                      setSelectedRetailer(r);
                      setHighlightBrand(null);
                    }}
                  />
                )}

                {/* Keyed by retailer → recomputes/re-animates on a shelf switch */}
                <div key={selectedRetailer} className="space-y-4 sm:space-y-5">
                  <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
                    <ShareOfShelf
                      keyword={state.keyword}
                      brands={displayInsights.brandShare}
                      onSelect={setSelectedBrand}
                      selectedBrand={selectedBrand}
                      highlightBrand={highlightBrand}
                    />
                    <WhatWeSeeNow
                      insights={displayInsights}
                      mode={state.mode}
                      refreshing={state.refreshing}
                      preview={state.preview}
                      onRefresh={onRefresh}
                    />
                  </div>

                  {displayInsights.topSelling.length > 0 && (
                    <SellingNow topSelling={displayInsights.topSelling} />
                  )}
                  {/* Raw product table intentionally hidden — this is an
                      executive review, not a data dump. */}
                </div>
              </div>
            )}
          </div>
        </Reveal>
      )}

      {/* Closing pitch — frame the report as a glimpse, drive the meeting. */}
      {displayInsights && (
        <Reveal>
          <div className="mt-12 overflow-hidden rounded-3xl border border-brand/25 bg-gradient-to-br from-brand/15 to-card p-6 text-center sm:p-8">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand">
              This is just a glimpse
            </p>
            <h3 className="mx-auto mt-2 max-w-2xl text-balance text-xl font-bold tracking-tight sm:text-2xl">
              A quick output of the data and insights Nimble can build for your business.
            </h3>
            <p className="mx-auto mt-2 max-w-xl text-pretty text-sm text-muted-foreground">
              Get in touch — we&apos;ll show you the real, full value the Nimble
              platform can create for your brand.
            </p>
            <button
              onClick={() => openLeadModal({ keyword: state.keyword, brand: ranBrand })}
              className="mt-5 inline-flex items-center gap-1.5 rounded-xl bg-gold px-5 py-2.5 text-sm font-bold text-background transition active:scale-[0.98]"
            >
              Get in touch for more data
              <ArrowUpRight className="h-4 w-4" />
            </button>
          </div>
        </Reveal>
      )}

      {/* Brand drilldown drawer — always computed across ALL retailers */}
      {selectedBrand && (
        <BrandDrawer
          brand={selectedBrand}
          results={state.retailerResults.filter(
            (r): r is RetailerResult => r.status === "ok",
          )}
          onClose={() => setSelectedBrand(null)}
          onSelectBrand={setSelectedBrand}
        />
      )}
    </section>
  );
}

// Unambiguous data-state badge on first paint: Demo · Indexed sample (pulling
// live) · Live just-pulled · Live cached. A data company can't leave "is this
// real?" unanswered.
function DataStateBadge({ state }: { state: SearchState }) {
  if (state.mode === "demo") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-medium text-amber-300">
        <span className="h-2 w-2 rounded-full bg-amber-400" />
        Demo data · sample shelf
      </span>
    );
  }
  // While the live pull is in flight, the scan-progress card already says
  // "Reading the live shelves" with per-retailer arrival — no top-bar badge.
  if (state.preview) return null;
  const t = state.insights
    ? new Date(state.insights.collectedAt).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      })
    : "";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/15 px-2.5 py-1 text-xs font-medium text-rose-400">
      <Radio className="h-3 w-3 animate-pulse-dot" />
      Live · {state.cached ? "cached" : "just pulled"}
      {t ? ` · ${t}` : ""}
    </span>
  );
}

// One-line narrated transition between beats — turns the module stack into a
// guided story ("Now, where does your brand sit?" → "But the shelf isn't the
// same everywhere.").
function LeadIn({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-3 text-base font-medium text-muted-foreground sm:text-lg">
      {children}
    </p>
  );
}

