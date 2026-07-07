# HERO STRATEGY REVIEW

**Question:** should the hero be one static headline, or adapt to user intent?
**Answer:** adapt. One message can't serve four very different mindsets. This doc reviews the problem, critiques the current price line, scores options, and recommends a dynamic system. **Design only — not implemented.**
**Date:** 2026-06-02

---

## 1. Why one static headline fails

A single hero is asked to land for four different people:

| Who | What they searched | What they want in 3 seconds |
|---|---|---|
| CMO / exec scanning a QR | nothing yet (default) | "What *is* this, and why is it different?" |
| Category manager | a **category** ("Energy Drinks") | "Who owns my shelf, and how do retailers differ?" |
| Brand / sales leader | a **brand** ("Quest") | "Where does *my* brand stand?" |
| Growth / SEO / retail-media | a **shopper keyword** ("best protein bar") | "What does the *shopper* actually see?" |

Today every one of those gets *"Who owns the {term} shelf right now?"* — which is right for a category, **clumsy for a brand** ("Who owns Monster? Monster."), and **wrong for a keyword** ("Who owns best protein bar?"). The framing leaks. Intent-aware heroes fix it.

**Important nuance:** the hero already varies by *divergence type* (the `heroKicker` switches on `crossRetailer[0].kind`). What it does **not** do is vary by *what the user was trying to do*. That's the upgrade.

---

## 2. Critical review — *"The same product, a different price on every shelf."*

**You don't like it. You're mostly right. Here's the precise read.**

**What it gets right**
- It's **concrete and visceral** — a CFO/CMO instantly translates it to *margin leakage / channel conflict*. That's a real "huh" reaction.
- It's **cross-retailer** (our wedge) and **time-anchored** ("right now").
- It's **falsifiable proof**, not marketing fluff.

**What it misses**
- **It's one axis.** Price is *a* story, not *the* story. It frames Nimble as a **price-monitoring tool**, which is a crowded, commoditized category (every repricer claims it). Our actual differentiator is the *whole shelf* read across retailers.
- **It's not universal.** That line only appears when price is the single largest divergence (`crossRetailer[0].kind === "price"`). For most categories the top divergence is *different leaders*, so this line isn't even the one shown — yet you saw it, which means for your test category price ranked #1 and the hero narrowed to its weakest framing.
- **It under-sells to the exec.** A VP of eCommerce doesn't lie awake over a 12% price delta; they lie awake over **losing visibility and share they can't see** because their tool watches one retailer.

**Is price too narrow a value prop? — Yes, as the *umbrella*. No, as a *proof*.**
You're correct that execs care more about **competitive visibility, share, sponsored pressure, availability, and retailer differences** than price alone. Price should be **one rotating proof among several**, never the headline thesis.

**Where I'll push back on you slightly:** don't *delete* price. A per-unit price gap is one of the most credible "I didn't know that" facts we have (and now that it's pack-adjusted, it's defensible). Keep it in the rotation as evidence — just stop letting it be the umbrella.

**The umbrella that should replace it:** **leadership/visibility divergence** — *"a different brand wins on every retailer."* It's broader (implicates share, strategy, and media spend, not just margin), it's almost always true when leaders differ, and it's the one fact that makes an exec say "wait, what?"

---

## 3. Scoring framework

Each option scored 1–10 on the five goals you set. (E = Executive appeal, Cf = Conference appeal, Cu = Curiosity, D = Nimble differentiation, Cv = Conversion.)

### Default / demo hero (pre-search)
| Option | E | Cf | Cu | D | Cv | Avg |
|---|---|---|---|---|---|---|
| A. *"Your reports show last week. See your shelf right now."* (current — freshness-led) | 6 | 6 | 5 | 6 | 6 | 5.8 |
| B. *"A different brand wins on every retailer. Most teams only watch one."* | 9 | 8 | 9 | 9 | 8 | **8.6** |
| C. *"Amazon, Walmart & Target don't tell the same story."* | 7 | 8 | 8 | 8 | 7 | 7.6 |
| D. *"Three retailers. Three #1 brands. One live search."* (conference-punchy) | 8 | 9 | 9 | 9 | 8 | **8.6** |

*Read:* the current freshness headline is the weakest — it assumes the reader already feels "stale report" pain (a DSA buyer), alienating the CMO/keyword personas. B and D tie; **B leads with the insight, D leads with the rhythm.** Recommend a B/D hybrid (see Recommendations).

### Category hero
| Option | E | Cf | Cu | D | Cv | Avg |
|---|---|---|---|---|---|---|
| A. *"Who owns {category}? Depends which shelf you check."* | 8 | 8 | 9 | 9 | 8 | 8.4 |
| B. *"{Leader} leads {category} on {topRetailer} — but not on {otherRetailer}."* (dynamic) | 9 | 8 | 9 | 9 | 8 | **8.6** |
| C. *"{category}, across every shelf, live."* (generic) | 5 | 5 | 4 | 6 | 5 | 5.0 |

*Read:* dynamic + concrete (B) beats the rhetorical question (A) when the data supports it; A is the perfect fallback when leaders *don't* differ.

### Brand hero
| Option | E | Cf | Cu | D | Cv | Avg |
|---|---|---|---|---|---|---|
| A. found — *"{Brand} is #{rank} of {N} — and missing on {absentRetailer}."* | 9 | 7 | 8 | 8 | 9 | **8.2** |
| B. absent — *"{Brand} isn't on page one for {category}. See who's taking the space."* | 9 | 8 | 9 | 8 | 9 | **8.6** |
| C. *"How does {Brand} compare across retailers?"* (question) | 7 | 6 | 7 | 6 | 7 | 6.6 |

*Read:* the brand hero must be **state-aware** (found vs absent). The absent case (B) is the highest-conversion moment in the whole app — lead with it when it's true.

### Keyword hero
| Option | E | Cf | Cu | D | Cv | Avg |
|---|---|---|---|---|---|---|
| A. *"Search '{keyword}' — here's what a shopper actually sees. It's not the same everywhere."* | 7 | 8 | 9 | 8 | 7 | 7.8 |
| B. *"For '{keyword}', Amazon shows {brandA}. Walmart shows {brandB}."* (dynamic) | 8 | 8 | 9 | 9 | 8 | **8.4** |
| C. *"See the shopper's first screen for '{keyword}'."* | 6 | 7 | 7 | 6 | 6 | 6.4 |

*Read:* B (dynamic contrast) is the strongest; wrap it in A's "what a shopper actually sees" framing.

---

## 4. Recommendations

1. **Best default →** B/D hybrid: **headline "A different brand wins on every retailer."** + a rotating live proof line (leaders → price → sponsored → availability) + freshness as the credibility note. Leads with the wedge, keeps price as *one* proof.
2. **Best category →** dynamic **"{Leader} leads {category} on {topRetailer} — but not on {otherRetailer}."** Fallback (leaders don't differ): "Who owns {category}? Depends which shelf you check."
3. **Best brand →** state-aware: **absent** → "{Brand} isn't on page one for {category}. See who's taking the space." · **found** → "{Brand} is #{rank} of {N} on the {category} shelf — and missing on {absentRetailer}."
4. **Best keyword →** dynamic **"For '{keyword}', {topRetailerA} shows {brandA}. {topRetailerB} shows {brandB}."** under the wrapper "This is what a shopper actually sees."

---

## 5. Two implementation prerequisites (flagging now, before build)

1. **Intent detection.** Classify the query: **category** if it matches `CATEGORIES`/aliases; **brand** if `canonicalizeBrand` returns high confidence (or it's in `CANONICAL_BRANDS`); else **keyword**. This is cheap and deterministic — no AI.
2. **Brand intent needs category context (the hard part).** Searching "Monster" today runs a SERP for *Monster* and returns mostly Monster products — there are no competitors to compare against, so a "how do you compare" hero has nothing to stand on. For the brand hero to work, a brand query should resolve to the **brand's category** (e.g., Monster → Energy Drinks) and run *that* shelf, then locate the brand within it. We already have brand→category rosters in `mock-data` for demo; for live we'd infer the category (a small lookup, or a "did you mean Energy Drinks?" chip). **This is the one real engineering decision** — call it before building the brand hero.

See `DYNAMIC_HERO_RECOMMENDATIONS.md` for the exact copy, tokens, and data sources.
