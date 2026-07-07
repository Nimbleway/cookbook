import type { RetailerId } from "./types";

// ─── Centralized retailer / Nimble agent configuration ──────────────────────
// All retailer intelligence comes from Nimble SERP agents. Endpoints are
// injected via env so the same code runs against staging/prod agents.

export const NIMBLE_AGENTS: Record<
  RetailerId,
  { name: string; endpoint?: string }
> = {
  amazon: {
    name: "Amazon SERP Agent",
    endpoint: process.env.NIMBLE_AMAZON_SERP_AGENT_ENDPOINT,
  },
  walmart: {
    name: "Walmart SERP Agent",
    endpoint: process.env.NIMBLE_WALMART_SERP_AGENT_ENDPOINT,
  },
  target: {
    name: "Target SERP Agent",
    endpoint: process.env.NIMBLE_TARGET_SERP_AGENT_ENDPOINT,
  },
};

// Display metadata for the UI (brand color, label). `color` is tuned to be
// legible on the near-black canvas while still reading as each brand's color:
// Amazon orange-yellow, Walmart blue, Target red.
export const RETAILER_META: Record<
  RetailerId,
  { label: string; short: string; color: string; bg: string; domain: string }
> = {
  amazon: { label: "Amazon", short: "AMZ", color: "#FF9D1C", bg: "#FFF7ED", domain: "amazon.com" },
  walmart: { label: "Walmart", short: "WMT", color: "#4DA3FF", bg: "#EFF6FF", domain: "walmart.com" },
  target: { label: "Target", short: "TGT", color: "#FF4D52", bg: "#FEF2F2", domain: "target.com" },
};

export const ALL_RETAILERS: RetailerId[] = ["amazon", "walmart", "target"];

// Brand color for a retailer (legible on dark). Use for retailer NAME text,
// dots, and bars so Amazon/Walmart/Target always read in their own color.
export function retailerColor(id: RetailerId): string {
  return RETAILER_META[id].color;
}

// Same, but resolved from a display label string (e.g. "Walmart") — handy where
// the UI only has the human label (hero answer, diffs). Returns undefined if the
// label isn't one of our retailers.
export function retailerColorByLabel(label?: string | null): string | undefined {
  if (!label) return undefined;
  const hit = ALL_RETAILERS.find(
    (r) => RETAILER_META[r].label.toLowerCase() === label.trim().toLowerCase(),
  );
  return hit ? RETAILER_META[hit].color : undefined;
}

// A retailer is "live-ready" only if its agent endpoint is configured.
export function liveReadyRetailers(): RetailerId[] {
  return ALL_RETAILERS.filter((r) => Boolean(NIMBLE_AGENTS[r].endpoint));
}
