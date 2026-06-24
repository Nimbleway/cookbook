# Brand Mention Monitor

**A triage console, not a list of mentions.**

Every mention is pre-scored and pre-sorted so your marketing team sees the one post that matters before it spirals — not the 400 that don't. Three layers: the crisis alert, the priority-score queue, and the situational-awareness dashboard.

Built for marketing teams. Powered by Nimble + Claude.

---

## What it does

Each run produces a fully interactive `brand_mentions.html` triage console rendered directly in Claude, plus `brand_mentions.md`. Sections render in this order:

1. **Brand header** — brand name, the date window scanned (set during onboarding), and total mention count.
2. **Sources searched** — collapsible panel showing exactly which sources were queried this run, each with a ✓ and a mention-count badge. Click any source to filter the feed to that platform. Source selection is market-specific (see below).
3. **Score summary** — four aggregate meters: Reach, Velocity, Sentiment risk, Opportunity.
4. **Market visibility (share of voice)** — a donut with a clean white center showing your brand's share of conversations vs competitors. Hover a segment or legend row to preview its share; **click** to open a detail panel with that brand's mention count, trend vs last window, estimated reach, sentiment split, and a one-line "Signal" takeaway.
5. **Crisis alert cards** — full-width decision cards for any mention scoring 80+. Each shows the excerpt, all four scores, published date, velocity signal, suggested owner, response window, and a specific draft action. These appear before the feed because the 2-hour response window is the whole point.
6. **Mentions by platform** — horizontal bars, clickable to filter the feed (synced with the sources panel).
7. **Geographic breakdown** — an interactive world map with mention hotspots colored by activity tier. Hover a point for a summary; **click** it to pin a panel listing every source from that location, each with an `↗ open` link to the exact article/post URL.
8. **Mention feed (2-column grid)** — sorted by composite score. Each card shows all four score pips plus a velocity arrow (↑ accelerating / → stable / ↓ declining), tier badge, platform tag, publish date, and source link. Click to expand for score breakdown and suggested action.
9. **Filter bar** — Tier + Score filters, stacked, with dismissable chips.

---

## The four scoring dimensions

| Score | What it measures | Color |
|---|---|---|
| **Reach** | Author follower count + domain authority + amplification | Blue |
| **Velocity** | Rate of engagement growth vs. baseline — the differentiator | Amber |
| **Sentiment** | Negative risk / positive opportunity, with sarcasm handling | Red / Green |
| **Risk topic** | Hits on flagged themes: legal, safety, outage, exec, fraud | Red |

**Composite** = `(Reach × 30%) + (Velocity × 30%) + (max(Sentiment, RiskTopic) × 25%) + (Opportunity × 15%)`

Velocity is the differentiator. A mention at 200 engagements flat is noise. The same 200 climbing 50%/hour is the story — and the 40-minute window where a response changes the outcome.

---

## Tier system

| Tier | Score | Action | Owner | Window |
|---|---|---|---|---|
| 🔴 Crisis | 80–100 | Route immediately | PR + Legal + Leadership | <2 hours |
| 🟠 Watch | 50–79 | Assign owner, monitor velocity | Marketing / Comms | <24 hours |
| 🟢 Engage | any, positive high-reach | Amplify / thank / share | Marketing / Social | 48 hours |
| ⚪ Log | <50, no risk | No action, searchable record | — | — |

---

## Source profiles (market-specific)

Source selection is based on where your audience actually talks — not a fixed list scanned equally. This also shapes the risk-topic dictionary and authority weighting (an "outage" is a crisis term for a SaaS platform but meaningless for a snack brand; a 5K-follower industry analyst can outweigh a 500K-follower lifestyle influencer for a B2B vendor).

| Brand type | Primary sources | Deprioritized |
|---|---|---|
| B2B enterprise SaaS | LinkedIn, G2, Capterra, HN, r/sysadmin, r/devops, trade press | TikTok, Instagram, Facebook |
| Consumer brand | TikTok, Instagram, X, Reddit, YouTube, Facebook, Trustpilot | HN, LinkedIn, trade press |
| Regulated (finance, healthcare) | News press, regulatory sites, journalist accounts, LinkedIn | TikTok, Instagram |
| Regional / non-English | Local-language news, regional platforms, local influencer accounts | English-only global platforms |
| Startup / developer tool | HN, Reddit, GitHub, Dev.to, X, ProductHunt | Facebook |

The sources-searched panel in the output shows exactly which were queried this run, with a mention-count badge on each.

---

## Requirements

- **Claude** (claude.ai or Claude desktop app)
- **Nimble MCP connector** — required. Enable in Claude under Settings → Connectors → Nimble.

The geographic map loads country geometry from a public CDN (world-atlas via jsDelivr/unpkg/cdnjs). If all are blocked by your network, the map shows "Map unavailable" and every other section still works.

---

## Installation

1. Download `brand-mention-monitor.skill`
2. In Claude, open **Settings → Capabilities → Skills**
3. Click **Upload skill** and select the downloaded file

---

## How to use

```
Monitor mentions of [brand name]
```

Other triggers: "What are people saying about [brand] this week?" / "Run a brand sweep for [brand]" / "Find high-risk mentions of [brand]"

**Claude automatically:** profiles the brand (industry, B2B/B2C, geography, audience), resolves alternate names and hashtags, and selects a source profile before asking anything.

**Claude then confirms four things:**
1. Brand + category, plus any competitors to track alongside
2. Date range to scan (default: last 7 days — say "last 30 days", "June 1–15", etc.)
3. Depth — quick scan or deep sweep (default: deep)
4. Routing — who gets flagged for Crisis-tier mentions (default: marketing team)

---

## Date range

The date window is chosen in onboarding using natural language ("last 7 days", "June 1–15", "this week"). It is shown in the output header as a read-only label (e.g. "Window: Jun 11–18, 2026"). To scan a different period, just ask Claude to re-run with the new range.

---

## Re-running

Say "refresh" or "re-run" — Claude sweeps for net-new mentions. Crisis and Watch items carry forward until marked handled. Claude re-checks velocity on any Watch-or-higher mention from the previous run — if engagement grew 20%+ since last check, it upgrades the tier.

**Cadence:** routine → daily or every few days · launches → every 6–12h for 48h · crisis → every 1–2 hours

---

## File structure

```
brand-mention-monitor/
├── SKILL.md
├── README.md
├── AGENT_SETUP.md
└── references/
    ├── template.html
    └── sources.md
```

Built with [Nimble](https://nimbleway.com) + [Claude](https://claude.ai)
