"""Comparison harness: the LLM's own built-in web search tool vs Nimble's Agent API,
given the exact same research prompt.

Not part of the agent. Generates the side-by-side evidence for the blog's comparison
section: the identical research objective already used in agent_api_v2.py's
run_research(), sent to the model provider's own hosted web search tool (OpenAI's
Responses API `web_search` tool for openai:gpt-5.1, the project default) instead of
Nimble, so the two can be compared honestly on the same ask.

    python builtin_search_compare.py "Chipotle" --window-days 90
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


def same_research_prompt(brand: str, window_days: int) -> str:
    """The exact research objective agent_api_v2.py sends to the Agent API."""
    return (
        f"Find and classify customer sentiment toward {brand} over the last "
        f"{window_days * 2} days, covering review platforms, community discussion, and "
        f"news coverage of any price or product changes. State the sample size and "
        f"source mix behind each theme, and cite the source and date for every item."
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
    parser.add_argument("brand")
    parser.add_argument("--window-days", type=int, default=90)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", default="examples/comparison/builtin_web_search_result.json")
    args = parser.parse_args()

    prompt = same_research_prompt(args.brand, args.window_days)
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
