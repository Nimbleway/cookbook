import { CATEGORIES, CANONICAL_BRANDS } from "./mock-data";
import { canonicalizeBrand } from "./brand-normalize";

// ─── Search-intent classification (deterministic, no AI) ────────────────────
// Decides whether a query is a CATEGORY ("energy drinks"), a BRAND ("Quest"),
// or a shopper KEYWORD ("best protein bar") so the hero can adapt. Brand is
// checked FIRST so "quest" reads as a brand, not the protein-bars alias.

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

export type Intent =
  | { kind: "category"; category: string }
  | { kind: "brand"; brand: string; category?: string }
  | { kind: "keyword"; keyword: string };

// The category whose roster contains this brand (e.g. Monster → Energy Drinks).
// Lets a brand search run its competitive category shelf. Undefined if unknown.
export function brandCategory(brand: string): string | undefined {
  const nb = norm(brand);
  for (const c of CATEGORIES) {
    if (c.brands.some((b) => norm(b.brand) === nb)) return c.label;
  }
  return undefined;
}

// Is this query a brand we recognize? Returns the canonical brand if so.
function knownBrand(query: string): string | undefined {
  const nb = norm(query);
  if (nb.length < 2) return undefined;
  const inRoster = CATEGORIES.some((c) => c.brands.some((b) => norm(b.brand) === nb));
  const inCanon = CANONICAL_BRANDS.some((b) => norm(b) === nb);
  if (inRoster || inCanon) return canonicalizeBrand(query).brand;
  // High-confidence rollup (e.g. "monster energy" → Monster).
  const c = canonicalizeBrand(query);
  if (c.confidence >= 0.9 && norm(c.brand) !== nb && brandCategory(c.brand)) {
    return c.brand;
  }
  return undefined;
}

// Is this query a category? EXACT match on key / label / alias only — never a
// substring (so "best protein bar" stays a keyword, not the protein-bars
// category) and never the hash fallback `matchCategory` uses for mock data.
function knownCategory(query: string): string | undefined {
  const k = query.trim().toLowerCase();
  const hit = CATEGORIES.find(
    (c) =>
      c.key === k ||
      c.label.toLowerCase() === k ||
      c.aliases.some((a) => a.toLowerCase() === k),
  );
  return hit?.label;
}

export function classifyIntent(query: string): Intent {
  const q = (query ?? "").trim();
  if (!q) return { kind: "keyword", keyword: q };

  // 1) Brand first — so "quest"/"celsius" are brands, resolved to their shelf.
  const brand = knownBrand(q);
  if (brand) return { kind: "brand", brand, category: brandCategory(brand) };

  // 2) Category.
  const category = knownCategory(q);
  if (category) return { kind: "category", category };

  // 3) Everything else is a shopper keyword.
  return { kind: "keyword", keyword: q };
}
