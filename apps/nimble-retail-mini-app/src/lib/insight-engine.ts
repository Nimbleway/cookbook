import type {
  BrandShare,
  InsightCard,
  InsightPayload,
  InsightTone,
  Kpi,
  RetailerId,
  RetailerResult,
  RetailerSerpResult,
  RetailerSummary,
  RightNowFact,
  VerdictCard,
  RetailerDifference,
  CrossRetailerMatrix,
  CrossMetricRow,
  Finding,
  FindingKind,
  PaidOrganic,
  BrandDependence,
} from "./types";
import { RETAILER_META } from "./retailers";
import { resolveCategoryLabel } from "./mock-data";
import { canonicalizeBrand } from "./brand-normalize";

// ─── Rule-based insight engine ──────────────────────────────────────────────
// Runs synchronously the moment normalized data arrives. No AI in this path —
// Claude summaries are layered on asynchronously elsewhere. Built to tolerate
// PARTIAL data: it computes from whatever retailers succeeded.

function pct(n: number, d: number): number {
  return d === 0 ? 0 : Math.round((n / d) * 100);
}

// ─── Pack-size normalization ────────────────────────────────────────────────
// A shelf mixes singles and multipacks (a Red Bull can vs a 24-pack), so raw
// price is apples-to-oranges. We pull the pack count out of the product title
// ("16oz, 15pk" → 15, "12ct" → 12) and compare price PER ITEM instead. Falls
// back to 1 (treat as a single) when no pack is stated — never wrong, just
// un-normalized. This keeps every cross-retailer price claim like-for-like.
export function packCount(title: string): number {
  const m = title.match(
    /(\d+)\s*[-\s]?\s*(?:pk\b|packs?\b|ct\b|count\b|cans?\b|bottles?\b|bars?\b|pods?\b|pouches?\b|pieces?\b|cups?\b|boxes?\b)/i,
  );
  if (m) {
    const n = parseInt(m[1], 10);
    if (Number.isFinite(n) && n >= 1 && n <= 1000) return n;
  }
  return 1;
}

// Median — the robust central price. We use it instead of the mean for every
// per-unit price claim because a single un-normalized bulk/case listing (e.g. a
// 12-box case of cereal at $58) skews the mean wildly but barely moves the
// median. This is the main data-quality guard against a fake "X is pricier".
export function median(nums: number[]): number | null {
  if (!nums.length) return null;
  const s = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

// Price for a single item (can / bar / bottle / count), pack-adjusted. Null when
// there's no usable price. Unit is always "per item" so values are comparable
// across products and retailers.
export function perItemPrice(
  row: { price?: number; productTitle: string },
): number | null {
  if (typeof row.price !== "number" || row.price <= 0) return null;
  return row.price / packCount(row.productTitle);
}

function computeBrandShare(rows: RetailerSerpResult[]): BrandShare[] {
  const map = new Map<string, BrandShare>();
  for (const r of rows) {
    const cur =
      map.get(r.brand) ??
      ({
        brand: r.brand,
        count: 0,
        sponsoredCount: 0,
        organicCount: 0,
        share: 0,
        avgRank: 0,
      } as BrandShare);
    cur.count += 1;
    if (r.sponsored) cur.sponsoredCount += 1;
    else cur.organicCount += 1;
    cur.avgRank += r.rank;
    map.set(r.brand, cur);
  }
  const total = rows.length;
  const shares = [...map.values()].map((b) => ({
    ...b,
    avgRank: Math.round((b.avgRank / b.count) * 10) / 10,
    share: total === 0 ? 0 : b.count / total,
  }));
  return shares.sort((a, b) => b.count - a.count);
}

function summarizeRetailer(
  retailer: RetailerId,
  rows: RetailerSerpResult[],
): RetailerSummary {
  const brands = computeBrandShare(rows);
  const sponsored = rows.filter((r) => r.sponsored).length;
  return {
    retailer,
    totalResults: rows.length,
    sponsoredPct: pct(sponsored, rows.length),
    topBrand: brands[0]?.brand ?? "—",
    brands,
  };
}

// Herfindahl-style concentration → "competitive intensity" (0 fragmented .. 100 concentrated)
function concentration(brands: BrandShare[]): number {
  const hhi = brands.reduce((acc, b) => acc + b.share * b.share, 0);
  return Math.round(hhi * 100);
}

export function buildInsights(
  keyword: string,
  retailerResults: RetailerResult[],
): InsightPayload {
  const ok = retailerResults.filter(
    (r): r is Extract<RetailerResult, { status: "ok" }> => r.status === "ok",
  );
  const failedRetailers = retailerResults
    .filter((r) => r.status === "error")
    .map((r) => r.retailer);

  // Roll product sub-lines up to a canonical brand for ALL strategic metrics
  // (share, verdicts, threat/opportunity, run-my-brand, cross-retailer). The
  // raw brand/product line is preserved on `brandRaw`/`productTitle` for the
  // raw-shelf table. Conservative — see brand-normalize.ts.
  const allRows = ok
    .flatMap((r) => r.results)
    .map((r) => {
      const c = canonicalizeBrand(r.brand, r.productTitle).brand;
      return c && c !== r.brand ? { ...r, brand: c, brandRaw: r.brand } : r;
    });
  const retailers = ok.map((r) => r.retailer);
  const categoryLabel = resolveCategoryLabel(keyword);

  const brandShare = computeBrandShare(allRows);
  // Per-retailer summaries must use the CANONICAL rows too, or cross-retailer
  // leaders/topBrand would compare un-normalized sub-lines.
  const perRetailer = retailers.map((rt) =>
    summarizeRetailer(rt, allRows.filter((r) => r.retailer === rt)),
  );

  const leader = brandShare[0];
  const totalSponsored = allRows.filter((r) => r.sponsored).length;
  const sponsoredPct = pct(totalSponsored, allRows.length);

  // Organic leader = most page-one placements that are NOT sponsored.
  const organicLeader = [...brandShare].sort(
    (a, b) => b.organicCount - a.organicCount,
  )[0];
  // Paid leader = most sponsored placements.
  const paidLeader = [...brandShare].sort(
    (a, b) => b.sponsoredCount - a.sponsoredCount,
  )[0];

  const intensity = concentration(brandShare);
  // Opportunity score: high when the shelf is fragmented & sponsored share is
  // low (room to win organically). 0..100.
  const opportunityScore = Math.max(
    0,
    Math.min(100, Math.round(100 - intensity * 0.7 - sponsoredPct * 0.3)),
  );

  // ── Hero insight ──────────────────────────────────────────────────────────
  // Lead with the single most DOMINANT brand-on-retailer fact — that peak number
  // is the "wow". A diluted cross-retailer average undersells the moment.
  const leaderShare = leader ? Math.round(leader.share * 100) : 0;
  const peak = perRetailer
    .map((s) => ({
      retailer: s.retailer,
      brand: s.brands[0]?.brand,
      share: s.brands[0]?.share ?? 0,
    }))
    .filter((p) => p.brand)
    .sort((a, b) => b.share - a.share)[0];

  const multi = retailers.length > 1;
  const peakPct = peak ? Math.round(peak.share * 100) : 0;
  const heroInsight = peak
    ? {
        question: `Who owns the ${categoryLabel.toLowerCase()} shelf right now?`,
        brand: peak.brand,
        share: peakPct,
        retailerLabel: RETAILER_META[peak.retailer].label,
        answer: multi
          ? `${peak.brand} owns ${peakPct}% of ${RETAILER_META[peak.retailer].label}'s ${categoryLabel.toLowerCase()} shelf — the most dominant position across all ${retailers.length} retailers.`
          : `${peak.brand} owns ${peakPct}% of ${RETAILER_META[peak.retailer].label}'s ${categoryLabel.toLowerCase()} shelf.`,
        tone: "positive" as InsightTone,
      }
    : {
        question: `Who owns the ${categoryLabel.toLowerCase()} shelf right now?`,
        brand: leader?.brand ?? "—",
        share: leaderShare,
        answer: "No results returned.",
        tone: "neutral" as InsightTone,
      };

  // ── KPI row ─────────────────────────────────────────────────────────────
  const kpis: Kpi[] = [
    {
      id: "visibility-leader",
      label: "Visibility Leader",
      value: leader?.brand ?? "—",
      sub: `${leaderShare}% of page one`,
      tone: "positive",
    },
    {
      id: "sponsored-pct",
      label: "Sponsored %",
      value: `${sponsoredPct}%`,
      sub: "of page-one slots are paid",
      tone: sponsoredPct >= 40 ? "warning" : "neutral",
    },
    {
      id: "organic-leader",
      label: "Organic Leader",
      value: organicLeader?.brand ?? "—",
      sub: `${organicLeader?.organicCount ?? 0} organic placements`,
      tone: "neutral",
    },
    {
      id: "share-of-shelf",
      label: "Top Share of Shelf",
      value: `${leaderShare}%`,
      sub: leader?.brand ?? "—",
      tone: "neutral",
    },
  ];

  // ── Actionable insight cards (what / why / what to do) ──────────────────────
  const cards: InsightCard[] = [];

  if (leader) {
    cards.push({
      id: "visibility",
      title: "Visibility Leader",
      what: `${leader.brand} holds ${leaderShare}% of page-one slots (${leader.count} of ${allRows.length}), avg rank ${leader.avgRank}.`,
      why: "Page-one share is the single best proxy for digital shelf dominance — shoppers rarely scroll past it.",
      action:
        leaderShare >= 35
          ? `To challenge ${leader.brand}, target the keywords where it ranks weakest before going head-to-head.`
          : `The shelf is contestable — a focused sponsored push could take the lead.`,
      tone: "positive",
      retailer: "cross",
    });
  }

  cards.push({
    id: "sponsored",
    title: "Sponsored vs Organic",
    what: `${sponsoredPct}% of page-one placements are sponsored. Paid leader: ${paidLeader?.brand ?? "—"} (${paidLeader?.sponsoredCount ?? 0} ads).`,
    why:
      sponsoredPct >= 40
        ? "Heavy paid penetration means organic ranking alone won't win this shelf — you're paying to play."
        : "Relatively light paid pressure — organic optimization still moves the needle here.",
    action:
      sponsoredPct >= 40
        ? "Model a sponsored-product budget to defend top slots; organic-only will lose share."
        : "Prioritize content & review velocity to win organic slots cheaply before competitors escalate spend.",
    tone: sponsoredPct >= 40 ? "warning" : "neutral",
    retailer: "cross",
  });

  // ── Cross-retailer insights (highest value per the integration spec) ────────
  if (perRetailer.length >= 2) {
    // Most competitive (most concentrated) vs most fragmented shelf.
    const ranked = [...perRetailer]
      .map((s) => ({ s, conc: concentration(s.brands) }))
      .sort((a, b) => b.conc - a.conc);
    const mostConcentrated = ranked[0];
    const mostFragmented = ranked[ranked.length - 1];

    cards.push({
      id: "retailer-competitiveness",
      title: "Most Contestable Retailer",
      what: `${RETAILER_META[mostFragmented.s.retailer].label} has the most fragmented shelf (no single brand dominates), while ${RETAILER_META[mostConcentrated.s.retailer].label} is locked up by ${mostConcentrated.s.topBrand}.`,
      why: "Fragmented shelves are where a challenger brand can realistically win page-one share.",
      action: `Concentrate launch/ad spend on ${RETAILER_META[mostFragmented.s.retailer].label} first — fastest path to visible share.`,
      tone: "opportunity",
      retailer: "cross",
    });

    // Highest sponsored penetration retailer.
    const bySponsored = [...perRetailer].sort(
      (a, b) => b.sponsoredPct - a.sponsoredPct,
    );
    cards.push({
      id: "retailer-sponsored",
      title: "Where Paid Pressure Is Highest",
      what: `${RETAILER_META[bySponsored[0].retailer].label} shows the highest sponsored penetration at ${bySponsored[0].sponsoredPct}% vs ${RETAILER_META[bySponsored[bySponsored.length - 1].retailer].label} at ${bySponsored[bySponsored.length - 1].sponsoredPct}%.`,
      why: "Sponsored penetration signals how much competitors are willing to pay to own the shelf.",
      action: `Expect higher CPCs on ${RETAILER_META[bySponsored[0].retailer].label}; ${RETAILER_META[bySponsored[bySponsored.length - 1].retailer].label} may offer cheaper visibility per dollar.`,
      tone: "neutral",
      retailer: "cross",
    });

    // Brand that wins organically on one retailer but is absent/weak on another.
    const overIndex = findOverIndexedBrand(perRetailer);
    if (overIndex) {
      cards.push({
        id: "over-index",
        title: "Cross-Retailer Gap",
        what: `${overIndex.brand} owns ${overIndex.strongPct}% of ${RETAILER_META[overIndex.strong].label} but only ${overIndex.weakPct}% of ${RETAILER_META[overIndex.weak].label}.`,
        why: "A brand strong on one retailer but weak on another reveals an unguarded shelf — either an opportunity to attack or a gap to defend.",
        action: `If this is your brand, close the gap on ${RETAILER_META[overIndex.weak].label}. If it's a competitor, attack them there.`,
        tone: "opportunity",
        retailer: "cross",
      });
    }
  }

  // Competitive threat: #2 brand closing on the leader.
  if (brandShare.length >= 2 && leader) {
    const challenger = brandShare[1];
    const gap = leaderShare - Math.round(challenger.share * 100);
    cards.push({
      id: "threat",
      title: "Competitive Threat",
      what: `${challenger.brand} is the #2 brand at ${Math.round(challenger.share * 100)}% — ${gap} pts behind ${leader.brand}.`,
      why:
        gap <= 8
          ? "A tight gap means leadership could flip with a modest shift in spend or ranking."
          : "A comfortable lead today, but #2 brands often escalate spend to close ground.",
      action: "Track this gap weekly with Nimble — static reports would miss the inflection.",
      tone: gap <= 8 ? "warning" : "neutral",
      retailer: "cross",
    });
  }

  // ── Real-time signal insights (the live-data differentiator) ───────────────
  // Demand velocity — what's actually SELLING right now, vs shelf visibility.
  const topSelling = allRows
    .filter((r) => r.recentSales)
    .map((r) => ({
      brand: r.brand,
      productTitle: r.productTitle,
      retailer: r.retailer,
      recentSales: r.recentSales as string,
      salesValue: parseSales(r.recentSales),
      visibilityRank: r.rank,
      imageUrl: r.imageUrl,
      price: r.price,
      productUrl: r.productUrl,
    }))
    .sort((a, b) => b.salesValue - a.salesValue)
    .slice(0, 6);

  if (topSelling[0] && topSelling[0].visibilityRank >= 3) {
    const t = topSelling[0];
    cards.push({
      id: "demand-velocity",
      title: "Demand ≠ Visibility",
      what: `On ${RETAILER_META[t.retailer].label}, ${t.brand} sits at #${t.visibilityRank} on the shelf — yet it's the category's #1 mover with ${t.recentSales}.`,
      why: "Shelf rank shows who paid or optimized; sales velocity shows what shoppers actually buy. They often disagree.",
      action:
        "Only live data exposes this gap. Defend the SKUs that sell, not just the ones that rank.",
      tone: "opportunity",
      retailer: t.retailer,
    });
  }

  // Live stockouts — a rival's slot to take TODAY.
  const oos = allRows.filter((r) => r.inStock === false);
  if (oos.length > 0) {
    const notable = oos.sort((a, b) => a.rank - b.rank)[0];
    cards.push({
      id: "stockout",
      title: "Stockout Radar",
      what: `${oos.length} page-one product${oos.length === 1 ? " is" : "s are"} out of stock right now — including ${notable.brand} at #${notable.rank} on ${RETAILER_META[notable.retailer].label}.`,
      why: "An out-of-stock competitor on page one is demand with nowhere to go — and a slot you can take today.",
      action: `Bid up on ${RETAILER_META[notable.retailer].label} while ${notable.brand} is dark. A weekly report would never catch this window.`,
      tone: "opportunity",
      retailer: notable.retailer,
    });
  }

  // Deepest live discount.
  const discounts = allRows
    .filter((r) => r.originalPrice && r.price && r.originalPrice > r.price)
    .map((r) => ({
      r,
      pct: Math.round((1 - (r.price as number) / (r.originalPrice as number)) * 100),
    }))
    .sort((a, b) => b.pct - a.pct);
  if (discounts[0] && discounts[0].pct >= 12) {
    const { r, pct } = discounts[0];
    cards.push({
      id: "discount",
      title: "Live Price Move",
      what: `${r.brand} is ${pct}% off on ${RETAILER_META[r.retailer].label} right now — $${r.price?.toFixed(2)} (was $${r.originalPrice?.toFixed(2)}).`,
      why: "Retail prices change by the hour. A static report quotes a number that may already be wrong.",
      action: "Match or hold against this move now — pricing decisions need today's number, not last week's.",
      tone: "warning",
      retailer: r.retailer,
    });
  }

  // (The Amazon's-Choice "default buy" card was removed: the `badge` field is
  // never populated by the live agents, so the card could never fire.)

  // ── "What we see right now" — point-in-time facts from THIS pull only ──────
  // Strictly current-state: availability, promotions, paid penetration, leader
  // gap. No movement, trends, deltas, or comparisons to a prior pull — there is
  // no historical snapshot to compare against. Every fact is defensible.
  const rightNowFacts: RightNowFact[] = [];

  // Availability — products out of stock on page one right now.
  if (oos.length > 0) {
    const n = [...oos].sort((a, b) => a.rank - b.rank)[0];
    rightNowFacts.push({
      id: "now-availability",
      kind: "availability",
      label: "Availability",
      value: `${oos.length} page-one product${oos.length === 1 ? "" : "s"} out of stock`,
      detail: `${n.brand} at #${n.rank} on ${RETAILER_META[n.retailer].label}`,
      tone: "opportunity",
    });
  }

  // Promotions — share of page one on promo right now + depth.
  const promoRows = allRows.filter(
    (r) => r.originalPrice && r.price && r.originalPrice > r.price,
  );
  if (promoRows.length > 0 && allRows.length > 0) {
    const sharePct = Math.round((promoRows.length / allRows.length) * 100);
    const depths = promoRows.map(
      (r) => 1 - (r.price as number) / (r.originalPrice as number),
    );
    const avgDepth = Math.round(
      (depths.reduce((a, b) => a + b, 0) / depths.length) * 100,
    );
    const deepest = discounts[0];
    rightNowFacts.push({
      id: "now-promo",
      kind: "promo",
      label: "Promotions",
      value: `${sharePct}% of page one on promo · avg ${avgDepth}% off`,
      detail:
        deepest && deepest.pct >= 8
          ? `deepest: ${deepest.r.brand} ${deepest.pct}% off on ${RETAILER_META[deepest.r.retailer].label}`
          : undefined,
      tone: "warning",
    });
  }

  // Paid penetration — share of page one that is sponsored right now.
  if (allRows.length > 0) {
    const sponsoredCount = allRows.filter((r) => r.sponsored).length;
    const sponsoredPct = Math.round((sponsoredCount / allRows.length) * 100);
    const sponRetailer = [...perRetailer].sort(
      (a, b) => b.sponsoredPct - a.sponsoredPct,
    )[0];
    rightNowFacts.push({
      id: "now-sponsored",
      kind: "sponsored",
      label: "Paid penetration",
      value: `${sponsoredPct}% of page one is paid placement`,
      detail: sponRetailer
        ? `heaviest on ${RETAILER_META[sponRetailer.retailer].label} (${sponRetailer.sponsoredPct}%)`
        : undefined,
      tone: sponsoredPct >= 40 ? "warning" : "neutral",
    });
  }

  // Leader gap — how far #1 leads #2 right now (no movement implied).
  if (brandShare[0] && brandShare[1]) {
    const gap = Math.round((brandShare[0].share - brandShare[1].share) * 100);
    rightNowFacts.push({
      id: "now-leader",
      kind: "leader",
      label: "Leader gap",
      value: `${brandShare[0].brand} leads by ${gap} pt${gap === 1 ? "" : "s"}`,
      detail: `${Math.round(brandShare[0].share * 100)}% vs ${brandShare[1].brand} ${Math.round(brandShare[1].share * 100)}%`,
      tone: "positive",
    });
  }

  const rightNow = { facts: rightNowFacts.slice(0, 4) };

  // ── Cross-retailer price gap (same brand, priced differently right now) ─────
  // PACK-ADJUSTED: compares price PER ITEM, not raw shelf price, so a 24-pack on
  // one retailer vs a single on another can't manufacture a fake "X% cheaper"
  // claim. `price` here is the per-item price. Reused by the Pricing verdict and
  // the divergence engine.
  const priceGap = (() => {
    const seen = new Set<string>();
    const candidates = [leader?.brand, ...brandShare.map((b) => b.brand)].filter(
      (b): b is string => Boolean(b),
    );
    for (const brand of candidates) {
      if (seen.has(brand)) continue;
      seen.add(brand);
      const byR = retailers
        .map((rt) => {
          const perItem = allRows
            .filter((r) => r.retailer === rt && r.brand === brand)
            .map(perItemPrice)
            .filter((p): p is number => p !== null);
          const med = median(perItem); // robust to outlier multipacks
          if (med === null) return null;
          return { retailer: rt, price: med };
        })
        .filter((x): x is { retailer: RetailerId; price: number } => x !== null);
      if (byR.length >= 2) {
        const lo = byR.reduce((a, b) => (a.price < b.price ? a : b));
        const hi = byR.reduce((a, b) => (a.price > b.price ? a : b));
        const spread = Math.round((1 - lo.price / hi.price) * 100);
        if (spread >= 5) return { brand, lo, hi, spread };
      }
    }
    return null;
  })();

  // ── Executive Verdict — Winner · Opportunity · Threat · Pricing · Availability
  // Every card answers what / why / next. Deterministic, current-pull only.
  const verdicts: VerdictCard[] = [];

  if (leader && peak) {
    verdicts.push({
      id: "v-winner",
      kind: "winner",
      label: "Biggest Winner",
      headline: `${leader.brand} owns the shelf`,
      what: `${leader.brand} holds ${leaderShare}% of page one, peaking at ${peakPct}% on ${RETAILER_META[peak.retailer].label}.`,
      why: "It's the default consideration set — the visibility every competitor has to convert against.",
      action: `Benchmark your assortment, price, and content against ${leader.brand} on ${RETAILER_META[peak.retailer].label} first.`,
      retailer: peak.retailer,
      tone: "positive",
    });
  }

  const openRetailer = [...perRetailer]
    .filter((s) => s.brands[0])
    .sort((a, b) => a.brands[0].share - b.brands[0].share)[0];
  if (multi && openRetailer) {
    const topPct = Math.round(openRetailer.brands[0].share * 100);
    verdicts.push({
      id: "v-opp",
      kind: "opportunity",
      label: "Biggest Opportunity",
      headline: `${RETAILER_META[openRetailer.retailer].label} is the most open shelf`,
      what: `On ${RETAILER_META[openRetailer.retailer].label} the top brand holds only ${topPct}% — the least concentrated of the ${retailers.length} shelves.`,
      why: "Fragmented shelves are the cheapest to climb — there's no entrenched leader to outspend.",
      action: `Prioritize ${RETAILER_META[openRetailer.retailer].label} for organic + sponsored gains while the shelf is still up for grabs.`,
      retailer: openRetailer.retailer,
      tone: "opportunity",
    });
  } else {
    verdicts.push({
      id: "v-opp",
      kind: "opportunity",
      label: "Biggest Opportunity",
      headline: opportunityScore >= 60 ? "This shelf is winnable" : "This shelf is concentrated",
      what:
        opportunityScore >= 60
          ? "The shelf is fragmented — no single brand runs away with it, so there's room to win organically."
          : "A few brands dominate this shelf, so winning means displacing an entrenched leader.",
      why:
        opportunityScore >= 60
          ? "Low concentration and modest paid pressure mean organic gains are achievable."
          : "High concentration means winning requires displacing an entrenched leader.",
      action:
        opportunityScore >= 60
          ? "Invest in content and organic rank — this shelf rewards it."
          : "Pick one beachhead SKU on one retailer rather than spreading thin.",
      tone: "opportunity",
    });
  }

  if (brandShare[1] && brandShare[0]) {
    const c = brandShare[1];
    const gap = Math.round((brandShare[0].share - c.share) * 100);
    const heavierPaid = c.sponsoredCount > brandShare[0].sponsoredCount;
    verdicts.push({
      id: "v-threat",
      kind: "threat",
      label: "Biggest Threat",
      headline: `${c.brand} is closing in`,
      what: `${c.brand} is #2 at ${Math.round(c.share * 100)}% — ${gap} pt${gap === 1 ? "" : "s"} behind ${brandShare[0].brand}${heavierPaid ? ", and running more paid placements" : ""}.`,
      why: "A close, well-funded #2 can flip leadership with a modest shift in spend.",
      action: `Track ${c.brand}'s sponsored slots and defend the rank of your top-selling SKUs.`,
      tone: "warning",
    });
  }

  if (priceGap) {
    verdicts.push({
      id: "v-pricing",
      kind: "pricing",
      label: "Pricing Watchout",
      headline: `${priceGap.brand} is ${priceGap.spread}% cheaper per unit on ${RETAILER_META[priceGap.lo.retailer].label}`,
      what: `Pack-adjusted, ${priceGap.brand} runs $${priceGap.lo.price.toFixed(2)}/unit on ${RETAILER_META[priceGap.lo.retailer].label} vs $${priceGap.hi.price.toFixed(2)}/unit on ${RETAILER_META[priceGap.hi.retailer].label} right now — a ${priceGap.spread}% gap on the same item, not a pack-size mirage.`,
      why: "Cross-retailer price gaps are channel conflict and margin leakage — and they move by the hour.",
      action: "Audit your own cross-retailer price consistency today; a weekly report quotes one number that's already wrong on another shelf.",
      retailer: priceGap.lo.retailer,
      tone: "warning",
    });
  } else if (discounts[0] && discounts[0].pct >= 10) {
    const { r, pct: p } = discounts[0];
    verdicts.push({
      id: "v-pricing",
      kind: "pricing",
      label: "Pricing Watchout",
      headline: `${r.brand} is ${p}% off right now`,
      what: `${r.brand} is ${p}% off on ${RETAILER_META[r.retailer].label} — $${r.price?.toFixed(2)} (was $${r.originalPrice?.toFixed(2)}).`,
      why: "Live promotions move the price you're competing against by the hour.",
      action: "Decide whether to match or hold using today's number, not last week's.",
      retailer: r.retailer,
      tone: "warning",
    });
  }

  if (oos.length > 0) {
    const n = [...oos].sort((a, b) => a.rank - b.rank)[0];
    verdicts.push({
      id: "v-avail",
      kind: "availability",
      label: "Availability Watchout",
      headline: `${oos.length} out of stock on page one`,
      what: `${oos.length} page-one product${oos.length === 1 ? " is" : "s are"} out of stock right now — including ${n.brand} at #${n.rank} on ${RETAILER_META[n.retailer].label}.`,
      why: "An out-of-stock product on page one is demand with nowhere to go — capturable today.",
      action: "If it's a rival, push visibility while they're dark; if it's yours, escalate replenishment now.",
      retailer: n.retailer,
      tone: "opportunity",
    });
  } else {
    verdicts.push({
      id: "v-avail",
      kind: "availability",
      label: "Availability Watchout",
      headline: "Page one is fully in stock",
      what: `Every page-one product is in stock right now${multi ? ` across all ${retailers.length} retailers` : ""}.`,
      why: "No availability gaps to exploit — and none exposing you, either.",
      action: "Compete on price, content, and paid visibility; re-check availability on your next pull.",
      tone: "positive",
    });
  }

  // ── What changes across retailers — divergence engine (most surprising first)
  const crossRetailer: RetailerDifference[] = [];
  if (retailers.length >= 2) {
    // Data-trust guard: a retailer that returned too few products gives noisy
    // percentages and an unreliable "leader", so we exclude it from divergence
    // claims rather than surface a number we can't stand behind.
    const MIN_RELIABLE = 6;
    const reliable = perRetailer.filter((s) => s.totalResults >= MIN_RELIABLE);
    const leaders = reliable
      .map((s) => ({ r: s.retailer, brand: s.brands[0]?.brand }))
      .filter((x): x is { r: RetailerId; brand: string } => Boolean(x.brand));
    const uniqueLeaders = new Set(leaders.map((l) => l.brand));
    if (uniqueLeaders.size > 1) {
      crossRetailer.push({
        id: "d-leaders",
        kind: "leaders",
        label: "Different leaders",
        headline:
          uniqueLeaders.size === leaders.length
            ? "A different brand leads each shelf"
            : "The category leader flips by retailer",
        detail: leaders.map((l) => `${RETAILER_META[l.r].label} → ${l.brand}`).join("  ·  "),
        magnitude: uniqueLeaders.size === leaders.length ? 0.95 : 0.78,
        tone: "opportunity",
      });
    }

    if (priceGap) {
      crossRetailer.push({
        id: "d-price",
        kind: "price",
        label: "Different prices",
        headline: `${priceGap.brand} costs ${priceGap.spread}% more per unit on ${RETAILER_META[priceGap.hi.retailer].label} than ${RETAILER_META[priceGap.lo.retailer].label}`,
        detail: `$${priceGap.lo.price.toFixed(2)} vs $${priceGap.hi.price.toFixed(2)} per unit — pack-adjusted`,
        magnitude: Math.min(priceGap.spread / 30, 1) * 0.9,
        tone: "warning",
      });
    }

    const sp = reliable
      .map((s) => ({ r: s.retailer, pct: s.sponsoredPct }))
      .sort((a, b) => b.pct - a.pct);
    if (sp.length >= 2 && sp[0].pct - sp[sp.length - 1].pct >= 8) {
      const hi = sp[0];
      const lo = sp[sp.length - 1];
      crossRetailer.push({
        id: "d-spon",
        kind: "sponsored",
        label: "Different ad pressure",
        // Lead with the RELATIVE read (robust), numbers as support — exact
        // sponsored counts vary by how each retailer flags ads.
        headline: `Paid placement is far heavier on ${RETAILER_META[hi.r].label} than ${RETAILER_META[lo.r].label}`,
        detail: `${hi.pct}% of ${RETAILER_META[hi.r].label}'s shelf is paid vs ${lo.pct}% on ${RETAILER_META[lo.r].label}`,
        magnitude: Math.min((hi.pct - lo.pct) / 50, 1) * 0.7,
        tone: "neutral",
      });
    }

    const oosByR = reliable
      .map((s) => ({
        r: s.retailer,
        n: allRows.filter((x) => x.retailer === s.retailer && x.inStock === false).length,
      }))
      .sort((a, b) => b.n - a.n);
    if (oosByR[0] && oosByR[0].n > 0 && oosByR[0].n !== oosByR[oosByR.length - 1].n) {
      const hi = oosByR[0];
      const lo = oosByR[oosByR.length - 1];
      crossRetailer.push({
        id: "d-avail",
        kind: "availability",
        label: "Different availability",
        headline: `${hi.n} out of stock on ${RETAILER_META[hi.r].label}, ${lo.n === 0 ? "none" : lo.n} on ${RETAILER_META[lo.r].label}`,
        magnitude: 0.55,
        tone: "opportunity",
      });
    }

    const promoByR = reliable
      .map((s) => {
        const rows = allRows.filter((x) => x.retailer === s.retailer);
        const promo = rows.filter(
          (x) => x.originalPrice && x.price && x.originalPrice > x.price,
        ).length;
        return { r: s.retailer, pct: rows.length ? Math.round((promo / rows.length) * 100) : 0 };
      })
      .sort((a, b) => b.pct - a.pct);
    if (promoByR.length >= 2 && promoByR[0].pct - promoByR[promoByR.length - 1].pct >= 10) {
      const hi = promoByR[0];
      const lo = promoByR[promoByR.length - 1];
      crossRetailer.push({
        id: "d-promo",
        kind: "promo",
        label: "Different promotions",
        headline: `${hi.pct}% of ${RETAILER_META[hi.r].label}'s shelf is on promo vs ${lo.pct}% on ${RETAILER_META[lo.r].label}`,
        magnitude: Math.min((hi.pct - lo.pct) / 50, 1) * 0.5,
        tone: "warning",
      });
    }

    crossRetailer.sort((a, b) => b.magnitude - a.magnitude);
  }

  // ── Cross-retailer matrix — the same metrics laid side-by-side per retailer.
  // Pure reformat of the data already computed above; `diverges` flags the rows
  // worth highlighting (a single-retailer report can't produce this view).
  const crossRetailerMatrix: CrossRetailerMatrix = (() => {
    const rows: CrossMetricRow[] = [];
    if (retailers.length < 2) return { retailers, rows };

    // Leader per shelf.
    const leaderVals: Partial<Record<RetailerId, string>> = {};
    perRetailer.forEach((s) => {
      leaderVals[s.retailer] = s.brands[0]?.brand ?? "—";
    });
    const uniqueLeaders = new Set(
      perRetailer.map((s) => s.brands[0]?.brand).filter(Boolean),
    );
    rows.push({
      id: "leader",
      label: "Leader",
      values: leaderVals,
      diverges: uniqueLeaders.size > 1,
      note: uniqueLeaders.size > 1 ? `${uniqueLeaders.size} different #1 brands` : undefined,
    });

    // Avg price PER UNIT (pack-adjusted) — comparing raw shelf price across
    // retailers is meaningless when one stocks singles and another multipacks.
    const priceByR = retailers.map((rt) => {
      const ps = allRows
        .filter((r) => r.retailer === rt)
        .map(perItemPrice)
        .filter((p): p is number => p !== null);
      return { rt, avg: median(ps) }; // median, not mean — outlier-proof
    });
    const priced = priceByR.filter(
      (x): x is { rt: RetailerId; avg: number } => x.avg !== null,
    );
    if (priced.length >= 2) {
      const vals: Partial<Record<RetailerId, string>> = {};
      priceByR.forEach((x) => {
        if (x.avg !== null) vals[x.rt] = `$${x.avg.toFixed(2)}`;
      });
      const lo = Math.min(...priced.map((p) => p.avg));
      const hi = Math.max(...priced.map((p) => p.avg));
      const spread = hi > 0 ? Math.round((1 - lo / hi) * 100) : 0;
      const cheapest = priced.reduce((a, b) => (b.avg < a.avg ? b : a));
      rows.push({
        id: "avgPrice",
        label: "Price / unit",
        values: vals,
        diverges: spread >= 5,
        note: spread >= 5 ? `${spread}% cheaper on ${RETAILER_META[cheapest.rt].label}` : undefined,
      });
    }

    // Sponsored penetration.
    const sponVals: Partial<Record<RetailerId, string>> = {};
    perRetailer.forEach((s) => {
      sponVals[s.retailer] = `${s.sponsoredPct}%`;
    });
    const sponNums = perRetailer.map((s) => s.sponsoredPct);
    const sponGap = Math.max(...sponNums) - Math.min(...sponNums);
    const topSpon = perRetailer.reduce((a, b) => (b.sponsoredPct > a.sponsoredPct ? b : a));
    rows.push({
      id: "sponsored",
      label: "Sponsored",
      values: sponVals,
      diverges: sponGap >= 8,
      note: sponGap >= 8 ? `most ads on ${RETAILER_META[topSpon.retailer].label}` : undefined,
    });

    // (Out-of-stock row intentionally omitted — availability is Walmart-only in
    // practice, so it was a mostly-"—", low-signal row that added height without
    // insight. The stockout signal still lives in the dedicated modules.)

    // On promo — only when discounting is present on this pull.
    if (allRows.some((r) => r.originalPrice && r.price && r.originalPrice > r.price)) {
      const promoVals: Partial<Record<RetailerId, string>> = {};
      const nums = retailers.map((rt) => {
        const rrows = allRows.filter((r) => r.retailer === rt);
        const promo = rrows.filter(
          (r) => r.originalPrice && r.price && r.originalPrice > r.price,
        ).length;
        const p = rrows.length ? Math.round((promo / rrows.length) * 100) : 0;
        promoVals[rt] = `${p}%`;
        return p;
      });
      const gap = Math.max(...nums) - Math.min(...nums);
      const topPromoR = retailers[nums.indexOf(Math.max(...nums))];
      rows.push({
        id: "promo",
        label: "On promo",
        values: promoVals,
        diverges: gap >= 10,
        note: gap >= 10 ? `most discounting on ${RETAILER_META[topPromoR].label}` : undefined,
      });
    }

    return { retailers, rows };
  })();

  // ── Paid vs Organic — "earned vs bought" (deterministic; Claude may enrich) ─
  const paidOrganic = buildPaidOrganic(
    brandShare,
    perRetailer,
    sponsoredPct,
    organicLeader,
    paidLeader,
  );

  // ── "3 things we found" — the most SURPRISING signals, plain voice ──────────
  // Re-ranks the signals already computed above; no new data. Leads with the
  // cross-retailer surprise (the centerpiece), then mixes in non-cross surprises
  // (demand≠visibility, stockouts, live price moves) for variety. Each answers
  // "why is this interesting?" — never "what to do."
  const findings: Finding[] = (() => {
    const crossWhy: Record<string, string> = {
      leaders:
        "So a national share number hides the truth — you can lead one shelf and be invisible on the next. Win them one at a time.",
      price:
        "So your price and promo guardrails are leaking across channels — someone's beating you per unit on a shelf you're not watching.",
      sponsored:
        "So a paid budget that pays off on one retailer burns money on another — your media plan can't be one-size-fits-all.",
      availability:
        "So there's a rival's slot to take on one shelf today — and a gap to defend on another.",
      promo:
        "So a competitor is buying the deal-seekers on one shelf while you hold price on another. Decide if that's a choice.",
    };

    type Cand = { score: number; cross: boolean; f: Finding };
    const cands: Cand[] = [];

    // Cross-retailer divergences (the centerpiece surprise) — top 2 by magnitude.
    crossRetailer.slice(0, 2).forEach((d, i) => {
      cands.push({
        score: 0.95 - i * 0.12,
        cross: true,
        f: {
          id: `find-${d.id}`,
          kind: d.kind as FindingKind,
          headline: d.headline,
          why: crossWhy[d.kind] ?? d.detail ?? "",
          tone: d.tone,
        },
      });
    });

    // Demand ≠ visibility — what sells isn't what's most visible.
    const mover = topSelling[0];
    if (mover && mover.visibilityRank >= 3) {
      cands.push({
        score: 0.83,
        cross: false,
        f: {
          id: "find-demand",
          kind: "demand",
          headline: "What's selling isn't what's winning the shelf",
          why: `${mover.brand}'s top seller sits at #${mover.visibilityRank} on ${RETAILER_META[mover.retailer].label} yet outsells everything — so defend the SKUs that move units, not just the ones that rank.`,
          tone: "opportunity",
        },
      });
    }

    // Earned vs bought — a leader propped up by ads, or a clear organic winner.
    if (paidOrganic.dependence.length && paidOrganic.sponsoredPct > 0) {
      const topDep = paidOrganic.dependence[0]; // the visibility leader
      if (topDep.paidPct >= 45) {
        cands.push({
          score: 0.8,
          cross: false,
          f: {
            id: "find-paid",
            kind: "sponsored",
            headline: `${topDep.brand} looks dominant — but ${topDep.paidPct}% of its shelf is paid`,
            why: "So its lead is rented, not owned — cut the ad budget and the position moves. That's a very different competitive picture than it first looks.",
            tone: "warning",
          },
        });
      } else if (
        paidOrganic.organicLeader &&
        paidOrganic.paidLeader &&
        paidOrganic.organicLeader.brand !== paidOrganic.paidLeader.brand
      ) {
        cands.push({
          score: 0.7,
          cross: false,
          f: {
            id: "find-paid",
            kind: "sponsored",
            headline: `${paidOrganic.organicLeader.brand} earns the shelf; ${paidOrganic.paidLeader.brand} buys it`,
            why: "So two brands are winning two different ways — one on merit, one on budget. Know which game you're playing before you commit spend.",
            tone: "opportunity",
          },
        });
      }
    }

    // Live stockouts — empty slots on page one right now.
    if (oos.length > 0) {
      const n = [...oos].sort((a, b) => a.rank - b.rank)[0];
      cands.push({
        score: 0.62,
        cross: false,
        f: {
          id: "find-stockout",
          kind: "stockout",
          headline: `${oos.length} page-one product${oos.length === 1 ? " is" : "s are"} out of stock right now`,
          why: `${n.brand} is dark at #${n.rank} on ${RETAILER_META[n.retailer].label} — so that demand is up for grabs today: bid in if it's a rival, replenish fast if it's yours.`,
          tone: "opportunity",
        },
      });
    }

    // Live price move — a discount that a weekly report would miss.
    if (discounts[0] && discounts[0].pct >= 12) {
      const { r, pct: p } = discounts[0];
      cands.push({
        score: 0.55,
        cross: false,
        f: {
          id: "find-price",
          kind: "price",
          headline: `${r.brand} is ${p}% off on ${RETAILER_META[r.retailer].label} — right now`,
          why: "So the price you're competing against changed today — decide whether to match or hold on today's number, not last week's.",
          tone: "warning",
        },
      });
    }

    // Is the shelf winnable or locked up? (concentration → the Opportunity read)
    if (leader) {
      const leadPct = Math.round(leader.share * 100);
      if (intensity <= 20 && leadPct < 30) {
        cands.push({
          score: 0.6,
          cross: false,
          f: {
            id: "find-open",
            kind: "fragmentation",
            headline: "This shelf is up for grabs",
            why: `No one owns it — the leader holds just ${leadPct}% and ${brandShare.length} brands split page one. That's a cheap shelf to climb before someone else does.`,
            tone: "opportunity",
          },
        });
      } else if (intensity >= 45) {
        cands.push({
          score: 0.52,
          cross: false,
          f: {
            id: "find-locked",
            kind: "fragmentation",
            headline: `${leader.brand} has this shelf locked up`,
            why: `${leader.brand} holds ${leadPct}% of a highly concentrated shelf — winning here means displacing an entrenched leader, not finding open space.`,
            tone: "warning",
          },
        });
      }
    }

    // Fallback — sheer dominance, so we always have something to say.
    if (leader && peak) {
      cands.push({
        score: 0.4,
        cross: false,
        f: {
          id: "find-dominance",
          kind: "dominance",
          headline: `${peak.brand} owns ${peakPct}% of ${RETAILER_META[peak.retailer].label}`,
          why: "So everyone else is converting against the default shopper sees first — you're paying a visibility tax just to be considered.",
          tone: "positive",
        },
      });
    }

    // Sort by surprise, then prefer NON-cross signals: the dedicated
    // cross-retailer section right above already owns the divergence story, so
    // the "3 things" shouldn't repeat it. Top up with a cross divergence only
    // if we'd otherwise have fewer than 3.
    cands.sort((a, b) => b.score - a.score);
    const out: Finding[] = [];
    for (const c of cands) {
      if (out.length >= 3) break;
      if (!c.cross) out.push(c.f);
    }
    for (const c of cands) {
      if (out.length >= 3) break;
      if (c.cross && !out.includes(c.f)) out.push(c.f);
    }
    return out;
  })();

  // Prioritize signal cards near the top, then cap so it never feels like a
  // wall of charts. Real-time signals first — they're the differentiator.
  const priority = [
    "demand-velocity",
    "visibility",
    "stockout",
    "sponsored",
    "discount",
    "retailer-competitiveness",
    "over-index",
    "badge",
    "retailer-sponsored",
    "threat",
  ];
  const orderedCards = [...cards].sort(
    (a, b) =>
      (priority.indexOf(a.id) + 1 || 99) - (priority.indexOf(b.id) + 1 || 99),
  );

  return {
    keyword,
    collectedAt: allRows[0]?.collectedAt ?? new Date(0).toISOString(),
    retailers,
    failedRetailers,
    heroInsight,
    kpis,
    verdicts,
    findings,
    crossRetailer,
    crossRetailerMatrix,
    paidOrganic,
    cards: orderedCards.slice(0, 8),
    perRetailer,
    brandShare,
    topSelling,
    rightNow,
    results: allRows,
  };
}

function parseSales(s?: string): number {
  if (!s) return 0;
  const m = s.match(/([\d.]+)\s*([kKmM])?/);
  if (!m) return 0;
  let n = parseFloat(m[1]);
  if (/k/i.test(m[2] ?? "")) n *= 1000;
  if (/m/i.test(m[2] ?? "")) n *= 1_000_000;
  return n;
}

// ─── Paid vs Organic — "earned vs bought" ───────────────────────────────────
// Pure derivation from the sponsored flag (the most reliable cross-retailer
// signal). Produces the contrast leaders, per-brand paid dependence, the
// per-retailer pay-to-play strip, and deterministic verdict/soWhat strings that
// the UI shows immediately and Claude may later enrich.
function buildPaidOrganic(
  brandShare: BrandShare[],
  perRetailer: RetailerSummary[],
  sponsoredPct: number,
  organicLeader?: BrandShare,
  paidLeader?: BrandShare,
): PaidOrganic {
  const byRetailer = perRetailer.map((s) => ({
    retailer: s.retailer,
    sponsoredPct: s.sponsoredPct,
  }));

  // How much of each top brand's visibility is bought vs earned (need ≥2
  // placements for the ratio to mean anything).
  const dependence: BrandDependence[] = brandShare
    .filter((b) => b.count >= 2)
    .slice(0, 4)
    .map((b) => ({
      brand: b.brand,
      share: b.share,
      paidPct: Math.round((b.sponsoredCount / b.count) * 100),
      sponsoredCount: b.sponsoredCount,
      organicCount: b.organicCount,
    }));

  // Most efficient organic brand: earns the most slots with little/no ad help.
  const mostEfficientOrganic =
    [...brandShare]
      .filter((b) => b.organicCount >= 2 && b.count >= 2)
      .map((b) => ({
        brand: b.brand,
        organicCount: b.organicCount,
        paidPct: Math.round((b.sponsoredCount / b.count) * 100),
      }))
      .filter((b) => b.paidPct <= 25)
      .sort((a, b) => b.organicCount - a.organicCount)[0] ?? null;

  const oLead =
    organicLeader && organicLeader.organicCount > 0
      ? { brand: organicLeader.brand, organicCount: organicLeader.organicCount }
      : null;
  const pLead =
    paidLeader && paidLeader.sponsoredCount > 0
      ? { brand: paidLeader.brand, sponsoredCount: paidLeader.sponsoredCount }
      : null;

  // ── Deterministic verdict + soWhat (fallback when Claude is unavailable) ──
  const leader = brandShare[0];
  const leaderPaidPct =
    leader && leader.count
      ? Math.round((leader.sponsoredCount / leader.count) * 100)
      : 0;

  let verdict: string;
  if (sponsoredPct === 0) {
    verdict = leader
      ? `${leader.brand} owns this shelf on merit — there's almost no paid placement here.`
      : "This shelf is won organically — there's almost no paid placement here.";
  } else if (oLead && pLead && oLead.brand !== pLead.brand) {
    verdict = `${oLead.brand} earned the most shelf space. ${pLead.brand} bought the most.`;
  } else if (leader && leaderPaidPct >= 40) {
    verdict = `${leader.brand} looks like it owns the shelf — but ${leaderPaidPct}% of that visibility is paid.`;
  } else if (leader) {
    verdict = `${leader.brand} leads this shelf mostly on merit — ${100 - leaderPaidPct}% of its placements are organic.`;
  } else {
    verdict = "No clear leader on this shelf yet.";
  }

  const soWhat =
    sponsoredPct >= 40
      ? "Nearly half this shelf is pay-to-play — organic ranking alone won't hold the top slots."
      : sponsoredPct >= 20
        ? "Paid placement is real but not dominant — earned rank still moves the needle here."
        : "This shelf is still won organically — content and reviews beat ad budget for now.";

  return {
    organicLeader: oLead,
    paidLeader: pLead,
    sponsoredPct,
    byRetailer,
    dependence,
    mostEfficientOrganic,
    verdict,
    soWhat,
  };
}

function findOverIndexedBrand(summaries: RetailerSummary[]) {
  let best: {
    brand: string;
    strong: RetailerId;
    weak: RetailerId;
    strongPct: number;
    weakPct: number;
    spread: number;
  } | null = null;

  const brands = new Set<string>();
  summaries.forEach((s) => s.brands.forEach((b) => brands.add(b.brand)));

  for (const brand of brands) {
    const shares = summaries.map((s) => ({
      retailer: s.retailer,
      pct: Math.round(((s.brands.find((b) => b.brand === brand)?.share ?? 0) as number) * 100),
    }));
    const sorted = [...shares].sort((a, b) => b.pct - a.pct);
    const strong = sorted[0];
    const weak = sorted[sorted.length - 1];
    const spread = strong.pct - weak.pct;
    if (strong.pct >= 20 && spread >= 15 && (!best || spread > best.spread)) {
      best = {
        brand,
        strong: strong.retailer,
        weak: weak.retailer,
        strongPct: strong.pct,
        weakPct: weak.pct,
        spread,
      };
    }
  }
  return best;
}
