"""Collect runs that outlived their timeout.

This is the function the integration docs leave as an exercise:

    except NimbleAgentTimeoutError as error:
        save_run_for_later(error.run_id, error.agent_id)   # your own function

`NimbleAgentTimeoutError` is not a failure. The run keeps executing on Nimble's
side and the result stays fetchable; only the client stopped waiting. `research()`
persists `run_id` and `agent_id` into data/jobs/ when that happens, and this script
fetches whatever has since completed and files it into the corpus as though the
original call had returned.

The connector itself has no start-now/collect-later split, so recovery goes through
the runs API directly.

    ./.venv/bin/python recover_runs.py            # report recoverable jobs
    ./.venv/bin/python recover_runs.py --collect  # fetch and file the finished ones
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from nimble_python import Nimble

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from desk.research import (  # noqa: E402
    JOBS_DIR, Lane, _save_raw, clear_job, open_jobs,
)

RECOVERABLE = {"timeout", "running"}

# How far apart a job's start and a run's creation may be and still be the same run.
MATCH_WINDOW_S = 180


def reconcile_missing_id(client, job: dict) -> str | None:
    """Find the run id for a job that never got one, by creation time.

    `run()` blocks and doesn't expose the run id until it returns or raises, so a
    process killed mid-run leaves a job with `run_id: None` and a paid run with no
    handle. This is the reconciliation the docs point at: list the agent's recent runs
    and match by when they were created.

    Time is the only usable key. With `input_data`, the run's `prompt` is the task
    text — identical for every entity — so it cannot tell you which row a run was for.
    If more than one run falls in the window, this refuses to guess.
    """
    started = job.get("started_at")
    agent_id = job.get("agent_id") or os.environ.get(
        "NIMBLE_OVERLAY_AGENT_ID" if job.get("kind") == "overlay"
        else "NIMBLE_RATE_AGENT_ID"
    )
    if not (started and agent_id):
        return None
    began = datetime.fromisoformat(started)
    if began.tzinfo is None:
        began = began.replace(tzinfo=timezone.utc)

    try:
        payload = json.loads(client.agents.runs.list(agent_id=agent_id, limit=20).to_json())
    except Exception as exc:  # noqa: BLE001
        print(f"     could not list runs: {type(exc).__name__}: {exc}")
        return None

    matches = []
    for run in payload.get("items") or []:
        created = run.get("created_at")
        if not created:
            continue
        when = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if abs((when - began).total_seconds()) <= MATCH_WINDOW_S:
            matches.append(run)

    if not matches:
        print(f"     no run on {agent_id} created within {MATCH_WINDOW_S}s of the job")
        return None
    if len(matches) > 1:
        print(f"     {len(matches)} runs fall in the window — refusing to guess:")
        for run in matches:
            print(f"       {run.get('id')} {run.get('status')} {run.get('created_at')}")
        return None
    run_id = matches[0].get("id")
    print(f"     reconciled to {run_id} ({matches[0].get('status')})")
    return run_id


def lane_from_job(job: dict) -> Lane:
    hts, origin, destination = (job.get("lane_key") or "||").split("|", 2)
    return Lane(hts_code=hts, origin=origin, destination=destination or "United States")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true",
                       help="fetch results and file them into the corpus")
    args = parser.parse_args()

    jobs = open_jobs()
    if not jobs:
        print(f"no open jobs in {JOBS_DIR.relative_to(HERE)} — nothing to recover")
        return 0

    print(f"{len(jobs)} open job(s):")
    for job in jobs:
        print(f"  {job.get('lane_key')} [{job.get('kind')}] status={job.get('status')} "
              f"run_id={job.get('run_id')}")
        if job.get("status") == "ambiguous_create":
            print("     ^ ambiguous create: DO NOT resubmit. A billable run may exist "
                  "with no id. Reconcile in the dashboard.")

    client = Nimble(api_key=os.environ["NIMBLE_API_KEY"])

    # Jobs with no id can often still be reconciled from the agent's run history.
    for job in jobs:
        if job.get("status") in RECOVERABLE and not job.get("run_id"):
            print(f"  {job.get('lane_key')} [{job.get('kind')}] has no run_id — "
                  "reconciling against run history")
            found = reconcile_missing_id(client, job)
            if found:
                job["run_id"] = found
                job.setdefault("agent_id", os.environ.get(
                    "NIMBLE_OVERLAY_AGENT_ID" if job.get("kind") == "overlay"
                    else "NIMBLE_RATE_AGENT_ID"))
                for candidate in JOBS_DIR.glob("*.json"):
                    existing = json.loads(candidate.read_text())
                    if (existing.get("lane_key") == job.get("lane_key")
                            and existing.get("kind") == job.get("kind")):
                        existing["run_id"] = found
                        existing["agent_id"] = job.get("agent_id")
                        existing["reconciled"] = True
                        candidate.write_text(json.dumps(existing, indent=2))

    candidates = [j for j in jobs
                  if j.get("status") in RECOVERABLE and j.get("run_id")]
    if not candidates:
        print("\nnothing recoverable (a job needs a run_id and a non-terminal status)")
        return 0
    if not args.collect:
        print(f"\n{len(candidates)} recoverable — pass --collect to fetch")
        return 0

    recovered = failed = pending = 0

    for job in candidates:
        lane, kind, run_id = lane_from_job(job), job["kind"], job["run_id"]
        agent_id = job.get("agent_id")
        label = f"{job.get('lane_key')} [{kind}] {run_id}"
        try:
            run = client.agents.runs.get(run_id, agent_id=agent_id)
        except Exception as exc:  # noqa: BLE001
            print(f"  {label}: could not poll — {type(exc).__name__}: {exc}")
            failed += 1
            continue

        if getattr(run, "is_active", False):
            print(f"  {label}: still running — leave the job in place")
            pending += 1
            continue
        if run.status != "completed":
            print(f"  {label}: terminated as {run.status} — clearing job")
            clear_job(lane, kind)
            failed += 1
            continue

        try:
            result = client.agents.runs.result(run_id, agent_id=agent_id)
            payload = json.loads(result.to_json())
        except Exception as exc:  # noqa: BLE001
            print(f"  {label}: completed but result fetch failed — "
                  f"{type(exc).__name__}: {exc}")
            failed += 1
            continue

        output = payload.get("output") or {}
        content = output.get("content")
        trust = output.get("trust") or {}
        text = content if isinstance(content, str) else json.dumps(content, indent=2)
        sources = trust.get("sources") or []
        if sources:
            text += "\n\nSources:\n" + "\n".join(
                f"- {s.get('title')} — {s.get('url')} ({s.get('type')})" for s in sources
            )
        metadata = {
            "run_id": run_id,
            "web_search_agent_id": agent_id,
            "effort": getattr(run, "effort", None),
            "output_type": output.get("type"),
            "confidence": trust.get("confidence"),
            "reasoning": trust.get("reasoning"),
            "sources": sources,
            "claims": trust.get("claims") or [],
            "recovered": True,
        }
        _save_raw(lane, kind, text, metadata, elapsed=0.0)
        clear_job(lane, kind)
        print(f"  {label}: recovered — confidence={trust.get('confidence')}")
        recovered += 1

    print(f"\n{recovered} recovered, {pending} still running, {failed} unrecoverable")
    if recovered:
        print("re-run the index build to pick these up")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
