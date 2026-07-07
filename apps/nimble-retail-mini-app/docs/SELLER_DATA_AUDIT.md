# Seller Field Validation Audit

**Goal:** measure real quality/coverage of the `seller` field before building Seller Intelligence.
**Method:** live Nimble SERP pulls, raw `data.parsing` inspected (not just normalized output).
**Samples:** Protein Bars · Energy Drinks · Sparkling Water · Cat Food × Amazon / Walmart / Target (12 pulls).
**Date:** 2026-06-01

---

## Headline finding

**Seller-of-record is not available from the SERP agents in a form that supports a 1P-vs-3P module.** It's a PDP-level datapoint; search results don't carry it — except Walmart, which returns a single 1P value ("Walmart.com") with **no third-party variance observed at all.**

---

## Per-retailer results

### Amazon (`amazon_serp`)
| Metric | Value |
|---|---|
| Rows sampled | 240 (60 × 4) |
| Seller fill rate | **0%** |
| Seller field present | **None** |
| % 1P / 3P | n/a |
| Classification confidence | n/a — no field |
- **Fields returned:** `product_name, asin, price, currency, rating, review_count, prime_eligible, amazons_choice, sponsored, recent_sales, store_location, agent_zip_code, position`.
- **Limitation:** the Amazon SERP agent does not return seller / "ships from and sold by". That's a product-page (offer/buy-box) field, not a search-result field.

### Walmart (`walmart_serp`)
| Metric | Value |
|---|---|
| Rows sampled | 90 (one keyword pull errored/timed out) |
| Seller fill rate | **88%** |
| Seller key | `product_seller` |
| Example values | **"Walmart.com" (only value seen)** |
| % 1P (of all rows) | 88% |
| % 3P | **0%** |
| % unknown (empty) | 12% |
| Classification confidence | **High for the value present** ("Walmart.com" → unambiguously 1P) |
- **Limitation:** every populated value across ~79 filled rows was "Walmart.com". Either only 1P ranks on these category page-ones, or the agent doesn't surface 3P marketplace seller names on SERP. **No 1P-vs-3P contrast exists to visualize.** One keyword (energy drinks) errored — minor reliability note.

### Target (`target_serp`)
| Metric | Value |
|---|---|
| Rows sampled | 120 (30 × 4) |
| Seller fill rate | **0%** |
| Seller field present | **None** |
| % 1P / 3P | n/a |
| Classification confidence | n/a — no field |
- **Fields returned:** `product_name, product_brand, product_price, is_sponsored, tcin, dpci, store…`. No seller.
- **Limitation:** Target SERP is effectively all-1P and doesn't expose seller anyway.

---

## Verdict on coverage

| Test | Result |
|---|---|
| Is seller present across retailers? | ❌ Only Walmart |
| Is there 1P/3P variance to show? | ❌ None observed (Walmart = 100% "Walmart.com") |
| Can we classify confidently? | ⚠️ Only Walmart 1P; Amazon/Target = no data |
| Can we show "3P resellers on your shelf"? | ❌ Not from SERP — would require fabrication |

**Coverage is NOT strong enough for a data-driven Seller Intelligence module.** Building one would mean either showing a one-sided "all 1P" panel (no insight) or inventing 3P (violates the credibility principle that gated all of Sprint 1).

---

## Recommendations

**1. Core module or capability teaser? → Capability teaser only.**
The SERP data can't substantiate 1P/3P penetration. Treat it like Localization: a clearly-labeled capability, never fabricated.

**2. Best UI treatment.**
A locked teaser card — "Who's *really* selling your shelf?" — pattern-matched to `localization-teaser.tsx`: the 1P/3P split shown as a locked/blurred placeholder with a "Nimble pulls seller-of-record at the product level" CTA. Optionally surface the one honest real fact we *do* have: a small "Walmart sells these directly (1P)" confirmation, kept factual.

**3. Best executive verdict format.**
Not a live verdict (no data to back it). A single capability line in the teaser: *"Third-party resellers, MAP erosion, lost buy-box — Nimble can see who controls your shelf, product by product. Talk to us."*

**4. Best "wow moment".**
The wow — *"third parties are selling YOUR brand"* — is real and powerful, but it's a **conversation-starter pitch**, not an on-page live reveal. Deliver it as the teaser's hook + a booth talking point, not a fabricated stat.

---

## If we want Seller Intelligence to be REAL (future, not "already available")

Seller-of-record lives on the **product page**, not the SERP. To make this a true module:
- Add a second Nimble step — a **product/extract (PDP) pull** on the top N page-one SKUs — to fetch buy-box seller, offer count, and 1P/3P. Nimble's Extract/product agents do this; it's a genuine capability, just a **new pipeline** beyond the SERP data we have today.
- That's a Sprint 3+ initiative with real cost/latency — scope it deliberately, don't bolt it on.

**Side finding (bonus):** the Amazon SERP rows include `agent_zip_code` and `store_location`. That suggests **localization may be genuinely feasible** with these agents — a stronger, real candidate than Seller for turning a current teaser into live data. Worth its own validation pull.

---

## Recommendation: do NOT build Seller Intelligence as a core module

Coverage failed the gate. Options:
- **Best:** ship a small **Seller capability teaser** (low effort, honest, keeps the differentiation talking point) **and** run a **localization validation pull** (the `agent_zip_code`/`store_location` finding hints localization could become *real* — higher payoff than Seller).
- Then **stop and polish.**

This is exactly why we validated before building — the headline "3P on your shelf" wow isn't backed by the data we have, and we will not fabricate it.
