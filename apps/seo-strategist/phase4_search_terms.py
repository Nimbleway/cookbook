#!/usr/bin/env python3
"""
Phase 4 — Generate 30 search terms from existing page inventory.
Run: python3 phase4_search_terms.py
Reads:  pages_extracted.json, company_understanding.json
Writes: search_terms.json
"""

import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

RUNS_ROOT = Path(".nimble/seo_runs")
CONFIG_PATH = Path("config/analysis_config.json")


# ── helpers ──────────────────────────────────────────────────────

def latest_run_dir() -> Path:
    config = json.loads(CONFIG_PATH.read_text())
    from urllib.parse import urlparse
    domain = urlparse(config["homepage_url"]).netloc.lstrip("www.")
    runs = sorted((RUNS_ROOT / domain).glob("*"))
    if not runs:
        print("[error] No completed run found. Run phase 1-3 first.")
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
    print(f"Run dir: {run_dir}")

    if (run_dir / "search_terms.json").exists():
        terms = load(run_dir, "search_terms.json")
        print(f"Already complete — {len(terms)} terms on disk.")
        return

    config  = load(run_dir, "input.json")
    cu      = load(run_dir, "company_understanding.json")
    pages   = load(run_dir, "pages_extracted.json")

    page_summary = "\n".join(
        f"- [{p['page_type']}] {p['url']} | topic: {p['primary_topic']} | audience: {p['target_audience']}"
        for p in pages
    )

    brand_exclude = ", ".join(config.get("brand_terms_to_exclude", []))
    mode = config.get("search_term_mode", "balanced")

    system = (
        "You are a senior SEO strategist specialising in B2B SaaS. "
        "You generate search terms by inferring intent from existing pages — "
        "not by brainstorming generically. Every term must map back to a real page."
    )

    prompt = f"""Company: {cu.get('company_name')}
What they sell: {cu.get('what_they_sell')}
Primary audience: {cu.get('primary_audience')}
Brand terms to EXCLUDE from all search terms: {brand_exclude}
Mode: {mode}

--- EXISTING PAGES ---
{page_summary}

Generate exactly 30 search terms distributed as:
  6  core_category    — broad category terms defining the space
  6  product_feature  — terms tied to specific products or features
  6  use_case         — job-to-be-done or workflow terms
  4  problem_aware    — terms from someone experiencing the problem, not yet solution-aware
  4  comparison       — "vs", "alternative to", "best X for Y" patterns
  4  long_tail_buying — specific, high-intent buying terms

Rules:
- No brand terms from the exclusion list in any search_term
- Every mapped_existing_page must be a real URL from the page list above
- Terms should reflect what a real buyer would type, not marketing language

Return a JSON array of exactly 30 objects:
[
  {{
    "search_term": "exact query string",
    "intent": "informational|commercial|transactional|navigational",
    "funnel_stage": "awareness|consideration|decision",
    "term_type": "core_category|product_feature|use_case|problem_aware|comparison|long_tail_buying",
    "mapped_existing_page": "https://...",
    "why_relevant": "one sentence",
    "keyword_it_is_probably_targeting": "current likely target keyword",
    "keyword_it_should_target": "better keyword this page should own",
    "opportunity_score": {{
      "relevance": 0,
      "commercial_intent": 0,
      "ranking_gap": 0,
      "serp_attainability": 0,
      "existing_page_fit": 0,
      "strategic_importance": 0,
      "total": 0
    }}
  }}
]

Max component scores: relevance 25, commercial_intent 20, ranking_gap 20,
serp_attainability 15, existing_page_fit 10, strategic_importance 10. Total max = 100."""

    print(f"Generating 30 search terms (mode: {mode})...")
    terms = ask_claude_json(system, prompt, max_tokens=8192)

    if isinstance(terms, dict):
        terms = list(terms.values())[0]

    save(run_dir, "search_terms.json", terms)

    type_counts = {}
    for t in terms:
        k = t.get("term_type", "?")
        type_counts[k] = type_counts.get(k, 0) + 1

    print(f"\n  {len(terms)} terms generated:")
    for k, n in sorted(type_counts.items()):
        print(f"    {k:<25} {n}")
    print()
    for t in terms:
        score = t.get("opportunity_score", {})
        total = score.get("total", "?") if isinstance(score, dict) else "?"
        print(f"  {str(total):>3}  [{t.get('term_type','?'):<20}]  {t['search_term']}")


if __name__ == "__main__":
    run()
