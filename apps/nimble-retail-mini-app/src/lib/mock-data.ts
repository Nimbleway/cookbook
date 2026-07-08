import type { RetailerId, RetailerSerpResult } from "./types";
import { ALL_RETAILERS } from "./retailers";

// ─── Deterministic mock data ────────────────────────────────────────────────
// Demo Mode is the default experience, so the data must look real and stay
// STABLE across renders (so a claim like "Premier Protein owns 42% of Walmart"
// is consistent). We use a seeded PRNG keyed by category+retailer.
//
// Claude never generates this data — it only summarizes what's here. These are
// real, recognizable brands; retailer dominance is intentionally varied so the
// cross-retailer insights have something interesting to say.

function mulberry32(seed: number) {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export type BrandDef = {
  brand: string;
  color: string;
  products: string[]; // product title templates
  priceRange: [number, number];
};

export type CategoryDef = {
  key: string;
  label: string;
  emoji: string;
  aliases: string[];
  brands: BrandDef[];
  // weighting per retailer: brand -> relative prevalence multiplier.
  // This is what makes one brand dominate Walmart but not Amazon, etc.
  retailerBias: Partial<Record<RetailerId, Record<string, number>>>;
};

// ── Category catalog (5 curated demo categories) ────────────────────────────
export const CATEGORIES: CategoryDef[] = [
  {
    key: "protein-bars",
    label: "Protein Bars",
    emoji: "🍫",
    aliases: ["protein bar", "protein bars", "protein", "premier protein", "quest"],
    brands: [
      { brand: "Quest", color: "#2B2B2B", priceRange: [19.99, 27.49], products: ["Quest Protein Bars, Chocolate Chip Cookie Dough, 12ct", "Quest Protein Bars, Birthday Cake, 12ct", "Quest Protein Bars Variety Pack, 12ct"] },
      { brand: "Premier Protein", color: "#0A2A66", priceRange: [14.98, 22.98], products: ["Premier Protein Bar, Chocolate Peanut Butter, 18ct", "Premier Protein Bar, Double Chocolate Crunch, 18ct"] },
      { brand: "ONE", color: "#E11D48", priceRange: [17.88, 24.99], products: ["ONE Protein Bars, Maple Glazed Doughnut, 12ct", "ONE Protein Bars, Birthday Cake, 12ct"] },
      { brand: "RXBAR", color: "#111111", priceRange: [21.99, 29.99], products: ["RXBAR Protein Bars, Chocolate Sea Salt, 12ct", "RXBAR Protein Bars Variety Pack, 12ct"] },
      { brand: "Pure Protein", color: "#1D4ED8", priceRange: [12.98, 18.99], products: ["Pure Protein Bars, Chocolate Deluxe, 12ct", "Pure Protein Bars, Chewy Chocolate Chip, 12ct"] },
      { brand: "CLIF", color: "#16A34A", priceRange: [11.99, 17.49], products: ["CLIF BAR Energy Bars, Chocolate Chip, 12ct", "CLIF BAR Energy Bars, Crunchy Peanut Butter, 12ct"] },
      { brand: "KIND", color: "#CA8A04", priceRange: [10.98, 16.49], products: ["KIND Protein Bars, Crunchy Peanut Butter, 12ct", "KIND Bars, Dark Chocolate Nuts & Sea Salt, 12ct"] },
      { brand: "Barebells", color: "#0EA5E9", priceRange: [22.99, 29.99], products: ["Barebells Protein Bars, Cookies & Cream, 12ct", "Barebells Protein Bars, Caramel Cashew, 12ct"] },
      { brand: "Gatorade", color: "#F97316", priceRange: [15.99, 21.99], products: ["Gatorade Whey Protein Bars, Chocolate Chip, 12ct"] },
      { brand: "Built", color: "#7C3AED", priceRange: [23.99, 31.99], products: ["Built Puff Protein Bars, Marshmallow, 12ct"] },
    ],
    retailerBias: {
      amazon: { Quest: 2.4, RXBAR: 1.8, Barebells: 1.6, Built: 1.4 },
      walmart: { "Premier Protein": 2.8, "Pure Protein": 2.0, Gatorade: 1.6, ONE: 1.3 },
      target: { ONE: 2.2, CLIF: 1.9, KIND: 1.8, Quest: 1.3 },
    },
  },
  {
    key: "energy-drinks",
    label: "Energy Drinks",
    emoji: "⚡",
    aliases: ["energy drink", "energy drinks", "monster", "red bull", "celsius"],
    brands: [
      { brand: "Monster", color: "#00FF66", priceRange: [24.99, 38.99], products: ["Monster Energy, Original, 16oz, 15pk", "Monster Energy, Zero Ultra, 16oz, 15pk"] },
      { brand: "Red Bull", color: "#001489", priceRange: [27.99, 41.99], products: ["Red Bull Energy Drink, 8.4oz, 24pk", "Red Bull Sugar Free, 8.4oz, 24pk"] },
      { brand: "Celsius", color: "#06B6D4", priceRange: [25.99, 36.99], products: ["CELSIUS Energy Drink, Sparkling Orange, 12oz, 12pk", "CELSIUS Variety Pack, 12oz, 12pk"] },
      { brand: "Bang", color: "#FACC15", priceRange: [22.99, 31.99], products: ["Bang Energy, Star Blast, 16oz, 12pk", "Bang Energy, Rainbow Unicorn, 16oz, 12pk"] },
      { brand: "C4", color: "#DC2626", priceRange: [21.99, 29.99], products: ["C4 Energy Drink, Frozen Bombsicle, 16oz, 12pk"] },
      { brand: "Rockstar", color: "#FACC15", priceRange: [19.99, 28.99], products: ["Rockstar Energy Drink, Original, 16oz, 12pk"] },
      { brand: "Alani Nu", color: "#FB7185", priceRange: [23.99, 33.99], products: ["Alani Nu Energy Drink, Breezeberry, 12oz, 12pk", "Alani Nu Energy Drink, Witch's Brew, 12oz, 12pk"] },
      { brand: "Reign", color: "#1E293B", priceRange: [22.99, 30.99], products: ["Reign Total Body Fuel, Razzle Berry, 16oz, 12pk"] },
      { brand: "Ghost", color: "#7C3AED", priceRange: [24.99, 34.99], products: ["GHOST Energy Drink, Sour Patch Kids Redberry, 16oz, 12pk"] },
      { brand: "5-hour Energy", color: "#EA580C", priceRange: [14.99, 24.99], products: ["5-hour ENERGY Shot, Extra Strength Berry, 12ct"] },
    ],
    retailerBias: {
      amazon: { Monster: 2.6, "Red Bull": 2.0, Bang: 1.6, Ghost: 1.4 },
      walmart: { Monster: 2.2, Rockstar: 2.0, "5-hour Energy": 1.8, C4: 1.4 },
      target: { Celsius: 2.8, "Alani Nu": 2.4, "Red Bull": 1.5 },
    },
  },
  {
    key: "sparkling-water",
    label: "Sparkling Water",
    emoji: "💧",
    aliases: ["sparkling water", "seltzer", "lacroix", "bubly", "spindrift"],
    brands: [
      { brand: "LaCroix", color: "#22D3EE", priceRange: [12.98, 18.49], products: ["LaCroix Sparkling Water, Pamplemousse, 12oz, 24pk", "LaCroix Sparkling Water, Lime, 12oz, 24pk"] },
      { brand: "Bubly", color: "#F472B6", priceRange: [9.98, 15.49], products: ["bubly Sparkling Water, Cherry, 12oz, 18pk", "bubly Sparkling Water Variety Pack, 12oz, 18pk"] },
      { brand: "Spindrift", color: "#FB923C", priceRange: [15.99, 22.99], products: ["Spindrift Sparkling Water, Raspberry Lime, 12oz, 20pk", "Spindrift Variety Pack, 12oz, 20pk"] },
      { brand: "Waterloo", color: "#0EA5E9", priceRange: [13.99, 19.99], products: ["Waterloo Sparkling Water, Black Cherry, 12oz, 12pk"] },
      { brand: "Topo Chico", color: "#16A34A", priceRange: [11.98, 17.99], products: ["Topo Chico Mineral Water, 12oz, 12pk"] },
      { brand: "Perrier", color: "#15803D", priceRange: [10.98, 16.99], products: ["Perrier Carbonated Mineral Water, 11.15oz, 10pk"] },
      { brand: "San Pellegrino", color: "#DC2626", priceRange: [12.98, 19.49], products: ["San Pellegrino Sparkling Natural Mineral Water, 11.15oz, 12pk"] },
      { brand: "AHA", color: "#9333EA", priceRange: [8.98, 13.99], products: ["AHA Sparkling Water, Lime + Watermelon, 12oz, 8pk"] },
      { brand: "Liquid Death", color: "#0F172A", priceRange: [16.99, 23.99], products: ["Liquid Death Sparkling Water, Severed Lime, 16.9oz, 12pk"] },
      { brand: "Poland Spring", color: "#1D4ED8", priceRange: [7.98, 12.99], products: ["Poland Spring Sparkling Water, Lemon, 12oz, 8pk"] },
    ],
    retailerBias: {
      amazon: { LaCroix: 2.4, Spindrift: 2.0, "Liquid Death": 1.8, Waterloo: 1.4 },
      walmart: { Bubly: 2.6, AHA: 2.0, "Topo Chico": 1.7, "Poland Spring": 1.5 },
      target: { Spindrift: 2.4, LaCroix: 1.8, "San Pellegrino": 1.6, Perrier: 1.4 },
    },
  },
  {
    key: "cat-food",
    label: "Cat Food",
    emoji: "🐱",
    aliases: ["cat food", "cat", "purina", "friskies", "fancy feast"],
    brands: [
      { brand: "Purina", color: "#E11D48", priceRange: [18.98, 32.99], products: ["Purina ONE Tender Selects Dry Cat Food, 16lb", "Purina Pro Plan Adult Chicken & Rice, 16lb"] },
      { brand: "Friskies", color: "#7C3AED", priceRange: [12.98, 22.49], products: ["Friskies Wet Cat Food Variety Pack, 5.5oz, 40ct", "Friskies Surfin' & Turfin' Favorites, 5.5oz, 32ct"] },
      { brand: "Fancy Feast", color: "#A16207", priceRange: [15.98, 28.99], products: ["Fancy Feast Classic Pate Variety Pack, 3oz, 30ct", "Fancy Feast Gravy Lovers, 3oz, 24ct"] },
      { brand: "Meow Mix", color: "#F59E0B", priceRange: [11.98, 19.99], products: ["Meow Mix Original Choice Dry Cat Food, 16lb"] },
      { brand: "Blue Buffalo", color: "#1D4ED8", priceRange: [24.98, 42.99], products: ["Blue Buffalo Wilderness High Protein Dry Cat Food, 11lb", "Blue Buffalo Tastefuls Variety Pack, 3oz, 24ct"] },
      { brand: "Hill's Science Diet", color: "#0F766E", priceRange: [29.99, 54.99], products: ["Hill's Science Diet Adult Indoor Dry Cat Food, 15.5lb"] },
      { brand: "Iams", color: "#DC2626", priceRange: [16.98, 29.99], products: ["IAMS Proactive Health Adult Dry Cat Food, 16lb"] },
      { brand: "Sheba", color: "#0EA5E9", priceRange: [14.98, 24.99], products: ["SHEBA PERFECT PORTIONS Pate Variety Pack, 2.6oz, 24ct"] },
      { brand: "Temptations", color: "#EA580C", priceRange: [9.98, 16.99], products: ["TEMPTATIONS Classic Cat Treats, Tasty Chicken, 30oz"] },
      { brand: "Royal Canin", color: "#7C2D12", priceRange: [34.99, 64.99], products: ["Royal Canin Indoor Adult Dry Cat Food, 15lb"] },
    ],
    retailerBias: {
      amazon: { "Blue Buffalo": 2.4, "Hill's Science Diet": 2.0, "Royal Canin": 1.8, Purina: 1.5 },
      walmart: { Purina: 2.6, "Meow Mix": 2.2, Friskies: 2.0, Iams: 1.5 },
      target: { "Fancy Feast": 2.2, Sheba: 2.0, Temptations: 1.9, Purina: 1.4 },
    },
  },
  {
    key: "coffee",
    label: "Coffee",
    emoji: "☕",
    aliases: ["coffee", "ground coffee", "k cups", "folgers", "starbucks"],
    brands: [
      { brand: "Folgers", color: "#DC2626", priceRange: [9.98, 18.99], products: ["Folgers Classic Roast Ground Coffee, 40.3oz", "Folgers Black Silk Ground Coffee, 22.6oz"] },
      { brand: "Starbucks", color: "#0F6B3D", priceRange: [12.98, 24.99], products: ["Starbucks Pike Place Roast Ground Coffee, 28oz", "Starbucks Medium Roast K-Cup Pods, 72ct"] },
      { brand: "Dunkin'", color: "#EA580C", priceRange: [10.98, 21.99], products: ["Dunkin' Original Blend Ground Coffee, 30oz", "Dunkin' Original Blend K-Cup Pods, 60ct"] },
      { brand: "Maxwell House", color: "#1D4ED8", priceRange: [8.98, 15.99], products: ["Maxwell House Original Roast Ground Coffee, 30.6oz"] },
      { brand: "Peet's", color: "#7C2D12", priceRange: [13.98, 23.99], products: ["Peet's Coffee Major Dickason's Blend Ground, 18oz"] },
      { brand: "Death Wish", color: "#0F172A", priceRange: [16.99, 27.99], products: ["Death Wish Coffee Dark Roast Ground, 16oz"] },
      { brand: "Café Bustelo", color: "#F59E0B", priceRange: [7.98, 14.99], products: ["Café Bustelo Espresso Ground Coffee, 36oz"] },
      { brand: "Green Mountain", color: "#16A34A", priceRange: [11.98, 22.99], products: ["Green Mountain Breakfast Blend K-Cup Pods, 72ct"] },
      { brand: "McCafé", color: "#B91C1C", priceRange: [10.98, 19.99], products: ["McCafé Premium Roast K-Cup Pods, 48ct"] },
      { brand: "Lavazza", color: "#1E3A8A", priceRange: [14.98, 25.99], products: ["Lavazza Super Crema Whole Bean Coffee, 2.2lb"] },
    ],
    retailerBias: {
      amazon: { Starbucks: 2.2, "Death Wish": 2.0, Lavazza: 1.8, "Green Mountain": 1.6 },
      walmart: { Folgers: 2.8, "Maxwell House": 2.2, "Café Bustelo": 1.8, "Dunkin'": 1.4 },
      target: { Starbucks: 2.2, "Peet's": 2.0, "Dunkin'": 1.7, McCafé: 1.5 },
    },
  },
];

export const DEMO_SUGGESTIONS = CATEGORIES.map((c) => ({
  key: c.key,
  label: c.label,
  emoji: c.emoji,
  // Top brands → used to render a real brand-logo cluster on each chip
  // (replaces the emoji). Derived from the category's brand roster.
  brands: c.brands.slice(0, 3).map((b) => b.brand),
}));

function matchCategory(keyword: string): CategoryDef {
  const k = keyword.trim().toLowerCase();
  const exact = CATEGORIES.find(
    (c) => c.key === k || c.label.toLowerCase() === k,
  );
  if (exact) return exact;
  const alias = CATEGORIES.find((c) =>
    c.aliases.some((a) => k.includes(a) || a.includes(k)),
  );
  if (alias) return alias;
  // Fallback so the demo never looks empty: pick deterministically by hash.
  return CATEGORIES[hashStr(k) % CATEGORIES.length];
}

// Deterministically allocate page-one SLOTS per brand for a retailer. We use a
// steep (squared) curve over the retailer bias so a clear leader emerges (~40%)
// — that dominance is the "wow" the experience is built around. Random sampling
// regresses toward uniform and kills the moment, so we allocate counts directly.
function allocateSlots(
  cat: CategoryDef,
  retailer: RetailerId,
  count: number,
): BrandDef[] {
  const bias = cat.retailerBias[retailer] ?? {};
  // Unbiased brands get a small baseline so the shelf still has variety.
  const weighted = cat.brands.map((b) => ({
    def: b,
    w: Math.pow(bias[b.brand] ?? 0.55, 2),
  }));
  const totalW = weighted.reduce((a, b) => a + b.w, 0);

  // First pass: proportional counts (floored).
  const slots: { def: BrandDef; n: number }[] = weighted.map((x) => ({
    def: x.def,
    n: Math.floor((x.w / totalW) * count),
  }));
  let assigned = slots.reduce((a, s) => a + s.n, 0);
  // Distribute the remainder to the highest-weight brands (keeps leader on top).
  const order = [...weighted]
    .map((x, i) => ({ i, w: x.w }))
    .sort((a, b) => b.w - a.w);
  let oi = 0;
  while (assigned < count) {
    slots[order[oi % order.length].i].n += 1;
    assigned += 1;
    oi += 1;
  }
  // Expand to a flat list of brand defs, leaders first.
  const expanded: BrandDef[] = [];
  slots
    .filter((s) => s.n > 0)
    .sort((a, b) => b.n - a.n)
    .forEach((s) => {
      for (let i = 0; i < s.n; i++) expanded.push(s.def);
    });
  return expanded;
}

const COLLECTED_AT = "2026-05-30T15:00:00.000Z";

function generateForRetailer(
  cat: CategoryDef,
  retailer: RetailerId,
  keyword: string,
  count: number,
): RetailerSerpResult[] {
  const rng = mulberry32(hashStr(`${cat.key}:${retailer}`));
  const brandsBySlot = allocateSlots(cat, retailer, count);

  // Assign ranks: the leader skews toward the top of page one (where it really
  // shows up), but interleave so the shelf looks natural rather than blocked.
  const ranked = brandsBySlot
    .map((def, i) => ({ def, jitter: i + rng() * 3 }))
    .sort((a, b) => a.jitter - b.jitter)
    .map((x) => x.def);

  const results: RetailerSerpResult[] = [];
  const titleCursor = new Map<string, number>();

  for (let rank = 1; rank <= count; rank++) {
    const brandDef = ranked[rank - 1];
    // Rotate through a brand's product titles so repeats vary.
    const c = titleCursor.get(brandDef.brand) ?? 0;
    titleCursor.set(brandDef.brand, c + 1);
    const title = brandDef.products[c % brandDef.products.length];

    // Sponsored placements cluster near the top (paid to win page one).
    const sponsoredProb = rank <= 4 ? 0.55 : rank <= 8 ? 0.3 : 0.1;
    const sponsored = rng() < sponsoredProb;

    const [lo, hi] = brandDef.priceRange;
    const price = Math.round((lo + rng() * (hi - lo)) * 100) / 100;
    const rating = Math.round((4.0 + rng() * 0.9) * 10) / 10;
    const reviewCount = Math.floor(150 + rng() * 48000);
    const inStock = rng() > 0.07;

    // ── Rich real-time signals (mirror the live agent fields) ──
    // Demand velocity is intentionally NOT perfectly correlated with rank — a
    // strong-rated mid-ranked product can out-sell a #1 ad. That gap is an aha.
    const salesScore = (17 - rank) * 0.5 + (rating - 4) * 9 + rng() * 7;
    const recentSales =
      salesScore > 5
        ? `${bucketSales(salesScore)} bought in past month`
        : undefined;

    // ~40% of items are discounted right now.
    const discounted = rng() < 0.4;
    const originalPrice = discounted
      ? Math.round((price / (1 - (0.1 + rng() * 0.25))) * 100) / 100
      : undefined;

    // Price-per-unit (true value) — derived plausibly from price.
    const perUnit = Math.round((price / (8 + rng() * 30)) * 100) / 100;
    const pricePerUnit = `$${perUnit.toFixed(2)}/oz`;

    // Walmart-style marketplace sellers: mostly 1P, sometimes 3P.
    const seller =
      retailer === "walmart" && rng() < 0.22
        ? THIRD_PARTY_SELLERS[Math.floor(rng() * THIRD_PARTY_SELLERS.length)]
        : undefined;

    // Algorithmic endorsement badge on the strongest organic slot.
    let badge: string | undefined;
    if (!sponsored && rank <= 3 && rng() < 0.5) {
      badge =
        retailer === "amazon"
          ? "Amazon's Choice"
          : retailer === "walmart"
            ? "Popular pick"
            : "Featured";
    }

    results.push({
      retailer,
      keyword,
      rank,
      productTitle: title,
      brand: brandDef.brand,
      price,
      rating,
      reviewCount,
      sponsored,
      productUrl: "#",
      // imageUrl omitted in demo — UI renders the real brand logo / tile.
      availability: inStock ? "In stock" : "Out of stock",
      collectedAt: COLLECTED_AT,
      recentSales,
      originalPrice,
      pricePerUnit,
      seller,
      inStock,
      badge,
    });
  }
  return results;
}

const THIRD_PARTY_SELLERS = [
  "MarketplacePro",
  "ShopRite Direct",
  "ValueGoods LLC",
  "PrimeDeals",
];

function bucketSales(score: number): string {
  if (score > 24) return "10K+";
  if (score > 18) return "5K+";
  if (score > 13) return "3K+";
  if (score > 9) return "1K+";
  return "500+";
}

// Real brand domains → used to fetch actual brand logos in the UI. This is what
// makes the demo read as a real product, not initials.
const BRAND_DOMAINS: Record<string, string> = {
  // Protein bars
  Quest: "questnutrition.com",
  "Premier Protein": "premierprotein.com",
  ONE: "one-brands.com",
  RXBAR: "rxbar.com",
  "Pure Protein": "pureprotein.com",
  CLIF: "clifbar.com",
  KIND: "kindsnacks.com",
  Barebells: "barebells.com",
  Gatorade: "gatorade.com",
  Built: "builtbar.com",
  // Energy drinks
  Monster: "monsterenergy.com",
  "Red Bull": "redbull.com",
  Celsius: "celsius.com",
  Bang: "bangenergy.com",
  C4: "cellucor.com",
  Rockstar: "rockstarenergy.com",
  "Alani Nu": "alaninu.com",
  Reign: "reignbodyfuel.com",
  Ghost: "ghostlifestyle.com",
  "5-hour Energy": "5hourenergy.com",
  // Sparkling water
  LaCroix: "lacroixwater.com",
  Bubly: "bubly.com",
  Spindrift: "spindriftfresh.com",
  Waterloo: "drinkwaterloo.com",
  "Topo Chico": "topochico.com",
  Perrier: "perrier.com",
  "San Pellegrino": "sanpellegrino.com",
  AHA: "drinkaha.com",
  "Liquid Death": "liquiddeath.com",
  "Poland Spring": "polandspring.com",
  // Cat food
  Purina: "purina.com",
  Friskies: "friskies.com",
  "Fancy Feast": "fancyfeast.com",
  "Meow Mix": "meowmix.com",
  "Blue Buffalo": "bluebuffalo.com",
  "Hill's Science Diet": "hillspet.com",
  Iams: "iams.com",
  Sheba: "sheba.com",
  Temptations: "temptationstreats.com",
  "Royal Canin": "royalcanin.com",
  // Coffee
  Folgers: "folgerscoffee.com",
  Starbucks: "starbucks.com",
  "Dunkin'": "dunkindonuts.com",
  "Maxwell House": "maxwellhousecoffee.com",
  "Peet's": "peets.com",
  "Death Wish": "deathwishcoffee.com",
  "Café Bustelo": "cafebustelo.com",
  "Green Mountain": "greenmountaincoffee.com",
  McCafé: "mccafe.com",
  Lavazza: "lavazza.com",
};

export function brandDomain(brand: string): string | undefined {
  return BRAND_DOMAINS[brand];
}

// The known, canonical brand catalog — used by brand normalization to roll
// product sub-lines up to a real brand. These are the authoritative names.
export const CANONICAL_BRANDS = Object.keys(BRAND_DOMAINS);

// Ordered logo image sources for a domain. DuckDuckGo serves real, colorful
// favicons (and 404s on a miss → the UI's monogram, never an ugly grey globe);
// Google is the secondary for the few domains DDG lacks. Clearbit's free logo
// API is dead. The UI always falls back to a clean gold monogram, so a broken
// or missing logo never shows.
export function logoSourcesForDomain(domain: string): string[] {
  return [
    `https://icons.duckduckgo.com/ip3/${domain}.ico`,
    `https://www.google.com/s2/favicons?domain=${domain}&sz=128`,
  ];
}

// Ordered list of logo image sources to try for a brand (best quality first).
// The UI walks this list, falling back to a branded tile if all fail.
export function brandLogoSources(brand: string): string[] {
  const domain = BRAND_DOMAINS[brand];
  if (!domain) return [];
  return logoSourcesForDomain(domain);
}

// Retailers Nimble has agents for — drives the "Meet Our Agents" marquee.
// Rendered via the logo CDN by domain (no hotlinking of fragile CDN assets).
export const AGENT_RETAILERS: { name: string; domain: string }[] = [
  { name: "Amazon", domain: "amazon.com" },
  { name: "Walmart", domain: "walmart.com" },
  { name: "Target", domain: "target.com" },
  { name: "Best Buy", domain: "bestbuy.com" },
  { name: "Chewy", domain: "chewy.com" },
  { name: "The Home Depot", domain: "homedepot.com" },
  { name: "Lowe's", domain: "lowes.com" },
  { name: "Costco", domain: "costco.com" },
  { name: "Kroger", domain: "kroger.com" },
  { name: "Instacart", domain: "instacart.com" },
  { name: "Wayfair", domain: "wayfair.com" },
  { name: "Staples", domain: "staples.com" },
  { name: "Office Depot", domain: "officedepot.com" },
  { name: "eBay", domain: "ebay.com" },
  { name: "Foot Locker", domain: "footlocker.com" },
  { name: "CVS", domain: "cvs.com" },
  { name: "Walgreens", domain: "walgreens.com" },
  { name: "Sephora", domain: "sephora.com" },
  { name: "Etsy", domain: "etsy.com" },
  { name: "Albertsons", domain: "albertsons.com" },
];

// Brand color lookup for the UI (falls back to a hashed hue).
export function brandColor(brand: string): string {
  for (const cat of CATEGORIES) {
    const def = cat.brands.find((b) => b.brand === brand);
    if (def) return def.color;
  }
  const hue = hashStr(brand) % 360;
  return `hsl(${hue} 65% 45%)`;
}

// Public API: deterministic mock SERP results for all retailers for a keyword.
export function getMockResults(
  keyword: string,
): Record<RetailerId, RetailerSerpResult[]> {
  const cat = matchCategory(keyword);
  const out = {} as Record<RetailerId, RetailerSerpResult[]>;
  for (const retailer of ALL_RETAILERS) {
    out[retailer] = generateForRetailer(cat, retailer, keyword || cat.label, 16);
  }
  return out;
}

export function resolveCategoryLabel(keyword: string): string {
  return matchCategory(keyword).label;
}
