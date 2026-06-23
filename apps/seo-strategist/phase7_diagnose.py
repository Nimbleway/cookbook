#!/usr/bin/env python3
"""
Phase 7 — Diagnose SEO issues per term and score the site.
Run: python3 phase7_diagnose.py
Reads:  search_terms.json, serp_results.json, pages_extracted.json,
        competitor_map.json, company_understanding.json
Writes: diagnosis.json
"""

import json
import os
import sys
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


def save(run_dir: Path, filename: str, data):
    path = run_dir / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ {filename}")


def ask_claude_json(system: str, prompt: str, max_tokens: int = 8192):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt + "\n\nRespond with valid JSON only. No markdown fences."}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1])
    return json.loads(text)


# ── main ─────────────────────────────────────────────────────────

def run():
    run_dir = latest_run_dir()
    print(f"Run dir: {run_dir}\n")

    if (run_dir / "diagnosis.json").exists():
        data = load(run_dir, "diagnosis.json")
        print(f"Already complete — diagnosis on disk.")
        score = data.get("site_seo_score", {})
        print(f"  Site SEO score: {score.get('total', '?')}/100")
        return

    cu           = load(run_dir, "company_understanding.json")
    terms        = load(run_dir, "search_terms.json")
    serps        = load(run_dir, "serp_results.json")
    pages        = load(run_dir, "pages_extracted.json")
    comp_map     = load(run_dir, "competitor_map.json")

    # Index for fast lookup
    serp_by_term = {s["search_term"]: s for s in serps}
    page_by_url  = {p["url"]: p for p in pages}

    # ── Build compact cross-reference ───────────────────────────
    print("Building cross-reference...")
    term_contexts = []
    for term in terms:
        query   = term["search_term"]
        mapped  = term.get("mapped_existing_page", "")
        serp    = serp_by_term.get(query, {})
        page    = page_by_url.get(mapped, {})

        top5 = [
            f"  #{r['rank']} {r['domain']} — {r['title']} | {r['snippet'][:100]}"
            for r in (serp.get("top_results") or [])[:5]
        ]

        term_contexts.append({
            "search_term":    query,
            "term_type":      term.get("term_type"),
            "funnel_stage":   term.get("funnel_stage"),
            "mapped_page":    mapped,
            "page_title":     page.get("title", ""),
            "page_h1":        page.get("h1", ""),
            "page_h2s":       page.get("h2s", [])[:5],
            "page_topic":     page.get("primary_topic", ""),
            "page_audience":  page.get("target_audience", ""),
            "stripe_rank":    serp.get("stripe_rank"),
            "stripe_url":     serp.get("stripe_url"),
            "status":         serp.get("status"),
            "top_5_serp":     top5,
        })

    # Compact competitor summary
    comp_summary = [
        f"  {c['competitor_domain']} — appears in {c['appears_in_serps']} SERPs, "
        f"best rank {c.get('best_rank','?')}, threat: {c.get('threat_level','?')}. "
        f"{c.get('main_inferred_positioning','')}"
        for c in (comp_map.get("aggregate") or [])[:10]
    ]

    # Compact page inventory
    page_inventory = [
        f"  [{p['page_type']}] {p['url']} | {p['primary_topic']} | {p['target_audience']}"
        for p in pages
    ]

    system = (
        "You are a senior SEO strategist. You diagnose SEO issues by comparing "
        "a company's existing pages against live SERP data. "
        "Base competitor observations only on SERP titles and snippets — "
        "you have not audited competitor pages directly."
    )

    prompt = f"""Company: {cu.get('company_name')} — {cu.get('what_they_sell')}

--- PAGE INVENTORY ({len(pages)} pages) ---
{chr(10).join(page_inventory)}

--- TOP COMPETITORS (SERP-observed) ---
{chr(10).join(comp_summary)}

--- 30 TERM CROSS-REFERENCE ---
{json.dumps(term_contexts, indent=2)}

Diagnose every term and score the site. Return this exact JSON structure:

{{
  "site_seo_score": {{
    "total": 0,
    "technical_seo": 0,
    "content_depth": 0,
    "search_intent_alignment": 0,
    "competitive_coverage": 0,
    "internal_linking": 0,
    "conversion_readiness": 0,
    "summary": "2-3 sentence overall assessment"
  }},
  "term_diagnoses": [
    {{
      "search_term": "...",
      "status": "winning|visible|weak|absent|wrong_page|intent_mismatch",
      "mapped_page": "...",
      "page_issues": ["weak_title|vague_h1|missing_keyword|thin_content|poor_heading_structure|no_faq|no_comparison_table|weak_internal_linking|no_proof_points|cta_mismatch"],
      "strategy_issues": ["no_page_fits|wrong_page_ranking|format_mismatch|query_too_broad|competitors_own_educational_layer|competitors_own_comparison_content|page_lacks_specificity"],
      "serp_issues": ["dominated_by_review_sites|dominated_by_docs|dominated_by_listicles|dominated_by_marketplaces|high_brand_bias|low_ranking_opportunity"],
      "top_competitor_for_term": "domain",
      "competitor_winning_angle": "what the top competitor does better (SERP-inferred only)",
      "diagnosis_summary": "one sentence",
      "page_priority_score": {{
        "total": 0,
        "business_value": 0,
        "ranking_opportunity": 0,
        "fixability": 0,
        "competitor_gap": 0,
        "internal_link_leverage": 0
      }}
    }}
  ]
}}

Site score max components: technical_seo 20, content_depth 20, search_intent_alignment 20,
competitive_coverage 20, internal_linking 10, conversion_readiness 10. Total max = 100.

Page priority score max components: business_value 30, ranking_opportunity 25,
fixability 20, competitor_gap 15, internal_link_leverage 10. Total max = 100."""

    print("Running Claude diagnosis...")
    diagnosis = ask_claude_json(system, prompt, max_tokens=16000)

    save(run_dir, "diagnosis.json", diagnosis)

    # Summary
    score = diagnosis.get("site_seo_score", {})
    print(f"\n  Site SEO Score: {score.get('total', '?')}/100")
    print(f"    Technical SEO          {score.get('technical_seo', '?')}/20")
    print(f"    Content depth          {score.get('content_depth', '?')}/20")
    print(f"    Search intent align    {score.get('search_intent_alignment', '?')}/20")
    print(f"    Competitive coverage   {score.get('competitive_coverage', '?')}/20")
    print(f"    Internal linking       {score.get('internal_linking', '?')}/10")
    print(f"    Conversion readiness   {score.get('conversion_readiness', '?')}/10")
    print(f"\n  {score.get('summary', '')}")

    # Top issues by frequency
    from collections import Counter
    all_page_issues     = Counter()
    all_strategy_issues = Counter()
    diagnoses = diagnosis.get("term_diagnoses", [])
    for d in diagnoses:
        for i in d.get("page_issues", []):     all_page_issues[i] += 1
        for i in d.get("strategy_issues", []): all_strategy_issues[i] += 1

    print(f"\n  Most common page issues:")
    for issue, n in all_page_issues.most_common(5):
        print(f"    {issue:<40} {n} terms")

    print(f"\n  Most common strategy issues:")
    for issue, n in all_strategy_issues.most_common(5):
        print(f"    {issue:<40} {n} terms")

    # Top priority pages
    page_scores = {}
    for d in diagnoses:
        url = d.get("mapped_page", "")
        score_val = (d.get("page_priority_score") or {}).get("total", 0)
        if url and score_val > page_scores.get(url, 0):
            page_scores[url] = score_val

    print(f"\n  Top 5 pages by improvement priority:")
    for url, s in sorted(page_scores.items(), key=lambda x: -x[1])[:5]:
        print(f"    {s:>3}  {url}")


if __name__ == "__main__":
    run()
