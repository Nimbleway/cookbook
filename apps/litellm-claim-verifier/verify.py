#!/usr/bin/env python3
"""
Claim verifier — document in, per-claim verdicts out.

    python verify.py samples/ai_draft.md

Pipeline: Haiku extracts checkable claims → each claim gets its own Nimble search
through LiteLLM → Opus adjudicates against the retrieved sources → an annotated
report, with search spend and token spend reported separately.

Both model calls and the search call go through one SDK, which is what makes the
cheap-extract / strong-adjudicate split a one-argument decision rather than a
second integration.

Set USE_LIVE=false to replay data/sample_run.json with no API calls at all.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")

import gateway  # noqa: E402  (reads env, so must follow load_dotenv)
from adjudicate import adjudicate_claim  # noqa: E402
from extract import extract_claims  # noqa: E402
from llm import ADJUDICATOR_MODEL, EXTRACTOR_MODEL  # noqa: E402
from progress import ClaimBoard  # noqa: E402
from report import write_html, write_markdown  # noqa: E402
from retrieve import retrieve_all  # noqa: E402
from schemas import Claim, ClaimResult, Evidence, Run, RunCost, Verdict  # noqa: E402

DATA = APP_DIR / "data"
CACHE = DATA / "cache"
RAW = DATA / "raw"
SAMPLE_RUN = DATA / "sample_run.json"

ADJUDICATE_CONCURRENCY = 5


def _cache_key(claim: Claim) -> str:
    # Time-sensitive claims get the UTC date in the key, so their cache expires daily
    # rather than serving last month's ranking as a live verification. Settled facts
    # cache indefinitely, which is the whole point of caching them.
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d") if claim.time_sensitive else "static"
    return hashlib.sha1(f"{claim.text}|{claim.time_sensitive}|{day}".encode()).hexdigest()[:16]


def _load_cached(claim: Claim) -> ClaimResult | None:
    path = CACHE / f"{_cache_key(claim)}.json"
    if not path.exists():
        return None
    try:
        cached = ClaimResult.model_validate_json(path.read_text())
    except Exception:
        return None  # a stale cache entry is not worth failing a run over
    # The key is claim TEXT, so a hit can come from a different document, carrying that
    # document's id, quote and offsets. Rebind to the claim in hand or the report would
    # anchor annotations to text that isn't there.
    cached.claim = claim
    return cached


def _store_cached(result: ClaimResult) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{_cache_key(result.claim)}.json").write_text(result.model_dump_json(indent=2))


def _require_keys() -> None:
    # In gateway mode the proxy holds the provider credentials, so requiring them locally
    # would break every centrally managed deployment. Only the proxy's own key is needed.
    if gateway.ENABLED:
        if not gateway.KEY:
            sys.exit(
                "LITELLM_BASE_URL is set but LITELLM_MASTER_KEY is not.\n"
                "Gateway mode authenticates to the proxy with its master key; the provider "
                "keys live on the proxy. Unset LITELLM_BASE_URL to call the providers directly."
            )
        return

    missing = [k for k in ("NIMBLE_API_KEY", "ANTHROPIC_API_KEY") if not os.getenv(k)]
    if missing:
        sys.exit(
            f"Missing {', '.join(missing)}.\n"
            "Copy .env.example to .env and fill it in, or run with USE_LIVE=false "
            "to replay the cached sample run."
        )


async def run_live(doc_path: Path, document: str, no_cache: bool) -> Run:
    cost = RunCost()

    print(f"→ extracting claims with {EXTRACTOR_MODEL.split('/')[-1]} …")
    extraction, extract_cost = extract_claims(document)

    # Ids come from a model, so they are neither guaranteed unique nor guaranteed safe to
    # put in HTML. They are used as dict keys and as anchors, so both matter: renumber
    # positionally and the ids become ours rather than the model's.
    for position, claim in enumerate(extraction.claims, 1):
        claim.id = f"c{position:02d}"
    cost.extract_spend = extract_cost
    print(f"  {len(extraction.claims)} claims, {len(extraction.skipped)} spans skipped  (${extract_cost:.4f})")

    claims = extraction.claims
    cached = {} if no_cache else {c.id: r for c in claims if (r := _load_cached(c))}
    todo = [c for c in claims if c.id not in cached]
    if cached:
        print(f"  {len(cached)} claim(s) served from cache, {len(todo)} to check")

    results: dict[str, ClaimResult] = {}
    fresh: set[str] = set()   # ids actually paid for in this run, as opposed to served from cache

    if todo:
        where = "the gateway" if gateway.ENABLED else "LiteLLM"
        print(f"→ searching Nimble via {where} ({len(todo)} queries, general focus), then adjudicating …\n")
        board = ClaimBoard(todo)
        board.start()

        retrieved = await retrieve_all(todo, RAW, on_start=lambda cid: board.set(cid, "searching"))
        semaphore = asyncio.Semaphore(ADJUDICATE_CONCURRENCY)

        async def judge(claim: Claim) -> ClaimResult:
            evidence, focus, query, search_cost = retrieved[claim.id]
            async with semaphore:
                board.set(claim.id, "judging")
                # complete_json is synchronous; a thread keeps the fan-out concurrent
                # without duplicating the retry logic in an async variant.
                verdict, adj_cost = await asyncio.to_thread(adjudicate_claim, claim, evidence)
            board.set(claim.id, verdict.status)
            return ClaimResult(
                claim=claim,
                evidence=evidence,
                verdict=verdict,
                search_focus=focus,
                search_query=query,
                search_cost=search_cost,
                adjudicate_cost=adj_cost,
            )

        # return_exceptions: claims are independent, so one failed judgment costs one
        # verdict, not the run. Anything already searched is still reported and cached.
        for claim, outcome in zip(todo, await asyncio.gather(*(judge(c) for c in todo), return_exceptions=True)):
            if isinstance(outcome, BaseException):
                board.set(claim.id, "failed")
                print(f"  ! adjudication failed for {claim.id}: {type(outcome).__name__}: {outcome}")
                continue
            results[outcome.claim.id] = outcome
            fresh.add(outcome.claim.id)
            _store_cached(outcome)

    results.update(cached)
    ordered = [results[c.id] for c in claims if c.id in results]

    # Only charge this run for what this run bought. A cached claim made no calls, so
    # adding its stored cost would report spend that never happened.
    for r in ordered:
        if r.claim.id not in fresh:
            continue
        cost.search_spend += r.search_cost
        cost.adjudicate_spend += r.adjudicate_cost
        cost.search_queries += 1

    return Run(
        document_path=str(doc_path),
        document_text=document,
        results=ordered,
        skipped=extraction.skipped,
        cost=cost,
        live=True,
    )


def load_cached_run() -> Run:
    if not SAMPLE_RUN.exists():
        sys.exit(
            f"USE_LIVE=false but {SAMPLE_RUN.relative_to(APP_DIR)} does not exist.\n"
            "Run once with USE_LIVE=true to record it."
        )
    run = Run.model_validate_json(SAMPLE_RUN.read_text())
    run.live = False
    return run


def _animate_replay(run: Run) -> None:
    """
    Walk the cached run through the same board the live path draws.

    Replay exists so the demo can be rehearsed and re-shot without spending anything;
    a replay that prints only the total is no use for that. REPLAY_DELAY=0 skips it.
    """
    delay = float(os.getenv("REPLAY_DELAY", "0.12"))
    if delay <= 0 or not run.results:
        return
    board = ClaimBoard([r.claim for r in run.results])
    board.start()
    board.set_all("searching")
    time.sleep(delay * 3)
    for result in run.results:
        board.set(result.claim.id, "judging")
        time.sleep(delay)
        board.set(result.claim.id, result.verdict.status)
        time.sleep(delay)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the factual claims in a document against live web sources.")
    parser.add_argument("document", nargs="?", default="samples/sports_draft.md", help="path to a .md or .txt document")
    parser.add_argument("--out", default="report.html", help="HTML report path (default: report.html)")
    parser.add_argument("--md", default="report.md", help="Markdown report path (default: report.md)")
    parser.add_argument("--no-cache", action="store_true", help="ignore cached per-claim results")
    parser.add_argument("--record", action="store_true", help="save this run as data/sample_run.json for demo mode")
    args = parser.parse_args()

    live = os.getenv("USE_LIVE", "true").strip().lower() not in {"false", "0", "no"}
    started = time.time()

    if live:
        doc_path = Path(args.document)
        if not doc_path.is_absolute():
            doc_path = APP_DIR / doc_path
        if not doc_path.exists():
            sys.exit(f"No such document: {doc_path}")
        _require_keys()
        document = doc_path.read_text()
        print(f"\nVerifying {doc_path.name}  ({len(document.split())} words)\n")
        run = asyncio.run(run_live(doc_path, document, args.no_cache))
        if args.record:
            DATA.mkdir(parents=True, exist_ok=True)
            SAMPLE_RUN.write_text(run.model_dump_json(indent=2))
            print(f"\n  recorded {SAMPLE_RUN.relative_to(APP_DIR)} for USE_LIVE=false replay")
    else:
        print("\nUSE_LIVE=false — replaying cached run, no API calls\n")
        run = load_cached_run()
        _animate_replay(run)

    html_path = write_html(run, APP_DIR / args.out, EXTRACTOR_MODEL, ADJUDICATOR_MODEL)
    md_path = write_markdown(run, APP_DIR / args.md)

    counts = {"supported": 0, "contradicted": 0, "unverifiable": 0}
    for r in run.results:
        counts[r.verdict.status] += 1
    c = run.cost

    print(
        f"\n  {counts['supported']} supported · {counts['contradicted']} contradicted · "
        f"{counts['unverifiable']} unverifiable"
    )
    if run.live:
        print(
            f"\n  search  ${c.search_spend:.4f}  ({c.search_queries} queries × $0.005)"
            f"\n  tokens  ${c.token_spend:.4f}  (extract ${c.extract_spend:.4f} + adjudicate ${c.adjudicate_spend:.4f})"
            f"\n  total   ${c.total:.4f}   →  ${c.per_claim(len(run.results)):.4f} per claim"
            f"\n  elapsed {time.time() - started:.1f}s"
        )
    print(f"\n  {html_path.name}  ·  {md_path.name}\n")


if __name__ == "__main__":
    main()
