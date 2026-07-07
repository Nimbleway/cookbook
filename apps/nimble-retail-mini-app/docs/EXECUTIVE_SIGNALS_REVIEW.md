# Executive Signals Review + Paid/Organic Data Audit

Two things in one doc, because they answer each other:
- **Part A** — the live data audit you asked for (is Paid/Organic statistically real?).
- **Part B** — the executive-signals reframe (move from dashboard → "I learned something").

**Headline finding:** the data is **robust at the category & retailer level** and **statistically weak at the per-brand leaderboard level.** That single fact drives both the audit verdicts and the reframe: lead with retailer/category *signals*, retire the per-brand *metrics*.

---

# Part A — Live data audit (5 categories, cache-bypassed)

Sample: energy drinks, protein bars, coffee, cold brew coffee, sparkling water. **326 products** total.

### 1. How many total products?
- **~24 per retailer per category**; **48–72 per category** depending on how many retailers respond (Target/Walmart occasionally short or absent).
- **326 across 5 categories.** Healthy page-one sample; thin once sliced to a single brand.

### 2. How many sponsored placements?
- **124 / 326 sponsored = 38%** overall. Per category total sponsored 21–27. Good volume.

### 3. Which retailers contain sponsored signals?
- **All three.** Amazon **always exactly 12/24 (50%)**, Target **always exactly 6/24 (25%)**, Walmart **7–9/24 (29–57%, genuinely variable)**.
- ⚠️ **Reliability flag:** Amazon's constant 12 and Target's constant 6 across *every* category strongly suggest those agents flag a **fixed positional pattern**, not true per-product ad detection. Walmart's variation looks real. **Consequence:** retailer-level *relative* paid pressure is trustworthy; *exact* per-brand sponsored counts on Amazon/Target are not.

### 4. Which fields are available?
| Field | Amazon | Walmart | Target |
|---|---|---|---|
| sponsored, price, brand, rank | ✅ | ✅ | ✅ |
| rating, reviewCount | ✅ | ✅ | ❌ 0% |
| recentSales (units sold) | ✅ ~100% | ❌ | ❌ |
| inStock (availability) | ❌ | ✅ 100% | ❌ |
| originalPrice (promo) | ❌ | rare | ❌ |
| descriptions, TCIN/DPCI, store | — | — | ✅ rich |

### 5. How many unique brands?
- **19–46 unique per category** (raw): energy 30, protein 30, coffee 46, cold brew 41, sparkling 19.
- **The shelf is highly fragmented** — only **6–19 brands per category have ≥2 placements**; the rest appear once. (Production `canonicalizeBrand` merges variants, so effective counts are a bit higher per brand — but the long tail is real.)

### 6. Variance check — is there enough to support each insight?

| Proposed insight | Verdict | Evidence |
|---|---|---|
| **Sponsored Pressure by Retailer** | ✅ **Supported** | Sponsored-% spread across retailers: **25, 32, 25, 25, 12 pts** — large & consistent (Amazon ~50% vs Target ~25%). Strong as a *directional/relative* claim. |
| **Paid Leader** | 🟡 **Partially** | #1-vs-#2 paid gap: **6, 2, 1, 0, 3**. Frequent near-ties (cold brew was a 0-gap tie). Only clear when one brand truly dominates ads (Red Bull 10/13). |
| **Organic Leader** | 🟡 **Partially** | #1-vs-#2 organic gap: **1, 1, 2, 1, 7** — usually a 1-placement margin, and often an obscure brand (Bloom, Maxwell House). Thin. |
| **Most Ad-Dependent Brand** | 🔴 **Partially → weak** | "Top dependence" is dominated by **100%-of-2-placements** noise (V8 2/2, David 2/2, Bones 3/3). Only **Red Bull (77% of n=13)** is statistically real. The current `count≥2` threshold surfaces noise. |
| **Most Efficient Organic Brand** | ✅ **Supported** | High-organic, ~0%-paid brands have real sample size: Clear American (11 org, 0%), Maxwell House (7, 0%), Bloom (9, 10%), Barebells (7, 13%). Genuinely "earned." |

### Audit conclusion
- **Robust:** category-level "% of this shelf is paid," **retailer-level** paid pressure, **leader-flips-by-retailer**, **fragmentation/concentration**, and **Amazon demand (recentSales)**.
- **Fragile:** per-brand **paid leaderboards** and **ad-dependence bars** — small-n, frequent ties, and the fixed-Amazon-12 artifact. These are the "impressive-looking but statistically weak" pieces.
- **Action on the existing Paid/Organic module:** keep the *signal* ("paid is driving this shelf, heaviest on Amazon"), **drop the per-brand dependence bars and exact per-brand %** (or gate the ad-dependence callout on n≥5, where it rarely fires). This makes it both more honest *and* more executive.

---

# Part B — Executive Signals framework

> The 5-second VP test: a VP should grasp each module's *point* in 5 seconds. If they have to read numbers to get it, it's a dashboard.

**Five signal categories** (every analysis must be one):
**Competition · Opportunity · Risk · Difference · Monitoring**

**Form:** a signal = a category chip + a plain-English claim + **at most one** supporting number + an optional "see the proof" expand. The claim is the hero; the number is evidence, not the headline.

## Module-by-module audit

| Module | Passes 5-sec VP test? | Signal type | Verdict |
|---|---|---|---|
| Hero ("Who owns the shelf right now?") | ✅ Yes | Competition | **Keep** — already a signal. |
| Cross-Retailer **lead line** ("leader flips by retailer") | ✅ Yes | Difference | **Keep** — strongest signal in the app. |
| Cross-Retailer **matrix** (5 rows × 3 cols of numbers) | ❌ No | — | **Simplify** — demote to "see the proof" under the lead line. It's a dashboard table; lead with the sentence. |
| Earned vs Bought — verdict line | ✅ Yes | Risk/Competition | **Keep** the line. |
| Earned vs Bought — **dependence bars + per-brand %** | ❌ No | — | **Remove/Simplify** — audit shows it's statistically weak *and* it reads as a dashboard. Collapse to one signal + one number (category paid % + heaviest retailer). |
| Top Takeaways ("3 things") | ✅ Yes | mixed | **Keep — this is the model.** Tag each with a category chip. |
| Run My Brand | ✅ Yes (verdict) | Competition/Opportunity | **Keep** — ensure it leads with the verdict, not the score. |
| Localization (Markets) | 🟡 Headline yes, table no | Difference/Monitoring | **Simplify** — lead with "the shelf changes by city," keep the locked table as proof/teaser. |
| Ask Nimble | n/a (interaction) | — | **Keep.** |
| Monitoring teaser | ✅ Yes | Monitoring | **Keep — the model for Monitoring.** |
| Supporting Evidence (share of shelf, what-we-see-now, selling-now, raw) | ❌ No (by design) | — | **Keep collapsed** — this is the "show me the numbers" drawer for skeptics. Fine where it is. |

**Already on-framework:** Hero, Cross-retailer lead, 3 Things, Run My Brand, Monitoring teaser.
**Simplify:** Cross-retailer matrix (demote), Earned-vs-Bought (collapse to a signal), Localization (lead with the line).
**Remove:** per-brand paid-dependence bars + exact per-brand % (weak data + dashboardy); the two thinnest "what we see right now" facts.

## The 5 strongest executive signals to add/elevate before launch

Each is **one per category, one-line, VP-graspable, and backed by data the audit confirmed is robust.** Most already exist as computed data — the work is *expressing* them as signals, not new analytics.

| # | Signal (the headline) | Category | Data backing (audited) | Why it lands |
|---|---|---|---|---|
| 1 | **"This shelf is up for grabs."** / "…locked up." | Opportunity | ✅ Strong — fragmentation (19–46 brands, thin leader gaps, top brand often <30%) | Instantly tells a VP whether to invest. Memorable. |
| 2 | **"Retailers don't agree on the winner."** | Difference | ✅ Strong — leader flips (Amazon/Walmart Monster, Target Celsius) | The #1 Nimble differentiator; one sentence beats the matrix. |
| 3 | **"Paid is buying this shelf — most on Amazon."** | Risk | ✅ Strong — 38% paid, Amazon ~2× Target (retailer-level) | Replaces the weak per-brand bars with the robust retailer story. |
| 4 | **"What sells isn't what ranks."** | Competition | ✅ Strong — Amazon recentSales (~100%) vs rank | Only *live* data reveals it — pure Nimble magic, very memorable. |
| 5 | **"This is today. Watch it move."** | Monitoring | ✅ N/A (teaser) — already built | The conversion close; makes the case for ongoing Nimble. |

> Deliberately **excluded:** "Paid Leader," "Organic Leader," and "Most Ad-Dependent Brand" as standalone headline signals — the audit shows they're small-n / tie-prone / artifact-prone. They can still appear as *supporting evidence* inside signal #3, never as the headline.

## Implementation principle (when we build)
- Give every section a **category chip** (Competition/Opportunity/Risk/Difference/Monitoring) + a **bold one-line claim** + **≤1 number** + an optional **"see the proof"** expand that holds the table/bars for the skeptic.
- No new KPI cards, no new % chips, no charts-for-charts. The 3 Things + Monitoring teaser are the template; bring every other module up to that bar.

**Net:** fewer numbers on screen, every section a sentence a VP repeats at lunch — *"I learned something,"* not *"I saw a dashboard."*
