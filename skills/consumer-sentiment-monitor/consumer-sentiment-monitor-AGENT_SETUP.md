# Consumer Sentiment Monitor — Agent Setup

## Required connector

**Nimble MCP** must be connected before running this skill. Without it, the skill cannot access review platforms, Reddit, or press sources.

1. Open Claude → **Settings → Integrations**
2. Find **Nimble** and click **Connect**
3. Authorize with your Nimble account
4. Return to Claude — the skill will detect the connector automatically

If you don't have a Nimble account: [nimbleway.com](https://nimbleway.com)

---

## Trigger phrases

Say any of the following to start the skill:

```
Run a sentiment report on [brand name]
```
```
What are people saying about [brand] this month?
```
```
How does [brand] compare to [competitor A] and [competitor B] in sentiment?
```
```
Any new G2 reviews for [brand] we should know about?
```
```
Is there anything negative trending about [brand] right now?
```
```
Run a sentiment report on [brand] vs [competitor] — 30 days, deep
```

---

## Setup questions

On first run (or if preferences aren't saved), Claude asks:

| # | Question | Default |
|---|---|---|
| 1 | Scope — brand only, or vs competitors? | Brand only |
| 2 | Time window — how far back to look | 30 days |
| 3 | Depth — surface scan or deep | Deep |

Say **"just run it"** to skip all questions and use defaults.

---

## Output

Every run produces:

- **Interactive HTML widget** rendered directly in Claude — platform scorecards (clickable to filter), competitive comparison table, filterable quote wall, expandable emerging themes tracker
- **`sentiment.html`** — downloadable version of the same report
- **`sentiment.md`** — structured markdown with full quote inventory and platform scores

### Quote wall filters
- **Brand filter:** All / [Brand A] / [Brand B] / [Brand C]
- **Sentiment filter:** All / Positive / Negative / Watch
- **Platform filter:** Click any scorecard to filter quotes to that source
- All three filters stack independently

### Emerging themes
Click any row in the themes table to expand the source mentions behind it.

---

## Sources searched

This skill searches across 5 tiers — 40+ sources including:

- **Review platforms:** G2, Trustpilot, Capterra, Gartner Peer Insights, TrustRadius, PeerSpot, GetApp, Spiceworks, StackShare, Product Hunt
- **Community & social:** Reddit, Hacker News, X/Twitter, LinkedIn, Dev.to, Medium, Substack, Discord, Quora
- **Press:** TechCrunch, The Verge, Wired, Ars Technica, VentureBeat, ZDNet, The Register, SiliconAngle
- **Developer:** Stack Overflow, GitHub, GitLab, Indie Hackers
- **Forward-looking:** Changelog activity, job postings, community forums, newsletter mentions

Full source list and query patterns: `references/sources.md`

---

## Saving preferences

After first run, Claude asks whether to save your preferences. If saved, future runs skip all setup questions. Say **"change settings"** at any time to update.

---

## Re-running

To surface only what's new since your last run:
```
Re-run sentiment — what's new since last time?
```
```
Refresh the sentiment report for [brand]
```

Claude will ask when you last ran it and use that as the start of the time window.

---

## Passing config inline

```
Run a sentiment report on Notion vs Linear vs Asana — 30 days, deep, competitive comparison
```

---

## Recommended cadence

- **Weekly brand pulse:** Run every Monday for a quick read on what's new
- **Pre-launch:** Run before announcing a new feature to establish a sentiment baseline
- **Post-launch:** Run 48h and 7 days after a launch to catch any reaction spikes
- **Competitive intel:** Run whenever a competitor launches something new

---

## Spike alerts

If Nimble surfaces a sudden surge in mentions (positive or negative), Claude will surface a spike alert banner at the top of the report. This means something unusual happened — investigate before the next run.

---

## Troubleshooting

**Reviews not found on G2 / Trustpilot**
→ Nimble can access these platforms — check the connector is active
→ The product may have low review volume — this is itself a signal

**Quote wall shows no results after filtering**
→ Use "Clear filters" to reset — you may have stacked filters with no matching quotes

**Competitor comparison missing**
→ Make sure you named competitors in your setup question or trigger phrase

**Skill not triggering**
→ Use one of the exact trigger phrases listed above
→ Confirm the skill is installed in Settings → Skills
