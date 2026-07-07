# Launch Readiness Assessment

**Date:** 2026-06-01 · Companion to `FINAL_PRODUCT_REVIEW.md`. No new features — clarity/curiosity/differentiation/conversion only.

---

## Recommendation: **B — Launch after minor polish**

Not A (one real credibility item shouldn't ship as-is), not C (there are no architectural or strategic blockers — the core is strong and on-wedge).

### Why B, defended
- **The core works and is differentiated.** Verdict-first → cross-retailer differences → Run My Brand is the right story, and the cross-retailer moment is genuinely something competitors don't show this way. The thing the app is *for* — start a conversation by showing the unseen — is present and credible.
- **The blockers are not features; they're clarity and emphasis.** Every gap in the review is fixable with copy, a badge, ordering, and *removal* — not new building. That's the definition of "minor polish," and it materially raises conversion and protects credibility.
- **Why not A:** the demo-vs-live ambiguity is a real risk for a *data* company. Shipping a first impression that might be mock data, unlabeled, invites "is any of this real?" — the one objection we can least afford. It's a one-line fix; do it first.
- **Why not C:** the two hard constraints (live latency, localization-as-claim) are **known, bounded, and acceptable for a booth** — latency is masked by the instant preview and framed honestly; localization is already labeled a capability, not data. Neither warrants holding launch. They're roadmap, not blockers.

### Minimum pre-launch polish (all reduction/clarity — no features)
1. **Kill the demo-vs-live ambiguity (P0).** Make it unmistakable on first paint whether data is the indexed sample or a live pull. One badge + one line of copy. This is the only true gate.
2. **Make the cross-retailer wedge unmissable in 30s.** It's the memorable differentiator; ensure a 30-second visitor cannot leave without seeing "the shelves look different." Emphasis/ordering, not new UI.
3. **Trim the focus taxes** (per "Remove 25%"): drop the agents marquee, the Opportunity Score, and one of {auto-cycling preview card / discovery tabs}; demote the raw-shelf explorer. Sharpens the story; removes skepticism bait.
4. **Don't oversell localization.** Keep it explicitly a *capability* ("Nimble can pull by ZIP/DMA — ask us"), never implied as live. Protects credibility if probed.
5. **Frame the live wait as proof, not lag.** The 9–24s pull should read as "we're reading the real shelves right now," not a spinner — copy only.

### Explicitly NOT pre-launch (roadmap / accepted risk)
- Real localization (needs Nimble-side geo — see `LOCALIZATION_VALIDATION.md`).
- Seller 1P/3P (data not available — see `SELLER_DATA_AUDIT.md`).
- Email delivery/tracking infra (capture works; wiring is a config task).
- Any new section, chart, or AI surface.

---

## Readiness scorecard

| Dimension | State | Gate? |
|---|---|---|
| Product clarity | Good once demo/live is labeled | **#1 fixes it** |
| Curiosity | Strong (cross-retailer, price gap, demand≠visibility) | No |
| Differentiation | Strong on cross-retailer + live; weak/over-claimed on local | Manage copy |
| Conversion | Clear, well-timed CTA; depends on reaching section 2–3 | #2 protects it |
| Conference effectiveness | Good; latency + focus-taxes are the risks | #3, #5 mitigate |
| Technical | Build/lint clean, mobile no overflow, runs on Vercel | No |

## Go/No-Go
**GO — conditional on items #1–#3** (demo/live clarity, wedge unmissable, trim focus taxes). Those are hours, not days, and all reduction/clarity. #4–#5 are copy passes that should ride along. Localization and seller stay clearly framed as capabilities. Ship it.

**The honest risk we're accepting:** on a prospect's *own* live search, a slow or thin pull can blunt the wow. We accept it because (a) the prepared categories carry the demo, (b) the preview masks most latency, and (c) the alternative is holding launch for something inherent to live data. Watch booth reactions; if own-search latency is killing conversions, lead reps toward the prepared categories first.
