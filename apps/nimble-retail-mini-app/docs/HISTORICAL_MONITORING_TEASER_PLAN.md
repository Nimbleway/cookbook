# Historical Monitoring Teaser — Plan

**Goal:** communicate that Nimble can monitor the shelf **over time** — without fabricating a single trend, delta, or data point.
**Verdict:** ✅ **Build a tasteful, visibly-locked teaser.** High conference appeal, high Nimble differentiation, low data risk. It's the literal payoff of the homepage thesis ("your reports can't keep up with the shelf").

---

## 1 · Should this exist? Yes — and it's the natural conversion bridge

- Continuous, over-time monitoring **is** Nimble's core product. The whole app currently shows a single point-in-time pull; the one thing a static competitor report *also* can't do is *keep watching*. Naming that is the strongest reason to talk to us.
- It's already woven into the copy ("This is today." / "what we see right now" / "a weekly report would miss this"). The teaser makes the implicit promise explicit and gives it a home.
- It sits perfectly between the analysis and the **"book 15 minutes"** capture: *we showed you today → here's everything we'd watch for you → let's set it up.*

---

## 2 · The hard rule: communicate the capability, never fake it

**Do NOT:**
- Render a line chart with invented historical points.
- Show any "% change", "up/down vs last week", arrows, or sparklines with fabricated data.
- Imply we already have history for this brand.

**DO:**
- Make it unmistakably a **locked / future-state** panel (blur, lock icon, "starts when you do" language).
- List the **real metrics** we track over time (these we genuinely have *today's* value for): Share of Shelf, Price, Availability, Sponsored Visibility, Search Rank.
- Anchor honestly: *"This is today's snapshot. Nimble turns it into a live feed — here's what we'd watch."*

---

## 3 · Look & placement

**Look — a locked "Track this over time" panel:**

```
┌─ TRACK THIS OVER TIME ──────────────────────  🔒 ─┐
│  This is today. The shelf changes daily.           │
│  Nimble watches it so your reports don't go stale.  │
│                                                     │
│   Share of Shelf      ▁▂▃▅▆  ·····  (locked)        │
│   Price               ▃▃▂▄▅  ·····  (locked)        │
│   Availability        ▅▅▄▅▅  ·····  (locked)        │
│   Sponsored Visibility▂▄▆▇█  ·····  (locked)        │
│   Search Rank         ▄▃▃▂▁  ·····  (locked)        │
│   └ blurred / greyed, clearly illustrative ─        │
│                                                     │
│  ▸ Today's starting point:                          │
│     Quest 31% share · avg $1.42/unit · 2 OOS · 38% paid │
│     (these are real — from this pull)               │
│                                                     │
│  [ Start tracking this shelf →  book 15 minutes ]   │
└─────────────────────────────────────────────────────┘
```

- The mini bar shapes are **explicitly decorative/blurred placeholders** (a lock badge + reduced opacity make it obvious they're not data). No axis, no numbers on them.
- The **"today's starting point"** line uses the *real* current-pull values — honest, and it makes the "this becomes data point #1" idea concrete.

**Placement:** right **before Report Capture** (after Ask Nimble). It's the "here's the ongoing value → let's start" hand-off into the CTA. Register in `NAV_SECTIONS` as `{ id: "monitoring", label: "Track over time" }` with `scroll-mt-32`.

---

## 4 · Where Claude adds value (utilize Claude)

Claude makes the teaser **personalized and specific** instead of generic boilerplate — describing *what would be worth watching for this exact shelf/brand*, which is forward-looking guidance, **not** fabricated history.

| Layer | Owner |
|---|---|
| The locked metric list + "today's starting point" values | **Deterministic** (real current pull) |
| A 1–2 line **"what we'd watch for you"** tailored to this shelf | **Claude** — e.g. *"Given how much of this shelf is paid, I'd watch Monster's sponsored share weekly — that's where leadership will flip first."* |
| Tailoring to a brand when "Run My Brand" was used | **Claude** — *"For Celsius, the metric to watch is its Walmart rank gap vs Amazon."* |

- Reuse the existing structured Claude approach; feed it only the deterministic snapshot.
- **Demo-safe fallback:** a generic-but-honest line ("We'd track share, price, availability, sponsored visibility and rank — daily.") if Claude is unavailable. The teaser stands on its own; Claude personalizes it.

---

## 5 · Scoring

| Dimension | Score (1–5) | Note |
|---|---|---|
| Executive Value | 4 | Monitoring is the recurring-value use case execs buy. |
| Nimble Differentiation | 5 | Continuous monitoring is core Nimble; a static report can't. |
| Conference Appeal | 5 | The FOMO close — directly delivers the homepage promise. |
| Ease of Understanding | 5 | A locked "track over time" panel explains itself. |
| Implementation Effort | **Low–Med** | Pure UI + one optional Claude line; no new data. |

---

## 6 · Credibility checklist (must pass before stage)

- [ ] No fabricated numbers anywhere in the panel — bars are visibly decorative (blur + lock).
- [ ] "Today's starting point" values are pulled from the real current insight payload.
- [ ] Copy never claims we already have history ("starts when you do", future tense).
- [ ] The Claude line is forward-looking ("we'd watch…"), never a stated past change.
- [ ] Works in demo mode with the deterministic fallback line.

---

## 7 · Build checklist

1. **Component:** `monitoring-teaser.tsx` — locked panel, real "starting point" line from `InsightPayload`, decorative blurred bars, CTA to `bookingUrl`.
2. **Claude line:** optional structured/short call → "what we'd watch"; deterministic fallback string.
3. **Placement:** before `report-capture`; add to `NAV_SECTIONS`; `scroll-mt-32`.
4. **Demo-mode-first:** verify with `FORCE_DEMO=1` that the panel + fallback render with no live call.
5. **Report/email:** optional one-line "Nimble can track this over time" mirror; no fake chart.
