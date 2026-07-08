// ─── Core normalized schema ────────────────────────────────────────────────
// Every retailer's raw SERP payload is normalized into this shape so the
// insight engine and UI never have to care which retailer data came from.

export type RetailerId = "amazon" | "walmart" | "target";

export type RetailerSerpResult = {
  retailer: RetailerId;
  keyword: string;
  rank: number;
  productTitle: string;
  brand: string;
  price?: number;
  rating?: number;
  reviewCount?: number;
  sponsored: boolean;
  brandRaw?: string; // original brand/sub-line before canonical rollup (raw shelf)
  productUrl?: string;
  imageUrl?: string;
  availability?: string;
  collectedAt: string;
  // ─ Rich, real-time-only signals (per-retailer; optional) ─
  recentSales?: string; // Amazon: "5K+ bought in past month"
  originalPrice?: number; // pre-discount price (Walmart)
  pricePerUnit?: string; // Walmart: "$0.42/oz" — true value
  seller?: string; // Walmart: 1P vs 3P marketplace seller
  inStock?: boolean; // live availability
  badge?: string; // "Amazon's Choice" | "Prime" | "Bestseller"
};

// Per-retailer fetch outcome. We model failure explicitly so the UI can render
// partial results — one retailer failing must never fail the experience.
export type RetailerResult =
  | { retailer: RetailerId; status: "ok"; results: RetailerSerpResult[] }
  | { retailer: RetailerId; status: "error"; error: string };

// ─── Insights ───────────────────────────────────────────────────────────────

export type InsightTone = "positive" | "warning" | "neutral" | "opportunity";

// A KPI shown in the headline row (single number + label).
export type Kpi = {
  id: string;
  label: string;
  value: string;
  sub?: string;
  tone?: InsightTone;
};

// An actionable card answering: what happened / why it matters / what to do.
export type InsightCard = {
  id: string;
  title: string;
  what: string; // what happened
  why: string; // why it matters
  action: string; // what to do
  tone: InsightTone;
  retailer?: RetailerId | "cross"; // 'cross' = cross-retailer insight
};

// ─── Executive Verdict ──────────────────────────────────────────────────────
// A boardroom-ready verdict, computed from the CURRENT pull. Each answers:
// what happened · why it matters · what to do next. No trends/deltas.
export type VerdictKind =
  | "winner"
  | "opportunity"
  | "threat"
  | "pricing"
  | "availability";

export type VerdictCard = {
  id: string;
  kind: VerdictKind;
  label: string; // "Biggest Winner"
  headline: string; // short verdict, e.g. "Quest owns the shelf"
  what: string; // what happened
  why: string; // why it matters
  action: string; // what to do next
  retailer?: RetailerId;
  tone: InsightTone;
};

// ─── Cross-retailer divergence ──────────────────────────────────────────────
// The "what changes across retailers" engine — surfaces how Amazon, Walmart &
// Target differ RIGHT NOW. `magnitude` (0..1) drives "most surprising first".
export type RetailerDifferenceKind =
  | "leaders"
  | "price"
  | "sponsored"
  | "availability"
  | "promo";

export type RetailerDifference = {
  id: string;
  kind: RetailerDifferenceKind;
  label: string; // "Different leaders"
  headline: string; // the surprising one-liner
  detail?: string; // supporting line
  magnitude: number; // 0..1 surprise score (higher = lead with it)
  tone: InsightTone;
};

// ─── Cross-retailer comparison matrix ───────────────────────────────────────
// The "centerpiece" view: the same metrics laid side-by-side per retailer so the
// divergence is scannable at a glance. Pure reformat of the current pull — each
// row's display values are pre-formatted; `diverges` drives the highlight.
export type CrossMetricId = "leader" | "avgPrice" | "sponsored" | "oos" | "promo";

export type CrossMetricRow = {
  id: CrossMetricId;
  label: string;
  values: Partial<Record<RetailerId, string>>; // formatted per retailer ("$24.99", "31%", "Quest")
  diverges: boolean; // cells differ meaningfully → highlight the row
  note?: string; // short divergence tag, e.g. "17% spread" / "differs"
};

export type CrossRetailerMatrix = {
  retailers: RetailerId[];
  rows: CrossMetricRow[];
};

// ─── "3 Things We Found" ─────────────────────────────────────────────────────
// The 3 most SURPRISING things on this shelf, in plain voice — curiosity, not a
// consulting scaffold. Re-ranked from the signals already computed below; no
// what/why-it-matters/recommended-action. `why` answers "why is this interesting?"
export type FindingKind =
  | "leaders"
  | "price"
  | "sponsored"
  | "availability"
  | "promo"
  | "demand"
  | "stockout"
  | "dominance"
  | "fragmentation";

export type Finding = {
  id: string;
  kind: FindingKind;
  headline: string; // the surprising one-liner
  why: string; // one line — why this is interesting
  tone: InsightTone;
};

// Brand-level visibility aggregation used across modules.
export type BrandShare = {
  brand: string;
  count: number; // # of page-one placements
  sponsoredCount: number;
  organicCount: number;
  share: number; // 0..1 of total placements
  avgRank: number;
};

export type RetailerSummary = {
  retailer: RetailerId;
  totalResults: number;
  sponsoredPct: number;
  topBrand: string;
  brands: BrandShare[];
};

// ─── Paid vs Organic ("earned vs bought") ───────────────────────────────────
// Are brands winning because they EARNED visibility (organic page-one slots) or
// BOUGHT it (sponsored placements)? Every number here is deterministic from the
// `sponsored` flag — the most reliable cross-retailer signal we have. The
// verdict/soWhat strings are deterministic fallbacks; Claude may enrich them.
export type BrandDependence = {
  brand: string;
  share: number; // 0..1 of total page-one placements
  paidPct: number; // 0..100 — share of THIS brand's placements that are sponsored
  sponsoredCount: number;
  organicCount: number;
};

export type PaidOrganic = {
  organicLeader: { brand: string; organicCount: number } | null; // most earned slots
  paidLeader: { brand: string; sponsoredCount: number } | null; // most ads
  sponsoredPct: number; // 0..100 overall
  byRetailer: { retailer: RetailerId; sponsoredPct: number }[]; // pay-to-play per shelf
  dependence: BrandDependence[]; // top brands, how much of their visibility is paid
  mostEfficientOrganic: { brand: string; organicCount: number; paidPct: number } | null;
  verdict: string; // deterministic "earned vs bought" one-liner (fallback)
  soWhat: string; // deterministic strategic consequence (fallback)
};

// The full computed insight payload for a search.
export type InsightPayload = {
  keyword: string;
  collectedAt: string;
  retailers: RetailerId[]; // which retailers actually returned data
  failedRetailers: RetailerId[];
  heroInsight: {
    question: string;
    brand: string;
    share: number; // headline %, 0..100
    retailerLabel?: string; // set when the headline is a single-retailer fact
    answer: string;
    tone: InsightTone;
  };

  kpis: Kpi[];
  verdicts: VerdictCard[]; // the executive verdict (Winner/Opportunity/Threat/Pricing/Availability)
  findings: Finding[]; // "3 things we found" — the most surprising, plain-voice

  crossRetailer: RetailerDifference[]; // "what changes across retailers", divergence-ranked
  crossRetailerMatrix: CrossRetailerMatrix; // the same metrics laid out side-by-side per retailer
  paidOrganic: PaidOrganic; // "earned vs bought" — sponsored vs organic leadership
  cards: InsightCard[];
  perRetailer: RetailerSummary[];
  brandShare: BrandShare[]; // cross-retailer aggregated
  topSelling: TopSeller[]; // demand velocity (real-time only)
  rightNow: RightNowSnapshot; // point-in-time facts from THIS pull (no history)
  results: RetailerSerpResult[]; // raw normalized rows for the explorer
};

// ─── "What we see right now" — point-in-time facts, NO history implied ──────
// Every fact is derived from the CURRENT pull only (availability, promotions,
// paid penetration, leader gap). We never claim movement, trends, or deltas
// against a prior pull — there are no historical snapshots to compare against.
export type RightNowFact = {
  id: string;
  kind: "availability" | "promo" | "sponsored" | "leader";
  label: string; // e.g. "Availability"
  value: string; // e.g. "2 products out of stock right now"
  detail?: string; // e.g. "Quest at #4 on Walmart"
  tone: InsightTone;
};

export type RightNowSnapshot = {
  facts: RightNowFact[]; // 0–4 defensible point-in-time facts
};

// A high-velocity product — the "selling right now" signal that static reports
// can't show. visibilityRank vs sales order is where the aha lives.
export type TopSeller = {
  brand: string;
  productTitle: string;
  retailer: RetailerId;
  recentSales: string;
  salesValue: number;
  visibilityRank: number;
  imageUrl?: string;
  price?: number;
  productUrl?: string;
};

// ─── Search request ───────────────────────────────────────────────────────

export type SearchMode = "demo" | "live";

export type SearchRequest = {
  keyword: string;
  mode: SearchMode;
};
