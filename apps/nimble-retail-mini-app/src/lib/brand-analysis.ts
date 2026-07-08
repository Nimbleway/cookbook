import type { InsightPayload, RetailerId } from "./types";
import { RETAILER_META } from "./retailers";
import { canonicalizeBrand } from "./brand-normalize";
import { perItemPrice } from "./insight-engine";

// Single source of truth for "how does this brand stack up" — used by both the
// on-screen Run My Brand band and the emailed report so they never diverge.
// Deterministic, current-pull only (no trends).

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

// The brand's SIGNATURE — the one pattern that makes its story different from
// every other brand's. Detected from its real per-retailer + paid/organic
// footprint, so two brands never get the same write-up.
export type BrandSignature = {
  pattern: "skew-absent" | "concentrated" | "paid-reliant" | "organic-led" | "balanced";
  headline: string;
  detail: string;
};

export type BrandAnalysis =
  | {
      found: true;
      brand: string;
      rank: number;
      total: number;
      score: number; // share of page one, 0..100 — the "visibility score"
      isLeader: boolean;
      gap: number; // pts behind #1 (or ahead of #2 when leader)
      leaderBrand: string;
      leaderPct: number;
      secondBrand?: string;
      opportunity: string;
      action: string;
      signature: BrandSignature; // the brand-specific story
    }
  | {
      found: false;
      brand: string;
      leaderBrand: string;
      leaderPct: number;
      secondBrand?: string;
      // ─ Absence diagnostic: what the empty shelf slot tells us, from the
      //   current pull. The absence IS the insight, so we quantify it. ─
      competitors: number; // # brands holding page-one space
      topThreeShare: number; // % of page one locked by the top 3 (the wall)
      sponsoredPct: number; // % of page-one slots that are paid placements
      winnableRetailer: {
        retailer: RetailerId;
        label: string;
        leaderBrand: string;
        leaderPct: number; // smallest leader grip → cheapest shelf to break into
      } | null;
      priceBand: { low: number; high: number } | null; // entry price band (mid 50%)
      action: string;
    };

export function analyzeBrand(
  insights: InsightPayload,
  brandRaw: string,
): BrandAnalysis | null {
  const term = (brandRaw || "").trim();
  if (!term) return null;
  const brands = insights.brandShare;
  const perRetailer = insights.perRetailer;
  if (!brands.length) return null;

  const leader = brands[0];
  const leaderPct = Math.round(leader.share * 100);
  const second = brands[1];

  const q = norm(term);
  // Recognize aliases: "Monster Energy" / "Monster Ultra" → Monster, etc.
  const qCanon = norm(canonicalizeBrand(term).brand);
  let idx =
    q.length < 2
      ? -1
      : brands.findIndex((b) => norm(b.brand) === q || norm(b.brand) === qCanon);
  if (idx === -1 && q.length >= 2)
    idx = brands.findIndex((b) => {
      const nb = norm(b.brand);
      return nb.includes(q) || q.includes(nb) || nb === qCanon;
    });
  if (idx === -1) {
    // ── Brand is absent from page one → build the absence diagnostic. ──
    const competitors = brands.length;
    const topThreeShare = Math.round(
      brands.slice(0, 3).reduce((s, b) => s + b.share, 0) * 100,
    );

    const rows = insights.results;
    const sponsoredPct = rows.length
      ? Math.round((rows.filter((r) => r.sponsored).length / rows.length) * 100)
      : 0;

    // Most-winnable shelf = the retailer whose #1 brand holds the *smallest*
    // grip (most fragmented → cheapest to break into).
    const winnableRetailer = perRetailer
      .filter((s) => s.brands.length > 0)
      .map((s) => ({
        retailer: s.retailer,
        label: RETAILER_META[s.retailer].label,
        leaderBrand: s.brands[0].brand,
        leaderPct: Math.round(s.brands[0].share * 100),
      }))
      .sort((a, b) => a.leaderPct - b.leaderPct)[0] ?? null;

    // Entry price band = the middle 50% of page-one prices (p25–p75), PER UNIT
    // (pack-adjusted) — so a wall of 24-packs doesn't fake a sky-high entry price.
    const prices = rows
      .map(perItemPrice)
      .filter((p): p is number => p !== null)
      .sort((a, b) => a - b);
    const round2 = (n: number) => Math.round(n * 100) / 100;
    const priceBand =
      prices.length >= 2
        ? {
            low: round2(prices[Math.floor(prices.length * 0.25)]),
            high: round2(prices[Math.floor(prices.length * 0.75)]),
          }
        : null;

    const action = winnableRetailer
      ? `Win page-one presence on ${winnableRetailer.label} first — it's the most open door — before chasing rank on the others.`
      : `Win page-one presence before optimizing rank — right now ${leader.brand} (${leaderPct}%) is taking the space you'd need.`;

    return {
      found: false,
      brand: term,
      leaderBrand: leader.brand,
      leaderPct,
      secondBrand: second?.brand,
      competitors,
      topThreeShare,
      sponsoredPct,
      winnableRetailer,
      priceBand,
      action,
    };
  }

  const match = brands[idx];
  const rank = idx + 1;
  const isLeader = rank === 1;
  const score = Math.round(match.share * 100);
  const gap = isLeader
    ? second
      ? Math.round((match.share - second.share) * 100)
      : 0
    : leaderPct - score;

  const absent = perRetailer
    .filter((s) => !s.brands.some((b) => b.brand === match.brand))
    .map((s) => s.retailer);

  let opportunity: string;
  let action: string;
  if (absent.length > 0) {
    const rtId = absent[0];
    const rt = RETAILER_META[rtId].label;
    const rtLeader = perRetailer.find((s) => s.retailer === rtId)?.brands[0]?.brand;
    const rival =
      rtLeader && rtLeader !== match.brand
        ? rtLeader
        : leader.brand !== match.brand
          ? leader.brand
          : null;
    opportunity = `${rt} — you're absent there`;
    action = rival
      ? `Prioritize ${rt}, where you don't appear on page one but ${rival} does. That's the cheapest share to win.`
      : `Prioritize ${rt}, where you don't appear on page one yet. That's the cheapest share to win.`;
  } else if (isLeader) {
    opportunity = "Defend your lead";
    action = second
      ? `You lead, but ${second.brand} is ${gap} pt${gap === 1 ? "" : "s"} back. Hold rank on your top SKUs and watch their sponsored slots.`
      : `You lead the shelf. Hold rank on your top SKUs and keep content sharp.`;
  } else {
    opportunity = `Close the ${gap}-pt gap to ${leader.brand}`;
    action = `Invest in content and sponsored placement on your best-rated SKUs to close the ${gap}-pt gap to ${leader.brand}.`;
  }

  return {
    found: true,
    brand: match.brand,
    rank,
    total: brands.length,
    score,
    isLeader,
    gap,
    leaderBrand: leader.brand,
    leaderPct,
    secondBrand: second?.brand,
    opportunity,
    action,
    signature: detectSignature(match, perRetailer, {
      isLeader,
      rank,
      total: brands.length,
      gap,
      leaderBrand: leader.brand,
      runnerUp: second?.brand,
    }),
  };
}

// Detect the ONE pattern that makes this brand's story unique — magnitude-aware
// so it never overclaims (a 4% share is NOT "strong") and never falls back to a
// vague "balanced / differs" line. Every brand gets a specific, honest read.
function detectSignature(
  match: InsightPayload["brandShare"][number],
  perRetailer: InsightPayload["perRetailer"],
  ctx: {
    isLeader: boolean;
    rank: number;
    total: number;
    gap: number;
    leaderBrand: string;
    runnerUp?: string;
  },
): BrandSignature {
  const paidPct = match.count ? Math.round((match.sponsoredCount / match.count) * 100) : 0;
  const presence = perRetailer.map((s) => {
    const b = s.brands.find((x) => x.brand === match.brand);
    return {
      label: RETAILER_META[s.retailer].label,
      share: b ? Math.round(b.share * 100) : 0,
      present: !!b,
      leader: s.brands[0]?.brand,
    };
  });
  const present = presence.filter((p) => p.present).sort((a, b) => b.share - a.share);
  const absent = presence.filter((p) => !p.present);
  const multi = perRetailer.length >= 2;
  const top = present[0];
  const topShare = top?.share ?? 0;

  // 1. Barely on the shelf — the honest "ghost" read. Never call a tiny share
  //    "strong"; the absence of presence IS the insight for a small brand.
  if (match.count <= 2 || topShare < 10) {
    return {
      pattern: "skew-absent",
      headline: `${match.brand} is barely on this shelf`,
      detail: top
        ? `Just ${match.count} page-one spot${match.count === 1 ? "" : "s"} — a thin ${topShare}% on ${top.label}${absent.length ? `, nothing on ${absent.map((a) => a.label).join(" or ")}` : ""}. The leaders each hold far more.`
        : `${match.brand} barely registers on page one — the leaders own this shelf.`,
    };
  }

  // 2. Real presence on one retailer, but absent on another — the cross-retailer
  //    "I didn't know that" (only fires when the present share is genuinely high).
  if (multi && absent.length > 0 && topShare >= 15) {
    const miss = absent[0];
    return {
      pattern: "skew-absent",
      headline: `${match.brand} owns ${top.label} — but is invisible on ${miss.label}`,
      detail: `${topShare}% of ${top.label}'s page one, zero on ${miss.label}${miss.leader ? ` — open shelf for ${miss.leader}` : ""}. A different game at every retailer.`,
    };
  }

  // 3. Visibility concentrated on one retailer (present on several, lopsided).
  if (
    multi &&
    present.length >= 2 &&
    topShare - present[present.length - 1].share >= 12 &&
    topShare >= present[present.length - 1].share * 2
  ) {
    const weak = present[present.length - 1];
    return {
      pattern: "concentrated",
      headline: `${match.brand}'s visibility leans on ${top.label}`,
      detail: `${topShare}% on ${top.label} vs just ${weak.share}% on ${weak.label} — concentrated in one retailer, exposed if it slips there.`,
    };
  }

  // 4. The position is rented (paid-reliant).
  if (match.count >= 4 && paidPct >= 50) {
    return {
      pattern: "paid-reliant",
      headline: `${match.brand}'s shelf is rented, not owned`,
      detail: `${paidPct}% of its page-one placements are paid ads — cut the spend and the position moves.`,
    };
  }

  // 5. Earns its place organically.
  if (match.count >= 4 && paidPct <= 20) {
    return {
      pattern: "organic-led",
      headline: `${match.brand} earns its shelf — without paying for it`,
      detail: `${100 - paidPct}% of its placements are organic. It wins on merit, but a competitor with budget could outspend it.`,
    };
  }

  // 6. Specific fallback — rank + the gap + its strongest retailer. NEVER a vague
  //    "balanced / no weak spot" line.
  if (ctx.isLeader) {
    return {
      pattern: "balanced",
      headline: `${match.brand} leads this shelf — and it's not close`,
      detail: `#1 at ${Math.round(match.share * 100)}% of page one${ctx.runnerUp ? `, ${ctx.gap} pts clear of ${ctx.runnerUp}` : ""}. Strongest on ${top.label} (${topShare}%).`,
    };
  }
  return {
    pattern: "balanced",
    headline: `${match.brand} is the challenger — strongest on ${top.label}`,
    detail: `#${ctx.rank} of ${ctx.total}, ${ctx.gap} pts behind ${ctx.leaderBrand}. ${top.label} (${topShare}%) is where it's most visible — the shelf to defend first.`,
  };
}
