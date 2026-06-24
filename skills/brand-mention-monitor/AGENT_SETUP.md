# Brand Mention Monitor — Agent Setup

## Required connector

**Nimble MCP** must be connected before running this skill.

1. Open Claude → **Settings → Connectors**
2. Find **Nimble** and click **Connect**
3. Authorize with your Nimble account

If you don't have a Nimble account: [nimbleway.com](https://nimbleway.com)

---

## Trigger phrases

```
Monitor mentions of [brand name]
```
```
What are people saying about [brand] this week?
```
```
Run a brand sweep for [brand] — last 30 days
```
```
Find high-risk mentions of [brand]
```
```
Check social media for [brand] mentions
```
```
Brand monitoring for [brand] — 7 days, deep
```

---

## What Claude does before asking anything

**Step A — Brand variants resolved automatically:**
Claude searches for alternate spellings, common misspellings, hashtags, product names, and nicknames for the brand. All confirmed variants are added to search queries silently — you never see this step.

**Step B — Brand context + source profile established:**
Claude does a quick sweep to determine the brand's industry, business model (B2B/B2C), geography, and audience. This selects the market-specific source profile (where to actually listen) and calibrates scoring — what counts as "high reach" differs for a niche B2B tool vs a consumer app with millions of users. It also sets the risk-topic dictionary for the industry.

---

## Setup questions

| # | Question | Default |
|---|---|---|
| 1 | Brand confirmed + any competitors to track alongside? | What Claude found |
| 2 | Date range — what period to scan (natural language) | Last 7 days |
| 3 | Depth — quick scan or deep sweep | Deep |
| 4 | Routing — who to flag for Crisis-tier mentions | Marketing team |

Say **"just run it"** to accept all defaults.

**Inline config example:**
```
Monitor mentions of Nimble — last 14 days, deep, flag anything Crisis-tier to our PR lead
```

The date range is natural language — "last 7 days", "June 1–15", "this week", "since the launch". It is baked into the output header as a read-only label; there is no date picker in the output.

---

## Output

- **Interactive triage console** rendered directly in Claude
- **`brand_mentions.html`** — downloadable interactive report
- **`brand_mentions.md`** — structured markdown for downstream use

### Sections (in render order)

1. Brand header — name, window label, mention count
2. Sources searched — collapsible, click a source to filter the feed
3. Score summary — Reach / Velocity / Sentiment risk / Opportunity meters
4. Market visibility — share-of-voice donut (white center), click a brand for detail
5. Crisis alerts — full-width cards, only if Crisis-tier mentions exist
6. Mentions by platform — clickable bars
7. Geographic breakdown — interactive map, click a point for exact sources
8. Mention feed — 2-column scored cards
9. Filter bar — Tier + Score filters with chips

### Interacting with the output

| Element | How it works |
|---|---|
| Sources panel | Click the header to expand; click any source row to filter the feed to that platform |
| Score summary | Four aggregate meters across all mentions this run |
| Market visibility donut | Hover a segment/row to preview share; click to open the brand detail panel (mentions, trend vs last window, reach, sentiment split, signal) |
| Crisis cards | View thread (exact URL) · Mark handled |
| Platform bars | Click a bar to filter the feed to that platform (synced with sources panel) |
| Geographic map | Hover a hotspot for a summary; click to pin a panel listing every source from that location with an `↗ open` link |
| Score pips on cards | Four pips — R (reach) / V (velocity, with arrow) / S (sentiment) / Opp (opportunity) |
| Velocity arrow | ↑ accelerating (red) · → stable (amber) · ↓ declining (green) |
| Card expand | Click any card for the score breakdown + suggested action |
| ↗ source links | Open the exact post, thread, or article — never a homepage |
| Filters | Tier + Score, stacked, shown as dismissable chips |

---

## The four scoring dimensions

**Reach** — how many people could see this mention. Follower count, domain authority, amplification (reposts/upvotes). A 50-follower rant ≠ a journalist's post.

**Velocity** — rate of engagement growth vs. baseline. The differentiator: it separates "viral forming" from "stale". A mention climbing 50%/hour is the story; the same mention flat is noise.

**Sentiment** — negative risk / positive opportunity, with sarcasm handling. Negative + high reach = escalate; positive + high reach = amplify.

**Risk topic** — hits on flagged themes (defect, lawsuit, exec, safety, outage). Company-specific: "outage" is a crisis term for a SaaS platform, meaningless for a snack brand.

**Composite** = `(Reach × 30%) + (Velocity × 30%) + (max(Sentiment, RiskTopic) × 25%) + (Opportunity × 15%)`

The feed sorts by composite; the tier badge (Crisis / Watch / Engage / Log) is the primary label and the pips tell you why something ranked where it did.

---

## Tier routing

| Tier | Composite | Owner | Window |
|---|---|---|---|
| 🔴 Crisis | 80–100 | PR + Legal + Leadership | <2 hours |
| 🟠 Watch | 50–79 | Marketing / Comms | <24 hours |
| 🟢 Engage | positive high-reach | Marketing / Social | 48 hours |
| ⚪ Log | <50 | — | searchable only |

---

## Re-running

```
Refresh the brand sweep
```
```
Re-run — what's new since yesterday?
```

Net-new mentions only. Unresolved Crisis and Watch items carry forward; velocity is re-checked and tiers upgrade if engagement accelerated.

**Recommended cadence:**
- Routine: daily or every few days
- Around launches / campaigns: every 6–12h for the first 48h
- Crisis mode: every 1–2 hours

---

## Troubleshooting

**Source links open a homepage instead of the post**
→ Re-run and tell Claude: "Use the exact post URL — not the platform homepage. For Reddit it should look like `https://reddit.com/r/subreddit/comments/abc123/title`, for X like `https://x.com/username/status/1234567890`."

**No Instagram or TikTok mentions found**
→ These platforms block standard search — Nimble uses `focus:"social"` mode to access them. Confirm Nimble is connected and try again.

**The geographic map says "Map unavailable"**
→ The map loads country geometry from a public CDN (world-atlas via jsDelivr/unpkg/cdnjs). If your network blocks all three, the map can't draw — every other section still works. Ask your network admin to allow those CDN domains.

**Scores seem too low / too high**
→ Tell Claude the brand's typical mention volume and audience size. The Step B context calibration shapes scoring thresholds. You can also say "Treat this as a low-volume B2B brand" or "This is a high-volume consumer brand."

**Wrong sources for my brand**
→ Tell Claude the brand type explicitly ("this is a regulated fintech" / "this is a consumer beauty brand") or name the specific accounts, subreddits, or outlets to prioritize. Claude re-selects the source profile.

**Missing mentions you expected to see**
→ Tell Claude the specific account name, subreddit, or outlet. Claude runs targeted queries for those sources specifically.

**Skill not triggering**
→ Use one of the exact trigger phrases above
→ Confirm the skill is installed in Settings → Capabilities → Skills
