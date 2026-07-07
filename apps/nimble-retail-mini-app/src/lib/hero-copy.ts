import type { InsightPayload } from "./types";
import { analyzeBrand } from "./brand-analysis";
import { classifyIntent } from "./intent";

// ─── Intent-aware hero copy ─────────────────────────────────────────────────
// Produces the hero's eyebrow + headline + subline based on what the user
// searched (category / brand / keyword). Pure and deterministic; every value
// comes from the computed insights — missing data falls back to a static line,
// never a broken template or a fabricated number.

export type HeroCopy = { eyebrow: string; headline: string; subline: string };

const titleCase = (s: string) => s.replace(/\b\w/g, (c) => c.toUpperCase());

export function heroCopy(
  insights: InsightPayload,
  focusBrand?: string | null,
): HeroCopy {
  const category = titleCase(insights.keyword);

  // BRAND intent — a focus brand was searched/run, shown against its category.
  if (focusBrand) return brandHero(insights, focusBrand, category);

  // CATEGORY vs KEYWORD intent — from the query itself.
  const intent = classifyIntent(insights.keyword);
  if (intent.kind === "keyword") return keywordHero(insights, insights.keyword);
  return categoryHero(insights, category);
}

// ── Category: a COMPETITION signal — who owns the shelf right now ────────────
// Deliberately does NOT tell the divergence story — the cross-retailer section
// immediately below owns that ("the leader flips by retailer"). Leading with
// dominance here makes the first 60s a clean escalation: who owns it
// (Competition) → but they disagree (Difference) → and it's bought (Risk).
function categoryHero(insights: InsightPayload, category: string): HeroCopy {
  const h = insights.heroInsight; // peak dominance (brand shown in the big number)
  const leaderPct = insights.brandShare[0]
    ? Math.round(insights.brandShare[0].share * 100)
    : 0;
  const eyebrow = `Who owns ${category}?`;

  // Clear owner → state it plainly; the cross-retailer twist subverts it next.
  if (h.brand && h.brand !== "—" && h.share >= 22) {
    return {
      eyebrow,
      headline: `${h.brand} owns the ${category} shelf right now.`,
      subline: `The brand to beat across Amazon, Walmart & Target — pulled live, right now.`,
    };
  }

  // No clear owner — the fragmentation IS the signal (an open shelf).
  return {
    eyebrow,
    headline: `No single brand owns ${category} — the shelf is wide open.`,
    subline: `Even the most-visible brand holds just ${leaderPct}% across all three retailers — live, right now.`,
  };
}

// ── Brand: personal relevance — where you stand, where you don't ────────────
function brandHero(
  insights: InsightPayload,
  focusBrand: string,
  category: string,
): HeroCopy {
  const a = analyzeBrand(insights, focusBrand);
  const eyebrow = `How does ${titleCase(focusBrand.trim())} compare?`;

  if (!a) {
    return {
      eyebrow,
      headline: `Where does ${titleCase(focusBrand.trim())} stand on the ${category} shelf?`,
      subline: `Live across Amazon, Walmart & Target.`,
    };
  }

  if (!a.found) {
    const door = a.winnableRetailer
      ? ` ${a.winnableRetailer.label} is the cheapest door in.`
      : "";
    return {
      eyebrow,
      headline: `${a.brand} isn't on page one for ${category}. Here's who's taking the space.`,
      subline: `${a.leaderBrand} (${a.leaderPct}%)${a.secondBrand ? ` and ${a.secondBrand}` : ""} own the shelf ${a.brand} needs.${door}`,
    };
  }

  const headline = a.isLeader
    ? `${a.brand} owns the ${category} shelf — for now.`
    : `${a.brand} is #${a.rank} of ${a.total} on the ${category} shelf.`;
  const subline = a.isLeader
    ? `${a.score}/100 visibility · leading ${a.secondBrand ? `${a.secondBrand} by ${a.gap} pts` : "the shelf"}. The one move that protects it →`
    : `${a.score}/100 visibility · ${a.gap} pts behind ${a.leaderBrand}. The one move that closes it →`;
  return { eyebrow, headline, subline };
}

// ── Keyword: the shopper's point of view — a COMPETITION signal ─────────────
// Leads with who wins the shopper's first screen (the dominance fact the big
// number proves), then the paid FOMO. Does NOT tell the divergence story — the
// cross-retailer section right below owns "a different brand leads each shelf".
function keywordHero(insights: InsightPayload, keyword: string): HeroCopy {
  const h = insights.heroInsight; // peak brand shown in the big number
  const rows = insights.results;
  const sponsoredPct = rows.length
    ? Math.round((rows.filter((r) => r.sponsored).length / rows.length) * 100)
    : 0;
  const eyebrow = `What shoppers see for "${keyword}"`;

  const headline =
    h.brand && h.brand !== "—"
      ? `Search "${keyword}" — and ${h.brand} wins the first screen.`
      : `Search "${keyword}" — and no single brand wins the first screen.`;

  const subline =
    sponsoredPct > 0
      ? `${sponsoredPct}% of that first screen is paid placement — what wins attention isn't what wins the cart.`
      : `Pulled live across Amazon, Walmart & Target — what wins attention isn't always what wins the cart.`;

  return { eyebrow, headline, subline };
}

