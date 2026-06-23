#!/usr/bin/env python3
"""
Phase 5 — Live SERP check for all 30 search terms.
Run: python3 phase5_serp.py
Reads:  search_terms.json, input.json
Writes: serp_results.json
"""

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from nimble_python import Nimble

load_dotenv()

RUNS_ROOT = Path(".nimble/seo_runs")
CONFIG_PATH = Path("config/analysis_config.json")


# ── helpers ──────────────────────────────────────────────────────

def latest_run_dir() -> Path:
    config = json.loads(CONFIG_PATH.read_text())
    domain = urlparse(config["homepage_url"]).netloc.lstrip("www.")
    runs = sorted((RUNS_ROOT / domain).glob("*"))
    if not runs:
        print("[error] No completed run found. Run phases 1-4 first.")
        sys.exit(1)
    return runs[-1]


def load(run_dir: Path, filename: str):
    return json.loads((run_dir / filename).read_text(encoding="utf-8"))


def save(run_dir: Path, filename: str, data):
    path = run_dir / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ {filename}")


def rank_label(position: int) -> str:
    if position <= 3:   return "winning"
    if position <= 10:  return "visible"
    if position <= 20:  return "weak"
    return "absent"


# ── main ─────────────────────────────────────────────────────────

def run():
    run_dir = latest_run_dir()
    print(f"Run dir: {run_dir}\n")

    if (run_dir / "serp_results.json").exists():
        results = load(run_dir, "serp_results.json")
        print(f"Already complete — {len(results)} SERP results on disk.")
        return

    config = load(run_dir, "input.json")
    terms  = load(run_dir, "search_terms.json")

    domain  = config["_domain"]
    country = config["target_country"]

    nimble = Nimble(api_key=os.getenv("NIMBLE_API_KEY"))

    # Resume from cached individual results
    cache_dir = run_dir / "raw_serps"
    cache_dir.mkdir(exist_ok=True)

    serp_results = []
    total = len(terms)

    for i, term in enumerate(terms, 1):
        query = term["search_term"]
        cache_path = cache_dir / f"{i:02d}.json"

        print(f"[{i}/{total}] {query}")

        # Resumability: skip if already fetched
        if cache_path.exists():
            raw = json.loads(cache_path.read_text())
            print(f"  (cached)")
        else:
            resp = nimble.search(
                query=query,
                country=country,
                locale="en-US",
                max_results=20,
                search_depth="lite",
            )
            raw = resp.model_dump()
            cache_path.write_text(json.dumps(raw, indent=2))

        results_list = raw.get("results") or []
        organic = [
            r for r in results_list
            if (r.get("metadata") or {}).get("entity_type") == "OrganicResult"
        ]

        # Find Stripe's position
        stripe_rank = None
        stripe_url  = None
        for r in organic:
            url = r.get("url", "")
            pos = (r.get("metadata") or {}).get("position")
            if domain in url and stripe_rank is None:
                stripe_rank = pos
                stripe_url  = url

        # Determine status
        if stripe_rank:
            mapped = term.get("mapped_existing_page", "")
            mapped_path = urlparse(mapped).path.rstrip("/")
            actual_path = urlparse(stripe_url).path.rstrip("/")
            if mapped_path and actual_path and mapped_path != actual_path:
                status = "wrong_page"
            else:
                status = rank_label(stripe_rank)
        else:
            status = "absent"

        # Top 20 competitor snapshot
        top_results = [
            {
                "rank":     (r.get("metadata") or {}).get("position"),
                "domain":   urlparse(r.get("url", "")).netloc,
                "url":      r.get("url", ""),
                "title":    r.get("title", ""),
                "snippet":  r.get("description", ""),
            }
            for r in organic[:20]
        ]

        print(f"  Stripe: {'rank ' + str(stripe_rank) if stripe_rank else 'absent'} | status: {status}")

        serp_results.append({
            "search_term":         query,
            "term_type":           term.get("term_type"),
            "mapped_page":         term.get("mapped_existing_page"),
            "stripe_rank":         stripe_rank,
            "stripe_url":          stripe_url,
            "status":              status,
            "top_results":         top_results,
            "organic_count":       len(organic),
        })

    save(run_dir, "serp_results.json", serp_results)

    # Summary
    from collections import Counter
    statuses = Counter(r["status"] for r in serp_results)
    print(f"\n{'─'*40}")
    print(f"  SERP summary ({total} terms):")
    for s in ["winning", "visible", "weak", "absent", "wrong_page"]:
        n = statuses.get(s, 0)
        if n:
            print(f"    {s:<15} {n}")


if __name__ == "__main__":
    run()
