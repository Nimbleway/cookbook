import "server-only";
import type {
  RetailerId,
  RetailerResult,
  RetailerSerpResult,
} from "@/lib/types";
import { NIMBLE_AGENTS } from "@/lib/retailers";

// ─── Nimble live SERP service ───────────────────────────────────────────────
// Calls Nimble Web Search Agents and normalizes their output into our schema.
// All retailer intelligence comes from here — Claude never fabricates it.
//
// Reconciling the spec's per-retailer endpoint env vars with the real Nimble
// API: NIMBLE_<RETAILER>_SERP_AGENT_ENDPOINT may be EITHER
//   • a full URL to POST to, or
//   • a Nimble agent name (e.g. "amazon_serp")
// If unset, we fall back to the canonical public agent names below.

const NIMBLE_RUN_URL = "https://sdk.nimbleway.com/v1/agents/run";

const DEFAULT_AGENT_NAME: Record<RetailerId, string> = {
  amazon: "amazon_serp",
  walmart: "walmart_serp",
  target: "target_serp",
};

// Hard ceiling so one slow retailer can't stall the whole experience. Each
// retailer streams to the UI the instant it returns, so a slow one never blocks
// the others — this just caps the worst case. Amazon's SERP agent is the
// slowest/most variable (often 25-40s cold), so this is generous enough that a
// slow-but-fine pull isn't dropped from the cross-retailer view. Vercel allows
// up to 300s, and PREWARM_LIVE makes the common (cached) case instant anyway.
const PER_RETAILER_TIMEOUT_MS = 55_000;

function num(v: unknown): number | undefined {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const n = parseFloat(v.replace(/[^0-9.]/g, ""));
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
}

function str(v: unknown): string | undefined {
  if (typeof v === "string" && v.trim()) return v.trim();
  return undefined;
}

function bool(v: unknown): boolean {
  if (typeof v === "boolean") return v;
  if (typeof v === "string") return /^(true|yes|sponsored|ad)$/i.test(v.trim());
  return false;
}

// Find the array of product-like objects in the parsing payload. Nimble SERP
// agents return `data.parsing` as EITHER a direct array (amazon_serp,
// walmart_serp, target_serp) or an object wrapping one.
function findResultsArray(parsing: unknown): Record<string, unknown>[] {
  if (Array.isArray(parsing)) {
    return parsing.filter((x) => x && typeof x === "object") as Record<
      string,
      unknown
    >[];
  }
  if (!parsing || typeof parsing !== "object") return [];
  const obj = parsing as Record<string, unknown>;
  const preferredKeys = [
    "results",
    "products",
    "organic_results",
    "search_results",
    "items",
    "listings",
    "data",
  ];
  for (const key of preferredKeys) {
    const v = obj[key];
    if (Array.isArray(v) && v.length && typeof v[0] === "object") {
      return v as Record<string, unknown>[];
    }
  }
  // Otherwise, scan all values for the first plausible product array.
  for (const v of Object.values(obj)) {
    if (Array.isArray(v) && v.length && typeof v[0] === "object") {
      return v as Record<string, unknown>[];
    }
    if (v && typeof v === "object") {
      const nested = findResultsArray(v);
      if (nested.length) return nested;
    }
  }
  return [];
}

function pick<T>(row: Record<string, unknown>, keys: string[]): T | undefined {
  for (const k of keys) {
    if (row[k] !== undefined && row[k] !== null) return row[k] as T;
  }
  return undefined;
}

const BRAND_STOPWORDS = new Set([
  "the",
  "a",
  "an",
  "new",
  "premium",
  "original",
  "fresh",
]);

function deriveBrand(row: Record<string, unknown>, title: string): string {
  const explicit = str(pick(row, ["brand", "brand_name", "manufacturer"]));
  if (explicit) return explicit;
  // SERP product names usually lead with the brand. Skip leading filler words
  // and take 1-2 tokens so "The Original Donut Shop" → "Original Donut".
  const tokens = title.split(/[\s,]+/).filter(Boolean);
  if (!tokens.length) return "Unknown";
  let i = 0;
  while (i < tokens.length - 1 && BRAND_STOPWORDS.has(tokens[i].toLowerCase()))
    i++;
  const first = tokens[i];
  const second = tokens[i + 1];
  // Keep a two-word brand when the second token is also capitalized (e.g.
  // "Black Rifle", "Premier Protein"), otherwise just the first token.
  if (second && /^[A-Z]/.test(second) && !BRAND_STOPWORDS.has(second.toLowerCase())) {
    return `${first} ${second}`.replace(/[^\w\s'&-]/g, "");
  }
  return first.replace(/[^\w'&-]/g, "");
}

function sanitizeUrl(raw: string | undefined | null): string {
  if (!raw) return '';
  try {
    const u = new URL(raw);
    if (u.protocol === 'https:' || u.protocol === 'http:') return raw;
  } catch {
    // invalid URL
  }
  return '';
}

function normalizeRow(
  row: Record<string, unknown>,
  retailer: RetailerId,
  keyword: string,
  index: number,
  collectedAt: string,
): RetailerSerpResult | null {
  const title = str(
    pick(row, ["title", "name", "product_title", "productName", "product_name"]),
  );
  if (!title) return null;
  const rank = num(pick(row, ["rank", "position", "index"])) ?? index + 1;

  // Live availability: Walmart exposes an out-of-stock boolean.
  const oos = pick(row, ["product_out_of_stock"]);
  const availabilityStr = str(pick(row, ["availability", "product_availability", "stock"]));
  const inStock =
    typeof oos === "boolean"
      ? !oos
      : availabilityStr
        ? !/out of stock|unavailable/i.test(availabilityStr)
        : undefined;

  // Badges (Amazon).
  const badge = bool(pick(row, ["amazons_choice"]))
    ? "Amazon's Choice"
    : bool(pick(row, ["prime_eligible"]))
      ? "Prime"
      : undefined;

  return {
    retailer,
    keyword,
    rank,
    productTitle: title,
    brand: deriveBrand(row, title),
    price: num(pick(row, ["price", "product_price", "current_price", "sale_price", "price_value"])),
    rating: num(pick(row, ["rating", "product_rating", "stars", "average_rating"])),
    reviewCount: num(pick(row, ["reviews", "review_count", "product_reviews_count", "ratings_total"])),
    sponsored: bool(pick(row, ["sponsored", "is_sponsored", "ad", "is_ad"])),
    productUrl: sanitizeUrl(str(pick(row, ["url", "link", "product_url", "product_link"]))),
    imageUrl: str(pick(row, ["image", "image_url", "product_image", "thumbnail", "img"])),
    availability: availabilityStr ?? (inStock === false ? "Out of stock" : undefined),
    collectedAt,
    // Rich real-time signals.
    recentSales: str(pick(row, ["recent_sales", "bought_recently", "purchase_count"])),
    originalPrice: num(pick(row, ["product_price_original", "original_price", "list_price", "was_price"])),
    pricePerUnit: str(pick(row, ["product_price_per_unit", "price_per_unit", "unit_price"])),
    seller: str(pick(row, ["product_seller", "seller", "sold_by"])),
    inStock,
    badge,
  };
}

// Fetch + normalize a single retailer. Resolves to an explicit ok/error result
// so the orchestrator can render partial data — never throws to the caller.
export async function fetchRetailerLive(
  retailer: RetailerId,
  keyword: string,
): Promise<RetailerResult> {
  const apiKey = process.env.NIMBLE_API_KEY;
  if (!apiKey) {
    return { retailer, status: "error", error: "NIMBLE_API_KEY not configured" };
  }

  const configured = NIMBLE_AGENTS[retailer].endpoint?.trim();
  const isUrl = configured?.startsWith("http");
  const url = isUrl ? (configured as string) : NIMBLE_RUN_URL;
  const agent = isUrl
    ? DEFAULT_AGENT_NAME[retailer]
    : configured || DEFAULT_AGENT_NAME[retailer];

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PER_RETAILER_TIMEOUT_MS);
  const collectedAt = new Date().toISOString();

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ agent, params: { keyword } }),
      signal: controller.signal,
      cache: "no-store",
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      return {
        retailer,
        status: "error",
        error: `${NIMBLE_AGENTS[retailer].name} returned ${res.status}${text ? `: ${text.slice(0, 140)}` : ""}`,
      };
    }

    const json = (await res.json()) as { data?: { parsing?: unknown } };
    const rows = findResultsArray(json?.data?.parsing);
    const results = rows
      .map((r, i) => normalizeRow(r, retailer, keyword, i, collectedAt))
      .filter((r): r is RetailerSerpResult => r !== null)
      .slice(0, 24);

    if (!results.length) {
      return {
        retailer,
        status: "error",
        error: `${NIMBLE_AGENTS[retailer].name} returned no parseable results`,
      };
    }
    return { retailer, status: "ok", results };
  } catch (err) {
    const msg =
      err instanceof Error && err.name === "AbortError"
        ? `${NIMBLE_AGENTS[retailer].name} timed out`
        : err instanceof Error
          ? err.message
          : "Unknown error";
    return { retailer, status: "error", error: msg };
  } finally {
    clearTimeout(timeout);
  }
}
