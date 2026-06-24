# Consumer Sentiment Monitor

**See what customers, competitors, and the market are saying — before it becomes a problem.**

A Claude skill that tracks sentiment for any product or brand across review platforms, social media, developer communities, and press — and surfaces shifts, churn signals, emerging themes, and spike alerts as an interactive dashboard directly in Claude.

---

## What it does

Each run produces a fully interactive `sentiment.html` rendered in Claude, plus a structured `sentiment.md` for downstream use. The output includes:

- **Platform scorecards** — clickable cards for G2, Trustpilot, Reddit, HN, and more. Click any platform to filter the quote wall to that source only.
- **Sentiment theme bar chart** — top positive and negative themes by mention volume, color-coded
- **Competitive comparison table** — side-by-side scores, top praise theme, top complaint theme, and trend direction for each brand
- **Verbatim quote wall** — filterable by brand and sentiment (positive / negative / watch). Filters stack — selecting "Nimble + Negative" shows only negative Nimble quotes.
- **Emerging themes tracker** — table of newly detected themes with first-seen date, mention count, and status badge. Click any row to expand the source mentions behind it.
- **Signal of the day** — the single highest-signal finding from the run, surfaced at the top

---

## Requirements

- **Claude** (claude.ai or Claude desktop app)
- **Nimble MCP connector** — required for real-time web research. Enable in Claude under Settings → Integrations → Nimble. Nimble gives this skill access to review platforms, Reddit, paywalled press, LinkedIn, and other sources standard AI agents can't reach.

---

## Installation

1. Download `consumer-sentiment-monitor.skill`
2. In Claude, open **Settings → Skills**
3. Click **Install skill** and select the downloaded file
4. Claude will confirm installation and show an onboarding message on first use

---

## How to use

**Trigger phrase:**
```
Run a sentiment report on [brand name]
```

**Other ways to start:**
- "What are people saying about [brand] this month?"
- "How does our sentiment compare to [competitor A] and [competitor B]?"
- "Any new G2 reviews we should know about?"
- "Is there anything negative trending about us right now?"

**Claude will ask three questions before running:**

| Question | Default |
|---|---|
| Scope — just this brand, or vs competitors? | Brand only |
| Time window — how far back to look | 30 days |
| Depth — surface scan or deep (all tiers) | Deep |

Say **"just run it"** to skip to defaults immediately.

---

## Example run

```
You:    Run a sentiment report on Nimble vs Firecrawl and Exa. 30 days. Deep.

Claude: Running now — deep sweep across G2, Trustpilot, Reddit, HN,
        LinkedIn, and news for Nimble, Firecrawl, and Exa over the
        last 30 days.

        [runs research using Nimble]
        [renders interactive sentiment.html directly in Claude]
        [offers sentiment.html + sentiment.md as downloads]
```

---

## Output details

### Interactive HTML (`sentiment.html`)
Rendered directly in Claude. Fully interactive:
- Click any platform scorecard (G2, Trustpilot, Reddit, HN) to filter the quote wall to that source
- Brand filter pills and sentiment filter pills stack independently — select any combination
- Click any row in the emerging themes table to expand and read the source mentions behind it

### Structured Markdown (`sentiment.md`)
Machine-readable output with consistent schema — suitable for feeding into downstream agents, pipelines, or reporting tools. Includes per-brand signal blocks, platform scores, verbatim quotes with metadata, and emerging theme inventory.

---

## Saved preferences

On first use, Claude asks whether to save your preferences. If you save them, future runs skip the setup questions entirely. Say **"change settings"** at any time to update.

---

## Sources

This skill searches across 5 tiers:

| Tier | Sources |
|---|---|
| Review platforms | G2, Trustpilot, Capterra, Gartner Peer Insights, TrustRadius, PeerSpot, GetApp, Software Advice, App Store, Google Play, Chrome Web Store, Product Hunt |
| Community & social | Reddit, Hacker News, X/Twitter, LinkedIn, Dev.to, Hashnode, Medium, Substack, Discord, Quora, Facebook Groups |
| Tech press | TechCrunch, The Verge, Wired, Ars Technica, VentureBeat, InfoQ, ZDNet, TechRadar, The Register, SiliconAngle |
| Independent & niche | YouTube, Stack Overflow, GitHub, Indie Hackers, Glassdoor, Blind, AlternativeTo |
| Forward-looking | Job postings, changelog activity, community forum trends, newsletter mentions, conference coverage |

Full source list, query patterns, and extraction guidance are in `references/sources.md`.

---

## Saved themes reference

`references/themes.md` contains a curated library of positive and negative sentiment themes for enterprise software — used to map extracted quotes to patterns quickly. Themes include: ease of use, pricing, support quality, performance, integration depth, UX complexity, onboarding friction, vendor lock-in, and more.

---

## File structure

```
consumer-sentiment-monitor/
├── SKILL.md                    — skill definition and instructions
└── references/
    ├── template.html           — required HTML output template
    ├── sources.md              — source query patterns across 5 tiers
    └── themes.md               — enterprise software sentiment theme library
```

---

## Built with

[Nimble](https://nimbleway.com) + [Claude](https://claude.ai)

Nimble provides real-time web data access — including review platforms, paywalled press, Reddit, LinkedIn, and JavaScript-heavy pages — that standard AI agents cannot reach.
