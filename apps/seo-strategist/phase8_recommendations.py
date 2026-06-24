#!/usr/bin/env python3
"""
Phase 8 — Generate SEO recommendations and final report.
Run: python3 phase8_recommendations.py
Reads:  diagnosis.json, search_terms.json, pages_extracted.json,
        competitor_map.json, company_understanding.json
Writes: recommendations.json, report.md
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import anthropic
from dotenv import load_dotenv

load_dotenv()

RUNS_ROOT = Path(".nimble/seo_runs")
CONFIG_PATH = Path("config/analysis_config.json")


# ── helpers ──────────────────────────────────────────────────────

def latest_run_dir() -> Path:
    config = json.loads(CONFIG_PATH.read_text())
    domain = urlparse(config["homepage_url"]).netloc.lstrip("www.")
    runs = sorted((RUNS_ROOT / domain).glob("*"))
    if not runs:
        print("[error] No completed run found.")
        sys.exit(1)
    return runs[-1]


def load(run_dir: Path, filename: str):
    return json.loads((run_dir / filename).read_text(encoding="utf-8"))


def save_json(run_dir: Path, filename: str, data):
    path = run_dir / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ {filename}")


def save_text(run_dir: Path, filename: str, text: str):
    path = run_dir / filename
    path.write_text(text, encoding="utf-8")
    print(f"  ✓ {filename}")


def ask_claude(system: str, prompt: str, max_tokens: int = 8192, as_json: bool = True):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    user_content = prompt + ("\n\nRespond with valid JSON only. No markdown fences." if as_json else "")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_content}],
    )
    text = response.content[0].text.strip()
    if as_json:
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        return json.loads(text)
    return text


# ── main ─────────────────────────────────────────────────────────

def run():
    run_dir = latest_run_dir()
    print(f"Run dir: {run_dir}\n")

    recs_done   = (run_dir / "recommendations.json").exists()
    report_done = (run_dir / "report.md").exists()

    if recs_done and report_done:
        recs = load(run_dir, "recommendations.json")
        print("Already complete — recommendations.json and report.md on disk.")
        print(f"  Quick wins:           {len(recs.get('quick_wins', []))}")
        print(f"  Page recommendations: {len(recs.get('page_recommendations', []))}")
        print(f"  New pages needed:     {len(recs.get('new_pages_needed', []))}")
        print(f"  Strategic themes:     {len(recs.get('strategic_themes', []))}")
        return

    cu        = load(run_dir, "company_understanding.json")
    diagnosis = load(run_dir, "diagnosis.json")
    pages     = load(run_dir, "pages_extracted.json")
    comp_map  = load(run_dir, "competitor_map.json")

    score     = diagnosis["site_seo_score"]
    diagnoses = diagnosis["term_diagnoses"]

    # Sort terms by page priority score desc
    diagnoses_sorted = sorted(
        diagnoses,
        key=lambda d: (d.get("page_priority_score") or {}).get("total", 0),
        reverse=True,
    )

    # Group diagnoses by mapped page
    page_diag_map = {}
    for d in diagnoses:
        url = d.get("mapped_page") or ""
        page_diag_map.setdefault(url, []).append(d)

    # Top 8 pages by highest single-term priority score
    page_scores = {}
    for d in diagnoses:
        url = d.get("mapped_page") or ""
        val = (d.get("page_priority_score") or {}).get("total", 0)
        if url and val > page_scores.get(url, 0):
            page_scores[url] = val
    top_pages = sorted(page_scores.items(), key=lambda x: -x[1])[:8]

    # Build detailed context for top pages
    page_by_url = {p["url"]: p for p in pages}
    top_page_contexts = []
    for url, priority in top_pages:
        page = page_by_url.get(url, {})
        page_terms = page_diag_map.get(url, [])
        top_page_contexts.append({
            "url": url,
            "priority_score": priority,
            "title": page.get("title", ""),
            "h1": page.get("h1", ""),
            "h2s": page.get("h2s", [])[:6],
            "primary_topic": page.get("primary_topic", ""),
            "terms": [
                {
                    "term": d["search_term"],
                    "status": d.get("status"),
                    "page_issues": d.get("page_issues", []),
                    "strategy_issues": d.get("strategy_issues", []),
                    "top_competitor": d.get("top_competitor_for_term"),
                    "competitor_angle": d.get("competitor_winning_angle"),
                    "diagnosis": d.get("diagnosis_summary"),
                }
                for d in page_terms
            ],
        })

    # Terms with no good page match
    no_page_terms = [
        {
            "term": d["search_term"],
            "type": d.get("term_type"),
            "funnel": d.get("funnel_stage"),
            "diagnosis": d.get("diagnosis_summary"),
            "top_competitor": d.get("top_competitor_for_term"),
            "competitor_angle": d.get("competitor_winning_angle"),
        }
        for d in diagnoses
        if d.get("status") == "absent" or "no_page_fits" in (d.get("strategy_issues") or [])
    ]

    top_competitors = [
        {
            "domain": c["competitor_domain"],
            "threat": c.get("threat_level"),
            "positioning": c.get("main_inferred_positioning"),
            "strength": c.get("strength_assessment"),
        }
        for c in (comp_map.get("aggregate") or [])[:8]
    ]

    system = (
        "You are a senior SEO strategist producing a final action plan. "
        "Be specific and actionable. Every recommendation must reference actual URLs, "
        "exact terms, and concrete content changes. "
        "Base all competitor observations strictly on SERP-inferred data."
    )

    recs_prompt = f"""Company: {cu.get('company_name')} — {cu.get('what_they_sell')}

--- SITE SEO SCORE: {score.get('total')}/100 ---
Technical SEO:          {score.get('technical_seo')}/20
Content depth:          {score.get('content_depth')}/20
Search intent align:    {score.get('search_intent_alignment')}/20
Competitive coverage:   {score.get('competitive_coverage')}/20
Internal linking:       {score.get('internal_linking')}/10
Conversion readiness:   {score.get('conversion_readiness')}/10
Assessment: {score.get('summary')}

--- TOP 8 PRIORITY PAGES ---
{json.dumps(top_page_contexts, indent=2)}

--- TERMS WITH NO MATCHING PAGE ({len(no_page_terms)}) ---
{json.dumps(no_page_terms, indent=2)}

--- TOP COMPETITORS ---
{json.dumps(top_competitors, indent=2)}

Generate a complete SEO action plan. Return this exact JSON:

{{
  "executive_summary": "3-5 sentence strategic overview of the biggest opportunities",
  "quick_wins": [
    {{
      "rank": 1,
      "title": "concise action title",
      "type": "page_fix|new_page|internal_linking|technical",
      "impact": "High|Medium",
      "effort": "Low|Medium|High",
      "url": "the page this applies to",
      "description": "specific 1-2 sentence action",
      "terms_addressed": ["term1", "term2"]
    }}
  ],
  "page_recommendations": [
    {{
      "url": "...",
      "priority_score": 0,
      "terms_addressed": ["..."],
      "current_title": "...",
      "suggested_title": "...",
      "current_h1": "...",
      "suggested_h1": "...",
      "suggested_h2s": ["..."],
      "keywords_to_add": ["..."],
      "content_additions": ["specific section or element to add"],
      "faq_questions": ["question 1?", "question 2?"],
      "internal_links_to_add": ["url"],
      "estimated_impact": "one sentence on expected ranking improvement"
    }}
  ],
  "new_pages_needed": [
    {{
      "suggested_url": "/proposed-path",
      "page_title": "...",
      "page_type": "landing_page|comparison|guide|faq|use_case",
      "target_terms": ["..."],
      "content_brief": "2-3 sentences on what this page should cover",
      "format_rationale": "why this format wins for these terms",
      "priority": "High|Medium|Low",
      "competitor_to_outrank": "domain"
    }}
  ],
  "strategic_themes": [
    {{
      "theme": "short theme name",
      "description": "2-3 sentences",
      "terms_impacted": 0,
      "priority": "High|Medium|Low",
      "recommended_actions": ["action 1", "action 2"]
    }}
  ]
}}

Rules:
- quick_wins: 6-8 items ordered by impact/effort ratio (best ratio first)
- page_recommendations: one entry per top-priority page (all 8)
- new_pages_needed: 4-8 pages, ordered by business priority
- strategic_themes: 3-5 themes connecting multiple recommendations"""

    print("Generating recommendations...")
    recs = ask_claude(system, recs_prompt, max_tokens=16000, as_json=True)
    recs["site_seo_score"] = score
    recs["generated_at"] = datetime.now(timezone.utc).isoformat()
    save_json(run_dir, "recommendations.json", recs)

    # ── Report.md ────────────────────────────────────────────────
    print("Generating report.md...")

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    month_str = datetime.now(timezone.utc).strftime("%B %Y")

    # Pre-build appendix data (avoids f-string escaping issues with {})
    appendix_rows = [
        {
            "term": d["search_term"],
            "status": d.get("status", ""),
            "priority": (d.get("page_priority_score") or {}).get("total", 0),
            "top_issue": d.get("diagnosis_summary", ""),
        }
        for d in diagnoses_sorted
    ]

    report_prompt = f"""Write a final SEO strategy report for {cu.get('company_name')}.

Site: {cu.get('domain', 'stripe.com')}
Analysis date: {date_str}
Overall SEO score: {score.get('total')}/100

Full recommendations data:
{json.dumps(recs, indent=2)}

All 30 terms ranked by priority (for appendix):
{json.dumps(appendix_rows, indent=2)}

Write a clean professional markdown report using this exact structure:

# SEO Strategy Report — {cu.get('company_name')} ({month_str})

## Executive Summary
(paragraph expanding the executive_summary)

## Site SEO Score: {score.get('total')}/100
| Dimension | Score | Max |
|---|---|---|
(one row per dimension)

Brief 2-sentence interpretation below the table.

## Quick Wins
Numbered list. Each item: **Title** `impact: X` `effort: X` — description. Terms addressed listed below as a bullet.

## Page Optimisation Recommendations
One H3 per page. Format:
### `[url]` (Priority score: N)
**Terms targeted:** term1, term2
**Title:** ~~current~~ → suggested
**H1:** ~~current~~ → suggested
**H2s to add:** bulleted list
**Keywords to weave in:** inline list
**Content to add:** numbered list of additions
**FAQ questions to add:** bulleted list
**Internal links to add:** bulleted list of URLs
_Expected impact: ..._

## New Pages to Create
| URL | Type | Priority | Target Terms | Beat |
|---|---|---|---|---|
(one row per page)

Then for each High-priority page, a short content brief paragraph under its own H3.

## Strategic Themes
One H3 per theme with description paragraph and recommended actions as a bullet list.

## Appendix: All 30 Terms
| Term | Status | Priority | Top Issue |
|---|---|---|---|
(one row per term from appendix_rows, sorted by priority desc)

Tone: direct and professional. No filler sentences. Use markdown tables wherever they aid scannability."""

    report_md = ask_claude(system, report_prompt, max_tokens=16000, as_json=False)
    save_text(run_dir, "report.md", report_md)

    # Summary
    print(f"\n  Quick wins:           {len(recs.get('quick_wins', []))}")
    print(f"  Page recommendations: {len(recs.get('page_recommendations', []))}")
    print(f"  New pages needed:     {len(recs.get('new_pages_needed', []))}")
    print(f"  Strategic themes:     {len(recs.get('strategic_themes', []))}")
    print(f"\n  Report written to: {run_dir}/report.md")


if __name__ == "__main__":
    run()
