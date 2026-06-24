# Portfolio Briefer

**Track what's moving across your portfolio — before anyone tells you.**

A Claude skill that researches a list of companies using Nimble's real-time web access and delivers a signal-focused briefing covering funding moves, leadership changes, product launches, competitive shifts, and brand mentions across social channels — rendered as an interactive dashboard directly in Claude.

---

## What it does

Each run produces a fully interactive `briefing.html` rendered in Claude, plus a structured `briefing.md` for downstream use. The output includes:

- **Signal heatmap** — all companies × all signal dimensions (funding, legal, leadership, product, sentiment, competitors), color-coded at a glance
- **Brand mentions chart** — grouped bars by channel: Reddit, HN, press, Twitter/X, LinkedIn — shows share of voice across your portfolio
- **Interactive activity timeline** — one row per company, clickable event dots that expand into full signal details (type, source, date, implication)
- **Funding comparison bar chart** — total raised per company, color-coded by round type
- **Per-company signal cards** — color-coded findings with headline, implication, and source metadata

---

## Requirements

- **Claude** (claude.ai or Claude desktop app)
- **Nimble MCP connector** — required for real-time web research. Enable in Claude under Settings → Integrations → Nimble. Nimble gives this skill access to sources standard AI agents can't reach: paywalled news, LinkedIn, Reddit, JavaScript-heavy pages, and more.

---

## Installation

1. Download `portfolio-briefer.skill`
2. In Claude, open **Settings → Skills**
3. Click **Install skill** and select the downloaded file
4. Claude will confirm installation and show an onboarding message on first use

---

## How to use

**Trigger phrase:**
```
Run a briefing on [company A], [company B], [company C]
```

**Other ways to start:**
- "What's new with my portfolio this week?"
- "Update me on Stripe, Rippling, and Ramp"
- "Anything I should know about these companies before my call tomorrow?"

**Claude will ask three questions before running:**

| Question | Default |
|---|---|
| Companies — confirm or update the list | What you named |
| Time window — how far back to look | 7 days |
| Depth — surface (faster) or deep (more thorough) | Deep |
| Competitors — flag competitor moves too? | Off |

Say **"just run it"** to skip to defaults immediately.

---

## Example run

```
You:    Run a briefing on Exa, Firecrawl, Tavily, and Parallel

Claude: Got it — a few quick questions before I run:
        1. Companies: Exa, Firecrawl, Tavily, Parallel — anything to add or remove?
        2. Time window: How far back should I look? (default: 7 days)
        3. Depth: Surface-level or deep? (default: deep)
        4. Competitors: Flag competitor moves too? (default: off)

You:    Good list, 7 days, deep, yes on competitors

Claude: [runs research using Nimble]
        [renders interactive briefing.html directly in Claude]
        [offers briefing.html + briefing.md as downloads]
```

---

## Output details

### Interactive HTML (`briefing.html`)
Rendered directly in Claude. Fully interactive:
- Click any dot on the activity timeline to expand signal details
- Signal heatmap color-coded by severity (green / amber / red)
- Brand mentions chart shows per-channel breakdown with share-of-voice summary

### Structured Markdown (`briefing.md`)
Machine-readable output with consistent schema — suitable for feeding into downstream agents, pipelines, note systems, or databases. Includes per-company signal blocks, source URLs, dates, and implication sentences.

---

## Saved preferences

On first use, Claude asks whether to save your preferences. If you save them, future runs skip the setup questions entirely. Say **"change settings"** at any time to update.

---

## Sources

The skill searches across: press and news outlets, Reddit, Hacker News, Twitter/X, LinkedIn, company blogs, GitHub, funding databases (Crunchbase, PitchBook), SEC filings, and more. Full source list and query patterns are in `references/sources.md`.

---

## File structure

```
portfolio-briefer/
├── SKILL.md                    — skill definition and instructions
└── references/
    ├── template.html           — required HTML output template
    └── sources.md              — source query patterns and guidance
```

---

## Built with

[Nimble](https://nimbleway.com) + [Claude](https://claude.ai)

Nimble provides real-time web data access — including paywalled sources, LinkedIn, JavaScript-heavy pages, and review platforms — that standard AI agents cannot reach.
