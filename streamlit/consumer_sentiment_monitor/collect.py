"""
collect.py — Consumer sentiment monitor powered by Nimble Search API.

Runs a small set of focused searches around a product launch, caches the raw
Nimble responses immediately, normalizes results, and writes a structured
sentiment report for the Streamlit dashboard.

Usage:
    python3 collect.py --dry-run
    python3 collect.py --config config/example_config.json
    python3 collect.py --config config/example_config.json --output data/runs/my_run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

APP_DIR = Path(__file__).parent
DEFAULT_CONFIG = APP_DIR / "config" / "example_config.json"
DEFAULT_ENDPOINT = "https://sdk.nimbleway.com/v1/search"

# Normalized schema used for every result leaving the collection layer.
SCHEMA = {
    "query_id": "str",
    "query_label": "str",
    "source_type": "str",
    "focus": "str|list[str]",
    "title": "str",
    "url": "str",
    "snippet": "str",
    "content": "str",
    "sentiment": "positive|negative|neutral",
    "matched_terms": "list[str]",
    "fetched_at": "ISO-8601 str",
}

POSITIVE_TERMS = {
    "love", "loved", "great", "useful", "impressive", "easy", "fast", "accurate",
    "helpful", "promising", "excited", "saves", "better", "works", "clean", "simple",
    "strong", "recommend", "delight", "good", "valuable",
}
NEGATIVE_TERMS = {
    "bug", "broken", "bad", "expensive", "pricing", "slow", "confusing", "privacy",
    "concern", "concerns", "complaint", "complaints", "missing", "hard", "fails",
    "failed", "risk", "skeptical", "worse", "inaccurate", "hallucination", "lock-in",
    "compliance", "blocker", "blockers", "retention",
}
RISK_TERMS = {
    "privacy", "security", "pricing", "expensive", "bug", "broken", "inaccurate",
    "hallucination", "compliance", "lock-in", "slow", "missing", "fails", "blocker",
}


@dataclass
class NormalizedResult:
    query_id: str
    query_label: str
    source_type: str
    focus: Any
    title: str
    url: str
    snippet: str
    content: str
    sentiment: str
    matched_terms: List[str]
    fetched_at: str


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "query"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def search_payload(config: Dict[str, Any], query: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "query": query["query"],
        "focus": query.get("focus", "general"),
        "country": config.get("country", "US"),
        "locale": config.get("locale", "en-US"),
        "search_depth": query.get("search_depth", config.get("search_depth", "fast")),
        "include_answer": query.get("include_answer", config.get("include_answer", True)),
        "max_results": int(query.get("max_results", config.get("max_results", 8))),
    }


def call_nimble_search(payload: Dict[str, Any], api_key: str, endpoint: str) -> Dict[str, Any]:
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    try:
        body = response.json()
    except ValueError:
        body = {"raw_text": response.text}
    if response.status_code >= 400:
        raise RuntimeError(f"Nimble Search API returned {response.status_code}: {json.dumps(body)[:800]}")
    return body


def sample_raw_response(query: Dict[str, Any]) -> Dict[str, Any]:
    """Synthetic dry-run response shaped like a compact search result payload."""
    label = query.get("label", query["id"])
    source = query.get("source_type", "web")
    return {
        "status": "success",
        "answer": f"Early {label.lower()} shows mostly positive interest with a few repeated concerns around pricing, privacy, and onboarding clarity.",
        "results": [
            {
                "title": f"Builders praise the launch but ask about pricing — {label}",
                "url": f"https://example.com/{query['id']}/positive-pricing",
                "snippet": "Users say the workflow looks useful and fast, but several comments ask whether the paid plan is too expensive for small teams.",
                "content": "Positive launch reaction. Useful automation, clean setup, fast results. Pricing concern appears repeatedly.",
            },
            {
                "title": f"Privacy questions show up in {source} discussion",
                "url": f"https://example.com/{query['id']}/privacy-risk",
                "snippet": "Teams like the product idea, but privacy and data retention questions are a blocker for some buyers.",
                "content": "The product is promising, but privacy, compliance, and admin controls need clearer messaging.",
            },
            {
                "title": f"Unexpected use case: product teams share launch notes",
                "url": f"https://example.com/{query['id']}/unexpected-use-case",
                "snippet": "Several users mention using the product to summarize customer calls and turn them into launch follow-up tasks.",
                "content": "Useful and helpful for product marketing. Unexpected use case around launch retrospectives and customer calls.",
            },
        ],
    }


def candidate_result_lists(raw: Dict[str, Any]) -> Iterable[List[Dict[str, Any]]]:
    for key in ("results", "organic_results", "items"):
        value = raw.get(key)
        if isinstance(value, list):
            yield value
    data = raw.get("data")
    if isinstance(data, dict):
        for key in ("results", "organic_results", "items", "search_results"):
            value = data.get(key)
            if isinstance(value, list):
                yield value
        parsing = data.get("parsing")
        if isinstance(parsing, dict):
            for key in ("results", "organic_results", "items"):
                value = parsing.get(key)
                if isinstance(value, list):
                    yield value


def pick_text(item: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def classify_sentiment(text: str) -> tuple[str, List[str]]:
    words = set(re.findall(r"[a-z][a-z-]+", text.lower()))
    pos = sorted(words & POSITIVE_TERMS)
    neg = sorted(words & NEGATIVE_TERMS)
    if len(pos) > len(neg):
        return "positive", pos + neg
    if neg:
        return "negative", pos + neg
    return "neutral", pos + neg


def normalize_results(raw: Dict[str, Any], query: Dict[str, Any], fetched_at: str) -> List[NormalizedResult]:
    results: List[NormalizedResult] = []
    seen_urls = set()
    for result_list in candidate_result_lists(raw):
        for item in result_list:
            if not isinstance(item, dict):
                continue
            title = pick_text(item, ("title", "name", "headline"))
            url = pick_text(item, ("url", "link", "source_url"))
            snippet = pick_text(item, ("snippet", "description", "summary"))
            content = pick_text(item, ("content", "markdown", "text", "body"))
            if not title and not snippet and not content:
                continue
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            sentiment, matched = classify_sentiment(" ".join([title, snippet, content]))
            results.append(
                NormalizedResult(
                    query_id=query["id"],
                    query_label=query.get("label", query["id"]),
                    source_type=query.get("source_type", "web"),
                    focus=query.get("focus", "general"),
                    title=title or "Untitled result",
                    url=url,
                    snippet=snippet,
                    content=content,
                    sentiment=sentiment,
                    matched_terms=matched,
                    fetched_at=fetched_at,
                )
            )
    return results


def extract_answer(raw: Dict[str, Any]) -> str:
    if isinstance(raw.get("answer"), str):
        return raw["answer"].strip()
    data = raw.get("data")
    if isinstance(data, dict):
        for key in ("answer", "summary"):
            if isinstance(data.get(key), str):
                return data[key].strip()
        parsing = data.get("parsing")
        if isinstance(parsing, dict):
            for key in ("answer", "summary", "markdown"):
                if isinstance(parsing.get(key), str):
                    return parsing[key].strip()
    return ""


def top_terms(results: List[NormalizedResult], term_set: set[str], limit: int = 8) -> List[str]:
    counter = Counter()
    for result in results:
        words = set(re.findall(r"[a-z][a-z-]+", " ".join([result.title, result.snippet, result.content]).lower()))
        counter.update(words & term_set)
    return [term for term, _ in counter.most_common(limit)]


def make_report(config: Dict[str, Any], raw_by_query: Dict[str, Dict[str, Any]], normalized: List[NormalizedResult], output_dir: Path) -> Dict[str, Any]:
    sentiment_counts = Counter(r.sentiment for r in normalized)
    source_counts = Counter(r.source_type for r in normalized)
    query_counts = Counter(r.query_label for r in normalized)
    total = len(normalized)
    pos = sentiment_counts.get("positive", 0)
    neg = sentiment_counts.get("negative", 0)
    neutral = sentiment_counts.get("neutral", 0)
    overall = "positive" if pos > max(neg, neutral) else "negative" if neg > max(pos, neutral) else "mixed"

    buckets = defaultdict(list)
    for result in normalized:
        buckets[result.sentiment].append(asdict(result))

    risks = top_terms(normalized, RISK_TERMS, limit=6)
    positive_themes = top_terms(normalized, POSITIVE_TERMS, limit=6)
    negative_themes = top_terms(normalized, NEGATIVE_TERMS, limit=6)

    query_summaries = []
    for query in config.get("queries", []):
        raw = raw_by_query.get(query["id"], {})
        query_summaries.append({
            "query_id": query["id"],
            "label": query.get("label", query["id"]),
            "source_type": query.get("source_type", "web"),
            "focus": query.get("focus", "general"),
            "query": query["query"],
            "answer": extract_answer(raw),
            "result_count": query_counts.get(query.get("label", query["id"]), 0),
        })

    report = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "product_name": config.get("product_name", "Unknown product"),
        "launch_context": config.get("launch_context", ""),
        "config": config,
        "executive_summary": {
            "overall_sentiment": overall,
            "summary": (
                f"Found {total} normalized launch-sentiment signals. "
                f"Positive: {pos}, negative: {neg}, neutral: {neutral}. "
                f"Main positive themes: {', '.join(positive_themes) or 'none detected'}. "
                f"Main risks: {', '.join(risks) or 'none detected'}."
            ),
            "positive_themes": positive_themes,
            "negative_themes": negative_themes,
            "emerging_risks": risks,
        },
        "metrics": {
            "total_results": total,
            "sentiment_counts": dict(sentiment_counts),
            "source_counts": dict(source_counts),
            "query_counts": dict(query_counts),
        },
        "sentiment_buckets": {key: value[:12] for key, value in buckets.items()},
        "source_breakdown": [
            {"source_type": source, "result_count": count}
            for source, count in source_counts.most_common()
        ],
        "representative_examples": [asdict(r) for r in normalized[:12]],
        "query_summaries": query_summaries,
        "recommended_follow_up_searches": [
            f"{config.get('product_name', 'product')} pricing objections Reddit",
            f"{config.get('product_name', 'product')} privacy security concerns",
            f"{config.get('product_name', 'product')} alternatives comparison",
            f"{config.get('product_name', 'product')} launch user feedback product hunt",
        ],
        "product_marketing_actions": [
            "Turn repeated objections into FAQ or launch-page copy.",
            "Use representative positive examples as proof points if the source permits it.",
            "Run the same config weekly to separate launch spike from persistent sentiment.",
            "Create follow-up searches for any risk term that appears across multiple source types.",
        ],
        "files": {
            "report": str(output_dir / "report.json"),
            "normalized_results": str(output_dir / "normalized_results.json"),
            "raw_dir": str(output_dir / "raw"),
        },
    }
    return report


def run(config_path: Path, output_dir: Path, dry_run: bool) -> Path:
    config = load_json(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    endpoint = os.getenv("NIMBLE_SEARCH_ENDPOINT", DEFAULT_ENDPOINT)
    api_key = os.getenv("NIMBLE_API_KEY", "")

    if not dry_run and not api_key:
        raise SystemExit("NIMBLE_API_KEY is not set. Use --dry-run or add it to .env.")

    raw_by_query: Dict[str, Dict[str, Any]] = {}
    normalized: List[NormalizedResult] = []

    for query in config.get("queries", []):
        qid = query["id"]
        raw_path = raw_dir / f"{slugify(qid)}.json"
        fetched_at = now_iso()
        payload = search_payload(config, query)

        if raw_path.exists():
            print(f"✓ cache hit: {qid}")
            raw = load_json(raw_path)
        else:
            if dry_run:
                print(f"• dry-run: would POST /v1/search for {qid}: {payload['query']}")
                raw = sample_raw_response(query)
            else:
                print(f"→ searching: {qid} ({payload['focus']})")
                raw = call_nimble_search(payload, api_key=api_key, endpoint=endpoint)
                time.sleep(0.25)
            # Save raw response before any transformation.
            write_json(raw_path, {"request": payload, "fetched_at": fetched_at, "response": raw})
            print(f"  saved raw: {raw_path}")

        raw_response = raw.get("response", raw)
        raw_by_query[qid] = raw_response
        normalized.extend(normalize_results(raw_response, query, fetched_at=fetched_at))

    write_json(output_dir / "normalized_results.json", [asdict(r) for r in normalized])
    write_json(output_dir / "schema.json", SCHEMA)
    report = make_report(config, raw_by_query, normalized, output_dir)
    write_json(output_dir / "report.json", report)
    print(f"\nWrote report: {output_dir / 'report.json'}")
    print(report["executive_summary"]["summary"])
    return output_dir / "report.json"


def default_output_dir(dry_run: bool) -> Path:
    if dry_run:
        return APP_DIR / "data" / "dry_run"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return APP_DIR / "data" / "runs" / stamp


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect consumer sentiment signals with Nimble Search API.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to config JSON.")
    parser.add_argument("--output", type=Path, help="Output run directory. Defaults to data/runs/<timestamp> or data/dry_run.")
    parser.add_argument("--dry-run", action="store_true", help="Do not call Nimble; write synthetic sample-shaped responses.")
    args = parser.parse_args()

    output_dir = args.output or default_output_dir(args.dry_run)
    try:
        run(args.config, output_dir, args.dry_run)
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
