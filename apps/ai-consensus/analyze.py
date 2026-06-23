"""
analyze.py — One Claude Haiku pass per question.

Feeds all 3 raw responses (ChatGPT, Perplexity, Gemini) to Haiku, which
extracts a structured verdict + reason for each model and judges consensus
semantically. No regex parsing, no Jaccard scoring.

Usage:
    python3 analyze.py              # analyze all pending questions
    python3 analyze.py --id q_005   # single question
    python3 analyze.py --dry-run    # preview
    python3 analyze.py --force      # re-analyze already-done questions
"""

import json
import os
import re
import argparse
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
from dotenv import load_dotenv

load_dotenv()

RESPONSES_DIR = Path(__file__).parent / "data" / "responses"
ANALYSIS_DIR  = Path(__file__).parent / "data" / "analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

AGENTS = ["chatgpt", "perplexity", "gemini"]
CLIENT = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL  = "claude-haiku-4-5-20251001"

CONSENSUS_SCORES = {"strong": 0.90, "moderate": 0.55, "split": 0.10}

SYSTEM = (
    "You analyze how multiple AI models answered the same question. "
    "Return only valid JSON — no explanation, no markdown fences."
)

PROMPT_TEMPLATE = """\
Question asked to three AI models: {question}

--- ChatGPT ---
{chatgpt}

--- Perplexity ---
{perplexity}

--- Gemini ---
{gemini}

Extract each model's core position and judge whether the three models agree.

Return this exact JSON, nothing else:
{{
  "chatgpt":    {{"verdict": "...", "reason": "..."}},
  "perplexity": {{"verdict": "...", "reason": "..."}},
  "gemini":     {{"verdict": "...", "reason": "..."}},
  "consensus":  {{"label": "strong|moderate|split", "summary": "..."}}
}}

Rules:
- verdict: the model's answer in 5 words or fewer
- reason: one sentence capturing their key argument
- label: "strong" = all 3 broadly agree, "moderate" = 2 agree and 1 differs, "split" = clear 3-way disagreement
- summary: one sentence on what they agree or disagree on\
"""


def analyze_with_haiku(question, responses):
    """
    Returns a dict with keys: models, consensus.
    `responses` shape: {agent: {"raw": str, ...}}
    """
    prompt = PROMPT_TEMPLATE.format(
        question=question,
        chatgpt=responses["chatgpt"]["raw"],
        perplexity=responses["perplexity"]["raw"],
        gemini=responses["gemini"]["raw"],
    )

    msg = CLIENT.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    text = msg.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text.strip())

    result = json.loads(text)

    label = result["consensus"].get("label", "split")
    if label not in CONSENSUS_SCORES:
        label = "split"

    return {
        "models": {
            agent: {
                "verdict": result[agent]["verdict"],
                "reason":  result[agent]["reason"],
                "raw":     responses[agent]["raw"],
                "format":  responses[agent].get("format", "structured"),
            }
            for agent in AGENTS
        },
        "consensus": {
            "label":   label,
            "score":   CONSENSUS_SCORES[label],
            "summary": result["consensus"]["summary"],
        },
    }


def analyze(data):
    analysis = analyze_with_haiku(data["question"], data["responses"])
    return {
        "id":          data["id"],
        "category":    data["category"],
        "question":    data["question"],
        **analysis,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id",      help="Analyze a single question ID")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force",   action="store_true", help="Re-analyze already-done questions")
    args = parser.parse_args()

    all_responses = []
    for path in sorted(RESPONSES_DIR.glob("q_*.json")):
        d = json.loads(path.read_text())
        if all(a in d.get("responses", {}) for a in AGENTS):
            all_responses.append(d)

    if args.id:
        all_responses = [r for r in all_responses if r["id"] == args.id]

    pending = all_responses if args.force else [
        r for r in all_responses
        if not (ANALYSIS_DIR / f"{r['id']}.json").exists()
    ]

    if not pending:
        print("All questions already analyzed. Use --force to re-analyze.")
        return

    print(f"Analyzing {len(pending)} questions via Claude Haiku...")

    if args.dry_run:
        for r in pending:
            print(f"  {r['id']} — {r['question'][:70]}")
        return

    completed = failed = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(analyze, r): r for r in pending}
        for future in as_completed(futures):
            data = futures[future]
            try:
                result = future.result()
                (ANALYSIS_DIR / f"{data['id']}.json").write_text(json.dumps(result, indent=2))
                completed += 1
                con = result["consensus"]
                gpt_v = result["models"]["chatgpt"]["verdict"]
                print(f"  ✓ {data['id']}  {con['label']}  gpt={gpt_v[:40]!r}")
            except Exception as e:
                failed += 1
                print(f"  ✗ {data['id']}  — {e}")

    print(f"\nDone: {completed} analyzed, {failed} failed.")


if __name__ == "__main__":
    main()
