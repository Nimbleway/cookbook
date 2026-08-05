"""The Nimble layer: run a lane's two fact classes, save raw, stay resumable.

Design rules this file exists to enforce (DESIGN.md §4):
  * `timeout=1800`, never the 300 s default — the default is shorter than a
    healthy run and is the single most likely thing to bite a reader.
  * Raw Document text + full metadata hits disk BEFORE anything transforms it.
  * A lane already researched and still fresh is never re-run.
  * `NimbleAgentTimeoutError` is recoverable state, not failure: the run keeps
    going server-side, so the ids are persisted for `recover_runs.py`.
  * `NimbleAgentCreateAmbiguousError` is NEVER retried — creation is billable and
    issued exactly once, so a run may exist with no id to address it.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from llama_index.tools.nimble import (
    NimbleAgentCreateAmbiguousError,
    NimbleAgentRunError,
    NimbleAgentTimeoutError,
    NimbleAgentToolSpec,
)

from .agents_config import (
    EFFORT, OVERLAY_SCHEMA, OVERLAY_SOURCES, RATE_SCHEMA, RATE_SOURCES, TTL_DAYS,
)
from .io import read_json as io_read_json

Kind = Literal["rate", "overlay"]

HERE = Path(__file__).parent.parent
RUNS_DIR = HERE / "data" / "runs"
JOBS_DIR = HERE / "data" / "jobs"
SAMPLES_DIR = HERE / "data" / "samples"

TIMEOUT_S = 1800
POLL_INTERVAL_S = 15
MAX_CONCURRENT_RUNS = 4

_slots = threading.BoundedSemaphore(MAX_CONCURRENT_RUNS)


# --- lane identity --------------------------------------------------------


@dataclass(frozen=True)
class Lane:
    """A product moving from an origin into a destination."""

    hts_code: str
    origin: str
    destination: str = "United States"
    product: str = ""

    @property
    def key(self) -> str:
        return f"{self.hts_code}|{self.origin}|{self.destination}"

    @property
    def rate_key(self) -> str:
        """The base MFN rate is a property of the CODE, not the lane.

        Discovered from the pre-warm corpus: 8507.60.00 returned 3.4% from both
        Vietnam and China, 6109.10.00 returned 16.5% from both India and
        Bangladesh. Keying rate Documents by full lane paid for the same research
        once per origin. Origin-free keying means adding a new origin for a code
        already covered costs ONE run (the overlay), not two.
        """
        return f"{self.hts_code}|{self.destination}"

    def key_for(self, kind: Kind) -> str:
        return self.rate_key if kind == "rate" else self.key

    def doc_id(self, kind: Kind) -> str:
        return f"{self.key_for(kind)}#{kind}"

    def slug(self, kind: Kind) -> str:
        safe = self.key_for(kind).replace("|", "_").replace("/", "-").replace(" ", "-")
        return f"{safe}.{kind}"


# --- tasks ----------------------------------------------------------------

RATE_TASK = (
    "Report the Column 1 General (MFN) duty rate for this HTS subheading in the "
    "current Harmonized Tariff Schedule of the United States. This is a base "
    "schedule rate only: do not include Section 301, Section 232, IEEPA, or "
    "reciprocal duties. Quote the rate exactly as the schedule states it, name "
    "the HTSUS revision it came from, and give the URL it was read from. If the "
    "official schedule cannot be retrieved, say so explicitly rather than "
    "estimating, and state which official mirrors were attempted."
)

OVERLAY_TASK = (
    "Establish which duty overlays are currently in force for this lane — "
    "Section 301, Section 232, IEEPA, reciprocal tariffs, and any exclusions. "
    "Report each component separately with the legal instrument that created it "
    "and its effective date; never blend them into one figure. Do not report the "
    "Column 1 General (MFN) base rate. Where an instrument was later modified or "
    "terminated, report the current state and cite both instruments. Put overlays "
    "checked and confirmed not to apply in confirmed_absent, and anything you "
    "could not verify in unverified."
)

_SPEC: dict[Kind, dict[str, Any]] = {
    "rate": {"task": RATE_TASK, "schema": RATE_SCHEMA, "sources": RATE_SOURCES,
             "env": "NIMBLE_RATE_AGENT_ID"},
    "overlay": {"task": OVERLAY_TASK, "schema": OVERLAY_SCHEMA, "sources": OVERLAY_SOURCES,
                "env": "NIMBLE_OVERLAY_AGENT_ID"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def use_live() -> bool:
    return os.environ.get("USE_LIVE", "false").strip().lower() in {"1", "true", "yes"}


# --- cache / freshness ----------------------------------------------------


def read_json(path: Path) -> dict[str, Any] | None:
    """Kept as a re-export: `desk.io` owns the implementation now."""
    return io_read_json(path)


def cached_path(lane: Lane, kind: Kind) -> Path:
    """Where a NEW run gets written. Always data/runs — samples are read-only."""
    return RUNS_DIR / f"{lane.slug(kind)}.json"


def load_cached(lane: Lane, kind: Kind) -> dict[str, Any] | None:
    """Latest saved run for this lane+kind, from whichever corpus is active.

    Must read the same directory the index was built from, or the badge and the
    freshness guard disagree: the first version read `data/runs/` unconditionally and
    reported a backdated sample as "from corpus" while the guard was withholding it
    as stale.
    """
    from .ingest import active_dir  # local import keeps module import order simple

    for candidate in (active_dir() / f"{lane.slug(kind)}.json", cached_path(lane, kind)):
        if candidate.exists():
            record = read_json(candidate)
            if record is not None:
                return record
    return None


def is_fresh(record: dict[str, Any], kind: Kind, now: datetime | None = None) -> bool:
    """True while the record is inside its TTL. Rate: 90 days. Overlay: 7 days."""
    stamp = record.get("researched_at")
    if not stamp:
        return False
    try:
        researched = datetime.fromisoformat(stamp)
    except ValueError:
        return False
    if researched.tzinfo is None:
        researched = researched.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return now - researched < timedelta(days=TTL_DAYS[kind])


def age_days(record: dict[str, Any]) -> float | None:
    stamp = record.get("researched_at")
    if not stamp:
        return None
    try:
        researched = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if researched.tzinfo is None:
        researched = researched.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - researched
    return round(delta.total_seconds() / 86400, 2)


# --- job state (survives closing the tab) ---------------------------------


def job_path(lane: Lane, kind: Kind) -> Path:
    return JOBS_DIR / f"{lane.slug(kind)}.json"


def write_job(lane: Lane, kind: Kind, **fields: Any) -> dict[str, Any]:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = job_path(lane, kind)
    job = (read_json(path) or {}) if path.exists() else {}
    job.update({"lane_key": lane.key, "kind": kind, "updated_at": _now(), **fields})
    path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    return job


def read_job(lane: Lane, kind: Kind) -> dict[str, Any] | None:
    path = job_path(lane, kind)
    return read_json(path) if path.exists() else None


def clear_job(lane: Lane, kind: Kind) -> None:
    job_path(lane, kind).unlink(missing_ok=True)


def open_jobs() -> list[dict[str, Any]]:
    if not JOBS_DIR.exists():
        return []
    jobs = []
    for path in sorted(JOBS_DIR.glob("*.json")):
        job = read_json(path)
        if job is not None:
            jobs.append(job)
    return jobs


# --- the run ---------------------------------------------------------------


def _tool(kind: Kind) -> NimbleAgentToolSpec:
    agent_id = os.environ.get(_SPEC[kind]["env"])
    if not agent_id:
        raise RuntimeError(
            f"{_SPEC[kind]['env']} is not set — run setup_agents.py first"
        )
    return NimbleAgentToolSpec(
        agent_id=agent_id,
        effort=EFFORT[kind],
        timeout=TIMEOUT_S,
        poll_interval=POLL_INTERVAL_S,
    )


def _save_raw(lane: Lane, kind: Kind, doc_text: str, metadata: dict[str, Any],
              elapsed: float) -> dict[str, Any]:
    """Write the raw Document before anything transforms it."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "lane": {"hts_code": lane.hts_code, "origin": lane.origin,
                 "destination": lane.destination, "product": lane.product},
        "lane_key": lane.key,
        "doc_key": lane.key_for(kind),  # rate records are origin-free
        "kind": kind,
        "doc_id": lane.doc_id(kind),
        "researched_at": _now(),
        "elapsed_s": round(elapsed, 1),
        "text": doc_text,
        "metadata": metadata,
    }
    cached_path(lane, kind).write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return record


def research(lane: Lane, kind: Kind, force: bool = False) -> dict[str, Any]:
    """Research one fact class for one lane. Blocks. Returns the saved record.

    Resumable by design: a fresh cached record short-circuits before any billable
    call. Pass force=True to re-research regardless (that is what refresh does).
    """
    if not force:
        cached = load_cached(lane, kind)
        if cached and is_fresh(cached, kind):
            cached["from_cache"] = True
            return cached

    if not use_live():
        cached = load_cached(lane, kind)
        if cached:
            cached["from_cache"] = True
            cached["stale_but_offline"] = not is_fresh(cached, kind)
            return cached
        raise RuntimeError(
            f"USE_LIVE=false and no cached run for {lane.key} [{kind}]. "
            "Set USE_LIVE=true to research it, or ship a sample for this lane."
        )

    spec = _SPEC[kind]
    tool = _tool(kind)
    input_data = {
        "hts_code": lane.hts_code,
        "origin": lane.origin,
        "destination": lane.destination,
    }
    if lane.product:
        input_data["product"] = lane.product

    write_job(lane, kind, status="running", started_at=_now(), run_id=None)
    started = time.monotonic()

    with _slots:
        try:
            doc = tool.run(
                spec["task"],
                input_data=input_data,
                output_schema=spec["schema"],
                sources=spec["sources"],
            )
        except NimbleAgentTimeoutError as err:
            # Not a failure. The run continues server-side; keep the ids so
            # recover_runs.py can fetch the result later.
            write_job(lane, kind, status="timeout", run_id=err.run_id,
                      agent_id=getattr(err, "agent_id", None),
                      note="run still executing server-side; recoverable")
            raise
        except NimbleAgentCreateAmbiguousError as err:
            # Never retried: a billable run may exist with no id to address.
            write_job(lane, kind, status="ambiguous_create",
                      status_code=getattr(err, "status_code", None),
                      note="DO NOT resubmit — reconcile against the dashboard")
            raise
        except NimbleAgentRunError as err:
            write_job(lane, kind, status="failed", error=f"{type(err).__name__}: {err}",
                      run_id=getattr(err, "run_id", None))
            raise

    record = _save_raw(lane, kind, doc.text, dict(doc.metadata or {}),
                       time.monotonic() - started)
    write_job(lane, kind, status="completed", run_id=record["metadata"].get("run_id"))
    clear_job(lane, kind)
    record["from_cache"] = False
    return record


# --- background execution (Streamlit must never block) --------------------


@dataclass
class ResearchTask:
    lane: Lane
    kinds: list[Kind] = field(default_factory=lambda: ["rate", "overlay"])
    force: bool = False

    def start(self) -> list[threading.Thread]:
        threads = []
        for kind in self.kinds:
            t = threading.Thread(
                target=self._run_one, args=(kind,),
                name=f"research-{self.lane.slug(kind)}", daemon=True,
            )
            t.start()
            threads.append(t)
        return threads

    def _run_one(self, kind: Kind) -> None:
        try:
            research(self.lane, kind, force=self.force)
        except Exception:  # noqa: BLE001 — job file already carries the status
            pass


def needs_research(lane: Lane, kind: Kind) -> tuple[bool, str]:
    """(should_run, why) — drives the UI badge."""
    cached = load_cached(lane, kind)
    if cached is None:
        return True, "not covered"
    age = age_days(cached)
    human = ("just now" if (age or 0) < 0.04 else
             f"{max(1, int(round((age or 0) * 24)))}h ago" if (age or 0) < 1 else
             f"{int(round(age or 0))}d ago")
    if not is_fresh(cached, kind):
        return True, f"expired ({human}, holds for {TTL_DAYS[kind]}d)"
    return False, f"researched {human}"
