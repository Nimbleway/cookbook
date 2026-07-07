"use client";

import { useCallback, useRef, useState } from "react";
import type {
  InsightPayload,
  RetailerId,
  RetailerResult,
  SearchMode,
} from "./types";
import { ALL_RETAILERS } from "./retailers";
import { buildInsights } from "./insight-engine";
import { getMockResults } from "./mock-data";

type StreamEvent =
  | { type: "meta"; keyword: string; mode: SearchMode; retailers: RetailerId[] }
  | { type: "retailer"; result: RetailerResult }
  | { type: "done" };

export type SearchState = {
  status: "idle" | "loading" | "partial" | "done" | "error";
  keyword: string;
  mode: SearchMode;
  preview: boolean; // showing the instant indexed preview while live data loads
  pending: RetailerId[]; // live retailers still being pulled (phase 2)
  retailerResults: RetailerResult[];
  insights: InsightPayload | null;
  previewInsights: InsightPayload | null; // the indexed snapshot kept for reference
  liveSwapped: boolean; // true once live data has replaced the preview
  refreshing: boolean; // true during a manual "Refresh Live Data" re-pull
  cached: boolean; // true when the live data was served from the re-demo cache
  focusBrand: string | null; // brand-intent search: run its category, focus this brand
  error?: string;
};

const initial: SearchState = {
  status: "idle",
  keyword: "",
  mode: "demo",
  preview: false,
  pending: [],
  retailerResults: [],
  insights: null,
  previewInsights: null,
  liveSwapped: false,
  refreshing: false,
  cached: false,
  focusBrand: null,
};

function demoResultsFor(keyword: string): RetailerResult[] {
  const mock = getMockResults(keyword);
  return ALL_RETAILERS.map((r) => ({
    retailer: r,
    status: "ok" as const,
    results: mock[r],
  }));
}

export function useSearch() {
  const [state, setState] = useState<SearchState>(initial);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(
    async (
      keyword: string,
      mode: SearchMode = "demo",
      opts: { refresh?: boolean; focusBrand?: string | null } = {},
    ) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const live = mode === "live";
    const isRefresh = Boolean(opts.refresh) && live;

    if (isRefresh) {
      // ── Manual "Refresh Live Data" — re-pull Nimble in place, no preview
      // flicker. Keep the current view; just show the refreshing state and
      // swap to the genuinely fresh pull when it lands.
      setState((prev) => ({
        ...prev,
        status: "partial",
        preview: false,
        refreshing: true,
        pending: [...ALL_RETAILERS],
      }));
    } else if (!live) {
      // ── DEMO mode ── instant sample, clearly labeled. No live swap, so
      // nothing on screen can later contradict it.
      const demo = demoResultsFor(keyword);
      setState({
        status: "done",
        keyword,
        mode,
        preview: false,
        pending: [],
        retailerResults: demo,
        insights: buildInsights(keyword, demo),
        previewInsights: null,
        liveSwapped: false,
        refreshing: false,
        cached: false,
        focusBrand: opts.focusBrand ?? null,
      });
      return;
    } else {
      // ── LIVE mode ── show an HONEST "reading the live shelves" state. We do
      // NOT show mock numbers as the answer, because swapping a fake leader
      // (e.g. Folgers) for the real one (e.g. Starbucks) erodes trust. The real
      // result is the first concrete answer the prospect sees.
      setState({
        status: "partial",
        keyword,
        mode,
        preview: true,
        pending: [...ALL_RETAILERS],
        retailerResults: [],
        insights: null,
        previewInsights: null,
        liveSwapped: false,
        refreshing: false,
        cached: false,
        focusBrand: opts.focusBrand ?? null,
      });
    }

    // ── Phase 2: pull live from Nimble, swap in when ready ────────────────
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, mode: "live", refresh: isRefresh }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`Live pull failed (${res.status})`);

      // demo · cache · live — declared by the server so the UI can label it honestly.
      const fromCache = res.headers.get("X-Nimble-Source") === "cache";

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const liveResults: RetailerResult[] = [];

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          let evt: StreamEvent;
          try {
            evt = JSON.parse(line) as StreamEvent;
          } catch {
            continue;
          }
          if (evt.type === "retailer") {
            liveResults.push(evt.result);
            // Surface each real retailer AS IT LANDS — the scan UI shows
            // Amazon/Walmart/Target arriving one by one (honest, and proof
            // they're all being pulled).
            setState((prev) => ({
              ...prev,
              retailerResults: [...liveResults],
              pending: ALL_RETAILERS.filter(
                (r) => !liveResults.some((c) => c.retailer === r),
              ),
            }));
          }
        }
      }

      // Render the REAL shelf once it's in. If nothing came back, say so
      // honestly rather than leaving a stuck loader.
      const liveOk = liveResults.filter((r) => r.status === "ok");
      setState((prev) => ({
        ...prev,
        status: liveOk.length ? "done" : "error",
        preview: false,
        refreshing: false,
        cached: fromCache,
        pending: [],
        retailerResults: liveResults,
        insights: liveOk.length ? buildInsights(keyword, liveResults) : prev.insights,
        liveSwapped: liveOk.length ? true : prev.liveSwapped,
        error: liveOk.length
          ? undefined
          : "Couldn't reach the retailers just now — try again.",
      }));
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      // Live failed — show an honest error (nothing mock is on screen to keep).
      setState((prev) => ({
        ...prev,
        status: prev.insights ? "done" : "error",
        error: prev.insights ? prev.error : "Live pull failed — try again.",
        preview: false,
        refreshing: false,
        pending: [],
      }));
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState(initial);
  }, []);

  return { state, run, reset };
}
