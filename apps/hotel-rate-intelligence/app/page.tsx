"use client";

import { useState } from "react";
import { RateForm } from "./components/RateForm";
import { RateGrid } from "./components/RateGrid";
import { FlagList } from "./components/FlagList";
import { MonitorPanel } from "./components/MonitorPanel";
import { AgentResult } from "@/lib/types";
import { dateRange } from "@/lib/dates";

type Tab = "check" | "monitor";

export default function Page() {
  const [tab, setTab] = useState<Tab>("check");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastDates, setLastDates] = useState<string[]>([]);
  const [lastUserHotel, setLastUserHotel] = useState<string>("");

  const handleSubmit = async (data: {
    userHotel: { name: string; city: string };
    competitors: { name: string; city: string }[];
    windowDays: 7 | 14;
    startDate: string;
  }) => {
    setLoading(true);
    setProgress([]);
    setResult(null);
    setError(null);
    setLastUserHotel(data.userHotel.name);

    const start = new Date(data.startDate + "T00:00:00");
    setLastDates(dateRange(start, data.windowDays));

    try {
      const res = await fetch("/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!res.ok || !res.body) {
        setError(`Request failed: ${res.status} ${await res.text()}`);
        setLoading(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "progress") {
              setProgress((prev) => [...prev, event.message]);
            } else if (event.type === "result") {
              setResult(event.data);
            } else if (event.type === "error") {
              setError(event.message);
            }
          } catch {
            // ignore malformed SSE lines
          }
        }
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const sectionCls = "bg-[#161B26] border border-[#2A3348] rounded-xl p-5";
  const sectionTitleCls = "text-xs font-semibold text-[#6B7694] uppercase tracking-wider mb-4";

  return (
    <div className="min-h-screen bg-[#0E1118]">
      {/* Header */}
      <header className="border-b border-[#2A3348] bg-[#161B26]/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Nimble wordmark */}
            <svg width="88" height="20" viewBox="0 0 88 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <text x="0" y="16" fontFamily="system-ui, sans-serif" fontWeight="700" fontSize="16" fill="#6665EC">nimble</text>
            </svg>
            <span className="text-[#2A3348] text-lg font-light">/</span>
            <span className="text-sm font-medium text-[#A09DB2]">Rate Intelligence</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-[#6B7694]">
            <span className="w-1.5 h-1.5 bg-[#34C48B] rounded-full animate-pulse inline-block" />
            Powered by Nimble Web API
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Page title */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[#F0EFFB] tracking-tight">Competitive Rate Analysis</h1>
          <p className="text-sm text-[#6B7694] mt-1">
            Check nightly rates across Booking.com and Expedia, flag parity issues and undercutting, get an actionable summary.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-[#2A3348]">
          {(["check", "monitor"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === t
                  ? "border-[#6665EC] text-[#6665EC]"
                  : "border-transparent text-[#6B7694] hover:text-[#A09DB2]"
              }`}
            >
              {t === "check" ? "On-demand check" : "Cron monitor"}
            </button>
          ))}
        </div>

        {tab === "check" && (
          <div className="grid grid-cols-[340px_1fr] gap-6 items-start">
            {/* Sidebar form */}
            <div className={sectionCls}>
              <RateForm onSubmit={handleSubmit} loading={loading} />
            </div>

            {/* Main content */}
            <div className="space-y-5">
              {/* Progress */}
              {(loading || progress.length > 0) && (
                <div className={sectionCls}>
                  <h2 className={sectionTitleCls}>Analysis progress</h2>
                  <div className="space-y-1.5">
                    {progress.map((msg, i) => (
                      <div key={i} className="flex items-start gap-3 text-sm">
                        <span className="text-[#34C48B] text-xs mt-0.5 font-mono shrink-0">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span className="text-[#A09DB2]">{msg}</span>
                      </div>
                    ))}
                    {loading && (
                      <div className="flex items-center gap-2 text-sm text-[#6665EC] mt-1 pl-6">
                        <span className="w-3 h-3 border-2 border-[#6665EC]/30 border-t-[#6665EC] rounded-full animate-spin shrink-0" />
                        Working...
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="bg-[#E05C5C]/5 border border-[#E05C5C]/20 rounded-xl p-4 text-sm text-[#E05C5C]">
                  {error}
                </div>
              )}

              {result && (
                <>
                  {/* Retrieval errors */}
                  {result.errors.length > 0 && (
                    <div className="bg-yellow-900/10 border border-yellow-700/20 rounded-xl p-4">
                      <h2 className="text-xs font-semibold text-yellow-400 uppercase tracking-wider mb-2">
                        Retrieval issues ({result.errors.length})
                      </h2>
                      <div className="space-y-1">
                        {result.errors.map((e, i) => (
                          <div key={i} className="text-xs text-[#6B7694]">
                            {e.hotel} / {e.ota}: {e.reason}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Summary hero */}
                  {result.summary && (
                    <div className="bg-gradient-to-br from-[#6665EC]/10 to-[#161B26] border border-[#6665EC]/20 rounded-xl p-5">
                      <h2 className={sectionTitleCls + " text-[#6665EC]"}>Revenue manager summary</h2>
                      <p className="text-sm text-[#B8BDD6] leading-relaxed">{result.summary}</p>
                    </div>
                  )}

                  {/* Rate grid */}
                  <div className={sectionCls}>
                    <h2 className={sectionTitleCls}>Rate grid</h2>
                    <RateGrid
                      rates={result.rates}
                      flags={result.flags}
                      listings={result.listings}
                      dates={lastDates}
                      userHotelName={lastUserHotel}
                    />
                  </div>

                  {/* Flags */}
                  <div className={sectionCls}>
                    <h2 className={sectionTitleCls}>Flags</h2>
                    <FlagList flags={result.flags} />
                  </div>

                  {/* Source URLs */}
                  {result.listings.length > 0 && (
                    <div className={sectionCls}>
                      <h2 className={sectionTitleCls}>Source URLs</h2>
                      <div className="space-y-1.5">
                        {result.listings.map((l, i) => (
                          <div key={i} className="flex items-center gap-3 text-xs">
                            <span className="text-[#6B7694] w-36 shrink-0 truncate">{l.hotelName}</span>
                            <span className="text-[#6B7694] w-20 shrink-0 capitalize">
                              {l.ota === "booking" ? "Booking.com" : "Expedia"}
                            </span>
                            <a
                              href={l.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[#6665EC] hover:text-[#A09DB2] truncate transition-colors"
                            >
                              {l.url}
                            </a>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}

              {!loading && !result && !error && (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-[#6665EC]/10 border border-[#6665EC]/20 flex items-center justify-center mb-4">
                    <span className="text-[#6665EC] text-xl">&#9; </span>
                  </div>
                  <p className="text-sm text-[#6B7694]">Configure hotels and click <span className="text-[#A09DB2]">Check rates</span> to run an analysis.</p>
                  <p className="text-xs text-[#6B7694]/60 mt-1">Results typically take 30-90 seconds depending on the number of competitors.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "monitor" && (
          <div className="max-w-lg">
            <div className={sectionCls}>
              <MonitorPanel />
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-[#2A3348] mt-16">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between text-xs text-[#6B7694]">
          <span>Built with Nimble Web API + Anthropic Claude</span>
          <a href="https://nimbleway.com" target="_blank" rel="noopener noreferrer" className="hover:text-[#A09DB2] transition-colors">
            nimbleway.com
          </a>
        </div>
      </footer>
    </div>
  );
}
