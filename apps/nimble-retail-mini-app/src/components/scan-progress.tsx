"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, Sparkles, Clock } from "lucide-react";
import type { RetailerResult, SearchMode } from "@/lib/types";
import { ALL_RETAILERS, RETAILER_META } from "@/lib/retailers";
import { RetailerLogo } from "./product-tile";

// "Scanning the shelves" — shows ALL THREE retailers at once, each with its own
// live status. The stage phrase ("ranking the page…") advances MONOTONICALLY
// and stops at the last one — it never loops back, so it reads as real progress,
// not a scripted carousel. Plain language only (no SERP/agent jargon).
const PHRASES = [
  "reading the shelf",
  "sorting sponsored from organic",
  "matching brands across listings",
  "ranking the page",
  "checking availability",
  "almost there",
];

export function ScanProgress({
  mode,
  retailerResults,
}: {
  mode: SearchMode;
  retailerResults: RetailerResult[];
}) {
  const total = ALL_RETAILERS.length;
  const arrived = retailerResults.length;
  const done = arrived === total;

  // Ticking elapsed is the undeniable "it's running" signal.
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  // Stage phrase advances with time and CAPS at the last — never wraps.
  const phase = Math.min(Math.floor(elapsed / 2.2), PHRASES.length - 1);

  const byId = new Map(retailerResults.map((r) => [r.retailer, r]));
  const rows = ALL_RETAILERS.map((id) => {
    const res = byId.get(id);
    const meta = RETAILER_META[id];
    if (res?.status === "ok")
      return { id, label: meta.label, detail: `${res.results.length} products`, state: "ok" as const };
    if (res?.status === "error")
      return { id, label: meta.label, detail: "didn't respond", state: "err" as const };
    return { id, label: meta.label, detail: `${PHRASES[phase]}…`, state: "active" as const };
  });

  return (
    <section
      aria-busy="true"
      className="animate-fade-up overflow-hidden rounded-3xl border border-border bg-[oklch(0.17_0_0)] text-white"
    >
      {/* Always-animated bar — never freezes at a fraction, so a slow retailer
          can't read as "stuck". */}
      <div className="relative h-1 w-full overflow-hidden bg-white/10">
        <span
          className="absolute top-0 h-full rounded-full bg-gold"
          style={{ animation: "progress-indeterminate 1.1s ease-in-out infinite" }}
        />
      </div>

      <div className="flex items-center gap-2 px-5 pt-4">
        <Sparkles className="h-4 w-4 text-amber-300" />
        <span className="text-sm font-semibold tracking-tight">
          {mode === "live" ? "Reading the live shelves" : "Loading the shelf"}
        </span>
        <span className="ml-auto font-mono text-xs tabular-nums text-white/50">
          {Math.min(arrived, total)}/{total} · {elapsed}s
        </span>
      </div>

      {/* Set the expectation up front so a ~30s live pull never reads as broken. */}
      {mode === "live" && !done && (
        <div className="mx-5 mt-2 flex items-center gap-2 rounded-xl border border-amber-400/25 bg-amber-400/10 px-3 py-2.5 text-amber-200">
          <Clock className="h-4 w-4 shrink-0" />
          <p className="text-[13px] font-medium leading-snug">
            <span className="font-bold">~30 seconds</span> to read your live shelf across all
            three retailers — worth the wait for the real thing.
          </p>
        </div>
      )}

      {/* All three retailers, side by side — each with its own live status. */}
      <ul aria-live="polite" className="space-y-2 px-5 pb-3 pt-3.5">
        {rows.map((r) => (
          <li
            key={r.id}
            className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5"
          >
            <RetailerLogo retailer={r.id} className="h-5 w-5 shrink-0" />
            <span className="text-sm font-semibold text-white">{r.label}</span>
            <span
              className={`ml-auto flex items-center gap-1.5 text-xs ${
                r.state === "ok"
                  ? "text-white/70"
                  : r.state === "err"
                    ? "text-amber-300/90"
                    : "text-white/55"
              }`}
            >
              {r.state === "active" && <span className="font-mono">{r.detail}</span>}
              {r.state === "ok" && (
                <>
                  <span className="font-mono">{r.detail}</span>
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                </>
              )}
              {r.state === "err" && (
                <>
                  <span className="font-mono">{r.detail}</span>
                  <span className="text-amber-400">!</span>
                </>
              )}
              {r.state === "active" && (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-300" />
              )}
            </span>
          </li>
        ))}
      </ul>

      {done && (
        <p className="flex items-center gap-2 px-5 pb-4 text-xs text-white/55">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-300" />
          Working out who owns the shelf…
        </p>
      )}

      {/* If it runs past the stated ~30s, reassure rather than let it feel stuck. */}
      {mode === "live" && !done && elapsed >= 30 && (
        <p className="px-5 pb-4 text-[11px] leading-relaxed text-white/40">
          Almost there — Amazon&apos;s the slowest shelf to read. Hang tight, it&apos;s
          pulling fresh, not cached.
        </p>
      )}
    </section>
  );
}
