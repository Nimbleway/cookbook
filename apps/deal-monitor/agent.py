"""
agent.py — LangChain/LangGraph deal monitor powered by NimbleSearchTool.

Runs a live web search, filters out URLs it has already seen, summarizes the
new matches with an OpenRouter-compatible LLM, posts the digest to Slack, and
persists local state for the next run.

Usage:
    python3 agent.py --dry-run
    python3 agent.py
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import requests
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

load_dotenv()

BASE_DIR = Path(__file__).parent
STATE_PATH = BASE_DIR / ".state.json"


class MonitorState(TypedDict, total=False):
    query: str
    results: list[dict[str, Any]]
    new_results: list[dict[str, Any]]
    summary: str
    dry_run: bool


def _log(message: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


def load_seen_urls() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        payload = json.loads(STATE_PATH.read_text())
    except json.JSONDecodeError:
        return set()
    return set(payload.get("seen_urls", []))


def save_seen_urls(urls: set[str]) -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "seen_urls": sorted(urls),
    }
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def normalize_result(item: Any) -> dict[str, Any]:
    """Normalize common Nimble/LangChain result shapes into one dict."""
    if hasattr(item, "dict"):
        item = item.dict()
    if not isinstance(item, dict):
        return {"title": str(item), "url": "", "snippet": ""}

    return {
        "title": item.get("title") or item.get("name") or item.get("heading") or "Untitled result",
        "url": item.get("url") or item.get("link") or item.get("href") or "",
        "snippet": item.get("snippet") or item.get("description") or item.get("content") or item.get("text") or "",
        "raw": item,
    }


def extract_results(tool_output: Any) -> list[dict[str, Any]]:
    """Handle the result formats returned by NimbleSearchTool across versions."""
    if isinstance(tool_output, str):
        try:
            tool_output = json.loads(tool_output)
        except json.JSONDecodeError:
            return [{"title": "Nimble result", "url": "", "snippet": tool_output}]

    if isinstance(tool_output, dict):
        for key in ("results", "items", "data", "organic_results"):
            value = tool_output.get(key)
            if isinstance(value, list):
                return [normalize_result(item) for item in value]
        return [normalize_result(tool_output)]

    if isinstance(tool_output, list):
        return [normalize_result(item) for item in tool_output]

    return [normalize_result(tool_output)]


def build_nimble_search_tool():
    """Create NimbleSearchTool lazily so --dry-run validation stays lightweight."""
    from langchain_nimble import NimbleSearchTool

    api_key = _env("NIMBLE_API_KEY")
    if not api_key:
        raise RuntimeError("NIMBLE_API_KEY is required unless you run with --dry-run")

    return NimbleSearchTool(
        api_key=api_key,
        locale=_env("NIMBLE_SEARCH_LOCALE", "en") or "en",
        country=_env("NIMBLE_SEARCH_COUNTRY", "US") or "US",
        output_format=_env("NIMBLE_OUTPUT_FORMAT", "markdown") or "markdown",
    )


def fetch_news(state: MonitorState) -> MonitorState:
    query = state["query"]
    if state.get("dry_run"):
        _log(f"DRY RUN: would search Nimble for: {query}")
        sample = [
            {
                "title": "Example funding announcement",
                "url": "https://example.com/funding-announcement",
                "snippet": "A sample result used to validate the monitor without calling external APIs.",
            }
        ]
        return {**state, "results": sample}

    tool = build_nimble_search_tool()
    _log(f"Searching Nimble for: {query}")
    output = tool.invoke(
        {
            "query": query,
            "num_results": int(_env("NIMBLE_NUM_RESULTS", "10") or "10"),
            "search_depth": _env("NIMBLE_SEARCH_DEPTH", "lite"),
            "include_answer": (_env("NIMBLE_INCLUDE_ANSWER", "false") or "false").lower() == "true",
            "focus": _env("NIMBLE_SEARCH_FOCUS", "news"),
            "time_range": _env("NIMBLE_SEARCH_TIME_RANGE", "week"),
        }
    )
    results = extract_results(output)
    _log(f"Fetched {len(results)} result(s)")
    return {**state, "results": results}


def filter_seen(state: MonitorState) -> MonitorState:
    seen = load_seen_urls()
    new_results = []

    for result in state.get("results", []):
        url = result.get("url") or result.get("title")
        if url and url not in seen:
            new_results.append(result)

    _log(f"Found {len(new_results)} new result(s)")
    return {**state, "new_results": new_results}


def build_llm() -> ChatOpenAI:
    api_key = _env("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required unless you run with --dry-run")

    return ChatOpenAI(
        model=_env("OPENROUTER_MODEL", "google/gemma-3-27b-it:free"),
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0.2,
        default_headers={
            "HTTP-Referer": _env("OPENROUTER_SITE_URL", "https://nimbleway.com") or "https://nimbleway.com",
            "X-Title": _env("OPENROUTER_APP_NAME", "Nimble Deal Monitor") or "Nimble Deal Monitor",
        },
    )


def summarize_results(state: MonitorState) -> MonitorState:
    new_results = state.get("new_results", [])
    if not new_results:
        return {**state, "summary": "No new results."}

    compact_results = [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": item.get("snippet"),
        }
        for item in new_results[:10]
    ]

    if state.get("dry_run"):
        summary = "DRY RUN: 1 new example result found — Example funding announcement."
        return {**state, "summary": summary}

    llm = build_llm()
    messages = [
        SystemMessage(
            content=(
                "You write concise Slack alerts for business monitoring. "
                "Group related items, keep it short, include links, and call out why each result matters."
            )
        ),
        HumanMessage(
            content=(
                f"Monitoring query: {state['query']}\n\n"
                f"New search results as JSON:\n{json.dumps(compact_results, indent=2)}\n\n"
                "Write a Slack-friendly digest in under 160 words."
            )
        ),
    ]
    response = llm.invoke(messages)
    return {**state, "summary": str(response.content).strip()}


def notify_slack(state: MonitorState) -> MonitorState:
    new_results = state.get("new_results", [])
    summary = state.get("summary", "")

    if not new_results:
        _log("No Slack alert sent because there are no new results")
        return state

    if state.get("dry_run"):
        _log(f"DRY RUN: would send Slack alert:\n{summary}")
        return state

    webhook_url = _env("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("SLACK_WEBHOOK_URL is required unless you run with --dry-run")

    response = requests.post(
        webhook_url,
        json={"text": f"*Nimble deal monitor*\n{summary}"},
        timeout=15,
    )
    response.raise_for_status()
    _log("Slack alert sent")
    return state


def persist_state(state: MonitorState) -> MonitorState:
    seen = load_seen_urls()
    for result in state.get("results", []):
        url = result.get("url") or result.get("title")
        if url:
            seen.add(url)
    if not state.get("dry_run"):
        save_seen_urls(seen)
        _log(f"Saved {len(seen)} seen URL(s) to {STATE_PATH.name}")
    else:
        _log("DRY RUN: state not written")
    return state


def build_graph():
    graph = StateGraph(MonitorState)
    graph.add_node("fetch_news", fetch_news)
    graph.add_node("filter_seen", filter_seen)
    graph.add_node("summarize_results", summarize_results)
    graph.add_node("notify_slack", notify_slack)
    graph.add_node("persist_state", persist_state)

    graph.set_entry_point("fetch_news")
    graph.add_edge("fetch_news", "filter_seen")
    graph.add_edge("filter_seen", "summarize_results")
    graph.add_edge("summarize_results", "notify_slack")
    graph.add_edge("notify_slack", "persist_state")
    graph.add_edge("persist_state", END)
    return graph.compile()


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor live web results with Nimble + LangGraph")
    parser.add_argument("--query", default=_env("MONITOR_QUERY", "developer tools funding news this week"))
    parser.add_argument("--dry-run", action="store_true", help="Validate the flow without external API calls")
    args = parser.parse_args()

    app = build_graph()
    final_state = app.invoke({"query": args.query, "dry_run": args.dry_run})
    _log(final_state.get("summary", "Done"))


if __name__ == "__main__":
    main()
