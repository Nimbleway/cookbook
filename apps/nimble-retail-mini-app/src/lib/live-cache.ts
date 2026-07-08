import "server-only";
import type { RetailerResult } from "@/lib/types";

// ─── Instant re-demo cache ──────────────────────────────────────────────────
// A short-lived, in-memory cache of live Nimble pulls keyed by category. At a
// booth the same categories get demoed over and over — without this, every run
// waits 9–15s for Nimble. With it, a repeat pull streams back in ~50ms while
// staying fresh (TTL below). The "Re-scan now" path can bypass it (refresh) to
// prove genuinely live data.
//
// Note: this is per-server-instance memory. On a single long-running instance
// (a booth machine, or a warm Fluid Compute instance) it's highly effective;
// across cold serverless instances each starts empty, which is fine — it only
// ever makes things faster, never staler than a fresh pull.

type Entry = { results: RetailerResult[]; at: number };

const store = new Map<string, Entry>();

// 10 minutes: snappy repeat demos, while the shelf is still "today's" data.
export const LIVE_TTL_MS = 10 * 60 * 1000;

const key = (k: string) => k.trim().toLowerCase();

export function getCachedLive(keyword: string): RetailerResult[] | null {
  const e = store.get(key(keyword));
  if (!e) return null;
  if (Date.now() - e.at > LIVE_TTL_MS) {
    store.delete(key(keyword));
    return null;
  }
  return e.results;
}

export function setCachedLive(keyword: string, results: RetailerResult[]): void {
  // Never cache an all-failed pull — we'd rather retry live next time.
  if (!results.some((r) => r.status === "ok")) return;
  store.set(key(keyword), { results, at: Date.now() });
}
