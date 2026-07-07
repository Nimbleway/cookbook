# Final Nimble + Claude Intelligence Review

**The lens:** *Nimble discovers. Claude explains.* Not "dashboard + AI summary."

## Honest assessment of where Claude is today

| Touchpoint | What Claude does now | Verdict |
|---|---|---|
| Hero line (`/api/insights`) | Was a streamed interpretation; hero now uses deterministic `heroCopy` | 🔴 **Effectively dead** — route exists, barely used. Remove or repurpose. |
| **Ask Nimble** (`/api/ask`) | Structured Answer/Why/Evidence/Action over the data | 🟢 Genuine value — but verbose (4 parts) and buried |
| **Earned vs Bought verdict** (`/api/paid-organic`) | One-line "earned vs bought" read + so-what | 🟢 Good — real interpretation, demo-safe fallback |
| **Monitoring "what we'd watch"** (`/api/monitoring`) | Forward-looking watch line | 🟢 Good — turns a teaser into advice |
| Email summary | Narrative report intro | 🟡 Summary, not insight |
| **Run My Brand** | **No Claude at all** — deterministic templates | 🔴 The biggest miss |

**Bottom line:** Claude is currently a *thin amplifier* (one-liners on top of deterministic numbers). It's not yet doing the thing only an LLM can: **finding the cross-retailer pattern in a brand's footprint and naming it.** That's where "I didn't know that" lives.

## Where Claude should create value (pattern-finding, not summarizing)

The data has per-brand, per-retailer, paid/organic detail. A dashboard can't say *"Bloom is invisible on Amazon but owns Walmart"* in plain English — **Claude can.** Target these:

1. **Run My Brand → a brand signature.** Today: "close the {gap}-pt gap." That's the same story for every brand. Instead, Claude reads the brand's `perRetailer` + sponsored/organic split and names its **pattern**:
   - *"Bloom is under-indexed on Amazon — strong on Walmart, absent where the volume is."*
   - *"Red Bull's lead is rented — 77% of its shelf is paid."*
   - *"Celsius wins organically but barely shows up in sponsored — cheap to defend, exposed to a spender."*
   - *"Monster owns Target but not Walmart — your strength is concentrated."*
   Deterministic engine detects the pattern type (concentration / paid-reliance / organic-strength / retailer-skew); Claude writes the sentence. **This is the single highest-value Claude addition.**

2. **Cross-retailer "why."** The engine states *that* leaders differ; Claude can hypothesize *why this kind of category* splits (assortment, private label, ad intensity) — one careful, hedged sentence.

3. **Ask Nimble** — already pattern-capable; tighten format (below).

## Ask Nimble format — tighten from 4 parts to 3
Current: Answer · Why It Matters · Evidence · Recommended Action (verbose, prose-heavy "Evidence" array). Move to a crisp **executive triplet**:

> **Finding** — one line.
> **Why it matters** — one line.
> **Do this** — one imperative line.

Drop the multi-bullet Evidence block (it's the "prose-heavy" part). Keep one inline number in the Finding. Faster to read, more executive.

**New suggested prompts** (replace the generic "What's surprising?"):
- "Is my brand winning organically or paying for it?"
- "Which retailer should I attack first?"
- "Who's most exposed to losing the lead?"
- "Where am I overpaying vs the shelf?"

## Recommendations (scored)

| # | Recommendation | Exec Impact | Nimble Diff | Conf Value | Effort |
|---|---|---|---|---|---|
| 1 | **Run My Brand: Claude-written brand signature** (pattern, not "close the gap") | **High** | **High** | **High** | Med |
| 2 | Ask Nimble → 3-part Finding/Why/Do; new prompts | High | Med | High | Low–Med |
| 3 | Remove/repurpose the dead `/api/insights` hero route | Low | Low | Low | Low |
| 4 | Cross-retailer "why" — one hedged Claude line | Med | High | Med | Med |

**Principle for all:** deterministic owns every number (demo-safe, never fabricated); Claude owns the *sentence that explains it*. Every Claude call keeps a deterministic fallback.

## Verdicts
**Must change before launch:** #1 (brand signature — fixes the "same story" problem and is the strongest Nimble+Claude moment) + #2 (Ask format).
**Nice to have:** #4 cross-retailer why.
**Do not build:** chatbot free-for-all, multi-turn memory, Claude generating numbers, AI "summaries" of sections that already speak for themselves.
