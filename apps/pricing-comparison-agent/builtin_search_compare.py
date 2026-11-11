"""Comparison harness: the LLM's own built-in web search tool vs Nimble's Agent API,
given the exact same research prompt.

This is not part of the agent. It exists to generate the side-by-side evidence for the
blog's comparison section: run the identical research objective already used in
agent_api_v2.py's run_research() through the model provider's own hosted web search tool
(OpenAI's Responses API `web_search` tool for openai:gpt-5.1, the project default), and
capture what it returns, so it can be compared honestly against a real Agent API result
built from the same prompt.

    python builtin_search_compare.py "Datadog,New Relic,Grafana Labs"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = os.getenv("BUILTIN_SEARCH_MODEL", "gpt-5.1")


def same_research_prompt(vendors: list[str]) -> str:
    """The exact research objective agent_api_v2.py sends to the Agent API, minus the
    one clause ('tier_type: unpublished') that only means something inside our own
    schema. Everything else is identical, so this is a fair same-query comparison.
    """
    return (
        f"Research how {', '.join(vendors)} currently price and package their product. "
        f"For each, return plan tiers, list prices with their billing unit, included "
        f"usage allowances, overage rates, and any packaging change announced in the "
        f"last 90 days with its date. Cite the page each value came from, and mark any "
        f"value not published publicly as unavailable rather than estimating it."
    )


def run_builtin_search(prompt: str, model: str = DEFAULT_MODEL) -> dict:
    client = OpenAI()
    resp = client.responses.create(model=model, tools=[{"type": "web_search"}], input=prompt)

    citations: list[dict] = []
    search_calls = 0
    for item in resp.output:
        if getattr(item, "type", None) == "web_search_call":
            search_calls += 1
        if getattr(item, "type", None) == "message":
            for part in item.content:
                for ann in getattr(part, "annotations", None) or []:
                    if getattr(ann, "type", None) == "url_citation":
                        citations.append({"url": ann.url, "title": getattr(ann, "title", None)})

    return {
        "model": model,
        "prompt": prompt,
        "search_calls": search_calls,
        "output_text": resp.output_text,
        "citations": citations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vendors", help="Comma-separated vendor names")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", default="examples/comparison/builtin_web_search_result.json")
    args = parser.parse_args()

    vendors = [v.strip() for v in args.vendors.split(",") if v.strip()]
    prompt = same_research_prompt(vendors)
    print(f"Prompt sent to both channels:\n  {prompt}\n")
    print(f"Querying {args.model}'s built-in web search tool...", flush=True)
    result = run_builtin_search(prompt, args.model)

    print(f"\n{args.model} made {result['search_calls']} web_search call(s), "
          f"{len(result['citations'])} citation(s):")
    for c in result["citations"]:
        print(f"  - {c['title']}: {c['url']}")
    print(f"\n--- output_text ---\n{result['output_text']}\n")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
