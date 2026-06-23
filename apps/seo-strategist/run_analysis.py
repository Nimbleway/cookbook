#!/usr/bin/env python3
"""
Autonomous Competitive SEO Strategist — data pipeline
Run: python3 run_analysis.py

Artifacts saved to: .nimble/seo_runs/{domain}/{timestamp}/
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from typing import Optional

import anthropic
from dotenv import load_dotenv
from nimble_python import Nimble

load_dotenv()

_nimble: Optional[Nimble] = None
_claude: Optional[anthropic.Anthropic] = None


def nimble_client() -> Nimble:
    global _nimble
    if _nimble is None:
        key = os.getenv("NIMBLE_API_KEY")
        if not key:
            print("[error] NIMBLE_API_KEY not set in environment or .env")
            sys.exit(1)
        _nimble = Nimble(api_key=key)
    return _nimble


def claude_client() -> anthropic.Anthropic:
    global _claude
    if _claude is None:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            print("[error] ANTHROPIC_API_KEY not set in environment or .env")
            sys.exit(1)
        _claude = anthropic.Anthropic(api_key=key)
    return _claude

CONFIG_PATH = Path("config/analysis_config.json")
RUNS_ROOT = Path(".nimble/seo_runs")

# Page types that are high SEO value (to prioritise in map selection)
HIGH_VALUE_TYPES = {
    "product", "platform", "solution", "use_case", "industry",
    "feature", "pricing", "comparison", "resource_hub",
    "blog_category", "documentation_overview",
}

# Path segments that signal low-value / utility pages (deprioritise)
LOW_VALUE_SEGMENTS = {
    "login", "signin", "sign-in", "signup", "sign-up", "register",
    "contact", "privacy", "terms", "careers", "jobs", "support",
    "legal", "cookie", "accessibility", "sitemap", "status",
    "dashboard", "app", "account",
}


# ─────────────────────────── helpers ────────────────────────────

def save(run_dir: Path, filename: str, data):
    path = run_dir / filename
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ {filename}")


def load_json(run_dir: Path, filename: str):
    path = run_dir / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def banner(phase: str):
    print(f"\n{'─' * 50}")
    print(f"  {phase}")
    print(f"{'─' * 50}")


def ask_claude(system: str, prompt: str, max_tokens: int = 8192) -> str:
    """Call Claude with prompt caching on the system message."""
    response = claude_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def ask_claude_json(system: str, prompt: str, max_tokens: int = 8192):
    """Call Claude and parse JSON from the response."""
    text = ask_claude(system, prompt + "\n\nRespond with valid JSON only. No markdown fences, no commentary.", max_tokens)
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


# ─────────────────────────── phase 1 ────────────────────────────

def phase1_init():
    """Read config, normalise domain, create timestamped run folder."""
    banner("Phase 1 — Initialize run")

    if not CONFIG_PATH.exists():
        print(f"[error] Config not found at {CONFIG_PATH}")
        sys.exit(1)

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    # Validate required fields
    required = ["homepage_url", "target_country", "language",
                "business_model", "search_term_mode"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        print(f"[error] Config missing required fields: {missing}")
        sys.exit(1)

    # Normalise domain
    parsed = urlparse(config["homepage_url"])
    domain = parsed.netloc.lstrip("www.")
    if not domain:
        print(f"[error] Could not parse domain from homepage_url: {config['homepage_url']}")
        sys.exit(1)

    # Resume latest run if one exists, otherwise create a new one
    domain_dir = RUNS_ROOT / domain
    existing = sorted(domain_dir.glob("*")) if domain_dir.exists() else []
    if existing:
        run_dir = existing[-1]
        config = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
        print(f"\n  Resuming : {run_dir}")
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = domain_dir / ts
        run_dir.mkdir(parents=True, exist_ok=True)
        config["_domain"] = domain
        config["_timestamp"] = ts
        config["_run_dir"] = str(run_dir)
        save(run_dir, "input.json", config)
        print(f"\n  Domain  : {domain}")
        print(f"  Run dir : {run_dir}")

    print(f"  Country : {config['target_country']}")
    print(f"  Mode    : {config['search_term_mode']}")

    return config, run_dir


# ─────────────────────────── phase 2 ────────────────────────────

def phase2_discover(config: dict, run_dir: Path):
    """Fetch homepage and map site URLs. Classification happens in a later step."""
    banner("Phase 2 — Discover site structure")

    homepage_url = config["homepage_url"]
    country = config["target_country"]
    nimble = nimble_client()

    # ── 2a. Extract homepage as markdown (country=US for canonical links) ──
    print(f"\n[2a] Extracting homepage: {homepage_url}")
    if not (run_dir / "homepage.md").exists():
        result = nimble.extract(
            url=homepage_url,
            formats=["markdown"],
            render=True,
            country=country,
        )
        if result.status != "success" or not result.data.markdown:
            print("  Retrying with vx10 driver...")
            result = nimble.extract(
                url=homepage_url,
                formats=["markdown"],
                render=True,
                country=country,
                driver="vx10",
            )
        md = result.data.markdown or ""
        save(run_dir, "homepage.md", md)
        print(f"  Homepage markdown: {len(md):,} chars")
    else:
        md = (run_dir / "homepage.md").read_text(encoding="utf-8")
        print(f"  Loaded cached homepage.md ({len(md):,} chars)")

    # ── 2b. Mine URLs from homepage markdown ────────────────────
    import re
    print(f"\n[2b] Mining URLs from homepage markdown...")

    if not (run_dir / "raw_map.json").exists():
        domain = config["_domain"]
        base = f"https://{domain}"
        LINK_RE = re.compile(
            rf'https?://(?:www\.)?{re.escape(domain)}(/[^\s\)\"\'\|>\]]*)',
            re.IGNORECASE,
        )
        SKIP_SEGMENTS = {
            "login", "signin", "sign-in", "signup", "sign-up", "register",
            "contact", "privacy", "terms", "careers", "jobs", "support",
            "legal", "cookie", "accessibility", "status", "dashboard",
            "app", "account", "session", "oauth", "sitemap",
        }

        seen = set()
        raw_links = []
        for path in LINK_RE.findall(md):
            path = path.rstrip(").,")
            if not path or "?" in path or "#" in path or path.endswith(".pdf"):
                continue
            parts = set(path.strip("/").split("/"))
            if parts & SKIP_SEGMENTS:
                continue
            # Skip dashboard subdomain links that slipped through
            url = base + path
            if "dashboard.stripe.com" in url:
                continue
            if path in seen:
                continue
            seen.add(path)
            raw_links.append({"url": url, "path": path, "title": "", "description": ""})

        save(run_dir, "raw_map.json", raw_links)
        print(f"  Found {len(raw_links)} unique candidate URLs")
        for lnk in raw_links:
            print(f"    {lnk['url']}")
    else:
        raw_links = load_json(run_dir, "raw_map.json")
        print(f"  Loaded cached raw_map.json ({len(raw_links)} URLs)")

    # ── 2c. Company understanding ────────────────────────────────
    print(f"\n[2c] Analysing company from homepage...")
    if not (run_dir / "company_understanding.json").exists():
        excerpt = md[:5000]
        cu = ask_claude_json(
            "You are an expert B2B analyst. Analyse a company homepage and return a structured JSON profile.",
            f"""Homepage: {homepage_url}
Business model hint: {config['business_model']}

--- HOMEPAGE CONTENT ---
{excerpt}

Return this exact JSON:
{{
  "company_name": "...",
  "homepage_url": "{homepage_url}",
  "what_they_sell": "one sentence",
  "primary_audience": "who buys this",
  "key_value_props": ["...", "...", "..."],
  "product_categories": ["...", "...", "..."],
  "company_interpretation": "One clear sentence: what this company is and who it serves."
}}""",
            max_tokens=1024,
        )
        cu["domain_analyzed"] = config["_domain"]
        cu["timestamp"] = config["_timestamp"]
        save(run_dir, "company_understanding.json", cu)
    else:
        cu = load_json(run_dir, "company_understanding.json")
        print("  Loaded cached company_understanding.json")

    print(f"  → {cu.get('company_interpretation', '')}")

    # ── 2d. Classify URLs + select 30 pages ─────────────────────
    print(f"\n[2d] Classifying {len(raw_links)} URLs, selecting 30 for extraction...")
    if not (run_dir / "site_map.json").exists():
        url_list = "\n".join(
            f"{i+1}. {lnk['url']}" for i, lnk in enumerate(raw_links)
        )
        site_map = ask_claude_json(
            "You are an SEO site architect. Classify URLs by type and strategic SEO value.",
            f"""Company: {cu.get('company_name', 'Unknown')} — {cu.get('what_they_sell', '')}

--- CANDIDATE URLS ---
{url_list}

For EVERY URL return one JSON object. Mark exactly 30 as selected: true.

Selection rules:
  PRIORITISE (selected=true): product, platform, solution, use_case, industry,
    feature, pricing, comparison, resource_hub, blog_category, documentation_overview
  DEPRIORITISE (selected=false): individual blog posts, individual case studies,
    individual newsroom items, legal, utility, landing pages (lp/), annual-updates,
    roadmap, climate, sessions

Return a JSON array, one object per URL, in the same order:
[
  {{
    "url": "...",
    "page_name": "short label",
    "page_type": "product|platform|solution|use_case|industry|feature|pricing|comparison|resource_hub|blog_category|documentation_overview|blog_post|case_study|newsroom|legal|utility|other",
    "path": "/path/only",
    "main_topic": "what this page covers",
    "seo_value": "High|Medium|Low",
    "priority_reason": "one line",
    "selected": true
  }}
]

Exactly 30 must have selected: true.""",
            max_tokens=16000,
        )

        if isinstance(site_map, dict):
            site_map = list(site_map.values())[0]

        save(run_dir, "site_map.json", site_map)
    else:
        site_map = load_json(run_dir, "site_map.json")
        print("  Loaded cached site_map.json")

    selected = [p for p in site_map if p.get("selected")]
    print(f"\n  {len(selected)} pages selected for extraction:")
    type_counts = {}
    for p in selected:
        t = p.get("page_type", "other")
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t:<35} {n}")
    print()
    for p in selected:
        print(f"    {p.get('seo_value','?'):6}  {p['url']}")


# ─────────────────────────── phase 3 ────────────────────────────

def phase3_extract_pages(config: dict, run_dir: Path):
    """Batch-extract selected pages, lighter Claude pass for SEO fields."""
    banner("Phase 3 — Extract selected pages")

    if (run_dir / "pages_extracted.json").exists():
        print("  Already complete — skipping.")
        return

    site_map = load_json(run_dir, "site_map.json")
    selected = [p for p in site_map if p.get("selected")]
    print(f"\n  {len(selected)} pages to extract")

    nimble = nimble_client()
    country = config["target_country"]
    raw_dir = run_dir / "raw_pages"
    raw_dir.mkdir(exist_ok=True)
    batch_state_path = run_dir / "batch_state.json"

    # ── 3a. Submit batch (or resume) ────────────────────────────
    if batch_state_path.exists():
        batch_state = json.loads(batch_state_path.read_text())
        batch_id = batch_state["batch_id"]
        task_map = batch_state["task_map"]   # task_id → url
        print(f"  Resuming batch {batch_id}")
    else:
        print(f"\n[3a] Submitting extract_batch for {len(selected)} URLs...")
        batch = nimble.extract_batch(
            inputs=[{"url": p["url"]} for p in selected],
            shared_inputs={"formats": ["markdown"], "render": True, "country": country},
        )
        batch_id = batch.batch_id
        task_map = {t.id: t.input["url"] for t in batch.tasks}
        batch_state = {"batch_id": batch_id, "task_map": task_map}
        batch_state_path.write_text(json.dumps(batch_state, indent=2))
        print(f"  Batch submitted: {batch_id}  ({len(task_map)} tasks)")

    # ── 3b. Poll until complete ──────────────────────────────────
    import time
    print(f"\n[3b] Waiting for batch to complete...")
    while True:
        prog = nimble.batches.progress(batch_id)
        pct = int((prog.progress or 0) * 100)
        done = int(prog.completed_count or 0)
        print(f"  {pct}%  ({done}/{len(task_map)} complete)  status={prog.status}")
        if prog.completed:
            break
        time.sleep(5)

    # ── 3c. Fetch raw results ────────────────────────────────────
    print(f"\n[3c] Fetching task results...")
    raw_results = {}
    for task_id, url in task_map.items():
        cache_path = raw_dir / f"{task_id}.json"
        if cache_path.exists():
            raw_results[url] = json.loads(cache_path.read_text())
        else:
            res = nimble.tasks.results(task_id)
            cache_path.write_text(json.dumps(res, indent=2))
            raw_results[url] = res
    print(f"  Fetched {len(raw_results)} raw results")

    # ── 3d. Claude lighter pass ──────────────────────────────────
    import re
    print(f"\n[3d] Running lighter Claude pass on each page...")

    # Build a lookup from url → site_map entry
    sm_lookup = {p["url"]: p for p in site_map}

    HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

    def parse_headers(md: str):
        h1, h2s = "", []
        for m in HEADER_RE.finditer(md):
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and not h1:
                h1 = text
            elif level == 2:
                h2s.append(text)
        return h1, h2s[:8]   # cap at 8 H2s

    system = (
        "You are an SEO analyst. Given a webpage's markdown content, extract a short structured profile. "
        "Return only valid JSON with no markdown fences."
    )

    pages_extracted = []
    for i, (url, raw) in enumerate(raw_results.items(), 1):
        print(f"  [{i}/{len(raw_results)}] {url}")
        md = (raw.get("data") or {}).get("markdown") or ""
        sm = sm_lookup.get(url, {})

        # Parse headers from markdown directly (no LLM cost)
        h1, h2s = parse_headers(md)

        # Claude: primary_topic + target_audience only
        excerpt = md[:3000]
        try:
            parsed = ask_claude_json(
                system,
                f"""URL: {url}
Page type: {sm.get('page_type','')}

--- CONTENT (excerpt) ---
{excerpt}

Return:
{{
  "title": "page title (from first heading or obvious title)",
  "meta_description": "inferred meta description in ~150 chars",
  "primary_topic": "what this page is about in one phrase",
  "target_audience": "who this page is for"
}}""",
                max_tokens=256,
            )
        except Exception as e:
            print(f"    Claude error: {e}")
            parsed = {}

        pages_extracted.append({
            "url": url,
            "page_type": sm.get("page_type", ""),
            "seo_value": sm.get("seo_value", ""),
            "title": parsed.get("title") or h1,
            "meta_description": parsed.get("meta_description", ""),
            "h1": h1,
            "h2s": h2s,
            "primary_topic": parsed.get("primary_topic", ""),
            "target_audience": parsed.get("target_audience", ""),
        })

    save(run_dir, "pages_extracted.json", pages_extracted)
    print(f"\n  Extracted {len(pages_extracted)} pages")


# ─────────────────────────── phase 4 ────────────────────────────

def phase4_search_terms(config: dict, run_dir: Path):
    """Generate exactly 30 search terms inferred from the site's existing pages."""
    banner("Phase 4 — Generate search terms")

    if (run_dir / "search_terms.json").exists():
        terms = load_json(run_dir, "search_terms.json")
        print(f"  Already complete — {len(terms)} terms loaded.")
        return

    cu = load_json(run_dir, "company_understanding.json")
    pages = load_json(run_dir, "pages_extracted.json")

    # Build a compact page summary for the prompt
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
Mode: {mode} (conservative=fewer, higher-intent terms; aggressive=more, broader terms)

--- EXISTING PAGES ---
{page_summary}

Generate exactly 30 search terms distributed as:
  6  core_category    — broad category terms defining the space
  6  product_feature  — terms tied to specific products or features
  6  use_case         — job-to-be-done or workflow terms
  4  problem_aware    — terms from someone experiencing the problem, not yet aware of solutions
  4  comparison       — "vs", "alternative to", "best X for Y" patterns
  4  long_tail_buying — specific, high-intent buying terms

Rules:
- No brand terms from the exclusion list in any search_term
- Every term must have a real mapped_existing_page from the pages above
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
      "total": 0,
      "relevance": 0,
      "commercial_intent": 0,
      "ranking_gap": 0,
      "serp_attainability": 0,
      "existing_page_fit": 0
    }}
  }}
]

Opportunity score components (must sum to total, max values):
  relevance          25
  commercial_intent  20
  ranking_gap        20
  serp_attainability 15
  existing_page_fit  10
  strategic_importance 10
  (total max = 100)"""

    print(f"  Generating 30 search terms (mode: {mode})...")
    terms = ask_claude_json(system, prompt, max_tokens=8192)

    if isinstance(terms, dict):
        terms = list(terms.values())[0]

    save(run_dir, "search_terms.json", terms)

    # Summary by type
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
        print(f"  {total:>3}  [{t.get('term_type','?'):<20}]  {t['search_term']}")


# ─────────────────────────── main ───────────────────────────────

def main():
    config, run_dir = phase1_init()
    phase2_discover(config, run_dir)
    phase3_extract_pages(config, run_dir)
    phase4_search_terms(config, run_dir)
    print(f"\nDone. Artifacts in: {run_dir}\n")


if __name__ == "__main__":
    main()
