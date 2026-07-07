"use client";

/* eslint-disable @next/next/no-img-element */
import { useEffect, useRef, useState } from "react";
import { useSearch } from "@/lib/use-search";
import { landingCategory } from "@/lib/config";
import { SiteHeader } from "./site-header";
import { HeroSearch } from "./hero-search";
import { ResultsExperience } from "./results-experience";
import { LeadCapture } from "./lead-capture";
import { LeadModalProvider } from "./lead-modal";
import { TopProgress } from "./top-progress";
import { ToastProvider } from "./toast";

export function ExperienceApp({ liveAvailable }: { liveAvailable: boolean }) {
  const { state, run, reset } = useSearch();
  const hasSearched = state.status !== "idle";
  const hasInsights = Boolean(state.insights);

  // Land on a real result, not a search box: auto-run a flagship category once
  // on first load so a QR/booth visitor sees the answer + cross-retailer matrix
  // with zero action. The ref guard (touched only inside the effect) prevents a
  // StrictMode double-run. Disabled when NEXT_PUBLIC_LANDING_CATEGORY="".
  const didAutoRun = useRef(false);
  useEffect(() => {
    if (didAutoRun.current || !landingCategory) return;
    didAutoRun.current = true;
    run(landingCategory, liveAvailable ? "live" : "demo");
  }, [run, liveAvailable]);

  // "New search" returns to the hero. Until then (with auto-run on) we suppress
  // the hero so the page never flashes the landing before the result lands.
  const [showHero, setShowHero] = useState(!landingCategory);
  const handleReset = () => {
    setShowHero(true);
    reset();
  };
  const autoRunPending = !hasSearched && !showHero;

  return (
    <ToastProvider>
      <LeadModalProvider>
      <TopProgress state={state} />
      {/* Logo returns home; the Shoptalk CTA shows on every page. */}
      <SiteHeader onHome={hasSearched ? handleReset : undefined} />
      <main className="flex-1">
        {autoRunPending ? (
          <div className="flex min-h-[70vh] items-center justify-center" aria-busy>
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-brand" />
          </div>
        ) : !hasSearched ? (
          <div key="landing" className="animate-fade-in">
            <HeroSearch onSearch={run} liveAvailable={liveAvailable} />
            <Footer />
          </div>
        ) : (
          <div key="results" className="animate-fade-in">
            <ResultsExperience
              key={state.keyword}
              state={state}
              onReset={handleReset}
              onRefresh={() => run(state.keyword, "live", { refresh: true })}
            />
          </div>
        )}

        {/* Floating lead capture — appears only once value is on screen */}
        <LeadCapture
          visible={hasInsights}
          keyword={state.keyword}
          brand={state.focusBrand}
        />

        {state.status === "error" && (
          <div className="mx-auto max-w-md px-4 py-8 text-center">
            <p className="text-sm text-rose-400">{state.error}</p>
            <button
              onClick={handleReset}
              className="mt-3 rounded-xl border border-border px-4 py-2 text-sm font-medium"
            >
              Try again
            </button>
          </div>
        )}
      </main>
      </LeadModalProvider>
    </ToastProvider>
  );
}

function Footer() {
  return (
    <footer className="mt-8 bg-[oklch(0.17_0_0)] text-white">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-5 px-6 py-12 text-center">
        <img
          src="/nimble-logo-footer.svg"
          alt="Nimble"
          className="h-7 w-auto opacity-95"
          width={200}
          height={28}
        />
        <p className="max-w-md text-balance text-sm text-white/70">
          Retail intelligence powered by Nimble&apos;s live web data, with AI
          analysis. See any category, on any retailer, right now.
        </p>
        <a
          href="https://nimbleway.com"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-full bg-white/10 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/20"
        >
          nimbleway.com
        </a>
      </div>
    </footer>
  );
}
