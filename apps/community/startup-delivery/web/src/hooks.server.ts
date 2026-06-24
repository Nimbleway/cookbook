import type { Handle, RequestEvent } from "@sveltejs/kit";
import { dev } from "$app/environment";
import { env } from "$env/dynamic/private";

// Best-effort, in-memory per-IP rate limiter in front of the endpoints that trigger
// paid pipeline work on the bridge (OpenRouter / Nimble / name.com). It blunts naive
// single-source floods that would otherwise burn provider quota or hold all of the
// bridge's concurrency slots (denying every other user a 429). It is NOT globally
// exact: each serverless instance keeps its own buckets, so for hard guarantees front
// these routes with the Vercel WAF or a KV-backed limiter. Tunable via env; set
// RATE_LIMIT_DISABLED=1 to turn it off.

// Exact paths that proxy an expensive bridge call. Cheap reads — polling
// /api/jobs/<id>, /api/deliveries*, /api/history — are deliberately excluded so the
// live poll (every ~1.5s) and the dock gallery are never throttled.
const GUARDED_PATHS = new Set([
  "/api/jobs",
  "/api/deliver",
  "/api/deliver/stream",
  "/api/build-landing",
  "/api/refine",
  "/api/remix",
]);

function clampInt(raw: string | undefined, fallback: number, min: number, max: number): number {
  const n = Number.parseInt(raw ?? "", 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

// Token bucket: BURST tokens, one refilled every REFILL_MS. Defaults (10 / 6s ≈ a
// 10-token burst then ~10/min sustained) comfortably fit an engaged human session
// while starving a scripted flood.
const BURST = clampInt(env.RATE_LIMIT_BURST, 10, 1, 1000);
const REFILL_MS = clampInt(env.RATE_LIMIT_REFILL_MS, 6000, 100, 3_600_000);
const RATE_LIMIT_DISABLED = env.RATE_LIMIT_DISABLED === "1";

const IDLE_TTL_MS = 10 * 60 * 1000;
const SWEEP_MS = 5 * 60 * 1000;

type Bucket = { tokens: number; last: number };
const buckets = new Map<string, Bucket>();
let lastSweep = 0;

// Drop buckets that have been idle long enough to be irrelevant, so the Map can't grow
// unbounded with one entry per unique IP seen.
function sweep(now: number): void {
  if (now - lastSweep < SWEEP_MS) return;
  lastSweep = now;
  for (const [ip, b] of buckets) {
    if (now - b.last > IDLE_TTL_MS) buckets.delete(ip);
  }
}

// Returns 0 when the request is allowed, otherwise the seconds to wait (Retry-After).
function take(ip: string, now: number): number {
  let b = buckets.get(ip);
  if (!b) {
    b = { tokens: BURST, last: now };
    buckets.set(ip, b);
  }
  b.tokens = Math.min(BURST, b.tokens + (now - b.last) / REFILL_MS);
  b.last = now;
  if (b.tokens >= 1) {
    b.tokens -= 1;
    return 0;
  }
  return Math.max(1, Math.ceil(((1 - b.tokens) * REFILL_MS) / 1000));
}

function clientIp(event: RequestEvent): string {
  try {
    return event.getClientAddress();
  } catch {
    return event.request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  }
}

export const handle: Handle = async ({ event, resolve }) => {
  // Skip in local dev so iterating doesn't trip the limiter; preview/production enforce it.
  if (!RATE_LIMIT_DISABLED && !dev && GUARDED_PATHS.has(event.url.pathname)) {
    const now = Date.now();
    sweep(now);
    const retryAfter = take(clientIp(event), now);
    if (retryAfter > 0) {
      return new Response(JSON.stringify({ error: "Too many requests — please wait a moment and try again." }), {
        status: 429,
        headers: {
          "content-type": "application/json",
          "retry-after": String(retryAfter),
          "cache-control": "no-store",
        },
      });
    }
  }
  return resolve(event);
};
