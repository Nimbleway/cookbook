import { CANONICAL_BRANDS } from "./mock-data";

// ─── Brand normalization ────────────────────────────────────────────────────
// Rolls product sub-lines up to a canonical brand so strategic insights (share,
// verdicts, threat/opportunity, run-my-brand, cross-retailer) treat a brand
// family as ONE competitor — not "Monster Energy" vs "Monster Ultra" vs
// "Monster". Conservative by design: under-merge beats over-merge. Only the
// explicitly-approved force families roll up aggressively; everything else
// merges only on an exact or known-prefix match against the real catalog.

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

// Force-mapped families (approved). Variants are matched by exact OR prefix on
// the brand string AND the product title, longest variant first.
const FORCE_FAMILIES: { canonical: string; variants: string[] }[] = [
  {
    canonical: "Monster",
    variants: [
      "monster energy",
      "monster ultra",
      "monster open",
      "monster wireless",
      "monster rehab",
      "monster java",
      "monster reserve",
      "monster",
    ],
  },
  { canonical: "Red Bull", variants: ["red bull"] },
  { canonical: "Premier Protein", variants: ["premier protein", "premier"] },
  { canonical: "Quest", variants: ["quest nutrition", "quest"] },
  { canonical: "Celsius", variants: ["celsius"] },
  { canonical: "Liquid Death", variants: ["liquid death"] },
  // Common live category leaders whose listings carry trailing descriptors
  // ("Bloom Nutrition", "Ghost Energy") or sub-lines — roll them to one brand.
  { canonical: "Bloom", variants: ["bloom nutrition", "bloom sparkling energy", "bloom"] },
  { canonical: "Ghost", variants: ["ghost energy", "ghost"] },
  { canonical: "Alani Nu", variants: ["alani nu", "alani"] },
  { canonical: "Reign", variants: ["reign total body fuel", "reign storm", "reign"] },
  { canonical: "Rockstar", variants: ["rockstar energy", "rockstar"] },
  // "Energy" IS part of this brand — protected below so it's never stripped.
  { canonical: "5-hour Energy", variants: ["5-hour energy", "5 hour energy", "5hour energy"] },
];

// Trailing words that are category/marketing descriptors, not brand identity —
// stripped from UNKNOWN brands so live listings consolidate ("Bloom Nutrition"
// + "Bloom" → "Bloom"). Conservative: excludes brand-bearing words like
// "protein", "coffee", "water".
const TRAILING_DESCRIPTORS = new Set([
  "energy", "nutrition", "sparkling", "seltzer", "hydration", "drink",
  "drinks", "beverage", "beverages", "co", "company", "inc", "llc",
  "foods", "brands", "official", "store",
]);

// Brands where a descriptor word IS the name — never strip these.
const PROTECTED = new Set(
  ["5-hour Energy", "Liquid Death", "Red Bull"].map((s) => s.toLowerCase().replace(/[^a-z0-9]/g, "")),
);

const FORCE_N = FORCE_FAMILIES.flatMap((f) =>
  f.variants.map((v) => ({ canonical: f.canonical, v: norm(v) })),
).sort((a, b) => b.v.length - a.v.length);

// Known catalog, longest-first so "Premier Protein" beats "Premier", etc.
const DICT = [...CANONICAL_BRANDS].sort((a, b) => norm(b).length - norm(a).length);

export type CanonResult = { brand: string; confidence: number };

// Returns the canonical brand for a raw brand string (+ optional product title).
// confidence: 1 exact · 0.95/0.9 prefix/known · 0.4 fallback (no merge).
export function canonicalizeBrand(raw: string, title?: string): CanonResult {
  if (!raw) return { brand: raw || "Unknown", confidence: 0 };
  const texts = [raw, title].filter(Boolean).map((t) => norm(String(t)));

  // 1) Force families — exact or prefix on brand or title.
  for (const { canonical, v } of FORCE_N) {
    if (v.length < 3) continue;
    for (const t of texts) {
      if (t === v) return { brand: canonical, confidence: 1 };
      if (t.startsWith(v)) return { brand: canonical, confidence: 0.95 };
    }
  }

  // 2) Known catalog — exact match on the raw brand.
  const rawN = norm(raw);
  for (const c of DICT) {
    if (rawN === norm(c)) return { brand: c, confidence: 1 };
  }

  // 3) Known catalog — brand/title starts with a known brand (len >= 4, safe).
  for (const c of DICT) {
    const nc = norm(c);
    if (nc.length < 4) continue;
    for (const t of texts) {
      if (t.startsWith(nc)) return { brand: c, confidence: 0.9 };
    }
  }

  // 4) No confident match → strip trailing category descriptors so live
  //    listings consolidate ("Bloom Nutrition" + "Bloom" → "Bloom"), then fold
  //    case. Protected brands (where the descriptor IS the name) are left whole.
  let words = raw.trim().split(/\s+/);
  if (!PROTECTED.has(rawN)) {
    while (
      words.length > 1 &&
      TRAILING_DESCRIPTORS.has(
        words[words.length - 1].toLowerCase().replace(/[^a-z]/g, ""),
      )
    ) {
      words = words.slice(0, -1);
    }
  }
  const stripped = words.join(" ");
  const allCaps = /[A-Z]/.test(stripped) && stripped === stripped.toUpperCase();
  const allLower = stripped === stripped.toLowerCase();
  const brand = allCaps || allLower ? titleCase(stripped) : stripped;
  // Stripping a descriptor is a real (if light) normalization; flag confidence.
  return { brand, confidence: stripped !== raw.trim() ? 0.6 : 0.4 };
}

function titleCase(s: string): string {
  return s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}
