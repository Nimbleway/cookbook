# Autonomous Competitive SEO Strategist

An automated SEO strategy pipeline built with [Nimble](https://nimbleway.com) and Claude. Point it at any domain — it maps the site, pulls 30 live search rankings, identifies every competitor winning traffic you should own, and uses Claude to generate a prioritised action plan.

**Live dataset included.** The `.nimble/` folder contains a complete run against stripe.com (47 pages extracted, 30 terms tracked, full report generated) so you can explore the dashboard immediately without any API calls.

---

## What it does

| Phase | What happens | API |
|---|---|---|
| 1 | Fetches homepage as clean markdown | Nimble `extract()` |
| 2 | Discovers and classifies site URLs, selects top pages | Nimble `map()` + Claude |
| 3 | Batch-extracts selected pages in parallel | Nimble `extract_batch()` |
| 4 | Generates 30 targeted search terms across 6 intent categories | Claude |
| 5 | Fires all 30 queries as live Google searches | Nimble `search()` |
| 6 | Maps competitor presence and threat level across all SERPs | Claude |
| 7 | Diagnoses each term with a priority score | Claude |
| 8 | Generates quick wins, page briefs, new pages, strategic themes | Claude |

---

## Quickstart — just the dashboard

The Stripe dataset is already included. No API keys needed:

```bash
pip install -r requirements.txt
python3 -m streamlit run dashboard/app.py
```

---

## Run the full pipeline

To analyse a different domain, you'll need a [Nimble API key](https://nimbleway.com) and an [Anthropic API key](https://console.anthropic.com).

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your keys to .env
```

Edit `config/analysis_config.json`:

```json
{
  "homepage_url": "https://yourdomain.com",
  "target_country": "US",
  "language": "English",
  "business_model": "B2B SaaS",
  "known_competitors": ["competitor1.com", "competitor2.com"],
  "brand_terms_to_exclude": ["your brand name"],
  "search_term_mode": "balanced"
}
```

Then run:

```bash
python3 run_analysis.py
```

Each run is saved to `.nimble/seo_runs/{domain}/{timestamp}/`. The dashboard always loads the most recent run. Re-running skips already-completed phases.

---

## Dashboard tabs

**Overview** — Composite SEO score gauge, six-dimension bar chart, SERP status breakdown, executive summary, top quick wins preview.

**SERP Rankings** — Full 30-term table showing the Stripe page currently ranking for each query, its position, status, and top competitor. Filterable by status, term type, and funnel stage. SERP detail drill-down per term.

**Competitors** — Threat count metrics, SERP frequency bar chart for top 20 competitors, detail table sorted by threat level with domain, SERPs appeared in, best/avg rank, and inferred positioning.

**Diagnosis** — Most common page issues and strategy issues (frequency charts), per-term diagnosis table sorted by priority, expandable term detail with five-dimension priority score breakdown.

**Pages** — Full inventory of all extracted pages with type, SEO value, title, H1, primary topic, and target audience.

**Quick Wins** — Expandable action cards ranked by impact-to-effort ratio, each with the specific page, affected search terms, and what to change.

**Recommendations** — Page optimisation briefs (current vs suggested title, H1, H2s, keywords, FAQ questions), new pages to create with full content briefs, and strategic themes.

**Full Report** — Complete markdown report rendered inline.

---

## Project structure

```
├── run_analysis.py              # Full pipeline runner (phases 1–3 + orchestration)
├── phase4_search_terms.py       # Claude: generate 30 search terms
├── phase5_serp.py               # Nimble: live SERP data for all terms
├── phase6_competitors.py        # Claude: competitor map from SERP results
├── phase7_diagnose.py           # Claude: per-term diagnosis + priority scores
├── phase8_recommendations.py    # Claude: quick wins, page briefs, new pages, themes
├── dashboard/
│   └── app.py                   # Streamlit dashboard
├── config/
│   └── analysis_config.json     # Target domain + settings
├── .streamlit/
│   └── config.toml              # Dark theme config
├── requirements.txt
├── .env.example
└── .nimble/
    └── seo_runs/
        └── stripe.com/
            └── 20260521T132410Z/    # Complete sample run
                ├── company_understanding.json
                ├── search_terms.json
                ├── serp_results.json
                ├── pages_extracted.json
                ├── competitor_map.json
                ├── diagnosis.json
                ├── recommendations.json
                └── report.md
```

---

## Sample dataset — stripe.com (May 2026)

| Data | Count |
|---|---|
| Pages extracted | 47 |
| Search terms tracked | 30 |
| Unique competitors identified | 20 |
| Site SEO score | 58 / 100 |

**SERP breakdown:** 7 winning (top 3) · 16 wrong page · 7 absent

**Quick wins generated:** 8 (all High impact / Low effort)

**New pages recommended:** 7

---

## Requirements

- Python 3.9+
- Nimble API key (phases 1–3, 5 only) — [get one here](https://nimbleway.com)
- Anthropic API key (phases 4, 6–8 only) — [get one here](https://console.anthropic.com)
