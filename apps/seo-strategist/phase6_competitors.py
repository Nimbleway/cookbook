#!/usr/bin/env python3
"""
Phase 6 — SERP-based competitor analysis.
Run: python3 phase6_competitors.py
Reads:  serp_results.json, input.json
Writes: competitor_map.json
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import anthropic
from dotenv import load_dotenv

load_dotenv()

RUNS_ROOT = Path(".nimble/seo_runs")
CONFIG_PATH = Path("config/analysis_config.json")

SKIP_DOMAINS = {
    "wikipedia.org", "reddit.com", "youtube.com", "quora.com",
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "tiktok.com", "amazon.com", "google.com",
    "forbes.com", "investopedia.com", "techcrunch.com",
}


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


def normalise_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.lstrip("www.")


# ── main ─────────────────────────────────────────────────────────

def run():
    run_dir = latest_run_dir()
    print(f"Run dir: {run_dir}\n")

    if (run_dir / "competitor_map.json").exists():
        data = load(run_dir, "competitor_map.json")
        print(f"Already complete — {len(data.get('aggregate', []))} competitors on disk.")
        return

    config       = load(run_dir, "input.json")
    serp_results = load(run_dir, "serp_results.json")

    target_domain    = config["_domain"]
    known_competitor_domains = {
        normalise_domain("https://" + d) for d in config.get("known_competitors", [])
    }

    # ── Aggregate competitor appearances ────────────────────────
    print("Aggregating competitor appearances across 30 SERPs...")

    # domain → {serp_count, ranks, titles_snippets, page_types_raw}
    agg = defaultdict(lambda: {
        "serp_queries": [],
        "ranks": [],
        "titles": [],
        "snippets": [],
        "urls": [],
    })

    per_query_maps = []

    for serp in serp_results:
        query = serp["search_term"]
        query_map = []

        for result in serp.get("top_results", []):
            domain = normalise_domain(result.get("url", ""))
            if not domain or domain == target_domain:
                continue
            # Strip known noise domains
            base = ".".join(domain.split(".")[-2:])
            if any(skip in domain for skip in SKIP_DOMAINS):
                continue

            rank = result.get("rank") or 99
            agg[domain]["serp_queries"].append(query)
            agg[domain]["ranks"].append(rank)
            agg[domain]["titles"].append(result.get("title", ""))
            agg[domain]["snippets"].append(result.get("snippet", ""))
            agg[domain]["urls"].append(result.get("url", ""))

            query_map.append({
                "rank":    rank,
                "domain":  domain,
                "url":     result.get("url", ""),
                "title":   result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "is_known_competitor": domain in known_competitor_domains,
            })

        per_query_maps.append({
            "search_term": query,
            "results":     sorted(query_map, key=lambda x: x["rank"]),
        })

    # Sort by frequency × average rank quality
    def threat_score(d):
        ranks = agg[d]["ranks"]
        return len(set(agg[d]["serp_queries"])) * 10 - (sum(ranks) / len(ranks) if ranks else 99)

    top_competitors = sorted(agg.keys(), key=threat_score, reverse=True)[:20]

    print(f"  Found {len(agg)} unique competitor domains")
    print(f"  Top {len(top_competitors)} passed to Claude for analysis\n")

    # ── Claude: infer positioning per competitor ─────────────────
    print("Running Claude analysis on top competitors...")

    comp_snapshot = []
    for domain in top_competitors:
        data = agg[domain]
        ranks = data["ranks"]
        serps = list(set(data["serp_queries"]))
        avg_rank = round(sum(ranks) / len(ranks), 1) if ranks else None
        best_rank = min(ranks) if ranks else None

        # Sample up to 5 title+snippet pairs
        samples = [
            f"  [{data['urls'][i]}] {data['titles'][i]} — {data['snippets'][i]}"
            for i in range(min(5, len(data["titles"])))
        ]

        comp_snapshot.append({
            "domain": domain,
            "appears_in_serps": len(serps),
            "best_rank": best_rank,
            "avg_rank": avg_rank,
            "is_known_competitor": domain in known_competitor_domains,
            "sample_queries": serps[:5],
            "sample_results": samples,
        })

    snapshot_text = json.dumps(comp_snapshot, indent=2)

    aggregate = ask_claude_json(
        "You are a competitive SEO analyst. Analyse SERP-observed competitor data and classify each domain.",
        f"""Target company domain: {target_domain}

--- COMPETITOR SERP DATA ---
{snapshot_text}

For each competitor return one object. Infer page_type and positioning purely from the titles and snippets shown.

Return a JSON array:
[
  {{
    "competitor_domain": "...",
    "appears_in_serps": 0,
    "best_rank": 0,
    "avg_rank": 0.0,
    "is_known_competitor": true,
    "common_page_types": ["product_page|blog_post|listicle|docs|comparison|landing_page|category_page"],
    "main_inferred_positioning": "one sentence — what angle they use to win",
    "strength_assessment": "one sentence — why they rank well",
    "threat_level": "High|Medium|Low"
  }}
]""",
        max_tokens=4096,
    )

    if isinstance(aggregate, dict):
        aggregate = list(aggregate.values())[0]

    competitor_map = {
        "per_query": per_query_maps,
        "aggregate": aggregate,
    }

    save(run_dir, "competitor_map.json", competitor_map)

    # Print summary
    print(f"\n  {'Domain':<35} {'SERPs':>6} {'Best':>5} {'Avg':>5}  {'Threat':<8} Positioning")
    print("  " + "─" * 100)
    for c in sorted(aggregate, key=lambda x: -x.get("appears_in_serps", 0)):
        known = "★" if c.get("is_known_competitor") else " "
        print(
            f"  {known}{c['competitor_domain']:<34} "
            f"{c.get('appears_in_serps',0):>6} "
            f"{str(c.get('best_rank','?')):>5} "
            f"{str(c.get('avg_rank','?')):>5}  "
            f"{c.get('threat_level','?'):<8} "
            f"{c.get('main_inferred_positioning','')[:60]}"
        )


if __name__ == "__main__":
    run()
