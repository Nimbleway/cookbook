import type { NextRequest } from "next/server";
import type { RetailerId, RetailerResult } from "@/lib/types";
import { ALL_RETAILERS } from "@/lib/retailers";
import { getMockResults, DEMO_SUGGESTIONS } from "@/lib/mock-data";
import { fetchRetailerLive } from "@/services/nimble-serp";
import { getCachedLive, setCachedLive } from "@/lib/live-cache";
import { landingCategory } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Pull every retailer in parallel for one keyword, returning the settled set.
async function pullLive(keyword: string): Promise<RetailerResult[]> {
  return Promise.all(
    ALL_RETAILERS.map((retailer) => fetchRetailerLive(retailer, keyword)),
  );
}

// Optional booth pre-warm: when PREWARM_LIVE=true, warm the prepared categories
// once on the first live request so even the FIRST demo of each is instant.
// Fire-and-forget and deduped against the cache; off by default (it spends
// Nimble credits up front).
let prewarmStarted = false;
function maybePrewarm() {
  if (prewarmStarted || process.env.PREWARM_LIVE !== "true") return;
  prewarmStarted = true;
  // Warm the LANDING category FIRST — it's the auto-loaded first impression, so
  // it has to be the soonest one ready — then the rest of the prepared set.
  const seen = new Set<string>();
  const queue = [landingCategory, ...DEMO_SUGGESTIONS.map((s) => s.label)].filter(
    (label): label is string => {
      const k = (label ?? "").trim().toLowerCase();
      if (!k || seen.has(k)) return false;
      seen.add(k);
      return true;
    },
  );
  for (const label of queue) {
    if (getCachedLive(label)) continue;
    void pullLive(label)
      .then((results) => setCachedLive(label, results))
      .catch(() => {});
  }
}

// ─── Streaming search endpoint ──────────────────────────────────────────────
// Streams newline-delimited JSON (NDJSON). One line per retailer AS SOON AS it
// resolves (parallel, never sequential), then a final "done" line. The client
// recomputes insights after each retailer arrives → value appears in seconds,
// the experience never blocks on the slowest retailer, and one retailer failing
// never fails the whole stream.

type StreamEvent =
  | { type: "meta"; keyword: string; mode: "demo" | "live"; retailers: RetailerId[] }
  | { type: "retailer"; result: RetailerResult }
  | { type: "done" };

export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as {
    keyword?: string;
    mode?: "demo" | "live";
    refresh?: boolean; // bypass the cache to prove a genuinely fresh pull
  };
  const keyword = (body.keyword ?? '').trim();
  // Server-side enforcement: if FORCE_DEMO is set, always serve mock data
  const forceDemoEnv = process.env.FORCE_DEMO === 'true';
  const mode = forceDemoEnv ? 'demo' : (body.mode === 'live' ? 'live' : 'demo');
  const refresh = body.refresh === true;

  if (!keyword) {
    return new Response(JSON.stringify({ error: "keyword required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Resolve the data source BEFORE streaming so the client knows on response
  // exactly what it's getting: demo · cache · live. (Honesty/trust requirement.)
  const isDemo = mode === "demo";
  if (!isDemo) maybePrewarm();
  const cached = !isDemo && !refresh ? getCachedLive(keyword) : null;
  const source = isDemo ? "demo" : cached ? "cache" : "live";

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (e: StreamEvent) =>
        controller.enqueue(encoder.encode(JSON.stringify(e) + "\n"));

      send({ type: "meta", keyword, mode, retailers: ALL_RETAILERS });

      if (isDemo) {
        // Stagger the (instant) mock results so the UI shows progressive
        // rendering and the experience feels alive at the booth.
        const mock = getMockResults(keyword);
        for (let i = 0; i < ALL_RETAILERS.length; i++) {
          await new Promise((r) => setTimeout(r, i === 0 ? 120 : 200));
          const retailer = ALL_RETAILERS[i];
          send({
            type: "retailer",
            result: { retailer, status: "ok", results: mock[retailer] },
          });
        }
        send({ type: "done" });
        controller.close();
        return;
      }

      // Instant re-demo: serve a recent pull from cache, staggered for progressive feel.
      if (cached) {
        for (let i = 0; i < cached.length; i++) {
          await new Promise((r) => setTimeout(r, i === 0 ? 80 : 140));
          send({ type: "retailer", result: cached[i] });
        }
        send({ type: "done" });
        controller.close();
        return;
      }

      // Cache miss (or forced refresh): fire all retailers in PARALLEL, emit
      // each as it settles, then cache the full set for instant re-demos.
      const collected: RetailerResult[] = [];
      await Promise.all(
        ALL_RETAILERS.map(async (retailer) => {
          const result = await fetchRetailerLive(retailer, keyword);
          collected.push(result);
          send({ type: "retailer", result });
        }),
      );
      setCachedLive(keyword, collected);
      send({ type: "done" });
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Cache-Control": "no-store, no-transform",
      "X-Accel-Buffering": "no",
      "X-Nimble-Source": source,
    },
  });
}
