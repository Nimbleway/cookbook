# Ratings & Reviews Intelligence — Data-Quality Evaluation

**Question:** Is ratings/reviews data available and reliable enough to build surprising, executive-grade findings?
**Short answer:** **Partially. Recommend DEFER** for the cross-retailer version; an **Amazon-only "loved but buried" finding** is the only bulletproof option, and it's close to an insight previously declined.

---

## 1 · Data quality (empirical, 3 live categories)

| Field | Amazon | Walmart | Target |
|---|---|---|---|
| `rating` coverage | **100%** (24/24) | ~95% (14–23 / 14–24) | **0%** (0/24) |
| `reviewCount` coverage | ~65% (14–17 / 24) | ~95% | **0%** |

**Implications:**
- **Target returns no ratings or review counts at all.** Any cross-retailer rating comparison or matrix row would show Target blank — which at a booth reads as "the product is broken," not "the retailer doesn't expose it."
- **Amazon is the strongest surface:** 100% ratings, and crucially it *also* carries `recentSales` (~100%) and `rank` on the same rows — so on Amazon alone we can compare **visibility vs rating vs actual sales**.
- **Walmart** is strong on ratings/reviews but lacks `recentSales`, so the "best-selling but buried" angle isn't available there.

---

## 2 · Which proposed analyses survive the data?

| Proposed analysis | Verdict | Reason |
|---|---|---|
| Highest Rated Brand (cross-retailer) | 🔴 No | Target blank breaks the cross-retailer claim. |
| Most Reviewed Brand (cross-retailer) | 🔴 No | Same gap. |
| Visibility vs Rating Gap | 🟡 Amazon/Walmart only | Defensible *within* a single retailer; cannot be cross-retailer. |
| Visibility vs Review-Count Gap | 🟡 Walmart (best), Amazon (partial) | Walmart review coverage is strong. |
| **"Most visible ≠ highest rated / best-selling"** | 🟢 **Amazon-only, reliable** | Amazon has rating + reviewCount + recentSales + rank together. |

---

## 3 · The one strong version (if we build anything)

A **single Amazon-scoped finding**, framed honestly:

> *"On Amazon — where every product is rated — the most visible energy drink (#1) holds a 4.3. Three products buried below #8 rate 4.7+ with thousands more reviews. The shelf is rewarding spend, not satisfaction."*

- Reliable (Amazon ratings are 100%).
- Genuinely surprising → "I didn't know that."
- **Risk to manage:** it's adjacent to the trust-vs-visibility insight previously declined. And it must be explicitly **Amazon-scoped** ("On Amazon…") so no one infers we're hiding Target/Walmart.

### Where Claude helps (if built)
- Deterministic: find the rank↔rating↔reviews↔sales mismatch on Amazon.
- **Claude interprets:** writes the "loved but buried / rewarding spend not satisfaction" narrative and the one-line implication. Deterministic template fallback for demo safety.

---

## 4 · Scoring

| Dimension | Score (1–5) | Note |
|---|---|---|
| Executive Value | 4 | "Loved but buried" is compelling. |
| Nimble Differentiation | 3 | Ratings are widely available elsewhere; the *cross-retailer* angle (our differentiator) is exactly the part the data can't support. |
| Conference Appeal | 4 | Strong surprise — undercut by the single-retailer caveat. |
| Ease of Understanding | 5 | Instantly clear. |
| Implementation Effort | **Med** | Must special-case Target (exclude, never blank), Amazon-only framing, graceful absence. |

---

## 5 · Recommendation

**Defer for launch.** Reasons:
1. The differentiating version (cross-retailer) is the one the data **cannot** support (Target = 0).
2. The only bulletproof version is **single-retailer (Amazon)**, which weakens the cross-retailer story that is the app's whole thesis.
3. It overlaps a previously-declined insight.
4. Paid vs Organic delivers a stronger, more reliable, *cross-retailer* surprise for less effort — better use of the same launch slot.

**Revisit when:** Target ratings become available via the agent, **or** we explicitly decide the Amazon-only "loved but buried" finding is worth a clearly-scoped slot. If we do, build it as one finding inside "3 things," not a new section.
