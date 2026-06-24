# Company Due Diligence

**Turn a company name into a risk-graded intelligence brief.**

A Claude skill that runs a structured, multi-dimensional deep dive on any company — covering financial health, legal risk, leadership credibility, customer reputation, competitive position, employment trends, and news — using Nimble to access public records, court filings, review platforms, and sources standard AI agents can't reach. Rendered as an interactive brief directly in Claude.

---

## What it does

Each run produces a fully interactive `dd_brief.html` rendered in Claude, plus a structured `dd_brief.md` for downstream use. The output includes:

- **Overall risk grade** (A–F) — computed across all 7 dimensions, displayed prominently at the top
- **TL;DR** — 3–4 sentence summary of the most important findings and overall risk profile
- **7-dimension risk scorecard** — one card per dimension, color-coded by grade, with flag count and key finding
- **Funding timeline** — horizontal timeline of all known rounds with amounts, dates, and lead investors
- **Red flags panel** — numbered list of material risks with severity badges. Filterable by severity: All / High only / Medium only
- **Market context** — tailwinds and headwinds panels, each independently toggleable
- **Recommended next steps** — prioritized action list (Urgent / Important / Nice to have)
- **Escalation banner** — full-width alert rendered at the top if a critical flag is found (fraud, active SEC investigation, class action, bankruptcy)

---

## Requirements

- **Claude** (claude.ai or Claude desktop app)
- **Nimble MCP connector** — required for real-time web research. Enable in Claude under Settings → Integrations → Nimble. Nimble gives this skill access to sources standard AI agents can't reach: public records, court filings, paywalled news, LinkedIn, review platforms, SEC filings, and more.

---

## Installation

1. Download `company-due-diligence.skill`
2. In Claude, open **Settings → Skills**
3. Click **Install skill** and select the downloaded file
4. Claude will confirm installation and show an onboarding message on first use

---

## How to use

**Trigger phrase:**
```
Run a due diligence brief on [company name]
```

**Other ways to start:**
- "Vet this vendor before we sign"
- "What's the risk profile of [company]?"
- "We're thinking of acquiring [company] — what do we need to know?"
- "Quick background check on [company] — just the red flags"
- "Research [company] before our investor call"

**Claude will ask three questions before running:**

| Question | Default |
|---|---|
| Subject — company only, or include the market too? | Company only |
| Use case — investment / vendor eval / competitive intel / general vetting | General vetting |
| Depth — fast brief or standard (thorough) | Standard |

Say **"just run it"** to skip to defaults immediately.

---

## Dimensions covered

| Dimension | What's researched |
|---|---|
| **Financial health** | Funding history, total raised, investors, valuation signals, revenue indicators, financial distress signals |
| **Legal & litigation** | Lawsuits, court filings, regulatory actions, class actions, IP disputes, FTC complaints |
| **Leadership** | Founder/exec backgrounds, tenure, prior company history, public statements, controversies |
| **Customer reputation** | G2, Trustpilot, Capterra, Gartner Peer Insights, Reddit, HN — ratings, themes, churn signals |
| **Competitive position** | Market share signals, key integrations, partnerships, analyst positioning, competitor activity |
| **Employment trends** | Glassdoor score, headcount signals, hiring patterns, layoff signals, Blind/Levels.fyi sentiment |
| **News & controversy** | Press coverage tone, incident history, security events, public controversies |

---

## Example run

```
You:    Run a due diligence brief on Nimble

Claude: Got it — a few quick questions:
        1. Subject: Just Nimble, or should I also research the market it operates in?
        2. Use case: Investment / Vendor eval / Competitive intel / General vetting?
        3. Depth: Fast brief or Standard (thorough, default)?

You:    Both company and market. Investment. Standard.

Claude: Got it — running now. Profiling Nimble first to adapt
        queries to the right ecosystem and query angles.

        [runs research using Nimble across all 7 dimensions]
        [renders interactive dd_brief.html directly in Claude]
        [offers dd_brief.html + dd_brief.md as downloads]
```

---

## Output details

### Interactive HTML (`dd_brief.html`)
Rendered directly in Claude. Fully interactive:
- Red flags panel filters live by severity — click All / High only / Medium only
- Tailwinds and headwinds panels toggle independently — click either button to show/hide
- Escalation banner appears at the very top if a critical flag was found

### Structured Markdown (`dd_brief.md`)
Machine-readable output with consistent schema — suitable for feeding into deal management systems, legal review pipelines, downstream agents, or reporting tools. Includes per-dimension findings, source URLs, dates, red flag inventory, and recommended next steps.

---

## Saved preferences

On first use, Claude asks whether to save your preferences. If you save them, future runs skip the setup questions entirely. Say **"change settings"** at any time to update.

---

## Sources

The skill searches across public records and commercial sources including:

- **Financial** — Crunchbase, PitchBook, SEC EDGAR, SiliconAngle, TechCrunch, Bloomberg (via Nimble)
- **Legal** — CourtListener, PACER Monitor, FTC complaint database, state court records
- **Reviews** — G2, Trustpilot, Capterra, Gartner Peer Insights, TrustRadius, Glassdoor, Blind
- **News** — TechCrunch, The Information, Axios, Reuters, AP, trade press
- **Community** — Reddit, Hacker News, LinkedIn, Stack Overflow, GitHub
- **Employment** — LinkedIn Jobs, Greenhouse, Lever, Glassdoor, Levels.fyi

Full source list and query patterns are in `references/sources.md`.

---

## File structure

```
company-due-diligence/
├── SKILL.md                    — skill definition and instructions
└── references/
    ├── template.html           — required HTML output template
    ├── sources.md              — source query patterns and guidance
    ├── onboarding.md           — onboarding message and first-use flow
    └── red-flags.md            — red flag classification and escalation criteria
```

---

## Built with

[Nimble](https://nimbleway.com) + [Claude](https://claude.ai)

Nimble provides real-time web data access — including public records, court filings, paywalled news, LinkedIn, review platforms, and SEC data — that standard AI agents cannot reach.
