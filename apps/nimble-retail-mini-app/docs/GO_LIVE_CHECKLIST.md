# GO-LIVE CHECKLIST — Nimble Retail Intelligence

**Date:** 2026-06-02 · **Verdict: ✅ GO.** Smoke-tested clean on demo (desktop + mobile) and live. One config toggle is the only thing standing between you and a great live booth.

---

## Smoke test results (just run)

| Scenario | Result |
|---|---|
| Demo · desktop (1280) | ✅ 0 errors · all sections · no overflow |
| Demo · mobile (390) | ✅ 0 errors · all sections · no overflow |
| Live · desktop | ✅ 0 errors · honest scan → lands ~23s cold · LIVE badge · per-unit matrix · brand-split gone |

Verified in every pass: freshness badge · interpretation kicker · 3 Things (with "so what") · cross-retailer matrix (Avg price **/ unit**) · Run My Brand (absent band per-unit + the bandage CTA) · Ask Nimble visible & structured · "Book 15 minutes" CTA · 3 retailer favicons load.

---

## Pre-launch config (the one that matters is #3)

```
# Required for live
NIMBLE_API_KEY=...                         # + agent endpoints (defaults to public agents)
ANTHROPIC_API_KEY=...                       # hero line, Ask, email summary

# 🔴 BOOTH-CRITICAL — without this the first live scan is ~23s, not ~0.4s
PREWARM_LIVE=true

# Conference
NEXT_PUBLIC_EVENT_NAME="Shoptalk 2026"
NEXT_PUBLIC_BOOTH_NUMBER="A-42"
NEXT_PUBLIC_BOOKING_URL="https://nimbleway.com/book-a-demo"
NEXT_PUBLIC_LANDING_CATEGORY="energy drinks"   # auto-loaded first impression; "" = show hero instead

# Optional — turns "Email it" from lead-capture into an actual send
RESEND_API_KEY=...
RESEND_FROM="Nimble Retail <...>"
```

---

## The one launch-critical action
**Set `PREWARM_LIVE=true` and hit the page once after deploy** to prime the cache on the long-running instance. The cold live pull is ~23s; cached it's ~0.4s. The auto-loaded landing is your first impression — it must be instant. (Landing category warms first by design.)

## Booth-day runbook
1. Deploy with the env above. Open the page once → confirms the LIVE badge and primes the cache.
2. If venue wifi is unreliable: set `FORCE_DEMO=1` (or unset `NIMBLE_API_KEY`) → instant, fully-functional demo mode, labeled "Sample shelf." Nothing breaks.
3. Hand out the QR → it lands on a live result (no search needed), and "Book 15 minutes" works for anyone who scans and walks away.

## What's true now (the bar this clears)
- **Nimble = foundation, Claude = amplifier.** 100% of on-screen insight is Nimble→deterministic; 3 grounded Claude calls (hero interpretation, structured Ask, email summary) — none can fabricate.
- **Insight, not dashboard:** 3 Things lead with the surprise and end in an action; cross-retailer matrix is the centerpiece; pricing is **pack-adjusted** (no fake "% cheaper"); brands consolidate on live data.
- **Converts:** auto-run landing · loud freshness · the absence "bandage" · durable Book-a-demo · brand-personalized email.

## Nice-to-have (post-launch, non-blocking)
- Deliberate light/dark section "rule" doc for future contributors.
- Warm-on-boot (vs first-request) prewarm so even the very first cold visitor is instant.
- Bump the hero one-line interpretation to Sonnet if Haiku reads shallow on some categories.

**Bottom line: ship it.** Demo mode is bulletproof for any scenario; for live, flip `PREWARM_LIVE=true` and prime once.
