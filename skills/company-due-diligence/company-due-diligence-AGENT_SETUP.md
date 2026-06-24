# Company Due Diligence — Agent Setup

## Required connector

**Nimble MCP** must be connected before running this skill. Without it, the skill cannot access public records, court filings, review platforms, or paywalled sources.

1. Open Claude → **Settings → Integrations**
2. Find **Nimble** and click **Connect**
3. Authorize with your Nimble account
4. Return to Claude — the skill will detect the connector automatically

If you don't have a Nimble account: [nimbleway.com](https://nimbleway.com)

---

## Trigger phrases

Say any of the following to start the skill:

```
Run a due diligence brief on [company name]
```
```
Vet [company] before we sign
```
```
What's the risk profile of [company]?
```
```
We're thinking of acquiring [company] — what do we need to know?
```
```
Quick background check on [company] — just the red flags
```
```
Research [company] before our investor call
```
```
DD on [company] — investment, all 7 dimensions, standard depth
```

---

## Setup questions

On first run (or if preferences aren't saved), Claude asks:

| # | Question | Default |
|---|---|---|
| 1 | Subject — company only, or include the market too? | Company only |
| 2 | Use case — investment / vendor eval / competitive intel / general vetting | General vetting |
| 3 | Depth — fast brief or standard (thorough) | Standard |

Say **"just run it"** to skip all questions and use defaults.

---

## Output

Every run produces:

- **Interactive HTML widget** rendered directly in Claude — overall risk grade, 7-dimension scorecard, funding timeline, red flags panel with severity filter, market context with tailwinds/headwinds toggle, recommended next steps
- **`dd_brief.html`** — downloadable version of the same report
- **`dd_brief.md`** — structured markdown for deal management systems, legal review pipelines, or downstream agents

### Interactive features
- **Red flags severity filter:** Toggle between All / High only / Medium only
- **Market context toggle:** Show/hide Tailwinds and Headwinds panels independently
- **Escalation banner:** Appears automatically at the top if a critical flag is found (fraud, active SEC investigation, class action, bankruptcy)

---

## Dimensions covered

| Dimension | What's researched |
|---|---|
| Financial health | Funding history, total raised, investors, valuation signals, revenue indicators |
| Legal & litigation | Lawsuits, court filings, regulatory actions, class actions, IP disputes, FTC complaints |
| Leadership | Founder/exec backgrounds, tenure, prior company history, controversies |
| Customer reputation | G2, Trustpilot, Capterra, Gartner, Reddit — ratings, themes, churn signals |
| Competitive position | Market share signals, key integrations, partnerships, analyst positioning |
| Employment trends | Glassdoor score, headcount signals, hiring patterns, layoff signals |
| News & controversy | Press coverage tone, incident history, security events, public controversies |

---

## Risk grades

| Grade | Meaning |
|---|---|
| 🟢 A | Low risk — proceed with standard due diligence |
| 🟡 B | Moderate risk — investigate flagged items before proceeding |
| 🟠 C | Elevated risk — material concerns require resolution |
| 🔴 D | High risk — significant red flags, proceed with caution |
| ⛔ F | Critical — immediate escalation required |

---

## Saving preferences

After first run, Claude asks whether to save your preferences. If saved, future runs skip all setup questions. Say **"change settings"** at any time to update.

---

## Passing config inline

Skip setup entirely by providing config in your trigger:

```
Run a DD brief on Nimble — investment, both company and market, all 7 dimensions, standard depth
```

---

## Use case presets

Each use case shifts dimension weighting:

- **Investment/acquisition** → Financial, Legal, Leadership weighted heavily
- **Vendor eval** → Reputation, Legal, Employment weighted heavily
- **Competitive intel** → Competitive position, Financial, News weighted heavily
- **General vetting** → All 7 dimensions weighted evenly

You can select more than one use case in a single run.

---

## Recommended cadence

- **Pre-investment:** Run standard depth before any investment decision
- **Vendor onboarding:** Run fast brief before signing any contract over $10K/year
- **Acquisition target:** Run deep dive + market research before LOI
- **Ongoing monitoring:** Re-run quarterly on active vendors or portfolio companies

---

## Troubleshooting

**Legal section shows nothing found**
→ This is a positive signal — no litigation found. The skill searches court records, SEC filings, and press. If clean, it reports clean.

**Glassdoor score missing**
→ Very small companies may not have enough reviews. The skill will note the absence.

**Overall grade seems off**
→ The grade is computed across all 7 dimensions. A single high-severity red flag in one dimension can lower the overall grade even if other dimensions are clean.

**Escalation banner appeared**
→ A critical flag was found (fraud, SEC action, class action, or bankruptcy signal). Do not proceed without investigating this finding first.

**Skill not triggering**
→ Use one of the exact trigger phrases listed above
→ Confirm the skill is installed in Settings → Skills
→ If the company name is ambiguous, Claude will ask you to clarify — answer with the full company name and domain
