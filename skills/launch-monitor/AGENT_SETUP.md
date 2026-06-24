# Launch Monitor — Agent Setup

## Required connector

**Nimble MCP** must be connected before running this skill.

1. Open Claude → **Settings → Connectors**
2. Find **Nimble** and click **Connect**
3. Authorize with your Nimble account

If you don't have a Nimble account: [nimbleway.com](https://nimbleway.com)

---

## Trigger phrases

```
Monitor the launch of [product name]
```
```
Track coverage since we announced [product] yesterday
```
```
What's the reaction to our [product] launch?
```
```
Flag any mischaracterizations in our [product] press coverage
```
```
How are competitors responding to our [product] launch?
```
```
Monitor [product] launch — deep, competitors: Google, Samsung, OpenAI
```

---

## What Claude does before asking you anything

**Step A — Alternate names resolved automatically:**
Claude searches for codenames, version names, API names, and marketing-name variants and folds them into the queries silently. For AI products it checks model name, API name, and consumer-facing name separately; for hardware it checks internal vs marketing names.

**Step B — Launch date found automatically:**
Claude searches for the launch date before asking, then presents what it found and asks you to confirm or correct it — rather than asking a blank question.

---

## Setup questions

| # | Question | Default |
|---|---|---|
| 1 | Launch date — confirm what Claude found | What Nimble returned |
| 2 | Window — how far back to look | Launch date to now |
| 3 | Depth — quick scan or deep sweep | Deep |
| 4 | Competitors — Claude identifies automatically; add or exclude | On by default |

Say **"just run it"** to skip all questions and use defaults.

**Inline config example:**
```
Monitor the launch of Nimble MCP connector — launched Jun 11,
deep, competitors: Firecrawl and Exa
```

---

## Output

- **Interactive Response War Room** rendered directly in Claude
- **`launch_monitor.html`** — downloadable interactive report
- **`launch_monitor.md`** — structured markdown for downstream use

### Sections (in render order)

1. Launch header — product, launch date, time since launch, live indicator
2. Attention summary — the 2–3 most urgent things, in plain language
3. Stat cards — All / Act now / Monitor / Good / Mischaracterizations (clickable)
4. Sentiment velocity chart — positive/negative/neutral over time, clickable points
5. Signal feed — cards packed 2–3 across, sorted by urgency
6. View tabs + Refine panel — filter by urgency, action type, signal type
7. Mischaracterization tracker — claim vs correction (only if found)
8. Competitor responses — moves + suggested counter-moves (only if found)

### Interacting with the output

| Element | How it works |
|---|---|
| Stat cards | Click to filter the signal feed to that urgency level (synced with view tabs) |
| View tabs | All / Act now / Monitor / Good / Mischar. — synced with the stat cards |
| Refine button | Expands a panel to add action-type and signal-type filters, shown as dismissable chips |
| Signal feed layout | Responsive grid packing 2–3 cards across by width — compact, no long single column |
| Signal cards | Click to expand the suggested action text |
| Action badge | RESPOND / CORRECT / AMPLIFY / ESCALATE / WATCH — what to do about the signal |
| Urgency dot | 🔴 act now · 🟡 monitor · 🟢 good |
| ↗ source links | Open the exact article, thread, or post — never a homepage |
| Velocity chart | Click any data point to filter the feed to that time window; click again to clear |
| Copy correction | Copies the suggested response text to clipboard |

---

## Signal model

**Urgency** drives the colored dot and the feed sort order:
- 🔴 **Act now** — mischaracterization spreading, high-reach negative coverage, competitor counter-move
- 🟡 **Monitor** — emerging negative theme, mid-reach inaccuracy
- 🟢 **Good** — accurate positive coverage, organic enthusiasm

**Action badge** tells the reader what to do: `RESPOND`, `CORRECT`, `AMPLIFY`, `ESCALATE`, `WATCH`.

**Signal type** tags the source category: `press`, `community`, `social`, `competitor`, `mischar`.

The feed sorts by urgency (🔴 → 🟡 → 🟢). The responsive grid keeps it compact: cards pack 2–3 across rather than stacking one per row.

---

## Sources searched

**Press:** TechCrunch, The Verge, Wired, Ars Technica, VentureBeat, ZDNet, The Register, SiliconAngle, InfoQ, SD Times, and category-specific outlets

**Social (all platforms searched every run):**
- Reddit — broad sweep + multiple subreddit-specific queries
- X/Twitter — broad + complaint hunt (`wrong OR broken OR disappointed`) + correction chains
- LinkedIn — broad + practitioner/exec reactions
- Instagram — via Nimble `focus:"social"`
- TikTok — via Nimble `focus:"social"` + reaction/review queries
- YouTube — review/reaction/first-impressions + problems queries
- Facebook / Threads — via Nimble `focus:"social"`

**Community:** Hacker News, Dev.to, Stack Overflow, GitHub, Discord

**Competitor channels:** competitor blogs, social accounts, "vs [product]" content since launch

Full source list and Nimble configuration: `references/sources.md`

---

## Nimble configuration notes

- Discovery passes use `search_depth:"lite"` with `include_answer:true` for speed.
- Full article/thread extraction for mischaracterization analysis uses `search_depth:"deep"`.
- Instagram, TikTok, Facebook, and Threads require `focus:"social"` — standard `site:` search does not reach them.

---

## Re-running

```
Refresh the war room
```
```
Re-run — what's new since this morning?
```

Net-new signals only. Unresolved mischaracterizations and open action items carry forward.

**Recommended cadence:**
- First 6h: every 1–2 hours
- 6h–24h: every 3–4 hours
- After 24h: once or twice daily until momentum settles

---

## Troubleshooting

**Signal feed shows one card per row instead of 2–3 across**
→ The feed uses `grid-template-columns:repeat(auto-fill,minmax(215px,1fr))` so it packs by width. If it's collapsing to one column, the render area is unusually narrow — widen the view. Do not change it back to a fixed `repeat(2,...)`, which is what caused the single-column collapse originally.

**Source links open a homepage instead of the article**
→ Re-run and tell Claude: "Use the exact article URL for every signal — not the publication homepage. It should look like `https://techcrunch.com/2026/06/11/article-title`, not `https://techcrunch.com`."

**No social signals found**
→ Confirm Nimble is connected — social search requires Nimble's `focus:"social"` mode. Try a wider time window. For Instagram/TikTok, Nimble handles these via social focus mode, not `site:` search.

**No signals found at all**
→ Confirm Nimble is connected in Settings → Connectors. Try a wider time window. Confirm the product name — add the company name or domain.

**Mischaracterization tracker is empty**
→ No mischaracterizations were found — that's good. The skill specifically hunts for inaccurate claims; an empty tracker means none are spreading.

**Competitor panel missing**
→ Competitors are on by default. If missing, Claude may not have found any moves. Ask: "Did you check [competitor]'s blog and social?"

**Velocity chart didn't render**
→ The chart loads Chart.js from a public CDN. If your network blocks it, the chart can't draw — every other section still works.

**Skill not triggering**
→ Use one of the exact trigger phrases above. Confirm the skill is installed in Settings → Capabilities → Skills.
