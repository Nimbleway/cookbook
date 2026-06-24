# Launch Monitor

**Your response war room for launch day — and every day after.**

A Claude skill that monitors press, social media, developer communities, and competitor channels from any point around a product launch — tracking sentiment, flagging mischaracterizations, surfacing competitor responses, and telling you exactly what to do about each signal. Rendered as an interactive Response War Room directly in Claude.

Powered by Nimble + Claude.

---

## What it does

Each run produces a fully interactive `launch_monitor.html` rendered in Claude, plus a structured `launch_monitor.md`. Sections render in this order:

1. **Launch header** — product name, launch date, time since launch, last-updated timestamp, with a live pulse indicator.
2. **Attention summary** — a plain-language callout naming the 2–3 most urgent things right now, before any charts. Specific: the outlet, the claim, the competitor move.
3. **Stat cards** — five clickable counts (All / Act now / Monitor / Good / Mischaracterizations), synced with the feed view tabs.
4. **Sentiment velocity chart** — positive, negative, and neutral signal volume over time since launch. Click any data point to filter the feed to that time window.
5. **Signal feed** — every signal as a card in a responsive grid that packs **2–3 cards across** by available width, so the feed stays short instead of a long single column. Sorted by urgency (Act now → Monitor → Good). Each card shows an urgency dot, action badge, signal-type tag, headline, context, metadata, and an exact source link. Click a card to expand its suggested action.
6. **View switcher + Refine panel** — All / Act now / Monitor / Good / Mischaracterizations tabs (synced with the stat cards), plus a collapsible Refine panel to add action-type and signal-type filters, shown as dismissable chips with Clear all.
7. **Mischaracterization tracker** — claim vs. correction in two columns, with a spread-status badge and one-click copy of the suggested response. Only renders if mischaracterizations were found.
8. **Competitor responses** — what each competitor did and a suggested counter-move, with a link to their post. Only renders if competitor monitoring is on and moves were found.

---

## What makes this different

Designed to feel **operational**, not like a dashboard you have to interpret:

- The feed packs 2–3 cards across so you see more signals per screen — no endless scrolling.
- Every card carries an action badge (`RESPOND` / `CORRECT` / `AMPLIFY` / `ESCALATE` / `WATCH`) telling you what to do, not just what happened.
- Suggested response text is one click away on every card.
- Mischaracterization corrections copy to clipboard in one click.
- Every source link opens the exact article, thread, or post — never a homepage.

Social coverage is comprehensive: Reddit (multiple subreddits), X/Twitter, LinkedIn, Instagram, TikTok, YouTube, Facebook, Threads — plus press, Hacker News, and developer communities.

---

## Signal triage

| Urgency | Meaning |
|---|---|
| 🔴 Act now | Mischaracterization spreading, high-reach negative coverage, competitor counter-move |
| 🟡 Monitor | Emerging negative theme, mid-reach inaccuracy |
| 🟢 Good | Accurate positive coverage, organic enthusiasm |

| Action badge | Meaning |
|---|---|
| `RESPOND` | Direct public response needed |
| `CORRECT` | Correction or clarification needed |
| `AMPLIFY` | Worth sharing, reposting, or building on |
| `ESCALATE` | Needs comms, legal, or leadership |
| `WATCH` | No action yet — track for escalation |

---

## Requirements

- **Claude** (claude.ai or Claude desktop app)
- **Nimble MCP connector** — required. Enable in Claude under Settings → Connectors → Nimble.

The sentiment velocity chart loads Chart.js from a public CDN. If your network blocks it, every other section still works.

---

## Installation

1. Download `launch-monitor.skill`
2. In Claude, open **Settings → Capabilities → Skills**
3. Click **Upload skill** and select the downloaded file
4. Claude shows an onboarding message on first use

---

## How to use

**Trigger phrase:**
```
Monitor the launch of [product name]
```

**Other ways to start:**
- "Track coverage since we announced [product] yesterday"
- "What's the reaction to our [product] launch?"
- "Flag any mischaracterizations in our [product] press coverage"
- "How are competitors responding to our [product] launch?"

**Before asking questions, Claude automatically:**
1. Searches for alternate names, codenames, API names, and version names for the product
2. Finds the launch date and asks you to confirm or correct it

**Claude then confirms:**

| Question | Default |
|---|---|
| Launch date — confirm what Claude found | What Nimble returned |
| Window — how far back to look | Launch date to now |
| Depth — quick scan or deep sweep | Deep |
| Competitors — Claude identifies automatically; add or exclude | On by default |

Say **"just run it"** to accept all defaults.

---

## Sources

**Press:** TechCrunch, The Verge, Wired, Ars Technica, VentureBeat, ZDNet, The Register, SiliconAngle, InfoQ, SD Times, and category-specific outlets

**Social:** Reddit (broad + subreddit-specific), X/Twitter (broad + complaint/correction hunting), LinkedIn, Instagram, TikTok, YouTube, Facebook, Threads

**Community:** Hacker News, Dev.to, Stack Overflow, GitHub, Discord

**Competitor channels:** competitor blogs, social accounts, and "vs [product]" content since launch

Full query patterns and Nimble configuration: `references/sources.md`

---

## Re-running

Say "refresh" or "re-run" — Claude sweeps for net-new signals only and carries forward unresolved mischaracterizations and open action items.

**Recommended cadence:** every 1–2h in the first 6h · every 3–4h through day 1 · once or twice daily after that

---

## File structure

```
launch-monitor/
├── SKILL.md
├── README.md
├── AGENT_SETUP.md
└── references/
    ├── template.html
    └── sources.md
```

Built with [Nimble](https://nimbleway.com) + [Claude](https://claude.ai)
