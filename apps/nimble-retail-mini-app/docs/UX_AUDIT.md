# UX Audit

**App:** Nimble Retail Intelligence Experience (conference/prospect-facing)
**North star:** Not a dashboard — a discovery experience that makes a prospect think *"this is far more useful than a DSA report"* and *"let me run my own category."* Goal: generate conversations for Nimble.
**Date:** 2026-06-01

---

## 0. TL;DR

The experience is **visually strong, fast, mobile-clean, and well-sequenced** (3-act flow, instant preview, on-brand dark theme). The two things holding it back from being bulletproof in front of executives:
1. **Skepticism risk** from the fabricated "shelf is moving" content (see `DATA_PIPELINE_AUDIT.md` §5).
2. **The live-data story is implicit** — first-time users aren't told *"these are live Amazon/Walmart/Target search results,"* and demo-vs-live isn't visually distinct.

---

## 1. Hero (`hero-search.tsx`)

- Headline: *"Your reports show last week. See your shelf right now."* — sharp DSA contrast.
- Sub: shelf changes 15–30×/day; "Nimble reads **Amazon**, **Walmart** & **Target** live" (brand-colored).
- Search supports **category / brand / keyword** (placeholder says so); prepared category chips with brand-logo clusters; trust strip ("Live digital shelf intelligence", "Pulled live, in seconds", "Read by Nimble AI").
- **Gaps:** in **demo mode** the headline's "right now" promise is technically mock data, and the UI doesn't signal demo vs live; brand/keyword examples (Celsius, "sugar free energy drinks") aren't surfaced as chips to spark "run your own."

## 2. CTAs (`sticky-cta.tsx`, `site-header.tsx`, `conference-bar.tsx`)

- Soft "meet us at the event" — sticky panel (desktop) / bottom bar (mobile), appears only after value is on screen; header gold pill; optional event banner.
- **Gaps:** no booth number; no earlier curiosity hook ("Curious how your brand compares?"); single CTA archetype (all "meet us"), no "run your category" / "book a custom audit" variants.

## 3. Information hierarchy

3-act flow is sound:
- **Act 1 — Answer + proof:** hero insight → retailer tabs → KPI row → find-your-brand → share-of-shelf + live-shelf-pulse.
- **Act 2 — Why it matters:** insight cards (Claude top-3 when ready) → selling-now.
- **Act 3 — Go deeper:** Ask-the-Data → retail explorer → email report.

Lazy reveal on scroll, count-ups, no horizontal overflow at 390px.

## 4. Verdict grid

| Lens | Findings |
|---|---|
| ✅ Working | Fast instant preview; clean dark theme matching nimbleway.com; 3-act sequencing; find-your-brand personalization; share-of-shelf centerpiece; mobile responsive; CTA timing (after value). |
| ⚠️ Weak | Live-data story implicit; no booth #; single CTA type; rating/reviews/price-per-unit/1P-3P not surfaced; insight cards are generic vs exec-verdict framing. |
| ❓ Confusing | Demo vs live indistinguishable on first load; cached-vs-live "yesterday" framing (mock ≠ a real prior report). |
| 😮 Curiosity | "See your shelf right now"; find-your-brand FOMO; retailer toggle (shelf changes per retailer). |
| 🤯 Wow | Share-of-shelf dominance; demand-≠-visibility ("selling right now"); cross-retailer differences. |
| 🚩 Skepticism | "Shelf is moving" deltas / 9am→now timeline / "changed N× today" / Re-scan-that-only-animates — fabricated; a sharp analyst will catch it. |

## 5. Missing: localization

No ZIP / city / DMA / store-level anywhere. Localization is one of Nimble's biggest differentiators and is a strong **"Retail Intelligence Is Local"** module (National vs NYC vs LA vs Chicago) — see Roadmap §8. Must be **real (if Nimble SERP agents accept geo params) or a clearly-labeled capability teaser** — never fabricated local numbers.

## 6. UX priorities (detail in `IMPLEMENTATION_ROADMAP.md`)

1. **Remove the skepticism trigger** — strip fabricated freshness; reframe as "What we see right now."
2. **Make the live story explicit** — "Results generated from live Amazon, Walmart & Target search results powered by Nimble"; clear demo/live badge.
3. **Exec-verdict cards** — Biggest Winner / Threat / Opportunity / Pricing Watchout / Availability Watchout / Most Competitive Retailer.
4. **Stronger discovery + CTAs** — brand/keyword example chips; earlier "run your category" / booth-# CTA.
