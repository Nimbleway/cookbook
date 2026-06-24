# Portfolio Briefer — Agent Setup

## Required connector

**Nimble MCP** must be connected before running this skill. Without it, the skill has no access to real-time web data.

1. Open Claude → **Settings → Integrations**
2. Find **Nimble** and click **Connect**
3. Authorize with your Nimble account
4. Return to Claude — the skill will detect the connector automatically

If you don't have a Nimble account: [nimbleway.com](https://nimbleway.com)

---

## Trigger phrases

Say any of the following to start the skill:

```
Run a briefing on [company A], [company B], [company C]
```
```
What's new with [company] this week?
```
```
Update me on [company A] and [company B]
```
```
Anything I should know about [company] before my call?
```
```
Monitor [company A], [company B] — 7 days, deep
```

---

## Setup questions

On first run (or if preferences aren't saved), Claude asks:

| # | Question | Default |
|---|---|---|
| 1 | Company list — confirm or update | What you named |
| 2 | Time window — how far back to look | 7 days |
| 3 | Depth — surface or deep | Deep |
| 4 | Competitors — flag competitor moves? | Off |

Say **"just run it"** to skip all questions and use defaults.

---

## Output

Every run produces:

- **Interactive HTML widget** rendered directly in Claude — signal heatmap, brand mentions chart, clickable timeline, funding bars, signal cards
- **`briefing.html`** — downloadable version of the same report
- **`briefing.md`** — structured markdown for pipelines, note systems, or downstream agents

---

## Saving preferences

After first run, Claude asks whether to save your preferences. If saved, future runs skip all setup questions. Say **"change settings"** at any time to update.

---

## Re-running

Say any of the following to run again:
```
Run it again
```
```
Refresh the briefing
```
```
Update me — same companies
```

---

## Passing config inline

Skip setup questions entirely by providing config in your trigger:

```
Run a briefing on Stripe, Rippling, Ramp — 14 days, deep, competitors on
```

---

## Recommended cadence

- **Weekly:** Run every Monday before standup or LP calls
- **Event-triggered:** Run before a meeting, pitch, or announcement involving a tracked company
- **Ad hoc:** Any time you see news about a company you track

---

## Troubleshooting

**No results found**
→ Check that Nimble is connected in Settings → Integrations
→ Try a shorter time window (3 days instead of 7)
→ Confirm the company name is unambiguous — try adding the domain (e.g. "Stripe stripe.com")

**Output looks thin**
→ Run at deep depth instead of surface
→ Add competitors to surface more signals
→ Some companies have low web presence — this is itself a signal worth noting

**Skill not triggering**
→ Make sure the skill is installed in Settings → Skills
→ Use one of the exact trigger phrases listed above
