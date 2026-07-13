"""
collect.py - Competitor Battlecard Generator powered by Nimble Search API.

Runs a structured query plan against live web search, caches raw Nimble
responses, normalizes results into evidence records, and synthesizes a
source-backed battlecard report.

Usage:
    python3 collect.py --dry-run
    python3 collect.py --dry-run --output /tmp/battlecard-dry-run
    python3 collect.py --config config/example_config.json --dry-run
    python3 collect.py --config config/example_config.json --output data/runs/my_run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

APP_DIR = Path(__file__).parent
DEFAULT_CONFIG = APP_DIR / "config" / "example_config.json"
DEFAULT_ENDPOINT = os.getenv(
    "NIMBLE_SEARCH_ENDPOINT", "https://sdk.nimbleway.com/v1/search"
)

SCHEMA = {
    "evidence_id": "str (e.g. E001)",
    "query_id": "str",
    "query_label": "str",
    "signal_type": "pricing|positioning|comparison|review|launch|funding|leadership|market",
    "company_side": "company|competitor|both|market",
    "title": "str",
    "url": "str",
    "domain": "str",
    "snippet": "str",
    "content": "str",
    "answer": "str (Nimble answer field if present)",
    "published_at": "str or null",
    "confidence": "high|medium|low",
    "fetched_at": "ISO-8601 str",
}

# Templates use {company_alias} / {competitor_alias} for disambiguation.
# These default to the primary domain (e.g. "nimbleway.com") so short or
# ambiguous names like Nimble, Square, or Box resolve to the right company.
# Override via company_alias / competitor_alias in the config JSON.
QUERY_PLAN_TEMPLATE = [
    {
        "id": "company_positioning",
        "label": "Company positioning",
        "template": "{company_name} {company_alias} homepage positioning product features",
        "signal_type": "positioning",
        "company_side": "company",
        "focus": "general",
        "search_depth": "fast",
    },
    {
        "id": "competitor_positioning",
        "label": "Competitor positioning",
        "template": "{competitor_name} {competitor_alias} homepage positioning product features",
        "signal_type": "positioning",
        "company_side": "competitor",
        "focus": "general",
        "search_depth": "fast",
    },
    {
        "id": "company_pricing",
        "label": "Company pricing",
        "template": "site:{company_domain} pricing plans cost",
        "signal_type": "pricing",
        "company_side": "company",
        "focus": "general",
        "search_depth": "fast",
    },
    {
        "id": "competitor_pricing",
        "label": "Competitor pricing",
        "template": "site:{competitor_domain} pricing plans cost",
        "signal_type": "pricing",
        "company_side": "competitor",
        "focus": "general",
        "search_depth": "fast",
    },
    {
        "id": "comparison_pages",
        "label": "Comparison pages",
        "template": "{company_name} {company_alias} vs {competitor_name} {competitor_alias} comparison alternatives reviews",
        "signal_type": "comparison",
        "company_side": "both",
        "focus": "general",
        "search_depth": "fast",
    },
    {
        "id": "competitor_g2_reviews",
        "label": "Competitor G2 reviews",
        "template": "{competitor_name} {competitor_alias} G2 reviews pros cons pricing support",
        "signal_type": "review",
        "company_side": "competitor",
        "focus": "general",
        "search_depth": "lite",
    },
    {
        "id": "company_g2_reviews",
        "label": "Company G2 reviews",
        "template": "{company_name} {company_alias} G2 reviews pros cons pricing support",
        "signal_type": "review",
        "company_side": "company",
        "focus": "general",
        "search_depth": "lite",
    },
    {
        "id": "competitor_recent_launches",
        "label": "Competitor recent launches",
        "template": "{competitor_name} {competitor_alias} launched announced new feature product update 2026",
        "signal_type": "launch",
        "company_side": "competitor",
        "focus": "news",
        "search_depth": "lite",
    },
    {
        "id": "company_recent_launches",
        "label": "Company recent launches",
        "template": "{company_name} {company_alias} launched announced new feature product update 2026",
        "signal_type": "launch",
        "company_side": "company",
        "focus": "news",
        "search_depth": "lite",
    },
    {
        "id": "company_funding",
        "label": "Company funding",
        "template": "{company_name} {company_alias} funding Series acquisition valuation investors 2026",
        "signal_type": "funding",
        "company_side": "company",
        "focus": "news",
        "search_depth": "lite",
    },
    {
        "id": "competitor_funding",
        "label": "Competitor funding",
        "template": "{competitor_name} {competitor_alias} funding Series acquisition valuation investors 2026",
        "signal_type": "funding",
        "company_side": "competitor",
        "focus": "news",
        "search_depth": "lite",
    },
    {
        "id": "competitor_leadership",
        "label": "Competitor leadership",
        "template": "{competitor_name} {competitor_alias} CEO founder executive hire leadership appointed 2026",
        "signal_type": "leadership",
        "company_side": "competitor",
        "focus": "news",
        "search_depth": "lite",
    },
    {
        "id": "market_context",
        "label": "Market context",
        "template": "{company_name} {company_alias} {competitor_name} {competitor_alias} market category competitors",
        "signal_type": "market",
        "company_side": "market",
        "focus": "general",
        "search_depth": "fast",
    },
]


# ---- utilities ---------------------------------------------------------------


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_]+", "-", value)
    return value.strip("-")


def domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return url


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


# ---- query plan --------------------------------------------------------------


def build_query_plan(config: dict) -> List[dict]:
    company_domain = domain_from_url(config["company_url"])
    competitor_domain = domain_from_url(config["competitor_url"])
    # Alias defaults to the primary domain so ambiguous names (Nimble, Square,
    # Box) resolve to the right company. Set explicitly in config to override.
    company_alias = config.get("company_alias") or company_domain
    competitor_alias = config.get("competitor_alias") or competitor_domain
    subs = {
        "company_name": config["company_name"],
        "competitor_name": config["competitor_name"],
        "company_domain": company_domain,
        "competitor_domain": competitor_domain,
        "company_alias": company_alias,
        "competitor_alias": competitor_alias,
    }
    plan = []
    for tmpl in QUERY_PLAN_TEMPLATE:
        entry = dict(tmpl)
        entry["query"] = tmpl["template"].format(**subs)
        entry["company_domain"] = company_domain
        entry["competitor_domain"] = competitor_domain
        plan.append(entry)
    return plan


def search_payload(config: dict, query: dict) -> dict:
    return {
        "query": query["query"],
        "search_engine": "google_search",
        "country": config.get("country", "US"),
        "locale": config.get("locale", "en-US"),
        "search_depth": query.get("search_depth", "lite"),
        "num_results": config.get("max_results", 8),
        "include_answer": config.get("include_answer", True),
    }


def raw_path_for_query(output_dir: Path, query: dict) -> Path:
    return output_dir / "raw" / f"{query['id'].replace('_', '-')}.json"


# ---- dry run sample responses ------------------------------------------------


def sample_raw_response(config: dict, query: dict) -> dict:
    company = config["company_name"]
    competitor = config["competitor_name"]
    company_domain = domain_from_url(config["company_url"])
    competitor_domain = domain_from_url(config["competitor_url"])
    signal = query["signal_type"]
    side = query["company_side"]

    name = company if side == "company" else competitor if side == "competitor" else f"{company}/{competitor}"
    domain = company_domain if side == "company" else competitor_domain if side == "competitor" else company_domain

    sample_results = []

    if signal == "pricing":
        sample_results = [
            {
                "title": f"{name} Pricing | Plans and Cost",
                "url": f"https://{domain}/pricing",
                "snippet": f"{name} offers a free tier, a Pro plan at $12/user/month, and an Enterprise plan with custom pricing. Annual billing saves 20%.",
            },
            {
                "title": f"{name} Pricing Review 2026 - G2",
                "url": f"https://www.g2.com/products/{slugify(name)}/pricing",
                "snippet": f"Users rate {name} pricing 3.8/5. Common feedback: free tier is generous but Pro limits are reached quickly.",
            },
        ]
        answer = f"{name} has a freemium model. Pro is $12/user/month with annual billing. Enterprise is custom."

    elif signal == "positioning":
        sample_results = [
            {
                "title": f"{name} - The issue tracker for modern software teams",
                "url": f"https://{domain}",
                "snippet": f"{name} is purpose-built for software development teams who want speed without complexity. Designed for teams that ship fast.",
            },
            {
                "title": f"Why teams choose {name}",
                "url": f"https://{domain}/why",
                "snippet": f"{name} focuses on developer experience, keyboard-first workflows, and tight Git integrations to reduce friction.",
            },
        ]
        answer = f"{name} positions as a fast, developer-friendly tool for engineering teams."

    elif signal == "comparison":
        sample_results = [
            {
                "title": f"{company} vs {competitor}: Which is better in 2026?",
                "url": f"https://www.g2.com/compare/{slugify(company)}-vs-{slugify(competitor)}",
                "snippet": f"{company} scores higher on ease of use (9.1 vs 7.4). {competitor} scores higher on feature set breadth and enterprise integrations.",
            },
            {
                "title": f"I switched from {competitor} to {company} - here is why",
                "url": f"https://dev.to/post/{slugify(company)}-vs-{slugify(competitor)}",
                "snippet": f"After 6 months on {competitor}, our team moved to {company}. Setup took 30 minutes vs days. The speed difference is real.",
            },
        ]
        answer = f"{company} is rated higher on ease of use; {competitor} leads on enterprise breadth."

    elif signal == "review":
        sample_results = [
            {
                "title": f"{name} Reviews 2026 - G2",
                "url": f"https://www.g2.com/products/{slugify(name)}/reviews",
                "snippet": f"Pros: fast, clean UI, great keyboard shortcuts, solid GitHub integration. Cons: limited reporting, no time tracking, mobile app is weak.",
            },
            {
                "title": f"{name} Capterra Reviews",
                "url": f"https://www.capterra.com/p/{slugify(name)}/reviews",
                "snippet": f"4.5/5 from 320 reviews. Top praise: onboarding is smooth. Top complaint: enterprise SSO setup is painful.",
            },
        ]
        answer = f"{name} reviews highlight speed and UX as strengths; reporting and mobile are common complaints."

    elif signal == "launch":
        sample_results = [
            {
                "title": f"{name} announces AI-powered triage and sprint planning",
                "url": f"https://{domain}/blog/ai-triage-2026",
                "snippet": f"{name} launched AI issue triage in April 2026, automatically categorizing and prioritizing incoming issues based on team patterns.",
                "published_at": "2026-04-10",
            },
            {
                "title": f"{name} Product Update - Q1 2026",
                "url": f"https://{domain}/changelog",
                "snippet": f"Q1 2026 highlights: faster search, new roadmap view, Slack thread sync, and a redesigned mobile app.",
                "published_at": "2026-03-28",
            },
        ]
        answer = f"{name} launched AI triage in April 2026 and shipped major Q1 updates including a redesigned mobile app."

    elif signal == "funding":
        sample_results = [
            {
                "title": f"{name} raises $35M Series B to expand enterprise features",
                "url": f"https://techcrunch.com/{slugify(name)}-series-b-2026",
                "snippet": f"{name} closed a $35M Series B in February 2026, led by Accel. The round will fund enterprise integrations and international expansion.",
                "published_at": "2026-02-15",
            },
        ]
        answer = f"{name} raised a $35M Series B in February 2026."

    elif signal == "leadership":
        sample_results = [
            {
                "title": f"{name} appoints new Chief Revenue Officer",
                "url": f"https://{domain}/blog/cro-hire-2026",
                "snippet": f"{name} hired a CRO from Salesforce in March 2026 to lead the push into enterprise. The move signals a shift toward upmarket.",
                "published_at": "2026-03-05",
            },
        ]
        answer = f"{name} hired a CRO from Salesforce in March 2026."

    else:
        sample_results = [
            {
                "title": f"{name} and the project management market in 2026",
                "url": f"https://www.g2.com/categories/project-management",
                "snippet": f"The project management software market is growing 12% YoY. Key players include {company} and {competitor} alongside Asana, Monday, and Notion.",
            },
        ]
        answer = f"The project management market includes both {company} and {competitor} among key players."

    return {
        "query": query["query"],
        "answer": answer,
        "results": sample_results,
        "_dry_run": True,
    }


# ---- Nimble API --------------------------------------------------------------


def call_nimble_search(payload: dict, api_key: str, endpoint: str, retries: int = 3) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    last_err: Exception = RuntimeError("No attempts made")
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=90)
            if resp.ok:
                return resp.json()
            body_preview = resp.text[:400] if resp.text else "(empty body)"
            last_err = RuntimeError(f"Nimble API returned {resp.status_code}: {body_preview}")
            if resp.status_code in (502, 503, 504) and attempt < retries:
                print(f"    retrying ({attempt}/{retries})...")
                time.sleep(2 ** attempt)
                continue
            raise last_err
        except requests.exceptions.Timeout:
            last_err = RuntimeError("Nimble API request timed out after 90s")
            if attempt < retries:
                print(f"    timeout, retrying ({attempt}/{retries})...")
                time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Nimble API request failed: {exc}") from exc
    raise last_err


# ---- collection --------------------------------------------------------------


def run_collection(
    config: dict,
    output_dir: Path,
    dry_run: bool = True,
    api_key: Optional[str] = None,
    endpoint: str = DEFAULT_ENDPOINT,
) -> List[dict]:
    query_plan = build_query_plan(config)
    (output_dir / "raw").mkdir(parents=True, exist_ok=True)
    raw_responses = []

    for i, query in enumerate(query_plan, 1):
        raw_path = raw_path_for_query(output_dir, query)
        if raw_path.exists():
            print(f"  [{i}/{len(query_plan)}] {query['label']} - cached, skipping")
            raw = load_json(raw_path)
        elif dry_run:
            print(f"  [{i}/{len(query_plan)}] {query['label']} - dry run")
            raw = sample_raw_response(config, query)
            write_json(raw_path, raw)
        else:
            if not api_key:
                print(
                    "ERROR: NIMBLE_API_KEY is required for live mode. Set it in .env or the environment.",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(f"  [{i}/{len(query_plan)}] {query['label']} - fetching...")
            payload = search_payload(config, query)
            try:
                raw = call_nimble_search(payload, api_key, endpoint)
            except RuntimeError as exc:
                print(f"  [{i}/{len(query_plan)}] {query['label']} - SKIPPED ({exc})")
                raw = {"_skipped": True, "_error": str(exc), "results": [], "answer": ""}
            write_json(raw_path, raw)
            time.sleep(0.3)

        raw_responses.append((query, raw))

    return raw_responses


# ---- normalization -----------------------------------------------------------


def candidate_result_lists(raw: dict) -> List[dict]:
    for key in ["results", "organic_results", "items"]:
        if isinstance(raw.get(key), list):
            return raw[key]
    data = raw.get("data", {})
    if isinstance(data, dict):
        for key in ["results", "organic_results", "items", "search_results"]:
            if isinstance(data.get(key), list):
                return data[key]
        parsing = data.get("parsing", {})
        if isinstance(parsing, dict) and isinstance(parsing.get("results"), list):
            return parsing["results"]
    return []


def pick_text(item: dict, keys: List[str]) -> str:
    for k in keys:
        val = item.get(k)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def extract_answer(raw: dict) -> str:
    for key in ["answer", "summary", "ai_answer"]:
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    data = raw.get("data", {})
    if isinstance(data, dict):
        for key in ["answer", "summary"]:
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def confidence_for_result(item: dict, query: dict) -> str:
    url = (item.get("url") or item.get("link") or "").lower()
    title = (item.get("title") or "").lower()
    snippet = (item.get("snippet") or item.get("description") or "").lower()
    text = f"{title} {snippet}"

    company_domain = query.get("company_domain", "").lower()
    competitor_domain = query.get("competitor_domain", "").lower()
    signal = query.get("signal_type", "")
    side = query.get("company_side", "")

    relevant_domain = company_domain if side == "company" else competitor_domain if side == "competitor" else ""

    if relevant_domain and relevant_domain in url and signal in ("pricing", "positioning"):
        return "high"

    company_name_words = set(query.get("id", "").replace("_", " ").split())
    if any(w in text for w in [company_domain, competitor_domain] if w):
        return "high"

    review_domains = ("g2.com", "capterra.com", "trustpilot.com", "producthunt.com", "reddit.com")
    if any(d in url for d in review_domains):
        return "medium"

    news_domains = ("techcrunch.com", "venturebeat.com", "crunchbase.com", "forbes.com")
    if any(d in url for d in news_domains) and signal in ("funding", "leadership", "launch"):
        return "medium"

    return "low"


def _answer_citation_urls(raw: dict) -> List[str]:
    """Return source URLs cited in the Nimble answer, in citation order."""
    results = candidate_result_lists(raw)
    citations = raw.get("answer_citations", [])
    urls = []
    for c in citations:
        idx = c.get("result_index")
        if isinstance(idx, int) and idx < len(results):
            url = pick_text(results[idx], ["url", "link", "href"])
            if url:
                urls.append(url)
    return urls


def normalize_results(
    raw: dict, query: dict, fetched_at: str, id_offset: int = 0
) -> List[dict]:
    results = candidate_result_lists(raw)
    answer = extract_answer(raw)
    citation_urls = _answer_citation_urls(raw)
    is_dry_run = bool(raw.get("_dry_run"))
    evidence = []

    for i, item in enumerate(results):
        url = pick_text(item, ["url", "link", "href"])
        title = pick_text(item, ["title", "name", "heading"])
        snippet = pick_text(item, ["snippet", "description", "text", "body"])
        content = pick_text(item, ["content", "body_text", "text"])
        published_at = pick_text(item, ["published_at", "date", "published_date", "pubDate"])

        if not url:
            continue

        domain = domain_from_url(url)
        confidence = confidence_for_result(item, query)
        evidence_id = f"E{id_offset + i + 1:03d}"

        evidence.append({
            "evidence_id": evidence_id,
            "query_id": query["id"],
            "query_label": query["label"],
            "signal_type": query["signal_type"],
            "company_side": query["company_side"],
            "title": title,
            "url": url,
            "domain": domain,
            "snippet": snippet,
            "content": content,
            "answer": answer if i == 0 else "",
            "answer_citation_urls": citation_urls if i == 0 else [],
            "published_at": published_at or None,
            "confidence": confidence,
            "fetched_at": fetched_at,
            "dry_run": is_dry_run,
        })

    return evidence


# ---- report generation -------------------------------------------------------


def _evidence_for(evidence: List[dict], signal_types=None, company_side=None, confidence=None) -> List[dict]:
    result = evidence
    if signal_types:
        result = [e for e in result if e["signal_type"] in signal_types]
    if company_side:
        result = [e for e in result if e["company_side"] in (company_side if isinstance(company_side, list) else [company_side])]
    if confidence:
        order = {"high": 0, "medium": 1, "low": 2}
        allowed = {"high", "medium"} if confidence == "medium+" else {confidence}
        result = [e for e in result if e["confidence"] in allowed]
    return result


def _ids(items: List[dict]) -> List[str]:
    return [e["evidence_id"] for e in items]


def _first_snippet(items: List[dict], fallback: str = "No reliable signal found in this run.") -> str:
    for item in items:
        if item.get("answer"):
            return item["answer"]
        if item.get("snippet"):
            return item["snippet"]
    return fallback


def _snippets(items: List[dict], max_items: int = 3) -> List[str]:
    seen = set()
    out = []
    for item in items:
        text = item.get("answer") or item.get("snippet") or ""
        if text and text not in seen:
            seen.add(text)
            out.append(text)
        if len(out) >= max_items:
            break
    return out or ["No reliable signal found in this run."]


def make_report(config: dict, evidence: List[dict], output_dir: Path) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    company = config["company_name"]
    competitor = config["competitor_name"]

    # Positioning
    co_pos = _evidence_for(evidence, signal_types=["positioning"], company_side="company")
    cx_pos = _evidence_for(evidence, signal_types=["positioning"], company_side="competitor")
    comp_both = _evidence_for(evidence, signal_types=["comparison"], company_side=["both", "company", "competitor"])

    co_pos_summary = _first_snippet(co_pos, f"No reliable positioning signal found for {company}.")
    cx_pos_summary = _first_snippet(cx_pos, f"No reliable positioning signal found for {competitor}.")
    pos_diff = _first_snippet(comp_both, f"No direct comparison signal found between {company} and {competitor}.")

    # Pricing
    co_price = _evidence_for(evidence, signal_types=["pricing"], company_side="company")
    cx_price = _evidence_for(evidence, signal_types=["pricing"], company_side="competitor")
    co_price_signals = _snippets(co_price)
    cx_price_signals = _snippets(cx_price)

    price_angle = "No reliable pricing comparison signal found in this run."
    if co_price and cx_price:
        price_angle = (
            f"Both {company} and {competitor} offer freemium or tiered pricing. "
            f"Use pricing uncertainty or enterprise complexity as a discovery angle."
        )
    elif cx_price:
        price_angle = f"Competitor pricing data found. Use it to anchor value conversation."
    elif co_price:
        price_angle = f"{company} pricing found. Lead with value, then ask how they currently handle cost at scale."

    # Recent moves
    launches = _evidence_for(evidence, signal_types=["launch"])
    funding = _evidence_for(evidence, signal_types=["funding"])
    co_funding = _evidence_for(evidence, signal_types=["funding"], company_side="company")
    cx_funding = _evidence_for(evidence, signal_types=["funding"], company_side="competitor")
    leadership = _evidence_for(evidence, signal_types=["leadership"])

    launch_items = [
        {"signal": e["snippet"] or e["title"], "source": e["url"], "evidence_id": e["evidence_id"]}
        for e in launches[:4] if e.get("snippet") or e.get("title")
    ] or [{"signal": "No reliable launch signal found in this run.", "source": None, "evidence_id": None}]

    funding_items = [
        {"signal": e["snippet"] or e["title"], "source": e["url"], "evidence_id": e["evidence_id"]}
        for e in funding[:3] if e.get("snippet") or e.get("title")
    ] or [{"signal": "No reliable funding signal found in this run.", "source": None, "evidence_id": None}]

    leadership_items = [
        {"signal": e["snippet"] or e["title"], "source": e["url"], "evidence_id": e["evidence_id"]}
        for e in leadership[:3] if e.get("snippet") or e.get("title")
    ] or [{"signal": "No reliable leadership signal found in this run.", "source": None, "evidence_id": None}]

    # Reviews
    co_reviews = _evidence_for(evidence, signal_types=["review"], company_side="company")
    cx_reviews = _evidence_for(evidence, signal_types=["review"], company_side="competitor")
    all_reviews = co_reviews + cx_reviews

    praise = _snippets([e for e in all_reviews if any(w in (e.get("snippet") or "").lower() for w in ["great", "fast", "easy", "clean", "love", "good"])], 3)
    complaints = _snippets([e for e in all_reviews if any(w in (e.get("snippet") or "").lower() for w in ["cons", "complaint", "missing", "slow", "expensive", "weak", "painful"])], 3)
    switching = []
    if cx_reviews:
        switching = [f"Buyer moving from {competitor}: {e['snippet'][:120]}" for e in cx_reviews[:2] if e.get("snippet")]
    if not switching:
        switching = [f"No direct switching signals found. Ask prospects what made them evaluate alternatives to {competitor}."]

    # SWOT
    strengths = []
    if co_pos:
        strengths.append({"point": f"{company} clear positioning: {co_pos[0].get('snippet', '')[:100]}", "evidence_ids": _ids(co_pos[:1])})
    if co_reviews:
        strengths.append({"point": f"Positive review signals: {_first_snippet(co_reviews)[:100]}", "evidence_ids": _ids(co_reviews[:2])})
    if not strengths:
        strengths.append({"point": f"No high-confidence strength signals found for {company}.", "evidence_ids": []})

    weaknesses = []
    if not co_price:
        weaknesses.append({"point": f"No clear pricing signal found for {company}. May create buyer confusion.", "evidence_ids": []})
    cx_praise = [e for e in cx_reviews if any(w in (e.get("snippet") or "").lower() for w in ["great", "feature", "enterprise", "integration"])]
    if cx_praise:
        weaknesses.append({"point": f"{competitor} praised for: {cx_praise[0].get('snippet', '')[:100]}", "evidence_ids": _ids(cx_praise[:1])})
    if not weaknesses:
        weaknesses.append({"point": "No clear weakness signals found in this run.", "evidence_ids": []})

    opportunities = []
    cx_complaints = [e for e in cx_reviews if any(w in (e.get("snippet") or "").lower() for w in ["slow", "expensive", "complex", "hard", "missing", "painful", "complaint"])]
    if cx_complaints:
        opportunities.append({"point": f"{competitor} complaint signal - potential opening: {cx_complaints[0].get('snippet', '')[:100]}", "evidence_ids": _ids(cx_complaints[:1])})
    if comp_both:
        opportunities.append({"point": f"Active buyer comparison market: {_first_snippet(comp_both)[:100]}", "evidence_ids": _ids(comp_both[:2])})
    if not opportunities:
        opportunities.append({"point": "No clear opportunity signals found in this run.", "evidence_ids": []})

    threats = []
    if funding:
        threats.append({"point": f"{competitor} funding signal: {_first_snippet(funding)[:100]}", "evidence_ids": _ids(funding[:1])})
    if leadership:
        threats.append({"point": f"{competitor} leadership move: {_first_snippet(leadership)[:100]}", "evidence_ids": _ids(leadership[:1])})
    cx_launch = _evidence_for(evidence, signal_types=["launch"], company_side="competitor")
    if cx_launch:
        threats.append({"point": f"{competitor} recent launch: {_first_snippet(cx_launch)[:100]}", "evidence_ids": _ids(cx_launch[:1])})
    if not threats:
        threats.append({"point": "No clear threat signals found in this run.", "evidence_ids": []})

    # Battlecard
    lead_with = []
    if co_pos:
        lead_with.append({"point": f"Lead with {company} speed and developer experience positioning.", "evidence_ids": _ids(co_pos[:1])})
    if cx_complaints:
        lead_with.append({"point": f"Acknowledge {competitor}'s complexity. Ask where it costs them time.", "evidence_ids": _ids(cx_complaints[:1])})
    if not lead_with:
        lead_with.append({"point": "Gather more live positioning data before crafting lead-with messages.", "evidence_ids": []})

    watch_out_for = []
    if funding:
        watch_out_for.append({"point": f"{competitor} has recent funding - feature velocity may increase.", "evidence_ids": _ids(funding[:1])})
    cx_strong = [e for e in cx_reviews if e.get("confidence") == "high"]
    if cx_strong:
        watch_out_for.append({"point": f"{competitor} has strong review signals on G2/Capterra - don't dismiss.", "evidence_ids": _ids(cx_strong[:1])})
    if not watch_out_for:
        watch_out_for.append({"point": "Verify live competitive signals before the call.", "evidence_ids": []})

    objections = [
        {"objection": f"We already use {competitor}.", "response": f"Many teams start with {competitor} for its breadth. Where does it create friction for your engineers today?", "evidence_ids": _ids(cx_complaints[:1])},
        {"objection": "Switching cost is too high.", "response": "We've helped teams migrate in under a week. What's the cost of staying on a tool your team works around?", "evidence_ids": []},
        {"objection": f"{competitor} has more integrations.", "response": f"Which three integrations are non-negotiable? We likely cover them. Let's check.", "evidence_ids": []},
    ]

    discovery_questions = [
        f"How long does it take a new engineer to get productive in your current {competitor} setup?",
        f"What does your team do when {competitor} slows down a release?",
        "Who owns the backlog today, and how much time do they spend on triage vs. actual prioritization?",
        f"Have you compared {competitor} vs alternatives recently? What drove that evaluation?",
        "What would have to be true for your team to switch tools in the next quarter?",
    ]

    do_not_claim = [
        f"Do not claim {company} has specific integrations without verifying.",
        "Do not quote pricing without checking the live pricing page.",
        f"Do not imply {competitor} is declining without funding or review evidence.",
        "Do not fabricate G2 review scores. Always link to the source.",
    ]

    # Strength scores (0-10 per dimension, based on evidence signal count and confidence)
    def _score(items: List[dict], cap: int = 5) -> float:
        pts = sum(2 if e.get("confidence") == "high" else 1 for e in items[:cap])
        return round(min(pts / (cap * 2) * 10, 10), 1)

    co_launch = _evidence_for(evidence, signal_types=["launch"], company_side="company")
    strength_scores = {
        "dimensions": ["Positioning", "Pricing clarity", "Reviews", "Recent launches", "Funding momentum", "Market presence"],
        "company": [
            _score(co_pos),
            _score(co_price),
            _score(co_reviews),
            _score(co_launch),
            _score(co_funding),
            _score(_evidence_for(evidence, signal_types=["market"], company_side=["company", "both", "market"])),
        ],
        "competitor": [
            _score(cx_pos),
            _score(cx_price),
            _score(cx_reviews),
            _score(_evidence_for(evidence, signal_types=["launch"], company_side="competitor")),
            _score(funding),
            _score(_evidence_for(evidence, signal_types=["market"], company_side=["competitor", "both", "market"])),
        ],
    }
    strength_scores["company_total"] = round(sum(strength_scores["company"]) / len(strength_scores["dimensions"]), 1)
    strength_scores["competitor_total"] = round(sum(strength_scores["competitor"]) / len(strength_scores["dimensions"]), 1)
    strength_scores["verdict"] = (
        company if strength_scores["company_total"] > strength_scores["competitor_total"]
        else competitor if strength_scores["competitor_total"] > strength_scores["company_total"]
        else "Tied"
    )

    # Executive summary
    exec_summary = []
    if co_pos:
        text = co_pos[0].get('answer') or co_pos[0].get('snippet', '')
        exec_summary.append(text[:160] if text else f"No positioning signal found for {company}.")
    if cx_pos:
        text = cx_pos[0].get('answer') or cx_pos[0].get('snippet', '')
        exec_summary.append(text[:160] if text else f"No positioning signal found for {competitor}.")
    if comp_both:
        exec_summary.append(f"Comparison: {_first_snippet(comp_both)[:100]}")
    if co_funding:
        exec_summary.append(f"{company} funding: {_first_snippet(co_funding)[:100]}")
    if cx_funding:
        exec_summary.append(f"{competitor} funding: {_first_snippet(cx_funding)[:100]}")
    if not exec_summary:
        exec_summary.append("Run with live data or expand dry-run samples for richer signals.")

    report = {
        "metadata": {
            "company_name": company,
            "company_url": config["company_url"],
            "competitor_name": competitor,
            "competitor_url": config["competitor_url"],
            "generated_at": now,
            "evidence_count": len(evidence),
            "dry_run": any(e.get("fetched_at", "").startswith("dry") for e in evidence) or len(evidence) == 0,
        },
        "strength_scores": strength_scores,
        "executive_summary": exec_summary,
        "positioning": {
            "company": {"summary": co_pos_summary, "evidence_ids": _ids(co_pos[:3])},
            "competitor": {"summary": cx_pos_summary, "evidence_ids": _ids(cx_pos[:3])},
            "difference": pos_diff,
        },
        "pricing": {
            "company": {"signals": co_price_signals, "evidence_ids": _ids(co_price[:3])},
            "competitor": {"signals": cx_price_signals, "evidence_ids": _ids(cx_price[:3])},
            "sales_angle": price_angle,
        },
        "recent_moves": {
            "launches": launch_items,
            "funding": funding_items,
            "leadership": leadership_items,
        },
        "review_themes": {
            "praise": praise,
            "complaints": complaints,
            "switching_triggers": switching,
        },
        "swot": {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "opportunities": opportunities,
            "threats": threats,
        },
        "battlecard": {
            "lead_with": lead_with,
            "watch_out_for": watch_out_for,
            "objection_responses": objections,
            "discovery_questions": discovery_questions,
            "do_not_claim": do_not_claim,
        },
        "evidence": evidence,
    }

    write_json(output_dir / "report.json", report)
    write_json(output_dir / "normalized_evidence.json", evidence)
    write_json(output_dir / "schema.json", SCHEMA)

    return report


# ---- CLI ---------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Competitor Battlecard Generator")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to JSON config file")
    parser.add_argument("--output", default=None, help="Output directory (default: data/runs/<timestamp>)")
    parser.add_argument("--dry-run", action="store_true", help="Use sample data instead of live API")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_json(config_path)

    if args.output:
        output_dir = Path(args.output)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
        slug = f"{slugify(config['company_name'])}-vs-{slugify(config['competitor_name'])}"
        output_dir = APP_DIR / "data" / "runs" / f"{ts}-{slug}"

    api_key = os.getenv("NIMBLE_API_KEY", "")
    dry_run = args.dry_run or not api_key

    if not args.dry_run and not api_key:
        print("ERROR: NIMBLE_API_KEY is not set. Use --dry-run for sample data.", file=sys.stderr)
        sys.exit(1)

    mode = "dry-run" if dry_run else "live"
    print(f"Competitor Battlecard Generator - {mode} mode")
    print(f"  {config['company_name']} vs {config['competitor_name']}")
    print(f"  Output: {output_dir}")

    raw_responses = run_collection(config, output_dir, dry_run=dry_run, api_key=api_key)

    now = datetime.now(timezone.utc).isoformat()
    all_evidence = []
    id_offset = 0
    for query, raw in raw_responses:
        items = normalize_results(raw, query, now, id_offset)
        all_evidence.extend(items)
        id_offset += len(items)

    skipped = [(q["id"], raw.get("_error", "")) for q, raw in raw_responses if raw.get("_skipped")]
    report = make_report(config, all_evidence, output_dir)

    print(f"\nDone. {len(all_evidence)} evidence records, report at {output_dir}/report.json")
    if skipped:
        print(f"Skipped {len(skipped)} queries (API errors): {', '.join(q for q, _ in skipped)}")


if __name__ == "__main__":
    main()
