# Launch Checklist

**Status:** pre-launch polish complete. Next step is **deployment + user testing — not Sprint 4.** Feature development is stopped.
**Date:** 2026-06-01

---

## Pre-launch polish — done ✅

| # | Item | What changed | Verified |
|---|---|---|---|
| 1 | **Demo/live/cached clarity** | Server declares the data source (`X-Nimble-Source: demo\|cache\|live`); UI shows an unmistakable badge — **Demo data · sample shelf** (amber) / **Indexed sample · pulling live (n/3)** (while loading) / **Live · just pulled · {time}** / **Live · cached · {time}**. Landing eyebrow states "Live · pulled on demand…" or "Demo mode · sample data". | Badge + eyebrow confirmed on first paint |
| 2 | **Agent marquee removed** | Deleted `meet-our-agents.tsx` and its landing slot (logo-soup, no curiosity/conversion value). | Not present in DOM |
| 3 | **Opportunity Score removed** | Dropped the opaque 0–100 KPI; the Opportunity verdict now uses plain language ("winnable / concentrated", with a recommended action) — no mystery number. | "Opportunity Score" absent from UI |
| 4 | **Brand normalization across all engines** | Fixed the real gap: per-retailer summaries now aggregate **canonical** rows (not raw), so cross-retailer leaders/topBrand are normalized too. Share, verdicts, threat/opportunity, Run My Brand, cross-retailer, email all run on canonical brands. | Live: Monster Energy→Monster; Ghost/Celsius variants consolidated |
| 5 | **Walmart fallback + error messaging** | Partial-data path confirmed graceful: a failed retailer never breaks the experience; the source line lists only retailers that **responded** and notes which "didn't respond this pull"; raw error strings are never shown to the user. | Degradation verified by design + copy |
| 6 | **Cross-retailer impossible to miss** | Section moved to #2 (right after the verdict) and **rendered eagerly** (no scroll-gate), so the strongest differentiator can't be missed in 30s. | Section order: Verdict → Cross-Retailer → … |
| 7 | **Localization = capability only** | Copy stays strictly "Nimble can pull by ZIP/city/DMA — on request"; National column is real/live, city columns explicitly locked. No fabricated local data. | Copy reviewed |

**Build:** ✅ compiles · **Lint:** ✅ clean · **Mobile (390px):** ✅ no overflow · **Desktop:** ✅ verdict-first order intact.

---

## Deployment checklist (config — not features)

- [ ] **Vercel env vars:** `NIMBLE_API_KEY`, `ANTHROPIC_API_KEY`, `NIMBLE_{AMAZON,WALMART,TARGET}_SERP_AGENT_ENDPOINT`, `NEXT_PUBLIC_EVENT_NAME`, `NEXT_PUBLIC_BOOTH_NUMBER`, `NEXT_PUBLIC_BOOTH_URL`. (Email send is intentionally not wired — capture works without it.)
- [ ] **Smoke test in prod:** one prepared category (instant preview → live swap), one own-keyword search, one Refresh Live Data, one Download PDF.
- [ ] **Confirm data-state badge** shows correctly in prod (live just-pulled vs cached on a repeat search).
- [ ] **Mobile pass** on a real phone over conference Wi-Fi (latency reality check).
- [ ] **Booth config:** event name + booth number render in the bar/header/CTA.
- [ ] Note: the re-demo cache is **per-instance** on Vercel — repeat-search speedup is best on a warm instance; not shared across cold starts (acceptable for a booth).

## User-testing focus (what to watch, not what to build)

- Does the **cross-retailer "different leaders"** moment land as the "I didn't know that"? (It's the wedge.)
- Do prospects **reach and use Run My Brand**, or stop at the category verdict?
- Does **own-search latency** lose anyone? If so, steer reps to prepared categories first.
- Any **brand still fragmenting** (a sub-line not rolled up)? Capture it → add to the force list / catalog.
- Does anyone probe **localization**? Confirm the capability framing holds (no "show me LA" disappointment).

## Known, accepted limitations (roadmap — do NOT build now)

- **Live latency** 9–24s on a fresh own-search (inherent to live; masked by preview).
- **Localization** is a capability teaser, not live data (needs Nimble-side geo — see `LOCALIZATION_VALIDATION.md`).
- **Seller 1P/3P** not shown (SERP data insufficient — see `SELLER_DATA_AUDIT.md`).
- **Email delivery/tracking** not wired (capture + Download PDF work; Resend/Slack/Sheet is a config task).
- **Re-demo cache** is per-instance (not globally shared).

---

## Recommendation

**GO for deployment + user testing.** All pre-launch polish from `LAUNCH_READINESS_ASSESSMENT.md` (items #1–#5) is complete; the open items are config and observation, not engineering. **Stop feature development.** Ship, watch real prospects, and let booth feedback — not a Sprint 4 — drive whatever comes next.
