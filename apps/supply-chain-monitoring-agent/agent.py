"""
Supply Chain Disruption Monitoring Agent
========================================

A standalone news-monitoring agent for a single use case, in two patterns:

  Pattern A  LangChain agent + Search API
             A create_agent LLM agent (Claude via langchain-anthropic) that runs
             Nimble's search itself and reasons over the results. Recency is
             enforced at the tool level: search is bound to the current 30-day
             window, so results can only be current.

  Pattern B  Deterministic Agent-API harness (no LLM in the loop)
             Calls Nimble's Web Search Agent directly: run -> poll status in
             Python -> fetch result. skill (with goals and source guidance folded
             in) and effort are passed as real run parameters, and the full
             structured result (content + trust) is written straight to disk.

This file is self-contained: it depends only on the packages below, not on the
other use-case files.

Setup:
  pip install -r requirements.txt
  cp .env.example .env   # then set the keys below (or export them)
    NIMBLE_API_KEY      from online.nimbleway.com (both patterns)
    ANTHROPIC_API_KEY   workspace-scoped key; Pattern A only

Run:
  python agent.py        # runs both patterns for this use case
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

from langchain.agents import create_agent
from langchain_nimble import NimbleToolkit
from langchain_anthropic import ChatAnthropic
from nimble_python import Nimble
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"   # set to the Claude model your key can access
EFFORT = "high"               # Nimble WSA effort: low | medium | high | x-high | max
AGENT_NAME = "supply-chain-monitoring"

OUTPUT_DIR = Path("artifacts")
OUTPUT_DIR.mkdir(exist_ok=True)

# --- this use case ---------------------------------------------------------

AGENT_TASK = (
    "Monitor current events that could disrupt container shipping between "
    "Asia and Europe over recent weeks. Identify Red Sea and Suez rerouting "
    "around the Cape of Good Hope, port congestion, and freight-rate "
    "movements, plus any labor, weather, or security disruptions. For each "
    "disruption state the type, geography, affected lanes, likely "
    "operational impact, and severity, and attach a cited source to every "
    "factual and numeric claim. Do not include figures you cannot cite. "
    "Rank by significance and keep to the best-supported five or six."
)

SKILL = (
    "You are a supply-chain risk analyst monitoring the Asia-to-Europe "
    "container lane. Track events that could disrupt the movement, "
    "availability, or cost of goods. Categorize each by type, geography, "
    "and severity, and tie each to the lanes it affects. Prefer maritime "
    "and logistics trade sources, carrier advisories, and port authorities. "
    "Cite a source for every quantitative claim; if you cannot cite a "
    "number, omit it. Separate current developments from long-running "
    "background."
)

GOALS = [
    "Identify disruptions across rerouting, congestion, rates, labor, weather, security",
    "Categorize each by type, geography, and severity",
    "Map each to affected trade lanes and operational impact",
    "Cite every numeric claim; prioritize the best-supported five or six",
]

SOURCE_HINTS = (
    "Prefer port and transportation authority updates, carrier and "
    "logistics statements, and maritime trade publications. Exclude social "
    "platforms."
)

OUTPUT_FIELDS = ["event", "disruption_type", "geography", "severity", "affected_lanes", "source_url"]

# A sample query for trying the Search API directly (not used by either pattern).
SEARCH_QUERY = "Red Sea Suez container diversion Cape of Good Hope carriers"


def _model():
    # Bound a wedged request without tripping on normal long agentic turns.
    # Pattern A only; Pattern B has no LLM in the loop.
    return ChatAnthropic(model=MODEL, max_tokens=8000, timeout=600, max_retries=2)


def _skill_with_goals() -> str:
    """WSA skill string, with goals and source guidance folded in (the run API
    takes skill + sources, not a separate goals list)."""
    return (
        f"{SKILL}\n\n"
        "Goals:\n- " + "\n- ".join(GOALS) + "\n\n"
        f"Source guidance: {SOURCE_HINTS}\n\n"
        f"Return these fields per item: {', '.join(OUTPUT_FIELDS)}. "
        "Every item must carry a date and a source URL."
    )


# ===========================================================================
# Pattern A: LangChain agent + Search API (date-locked to the current window)
# ===========================================================================

def _pattern_a_system_prompt() -> str:
    today = date.today()
    window_start = today - timedelta(days=30)
    return (
        f"CRITICAL DATE CONTEXT. Today's real date is {today:%Y-%m-%d} "
        f"({today:%B %d, %Y}). Your training data ends earlier, so your prior sense "
        f"of 'now' is WRONG for this task. Trust this date, not your memory. "
        f"'The past 30 days' means {window_start:%Y-%m-%d} to {today:%Y-%m-%d} and "
        f"nothing else.\n\n"
        "Rules you must follow:\n"
        f"- Any date filter you pass to a search MUST fall inside "
        f"{window_start:%Y-%m-%d} to {today:%Y-%m-%d}. Never search a "
        f"{today.year - 1} window.\n"
        f"- Results from this window are the target. NEVER discard a result as "
        f"'future-dated'; if a result is dated in {today.year}, it is current.\n"
        f"- Every event you report must have occurred within this window. If you "
        f"cannot find enough {today.year} events, say so rather than substituting "
        f"older ones.\n"
        f"- Do not label the report with a {today.year - 1} cutoff. The research "
        f"cutoff is {today:%Y-%m-%d}.\n\n"
        f"{_skill_with_goals()}\n\n"
        "Method: run several targeted nimble_search queries, one per category, each "
        f"restricted to the {window_start:%Y-%m-%d} to {today:%Y-%m-%d} window. "
        "Deep retrieval is on. Use nimble_extract to pull the full text of the most "
        "authoritative pages. Deduplicate repeats of the same event and reason over "
        "the retrieved content to produce a concise ranked summary."
    )


def _date_locked_search_tool(window_start: date, window_end: date):
    """Wrap nimble_search so start_date/end_date are fixed to the current window.
    The model cannot pass its own dates, so retrieval can only return results from
    the target window. This is what actually enforces recency -- prompt text alone
    does not, because the model fills date args from its (stale) training prior."""
    from langchain_core.tools import tool as _tool

    base = {t.name: t for t in NimbleToolkit(include_search=True).get_tools()}["nimble_search"]
    lo, hi = window_start.isoformat(), window_end.isoformat()

    @_tool("nimble_search",
           description=(
               "Search the live web for CURRENT results only. The date window is fixed "
               f"to {lo}..{hi} and cannot be changed. Returns deep, full-page "
               "content. Pass a focused query string; results are already restricted "
               "to the window."))
    def date_locked_search(query: str, num_results: int = 5) -> str:
        return base.invoke({
            "query": query,
            "num_results": num_results,
            "search_depth": "deep",
            "start_date": lo,
            "end_date": hi,
        })

    return date_locked_search


def build_search_api_agent():
    today = date.today()
    window_start = today - timedelta(days=30)
    tools = [_date_locked_search_tool(window_start, today)]
    tools += [t for t in NimbleToolkit(include_extract=True).get_tools()
              if t.name == "nimble_extract"]
    return create_agent(model=_model(), tools=tools,
                        system_prompt=_pattern_a_system_prompt())


def run_search_api_agent() -> str:
    agent = build_search_api_agent()
    response = agent.invoke({"messages": [("user", AGENT_TASK)]})
    text = response["messages"][-1].content
    if isinstance(text, list):  # anthropic content blocks
        text = "".join(b.get("text", "") for b in text if isinstance(b, dict))
    out = OUTPUT_DIR / "supply_chain_disruption_monitoring_agent__pattern_A.md"
    out.write_text(text, encoding="utf-8")
    print(f"saved {out}")
    return text


# ===========================================================================
# Pattern B: deterministic Agent-API harness (Nimble does the research)
# ===========================================================================

def run_agent_api(effort: str = EFFORT, poll_every: int = 15, timeout: int = 1800) -> dict:
    """Start a Web Search Agent run, poll status in Python, save the full result.

    skill and effort are passed as real run parameters, so they reach
    Nimble's agent rather than only steering a wrapper LLM. Writes both the
    structured JSON (content + trust) and a readable .md.
    """
    client = Nimble(api_key=os.environ["NIMBLE_API_KEY"])

    started = client.agents.run(
        input=AGENT_TASK,
        agent_name=AGENT_NAME,
        effort=effort,
        use_case="research",
        skill=_skill_with_goals(),
    )
    agent_id = started.web_search_agent_id
    run_id = started.id
    print(f"[{AGENT_NAME}] run {run_id} started (effort={effort}); polling ...")

    deadline = time.time() + timeout
    while True:
        status = client.agents.runs.get(run_id, agent_id=agent_id).status
        if status == "completed":
            break
        if status in ("failed", "cancelled", "error"):
            raise RuntimeError(f"run {run_id} ended with status={status}")
        if time.time() > deadline:
            raise TimeoutError(f"run {run_id} not complete after {timeout}s (last status={status})")
        time.sleep(poll_every)

    result = client.agents.runs.result(run_id, agent_id=agent_id)
    payload = result.model_dump() if hasattr(result, "model_dump") else dict(result)

    json_path = OUTPUT_DIR / "supply_chain_disruption_monitoring_agent__pattern_B.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    output = payload.get("output", payload)
    content = output.get("content", "") if isinstance(output, dict) else ""
    md_path = OUTPUT_DIR / "supply_chain_disruption_monitoring_agent__pattern_B.md"
    md_path.write_text(content, encoding="utf-8")

    print(f"saved {json_path} and {md_path}")
    return payload


if __name__ == "__main__":
    print("== Supply Chain Disruption Monitoring Agent ==")
    print("\n--- Pattern A: LangChain + Search API ---")
    run_search_api_agent()
    print("\n--- Pattern B: deterministic Agent-API harness ---")
    run_agent_api()