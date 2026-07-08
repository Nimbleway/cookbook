import "server-only";

// ─── Claude enrichment cache + kill switch ──────────────────────────────────
// The auto-fired Claude calls (paid-organic verdict, monitoring line, brand
// signature) are pure enrichment over deterministic data. At a booth the same
// categories get demoed repeatedly, so without caching we'd re-spend Claude
// tokens on every view. This caches each response by key for 30 min, and
// `AI_ENRICH=off` disables the calls entirely (the UI falls back to the
// deterministic copy, which always renders).
//
// Note: per-server-instance memory (like the live cache). On a single booth
// machine it's fully effective; across cold serverless instances each warms
// independently — it only ever saves spend, never costs more.

type Entry = { value: unknown; at: number };
const store = new Map<string, Entry>();
const TTL_MS = 30 * 60 * 1000;

// AI enrichment is ON unless explicitly turned off — flip NEXT_PUBLIC… no:
// this is a SERVER env (no NEXT_PUBLIC_) so it can be toggled without exposing
// it client-side. Set AI_ENRICH=off to stop all auto Claude calls.
export const aiEnrichmentDisabled = (): boolean =>
  (process.env.AI_ENRICH || "").trim().toLowerCase() === "off";

export function getAiCache<T>(key: string): T | null {
  const e = store.get(key);
  if (!e) return null;
  if (Date.now() - e.at > TTL_MS) {
    store.delete(key);
    return null;
  }
  return e.value as T;
}

export function setAiCache(key: string, value: unknown): void {
  store.set(key, { value, at: Date.now() });
}
