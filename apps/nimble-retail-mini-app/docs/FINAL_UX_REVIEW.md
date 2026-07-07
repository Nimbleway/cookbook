# Final UX Review

**Lens:** VP eCommerce seeing this cold. **Mandate:** storytelling, hierarchy, visual structure, conversion, mobile, clarity. **No new features / data / AI.**
**Date:** 2026-06-02 · Review only — implementation separately approved.
**Confirmed directions:** takeaways = horizontal carousel · cross-retailer = comparison matrix · localization = market table.

---

## The core problem
It reads as **a stack of modules, not a story**. Each module is individually good; together they don't build an argument. The fixes below are all reorder / reformat / visual / copy — nothing new.

---

## 1. Hero — too big, says too little

**Now:** `hero-search.tsx` — `h1` at `text-6xl`, `pt-12 pb-12 sm:pt-16`, a large right-side cycling "Example" card competing with the search. A VP reads a lot of chrome before any value.

**Fix — compact hero (~40% shorter):**
- Tighten the headline (keep the "reports show last week → shelf right now" contrast but smaller, 2 lines max) and reduce vertical padding.
- One crisp value line: *"See any brand's shelf across Amazon, Walmart & Target — live."*
- **Search is the hero** — prominent input + the Category/Brand/Keyword example chips directly under it.
- Demote the cycling "Example" card to a slim single-line strip (or below the fold). It's a nice teaser but shouldn't own half the first screen.
- **5-second test passes:** what Nimble does (read the live shelf across 3 retailers) · why (yours is stale) · the action (search).

## 2. Latency — must feel like momentum, never "broken"

**Now:** `scan-progress.tsx` shows the honest live pull but uses **internal language** — `"Querying Amazon SERP Agent…"` (`NIMBLE_AGENTS[].name = "Amazon SERP Agent"`), `"Querying live retailer shelves"`, `"Normalizing SKUs"`.

**Fix — friendly, sequential momentum:**
- Replace the agent names with **plain verbs + retailer names**: "Analyzing **Amazon**… ✓ 60 products" → "Comparing **Walmart**…" → "Checking **Target**…" → "Building your takeaways…".
- Keep the progress bar advancing; light up a **retailer chip** as each lands (Amazon ✓, Walmart ✓, Target ✓).
- Set an honest expectation up top: *"Reading the live shelves — about 15 seconds."*
- **Banned words anywhere user-facing:** SERP, Agent, Scraper, Querying. **Use:** Analyze, Scan, Compare, Check, Retail Intelligence.

## 3. "Verdict" → Top takeaways carousel

**Now:** `executive-verdict.tsx` — `grid md:grid-cols-3` of 5 cards with a no-op `md:row-span-1` (the uneven spacing you flagged), labeled "THE VERDICT" (corporate).

**Fix — horizontal swipe carousel:**
- Rename to **"Top takeaways"** (or "What this means").
- One **scroll-snap row** of compact cards (icon · one-line headline · one-line "why" · action chip), peek-of-next-card, arrows on desktop, swipe on mobile, dots indicator.
- Eliminates the grid spacing problem and makes it scannable in seconds. Same 5 verdicts, far lighter.

## 4. Cross-retailer → comparison matrix (the differentiator)

**Now:** `cross-retailer-diff.tsx` — a dark lead block + a text list of difference sentences. It's the strongest Nimble story but reads as paragraphs.

**Fix — matrix table:**
```
              Amazon   Walmart   Target
Leader        Quest    Premier   ONE      ◄ differs
Avg price     $24.99   $21.97    $26.49   ◄ 17% spread
Sponsored     15%      31%       18%      ◄ differs
Out of stock   0        2         1
On promo      22%      41%       18%
```
- Columns = retailers (brand-colored), rows = dimensions, **divergent cells highlighted** with a one-word flag.
- One-line headline above: *"Amazon, Walmart & Target are not the same shelf."*
- All values already computed (`perRetailer`, `buildCrossRetailer`). Render change only. This becomes the visual centerpiece — "they behave differently" without reading a sentence.

## 5. Report capture — promote + gate

**Now:** `email-report.tsx` lives inline after the brand block; easy to miss; "Take this report with you."

**Fix:** a **persistent header CTA** — "Email me this report" / "Get the PDF" — present from the top but **disabled until results load** ("available after your scan"), then it activates. Keep one prominent inline capture at the end of the story (step 7). Value-led copy ("Take this live cross-retailer report with you").

## 6. Supporting evidence — insight-first, proof one tap away

**Now:** KPIs / share / what-we-see / selling-now sit in a "Supporting evidence" block far below the capture — proof feels hidden.

**Fix:** surface one proof element *with* each insight (the share-of-shelf bar under the brand answer; "what we see right now" facts near the takeaways), and make the deeper tables a labeled **"See the data"** expander right next to the claim — not a distant section. Evidence immediately available, never three sections down.

## 7. Ask Nimble — structured, moved up

**Now:** `ask-the-data.tsx` renders Claude's answer as a **prose bubble** (`whitespace-pre-wrap`), at the very bottom.

**Fix (reformat the existing call — not new AI):** constrain `/api/ask` to a structured shape and render a compact card:
- **Direct answer** (bold one-liner)
- **Evidence** (chips/bullets — the numbers it used)
- **Why it matters** (one line)
- **Recommended action** (one line)
Move it into the proof/explore zone (step 5), above the raw shelf. Keep the suggested-question chips.

## 8. Mobile (summary — full detail in FINAL_MOBILE_REVIEW.md)
Horizontal swipe (takeaways, selling-now); collapse/expand for evidence + matrix (matrix horizontal-scroll with a sticky first column); bigger tap targets; consistent spacing tokens; progressive disclosure to cut scroll fatigue.

## 9. Localization → market comparison table
Same visual language as the cross-retailer matrix: **National column real, NYC/LA/Chicago columns locked 🔒** + "unlock by market — talk to us." Capability only; no fabricated local numbers. Makes the strongest "what else Nimble can do" beat visual and consistent.

---

## Before → After (the feel)
| | Before | After |
|---|---|---|
| First screen | Big hero, cycling card, little value | Compact: value line + search + examples |
| The wait | "Querying Amazon SERP Agent (0/3)" | "Analyzing Amazon… ✓ → Comparing Walmart…" momentum |
| The point | "THE VERDICT" grid, uneven | Swipeable "Top takeaways" |
| Differentiator | Paragraphs of differences | A matrix you read in 2 seconds |
| Proof | Buried 3 sections down | One tap from each insight |
| Ask | Prose blob at the bottom | Structured answer card, mid-flow |
| Capture | Inline, easy to miss | Header CTA (gated) + a closing moment |
| Overall | Modules | A guided story |
