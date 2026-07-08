"use client";

import { useState } from "react";
import { Search, ArrowRight } from "lucide-react";
import { DEMO_SUGGESTIONS } from "@/lib/mock-data";
import { RETAILER_META, ALL_RETAILERS } from "@/lib/retailers";
import { classifyIntent } from "@/lib/intent";
import { HeroPreview } from "./hero-preview";
import { LandingPains } from "./landing-pains";
import { BrandLogo, RetailerLogo } from "./product-tile";
import type { SearchMode } from "@/lib/types";

// Discovery examples — drive "run your own" across all three search types.
const BRAND_EXAMPLES = ["Celsius", "Quest", "Liquid Death", "Premier Protein", "Monster"];
const KEYWORD_EXAMPLES = [
  "sugar free energy drinks",
  "high protein snacks",
  "electrolyte powder",
  "cold brew coffee",
];
const TABS = [
  { id: "categories", label: "Categories" },
  { id: "brands", label: "Brands" },
  { id: "keywords", label: "Keywords" },
] as const;

export function HeroSearch({
  onSearch,
  liveAvailable,
}: {
  onSearch: (
    keyword: string,
    mode: SearchMode,
    opts?: { focusBrand?: string | null },
  ) => void;
  liveAvailable: boolean;
}) {
  const [value, setValue] = useState("");
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("categories");
  // When Nimble agents are configured we pull the REAL shelf (incl. product
  // photos); otherwise we fall back to the offline demo data.
  const mode: SearchMode = liveAvailable ? "live" : "demo";
  // Intent-routed: a brand runs ITS CATEGORY shelf (so there are competitors to
  // compare against) with the brand as the focus; a category runs itself; a
  // shopper keyword runs literally.
  const go = (raw: string) => {
    const k = raw.trim();
    if (!k) return;
    const intent = classifyIntent(k);
    if (intent.kind === "brand" && intent.category) {
      onSearch(intent.category, mode, { focusBrand: intent.brand });
    } else if (intent.kind === "category") {
      onSearch(intent.category, mode);
    } else {
      onSearch(k, mode);
    }
  };

  return (
    <section className="hero-glow relative overflow-hidden">
      <div className="mx-auto grid max-w-6xl items-start gap-10 px-5 pb-12 pt-12 sm:pt-16 lg:grid-cols-[1.05fr_0.95fr] lg:gap-12 lg:pb-16">
        {/* ── Left: the hook — centered on mobile, left-aligned on desktop ── */}
        <div className="animate-fade-up text-center lg:text-left">
          {/* Demo-mode disclosure only — in live mode the retailer cluster below
              already signals freshness, so the badge would just repeat "live". */}
          {!liveAvailable && (
            <div className="mb-5 inline-flex max-w-[92vw] flex-wrap items-center justify-center gap-x-2 gap-y-1 rounded-full border border-brand/30 bg-brand/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-brand backdrop-blur">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-brand" />
              </span>
              <span>Demo mode · sample data</span>
            </div>
          )}

          <h1 className="text-balance text-[1.9rem] font-bold leading-[1.06] tracking-tight sm:text-5xl lg:text-6xl">
            Your shelf looks different on{" "}
            <span className="text-gradient">every retailer</span>.
          </h1>
          <p className="mx-auto mt-3 max-w-lg text-pretty text-base text-muted-foreground sm:text-lg lg:mx-0">
            Get fresh digital shelf data for any retailer in{" "}
            <span className="font-semibold text-foreground">30 seconds</span>.
          </p>

          {/* Reading-live proof — moved directly under the title so the
              "we read all three, at once" signal carries the headline. */}
          <div className="mt-5 hidden flex-wrap items-center justify-center gap-2.5 sm:flex lg:justify-start">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-brand">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-brand" />
              </span>
              {liveAvailable ? "Reading now" : "Sampling"}
            </span>
            {ALL_RETAILERS.map((r, i) => (
              <span
                key={r}
                className="card-hover animate-fade-up inline-flex items-center gap-1.5 rounded-full border border-border bg-card py-1 pl-1 pr-3"
                style={{ animationDelay: `${i * 90}ms` }}
              >
                <RetailerLogo retailer={r} className="h-6 w-6" />
                <span
                  className="text-sm font-semibold"
                  style={{ color: RETAILER_META[r].color }}
                >
                  {RETAILER_META[r].label}
                </span>
              </span>
            ))}
            <span className="text-xs font-medium text-muted-foreground">— side by side</span>
          </div>

          {/* Search */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              go(value);
            }}
            className="mx-auto mt-7 flex max-w-xl items-center gap-2 rounded-2xl border border-border bg-card p-2 shadow-[0_8px_40px_-12px_oklch(0_0_0/0.6)] focus-within:ring-2 focus-within:ring-brand/40 lg:mx-0"
          >
            <Search className="ml-2 h-5 w-5 shrink-0 text-muted-foreground" />
            <input
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Try your own category, brand, or keyword…"
              className="h-11 w-full bg-transparent text-base outline-none placeholder:text-muted-foreground/70"
              aria-label="Search a category, brand, or keyword"
            />
            <button
              type="submit"
              className="inline-flex h-11 items-center gap-1.5 rounded-xl bg-gold px-4 text-sm font-semibold text-background transition active:scale-[0.98]"
            >
              Explore
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          {/* Discovery — run a category, a brand, or a keyword live (or type your own) */}
          <p className="mt-6 text-sm font-medium text-muted-foreground lg:text-left">
            Try one live — or type your own:
          </p>
          <div className="mt-2 inline-flex rounded-full border border-border bg-card p-0.5 text-xs font-semibold">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`rounded-full px-3 py-1 transition ${
                  tab === t.id
                    ? "bg-gold text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-center gap-2 lg:justify-start [&>*:nth-child(n+4)]:hidden sm:[&>*:nth-child(n+4)]:inline-flex">
            {tab === "categories" &&
              DEMO_SUGGESTIONS.map((s) => (
                <button
                  key={s.key}
                  onClick={() => go(s.label)}
                  className="card-hover inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-1.5 text-sm font-medium text-foreground hover:border-brand/40"
                >
                  {s.label}
                </button>
              ))}

            {tab === "brands" &&
              BRAND_EXAMPLES.map((b) => (
                <button
                  key={b}
                  onClick={() => go(b)}
                  className="card-hover inline-flex items-center gap-2 rounded-full border border-border bg-card py-1.5 pl-2 pr-3.5 text-sm font-medium text-foreground hover:border-brand/40"
                >
                  <span className="flex h-6 w-6 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-black/10">
                    <BrandLogo brand={b} className="h-4 w-4 object-contain" />
                  </span>
                  {b}
                </button>
              ))}

            {tab === "keywords" &&
              KEYWORD_EXAMPLES.map((k) => (
                <button
                  key={k}
                  onClick={() => go(k)}
                  className="card-hover inline-flex items-center gap-2 rounded-full border border-border bg-card py-1.5 pl-3 pr-3.5 text-sm font-medium text-foreground hover:border-brand/40"
                >
                  <Search className="h-3.5 w-3.5 text-brand" />
                  {k}
                </button>
              ))}
          </div>
        </div>

        {/* ── Right rail: pain-points back up the headline, live example below.
            Shows on all sizes; on mobile it stacks under the hook. ── */}
        <div className="animate-fade-up space-y-5 lg:pl-4" style={{ animationDelay: "120ms" }}>
          <LandingPains />
          <HeroPreview onPick={(kw) => go(kw)} />
        </div>
      </div>
    </section>
  );
}
