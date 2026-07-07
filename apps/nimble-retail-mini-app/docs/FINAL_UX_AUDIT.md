# FINAL UX AUDIT

**Lens:** does the interface *feel* like a company a VP wants to talk to — premium, confident, effortless? Or like a dense internal tool?
**Date:** 2026-06-02 · Be brutal.

---

## PART 5 — UX audit

### Information hierarchy
- **Strong:** the hero answer is unmistakably the biggest thing; "3 Things We Found" reads as the second beat; the matrix has real weight.
- **Weak:** the hero's *biggest* element is the *least* surprising fact (brand + %). Visual weight ≠ information value. The most differentiated content (matrix) is third in the stack and only reached by scrolling.
- The **freshness timestamp** — our single most important credibility signal — is a quiet mono line inside a dark panel. It should be hero-adjacent and loud.

### Spacing & layout
- Generous, modern, breathes well. `max-w-5xl`, consistent rounded-3xl cards, good vertical rhythm. This part is genuinely premium.
- **But the page is long.** Hero → 3 things → matrix → run my brand → toggle → ask → localization → conversion → raw = 8–9 full viewport heights. That's a *report*, not a *booth interaction*.

### Visual density
- Individual sections are well-balanced (not cluttered). The problem is **cumulative**, not per-section: too many sections in sequence.
- **Alternating light/dark** (light hero card → light findings → dark matrix → light run-my-brand → dark "what we see" → dark selling → light localization) creates a slightly restless rhythm. It can read as "premium contrast" or "inconsistent theming" depending on execution. Right now it's borderline. Pick a deliberate pattern (e.g., dark = "live/real-time signals," light = "your analysis") and make it a rule.

### Mobile experience
- Functional and verified (matrix doesn't overflow at 390px; tap targets OK). But:
  - The **cycling cross-retailer preview stacks below** the hero copy → the best curiosity hook is offscreen on first paint.
  - **Scroll fatigue is worse on mobile** — 8–9 sections becomes a very long thumb-scroll for someone standing at a booth.
  - **Run My Brand requires typing** on a phone — high friction in a noisy hall.

### Scroll fatigue
- **The #1 UX risk for the booth goal.** The CTA and several differentiators live past the point where a casual scanner quits. Every section after the matrix is at risk of never being seen.

### Card usage
- Consistent and clean. Slight over-reliance: nearly everything is a rounded card, which flattens hierarchy (when everything is a card, nothing stands out). The matrix earns its container; the share-of-shelf + KPIs (now cut) did not.

### CTA placement
- Header pill ("Visit Booth") = always visible (good).
- Sticky CTA (side panel desktop / bottom bar mobile) = appears only after results (good pattern) — but the copy is *soft*: "Run your own category live — then come see us, we'll pull it together." For a conversion goal at a booth, this is under-asking.
- The primary email/booth conversion block is at the **very bottom**, after raw shelf. Most won't reach it.

### Interactive elements
- Search, chips, retailer tabs, Run My Brand, Ask, refresh, brand drawer — all work. **Possibly too many ways to interact** for a 30-second visit. Interactivity is a 5-minute-demo virtue; for a scan, it's friction.

### Verdicts
- **Feels premium:** dark/gold palette, the matrix, product photography, count-up animations, the floating header pill.
- **Feels cluttered:** the cumulative section count; everything-is-a-card.
- **Feels unfinished:** the soft/placeholder CTA copy ("we'll pull it together"); the quiet freshness stamp; demo-vs-live ambiguity.
- **Feels enterprise-grade:** the cross-retailer matrix and the localization table. These two carry the "serious platform" impression.

---

## PART 9 — Polish audit (ranked by impact)

| # | Issue | Type | Impact | Notes |
|---|---|---|---|---|
| 1 | **"Demo mode · sample data" badge** | Credibility | 🔴 Critical | A *data* company showing "sample data" at its own booth detonates the freshness pitch. If running offline, relabel ("Live sample · pulled today"); ideally run live. |
| 2 | **~20s live pull at the booth** | Loading | 🔴 Critical | Conference attention is seconds. The honest `ScanProgress` is good, but 20s of "reading shelves" loses people. Pre-warm + cap first paint to ~2 retailers. |
| 3 | **Payoff gated behind a search action** | Flow | 🔴 Critical | Landing shows a marketing hero, not a result. (See Product audit P1.) |
| 4 | **CTA buried + soft copy** | Conversion | 🟠 High | Primary ask is bottom-of-page; sticky copy under-asks. |
| 5 | **Freshness stamp is too quiet** | Credibility | 🟠 High | Our best proof point is a mono caption. Promote it. |
| 6 | **Scroll length / fatigue** | UX | 🟠 High | 8–9 sections; differentiators risk never being seen. |
| 7 | **Hero headline assumes "you run DSA reports"** | Copy | 🟡 Med | Alienates CMO/Retail Media who don't self-ID as the DSA buyer. |
| 8 | **Mobile: preview + matrix below the fold** | Mobile | 🟡 Med | The wow stacks under copy on phones. |
| 9 | **Light/dark section alternation** | Visual consistency | 🟡 Med | Make it a deliberate rule, not incidental. |
| 10 | **Run My Brand typing friction** | UX | 🟡 Med | Prefill/one-tap; don't make a standing attendee type. |
| 11 | **"Example" preview vs "Live" result distinction** | Demo/live clarity | 🟢 Low | Actually handled honestly today — keep, just make sure it never reads as the live number. |

**Loading-state note (positive):** the decision to *never* show a fake answer in live mode (honest scan until the real shelf lands) is the right call and protects credibility. Don't regress it — just make the wait *feel* shorter.

**Demo-vs-live (the throughline):** today the only signal is the badge wording. At minimum, the booth build must be unambiguous within 1 second whether this is real. This is the highest-leverage polish item in the whole app.
