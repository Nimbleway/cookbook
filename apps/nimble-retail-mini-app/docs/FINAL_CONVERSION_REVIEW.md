# Final Conversion & CTA Review

**Context: Shoptalk, NO booth.** Every "Visit Booth #A-42" must die. This is the #1 must-fix — it's currently in the header, the sticky CTA, localization, Run My Brand, and the emailed report.

## 1. Booth language footprint (remove all of it)

| File | Current | Replace with |
|---|---|---|
| `site-header.tsx` | "Visit Booth #A-42" / "Say hi" | **"Get your category review"** / "Let's talk" |
| `sticky-cta.tsx` | "Visit Booth #{n}" | **"See your brand live"** |
| `localization-teaser.tsx` | "· Visit Booth #A-42" | **"Talk to us about your markets"** |
| `run-my-brand.tsx` (`BrandCta`) | "Booth #A-42" | **"Get my brand's review"** |
| `report-html.ts` (`ctaSection`) | booth number | **"Book a custom category review"** |
| `conference-bar.tsx` | "come meet us at the event" | "We built this for Shoptalk" (drop booth/meet) or remove bar |
| `config.ts` | `boothNumber`, `boothUrl` | retire `boothNumber`; rename `boothUrl` → `contactUrl` (→ book-a-demo) |
| `ai-context.ts` `ANALYST_SYSTEM` | "at a conference booth" + "via Nimble Web Search Agents" | "live digital-shelf intelligence" (drop booth + the SERP-agent jargon) |

Implementation: collapse `boothNumber`/`boothUrl` into one `contactUrl` → `bookingUrl` (book-a-demo). Set `NEXT_PUBLIC_BOOTH_NUMBER=""` is not enough — the *fallback copy* still says "Meet us at the event"; rewrite the strings.

## 2. CTAs should sell the gap between this glimpse and the full product
Every CTA must answer **"why talk to Nimble?"** — by pointing at what this one-time view *can't* show.

| Placement | Now | Recommended |
|---|---|---|
| Header | "Visit Booth" | **"Get your category review →"** |
| Run My Brand (found) | "See {brand} in every market, live" ✓ (already good) | keep, drop booth chip → "Get my brand's review" |
| Run My Brand (absent) | "Want to get {brand} onto this shelf?" ✓ | keep, fix CTA chip |
| Markets / Localization | "Unlock any market" ✓ | keep, drop booth |
| Track Over Time | "Start tracking this shelf" ✓ | keep — strongest FOMO CTA |
| Global sticky | booth | **"This is one shelf, one moment. See your whole category, continuously →"** |

**FOMO lines to seed across CTAs** (curiosity, not feature lists):
- "This is one shelf at one moment. Nimble watches every retailer, every market, continuously."
- "A one-time report can't show you what changed this morning."
- "See your brand across every retailer, market, and store — not just page one."

## 3. Report capture — "Email me this" is weak

| Element | Now | Recommended |
|---|---|---|
| Headline | "Take this report with you" ✓ | keep |
| Button | "Email it" | **"Send me this category review"** |
| Top-bar CTA | "Email me this" | **"Get this review in my inbox"** |
| Frame | digital-shelf briefing | "Your {category} category review — what differs across retailers, where your brand stands, what to do" |

The value is "a **category review**," not "an email." Name the artifact.

## 4. Monitoring teaser (already built) — keep, sharpen the ask
The locked Share-of-Shelf / Share-of-Voice charts are the right FOMO. One change: the CTA should make the *recurring* value explicit — **"Start watching this category"** (not just "this shelf"), and the "what we'd watch" Claude line should name the specific metric to track.

## Recommendations (scored)

| # | Recommendation | Exec Impact | Nimble Diff | Conf Value | Effort |
|---|---|---|---|---|---|
| 1 | Remove ALL booth language; unify to one contact/booking CTA | High | Low | **High (factual)** | **Low** |
| 2 | Rewrite CTAs as FOMO ("this is one moment; Nimble watches always") | High | High | High | Low |
| 3 | "Email it" → "Send me this category review" | Med | Low | Med | Low |
| 4 | Monitoring CTA → "Start watching this category" | Med | High | Med | Low |

## Verdicts
**Must change before launch:** #1 (booth removal — factual error on the floor) + #3 (report language). Both Low effort.
**Nice to have:** #2 FOMO rewrites, #4 monitoring CTA wording.
**Do not build:** lead-gen forms beyond email, gated "unlock" walls, multi-step capture. One email field at peak intent is the right amount of friction.
