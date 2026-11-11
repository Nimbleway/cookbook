"""Pattern B: delegate sentiment research to a Nimble Web Search Agent.

Hands Nimble one research objective and lets its Web Search Agent plan the source
coverage, search, and classify. The output is the same SentimentExtractionBatch shape
Pattern A produces, so sentiment_model.build_result (dedupe, windowing, minimum sample,
escalation) is identical downstream. Only the retrieval step changes.

    python agent_api_v2.py "Chipotle" --window-days 90
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time

from dotenv import load_dotenv
from nimble_python import Nimble

from config import SKILL
from dashboard import open_dashboard, write_dashboard
from schema import ReviewItem, SentimentResult
from sentiment_model import ESCALATION_THRESHOLD_PCT, MIN_SAMPLE_SIZE, build_result

load_dotenv()

TERMINAL = {"completed", "failed", "cancelled", "error"}

SENTIMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "brand": {"type": "string"},
        "canonical_themes": {"type": "array", "items": {"type": "string"}},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "date": {"type": "string"},
                    "url": {"type": "string"},
                    "star_rating": {"type": "number"},
                    "text_excerpt": {"type": "string"},
                    "theme": {"type": "string"},
                    "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                },
                "required": ["source", "date", "url", "text_excerpt", "theme", "sentiment"],
            },
        },
    },
    "required": ["brand", "canonical_themes", "items"],
}


def run_research(brand: str, window_days: int, effort: str = "high", poll_interval: int = 15, timeout: int = 1800) -> dict:
    client = Nimble()  # reads NIMBLE_API_KEY from the environment

    prompt = (
        f"Find and classify customer sentiment toward {brand} over the last "
        f"{window_days * 2} days, covering review platforms, community discussion, and "
        f"news coverage of any price or product changes. State the sample_size and "
        f"source mix behind each theme, and cite the source and date for every item. "
        f"Require a required sample_size and sources field per theme."
    )

    started = client.agents.run(
        input=prompt,
        agent_name="brand-sentiment",
        use_case="research",
        skill=SKILL,
        effort=effort,
        output_schema=SENTIMENT_SCHEMA,
    )
    agent_id = started.web_search_agent_id
    run_id = started.id
    print(f"started run {run_id} on agent {agent_id} (effort={effort})", flush=True)

    deadline = time.time() + timeout
    while True:
        status = client.agents.runs.get(run_id, agent_id=agent_id)
        state = (getattr(status, "status", "") or "").lower()
        print(f"  status: {state}", flush=True)
        if state in TERMINAL:
            break
        if time.time() > deadline:
            raise TimeoutError(f"run {run_id} did not finish within {timeout}s")
        time.sleep(poll_interval)

    if state != "completed":
        raise RuntimeError(f"run ended as {state}")

    result = client.agents.runs.result(run_id, agent_id=agent_id)
    return result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)


def to_sentiment_result(raw: dict, window_days: int, as_of: dt.date) -> SentimentResult:
    output = raw.get("output", {})
    content = output.get("content", output) if isinstance(output, dict) else output
    items = [ReviewItem(**i) for i in content.get("items", [])]
    themes = content.get("canonical_themes", [])
    return build_result(content.get("brand", ""), items, themes, as_of, window_days, MIN_SAMPLE_SIZE, ESCALATION_THRESHOLD_PCT)


def main() -> int:
    from run import _print_result

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("brand")
    parser.add_argument("--window-days", type=int, default=90)
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "x-high", "max"])
    parser.add_argument("--poll-interval", type=int, default=15)
    parser.add_argument("--json", metavar="PATH", default=None)
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip writing/opening the HTML dashboard")
    args = parser.parse_args()

    raw = run_research(args.brand, args.window_days, effort=args.effort, poll_interval=args.poll_interval)
    result = to_sentiment_result(raw, args.window_days, dt.date.today())
    _print_result(result)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(raw, fh, indent=2, default=str)
        print(f"\nWrote {args.json}")
    if not args.no_dashboard:
        dashboard_path = write_dashboard(result, args.out_dir)
        print(f"Wrote {dashboard_path}")
        open_dashboard(dashboard_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
