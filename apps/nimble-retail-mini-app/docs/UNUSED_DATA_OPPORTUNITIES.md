# Unused Data Opportunities

**App:** Nimble Retail Intelligence Experience
**Question:** Of the live fields the Nimble SERP agents already return, which are NOT surfaced (or barely surfaced) in the UI — and which are the highest-value to add?
**Date:** 2026-06-01
**Source of truth:** `normalizeRow()` in `src/services/nimble-serp.ts:129–181` (every field below is already parsed today).

---

## 0. Surfacing status at a glance

| Field | Parsed? | Surfaced in UI today? | Verdict |
|---|---|---|---|
| `seller` (1P/3P) | ✅ `nimble-serp.ts:177` | ❌ **Nowhere** | **Biggest untapped asset** |
| `pricePerUnit` | ✅ `:176` | ❌ **Nowhere** | Untapped |
| `productUrl` | ✅ `:169` | ❌ Never linked | Untapped (credibility proof) |
| `reviewCount` | ✅ `:167` | ⚠️ Raw table only (`retail-explorer.tsx`) | Under-used |
| `rating` | ✅ `:166` | ⚠️ Raw table + brand drawer only | Under-used |
| `badge` (Amazon's Choice / Prime) | ✅ `:153` | ⚠️ One conditional card (Amazon's Choice only) | Under-used (Prime ignored) |
| `originalPrice` (promo) | ✅ `:175` | ⚠️ One conditional "discount" card | Under-used (no promo density / spread) |
| `recentSales` (velocity) | ✅ `:174` | ✅ `selling-now.tsx` + demand card | Used (extendable) |
| `inStock` / `availability` | ✅ `:145,171` | ✅ Stockout card | Used (extendable) |
| **Cross-retailer price spread** | derived from `price` | ❌ Nowhere | **Highest-wow derived opportunity** |

> Note: a few high-value items below are **derived** from fields we already collect (e.g. cross-retailer price spread from `price`, promo density from `originalPrice`). They're included because the raw inputs are already live in `results[]`.

---

## 1. `seller` — 1P vs 3P (marketplace) mix  ·  Wow 9 · Effort 4

- **Example value:** `"Sold by Walmart.com"` (1P) vs `"ABC Trading Co."` (3P marketplace) / Amazon `"Ships from and sold by Amazon.com"`.
- **Business meaning:** Whether page-one results are sold by the retailer (first-party) or third-party marketplace sellers.
- **Executive value:** 3P penetration is a top CPG concern — unauthorized resellers, MAP/price erosion, counterfeit risk, and lost share to marketplace arbitrage. CPG eComm leaders actively police this.
- **Potential insight:** *"38% of page-one {category} on Walmart is third-party — your brand is competing with marketplace resellers for your own shelf."*
- **UI treatment:** A "1P vs 3P" split bar per retailer in a "What we see right now" module; flag brands appearing under unknown 3P sellers.
- **Why it's #1:** Completely unused, uniquely Nimble-flavored, and instantly resonant with the exact audience (CPG eCommerce). Effort is modest — the string is there; needs a 1P/3P classifier heuristic + one component.

## 2. Cross-retailer price spread (same product, different retailer)  ·  Wow 10 · Effort 5

- **Example value:** Same SKU — Amazon `$24.99`, Walmart `$21.97`, Target `$26.49` → **17% spread**.
- **Business meaning:** Price dispersion for like products across the three retailers, right now.
- **Executive value:** Price consistency / MAP compliance is a board-level concern; spread = channel conflict and margin leakage.
- **Potential insight:** *"The same product is 17% cheaper on Walmart than Target right now — a static report would quote one number that's already wrong on two shelves."*
- **UI treatment:** A "Price varies by shelf right now" module — product image + three retailer price chips + spread %.
- **Effort note:** Requires fuzzy product matching across retailers (title/brand similarity) — the only Medium-effort item here, but the single highest wow.

## 3. `pricePerUnit` — true value per oz/unit  ·  Wow 7 · Effort 3

- **Example value:** `"$0.42/oz"`.
- **Business meaning:** Normalized unit price — the real value comparison shoppers (and Amazon's algorithm) use.
- **Executive value:** Headline price hides true value; unit price exposes who's actually cheapest and where pack-size games are happening.
- **Potential insight:** *"Brand A looks pricier by sticker but is 12% cheaper per ounce than the category leader."*
- **UI treatment:** Add a "$/unit" column/chip to the price showcase; rank by true value.
- **Effort:** Low — field is a ready string; light parsing for sorting.

## 4. `productUrl` — click-through to the live listing  ·  Wow 8 · Effort 2

- **Example value:** `https://www.amazon.com/dp/B0XXXXXXX`.
- **Business meaning:** Deep link to the exact live PDP the data came from.
- **Executive value:** **Credibility proof.** "We see X right now" → *click* → the real page confirms it live in front of the prospect. Converts skeptics on the spot.
- **Potential insight:** Not an insight per se — it's the trust mechanism that makes every other insight unimpeachable.
- **UI treatment:** Make product tiles / explorer rows link out (new tab, `rel="noopener"`); a subtle "view live ↗" affordance.
- **Effort:** Trivial — wrap existing tiles in anchors.

## 5. `reviewCount` — review volume leader  ·  Wow 6 · Effort 2

- **Example value:** `48,210`.
- **Business meaning:** Total ratings — a proxy for cumulative demand and entrenchment.
- **Executive value:** Review moat ≠ shelf position. A brand can lead visibility while a competitor owns the trust base (or vice-versa).
- **Potential insight:** *"Quest owns 19% of the shelf, but RXBAR has 3× the review volume — entrenched demand the rankings don't show."*
- **UI treatment:** "Review volume leader" stat; or a bubble (x = rank, size = reviews) in the explorer.
- **Effort:** Low — already parsed, only shown in the raw table.

## 6. `rating` — quality vs visibility  ·  Wow 6 · Effort 2

- **Example value:** `4.6`.
- **Business meaning:** Average star rating of page-one products.
- **Executive value:** Are top-ranked products actually well-rated, or is paid placement carrying weak products? Quality gaps = opportunity.
- **Potential insight:** *"The #2 sponsored result rates 4.1 vs the category's 4.6 — paid visibility propping up a weaker product."*
- **UI treatment:** Rating chip on tiles; "highest/lowest-rated on page one" callout.
- **Effort:** Low — parsed; only in table/drawer today.

## 7. `badge` — Amazon's Choice + Prime density  ·  Wow 6 · Effort 2

- **Example value:** `"Amazon's Choice"`, `"Prime"`.
- **Business meaning:** Platform-conferred trust/eligibility badges.
- **Executive value:** "Amazon's Choice" is the default-buy for voice/quick purchases; Prime eligibility affects conversion. Today only Amazon's Choice surfaces (one card); **Prime is parsed but ignored**, and badge *density* isn't shown.
- **Potential insight:** *"A competitor holds Amazon's Choice for your #1 keyword — the default add-to-cart for hands-free shoppers."*
- **UI treatment:** Badge chips on tiles; a "default-buy holder" callout; Prime-eligible share of shelf.
- **Effort:** Low.

## 8. Promotion density (from `originalPrice`)  ·  Wow 8 · Effort 3

- **Example value:** `originalPrice $34.99` vs `price $24.99` → **29% off**; "**41% of page-one is on promo right now**."
- **Business meaning:** Share of the shelf currently discounted, and discount depth — beyond the single "deepest discount" card today.
- **Executive value:** Promo intensity signals competitive pressure and margin environment; "right now" beats a stale weekly report.
- **Potential insight:** *"41% of the {category} shelf is on promotion right now, led by Walmart at avg 24% off — the shelf you're pricing against changes by the hour."*
- **UI treatment:** "Promo pressure" gauge per retailer (% on promo + avg depth) in the price showcase.
- **Effort:** Low–Med — `originalPrice` is parsed; needs aggregation + UI.

## 9. `recentSales` cross-retailer demand  ·  Wow 7 · Effort 3

- **Example value:** `"5K+ bought in past month"` (Amazon).
- **Business meaning:** Live purchase velocity — already used in "Selling right now," but only as a single list.
- **Executive value:** Demand ≠ visibility is one of the strongest aha moments; extending it cross-retailer / vs rank deepens it.
- **Potential insight:** *"The #6-ranked product is the #1 seller — paid competitors are outranking the product shoppers actually buy."* (Extend to compare velocity vs rank, and across retailers.)
- **UI treatment:** Velocity-vs-rank scatter, or a "demand outranks visibility" callout in the exec verdicts.
- **Effort:** Low–Med — field already drives `topSelling`.

## 10. Per-retailer availability map (from `inStock`)  ·  Wow 7 · Effort 2

- **Example value:** `inStock: false` on 2 of 16 Walmart results.
- **Business meaning:** Where page-one demand has nowhere to go (OOS) — today shown only as a single stockout card.
- **Executive value:** OOS competitors = capturable demand; OOS *of your own* products = lost sales the buyer needs to know now.
- **Potential insight:** *"3 page-one {category} products are out of stock on Target right now — open demand a daily report wouldn't catch."*
- **UI treatment:** Availability strip per retailer (in-stock vs OOS count) in the "right now" module.
- **Effort:** Low.

---

## Priority ranking (value = wow ÷ effort, tie-broken by wow)

| Rank | Opportunity | Wow | Effort | Notes |
|---|---|---|---|---|
| 1 | **`productUrl` click-through** | 8 | 2 | Trivial; turns every claim into live proof |
| 2 | **`seller` 1P vs 3P** | 9 | 4 | Unused; perfectly on-target for CPG eComm |
| 3 | **Promo density** (`originalPrice`) | 8 | 3 | Cheap aggregation, strong "right now" story |
| 4 | **Cross-retailer price spread** | 10 | 5 | Highest wow; needs product matching |
| 5 | **`pricePerUnit` true value** | 7 | 3 | Easy, differentiated |
| 6 | **Per-retailer availability map** | 7 | 2 | Easy extension of stockout card |
| 7 | **`recentSales` cross-retailer** | 7 | 3 | Deepens the best existing aha |
| 8 | **`reviewCount` volume leader** | 6 | 2 | Easy; "review moat ≠ shelf" |
| 9 | **`rating` quality vs visibility** | 6 | 2 | Easy quality-gap angle |
| 10 | **`badge` density (+Prime)** | 6 | 2 | Easy; surface Prime + default-buy |

**Highest-value data we already have but aren't using:** `seller` (1P/3P) and the **cross-retailer price spread** — both uniquely Nimble, both squarely in the CPG executive's pain set. The cheapest immediate wins are **`productUrl` click-through** (live proof) and surfacing **`pricePerUnit` / `rating` / `reviewCount`** beyond the raw table.

These feed directly into Roadmap §6 ("Pricing & availability showcase") in `IMPLEMENTATION_ROADMAP.md`. No code changed — analysis only.
