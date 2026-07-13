"""FastAPI backend for the Live Docs Grounding Agent web app.

This file contains NO Nimble Task Agents API logic of its own — it only
orchestrates the exact same functions from agent.py (TaskAgentsClient,
create_or_update, ask/poll_run building blocks, history read/write) behind
HTTP endpoints so the browser frontend can drive them. Runs happen on a
background thread per run_id, tracked in an in-memory dict, so the HTTP
endpoints never block on a multi-minute Nimble run.
"""

from __future__ import annotations

import json
import random
import threading
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent as core

QUESTION_POOL_PATH = Path(__file__).parent / "question_pool.json"
SAVED_PATH = Path(__file__).parent / "saved.jsonl"
DAILY_QUESTION_COUNT = 3

app = FastAPI(title="Live Docs Grounding Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Global state — one client/agent for this local single-user app.
# ============================================================================

STATE = {"client": None, "agent_id": None, "config": None, "base_url": core.DEFAULT_BASE_URL}
RUNS: dict = {}
RUNS_LOCK = threading.Lock()


def _reload_config() -> dict:
    STATE["config"] = json.loads(core.CONFIG_PATH.read_text())
    return STATE["config"]


def _load_existing_state() -> None:
    values = core.read_env()
    base_url = values.get("NIMBLE_BASE_URL") or core.DEFAULT_BASE_URL
    STATE["base_url"] = base_url
    if values.get("NIMBLE_API_KEY"):
        STATE["client"] = core.TaskAgentsClient(api_key=values["NIMBLE_API_KEY"], base_url=base_url)
    if core.AGENT_ID_PATH.exists():
        STATE["agent_id"] = core.AGENT_ID_PATH.read_text().strip()
    _reload_config()


_load_existing_state()


def _require_client() -> "core.TaskAgentsClient":
    if STATE["client"] is None:
        raise HTTPException(400, "No API key configured yet — complete setup first.")
    return STATE["client"]


# ============================================================================
# Daily suggested questions — a date-seeded rotating subset of a curated pool
# of currently-relevant library/API questions. Deterministic per calendar
# day (everyone sees the same set today, a different set tomorrow) with no
# scheduler, no extra API calls, and no external dependency. Edit
# question_pool.json to keep the pool current.
# ============================================================================

def _load_question_pool() -> list:
    try:
        data = json.loads(QUESTION_POOL_PATH.read_text())
        pool = data.get("questions") if isinstance(data, dict) else data
        if isinstance(pool, list) and pool:
            return [q for q in pool if isinstance(q, str) and q.strip()]
    except (OSError, ValueError):
        pass
    # Fall back to whatever the agent config carries.
    return (STATE["config"] or _reload_config()).get("suggested_questions", [])


def daily_questions(n: int = DAILY_QUESTION_COUNT, on_date: "date | None" = None) -> list:
    pool = _load_question_pool()
    if len(pool) <= n:
        return pool
    day = on_date or date.today()
    rng = random.Random(day.toordinal())  # deterministic per calendar day
    return rng.sample(pool, n)


# ============================================================================
# Saved answers — a curated bookmark list separate from the full history,
# so a useful answer can be pinned and reopened any day. One JSON object per
# line, same shape as a history entry.
# ============================================================================

def load_saved() -> list:
    if not SAVED_PATH.exists():
        return []
    return [json.loads(line) for line in SAVED_PATH.read_text().splitlines() if line.strip()]


def _write_saved(entries: list) -> None:
    if entries:
        with SAVED_PATH.open("w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
    elif SAVED_PATH.exists():
        SAVED_PATH.unlink()


# ============================================================================
# Setup / onboarding
# ============================================================================

class KeyRequest(BaseModel):
    api_key: str


@app.get("/api/setup/status")
def setup_status():
    values = core.read_env()
    has_key = bool(values.get("NIMBLE_API_KEY"))
    config = STATE["config"] or _reload_config()
    return {
        "has_key": has_key,
        "key_suffix": values["NIMBLE_API_KEY"][-4:] if has_key else None,
        "has_agent": STATE["agent_id"] is not None,
        "agent_id": STATE["agent_id"],
        "agent_name": config.get("agent_name"),
        "description": config.get("description"),
        "suggested_questions": daily_questions(),
        "suggestions_date": date.today().isoformat(),
        "effort": config.get("effort"),
    }


@app.post("/api/setup/key")
def setup_key(body: KeyRequest):
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(400, "API key was empty.")
    valid = core.validate_key(api_key, STATE["base_url"])
    if not valid:
        return {"valid": False, "message": "That key was rejected (401 unauthorized). Double-check and try again."}

    values = core.read_env()
    values["NIMBLE_API_KEY"] = api_key
    values.setdefault("NIMBLE_BASE_URL", STATE["base_url"])
    core.write_env(values)
    STATE["client"] = core.TaskAgentsClient(api_key=api_key, base_url=STATE["base_url"])
    return {"valid": True, "message": "Key looks valid."}


@app.post("/api/setup/agent")
def setup_agent():
    client = _require_client()
    had_agent_before = STATE["agent_id"] is not None
    agent_id = core.create_or_update(client)
    STATE["agent_id"] = agent_id
    config = _reload_config()
    return {"agent_id": agent_id, "agent_name": config.get("agent_name"), "created": not had_agent_before}


@app.post("/api/setup/reset")
def setup_reset():
    """Delete the cached agent id so the next /api/setup/agent call re-runs
    the real create-or-update flow from scratch — used by the 'Re-run setup'
    option so the onboarding sequence can be demoed again honestly."""
    if core.AGENT_ID_PATH.exists():
        core.AGENT_ID_PATH.unlink()
    STATE["agent_id"] = None
    return {"ok": True}


# ============================================================================
# Runs
# ============================================================================

class RunRequest(BaseModel):
    question: str


def _run_worker(run_id: str, question: str, agent_id: str, effort: str) -> None:
    client = STATE["client"]
    cancel_event = RUNS[run_id]["cancel_event"]

    def on_tick(elapsed: float, status: str) -> None:
        with RUNS_LOCK:
            if run_id in RUNS:
                RUNS[run_id]["status"] = status
                RUNS[run_id]["elapsed"] = elapsed

    try:
        run = client.poll_run(agent_id, run_id, poll_interval_seconds=3.0, on_tick=on_tick, cancel_event=cancel_event)
    except core.NimbleAgentRunCancelled:
        try:
            client.cancel_run(agent_id, run_id)
        except Exception:
            pass
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "cancelled"
        return
    except core.NimbleAgentRunError as exc:
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "failed"
            RUNS[run_id]["error"] = str(exc)
        return
    except Exception as exc:
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "failed"
            RUNS[run_id]["error"] = f"Unexpected error: {exc}"
        return

    if run["status"] != "completed":
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "failed"
            RUNS[run_id]["error"] = f"Run ended with status={run['status']}"
        return

    try:
        result = client.get_result(agent_id, run_id)
    except core.NimbleAgentRunError as exc:
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "failed"
            RUNS[run_id]["error"] = str(exc)
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core.append_entry(timestamp, question, effort, run_id, result)
    with RUNS_LOCK:
        RUNS[run_id]["status"] = "completed"
        RUNS[run_id]["result"] = result


@app.post("/api/run")
def start_run(body: RunRequest):
    client = _require_client()
    if not STATE["agent_id"]:
        raise HTTPException(400, "No agent set up yet — complete setup first.")
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Question was empty.")

    config = STATE["config"] or _reload_config()
    effort = config.get("effort", "unknown")

    run = client.create_run(STATE["agent_id"], question)
    run_id = run["id"]
    with RUNS_LOCK:
        RUNS[run_id] = {
            "question": question,
            "status": run["status"],
            "elapsed": 0.0,
            "error": None,
            "result": None,
            "cancel_event": threading.Event(),
        }
    threading.Thread(target=_run_worker, args=(run_id, question, STATE["agent_id"], effort), daemon=True).start()
    return {"run_id": run_id, "status": run["status"]}


@app.get("/api/run/{run_id}")
def get_run_status(run_id: str):
    with RUNS_LOCK:
        state = RUNS.get(run_id)
        if not state:
            raise HTTPException(404, "Unknown run_id.")
        return {
            "run_id": run_id,
            "question": state["question"],
            "status": state["status"],
            "elapsed": state["elapsed"],
            "error": state["error"],
        }


@app.get("/api/run/{run_id}/result")
def get_run_result(run_id: str):
    with RUNS_LOCK:
        state = RUNS.get(run_id)
        if not state:
            raise HTTPException(404, "Unknown run_id.")
        if state["status"] != "completed":
            raise HTTPException(409, f"Run not completed yet (status={state['status']}).")
        return {"run_id": run_id, "question": state["question"], "result": state["result"]}


@app.post("/api/run/{run_id}/cancel")
def cancel_run(run_id: str):
    with RUNS_LOCK:
        state = RUNS.get(run_id)
        if not state:
            raise HTTPException(404, "Unknown run_id.")
        state["cancel_event"].set()
    return {"ok": True}


# ============================================================================
# History
# ============================================================================

@app.get("/api/history")
def get_history():
    entries = core.load_entries()
    return [
        {
            "run_id": e.get("run_id"),
            "timestamp": e.get("timestamp"),
            "question": e.get("question"),
            "library": (e.get("result") or {}).get("library"),
        }
        for e in reversed(entries)
    ]


@app.get("/api/history/{run_id}")
def get_history_entry(run_id: str):
    for entry in core.load_entries():
        if entry.get("run_id") == run_id:
            return entry
    raise HTTPException(404, "No history entry with that run_id.")


@app.delete("/api/history/{run_id}")
def delete_history_entry(run_id: str):
    entries = core.load_entries()
    for i, entry in enumerate(entries, 1):
        if entry.get("run_id") == run_id:
            core.delete_entry(i)
            return {"ok": True}
    raise HTTPException(404, "No history entry with that run_id.")


# ============================================================================
# Saved answers (bookmarks)
# ============================================================================

class SaveRequest(BaseModel):
    run_id: str


def _find_entry(run_id: str) -> "dict | None":
    """Find a full Q&A entry by run_id — from history first, then from any
    completed in-memory run that hasn't been flushed to history yet."""
    for entry in core.load_entries():
        if entry.get("run_id") == run_id:
            return entry
    with RUNS_LOCK:
        state = RUNS.get(run_id)
        if state and state.get("status") == "completed" and state.get("result"):
            return {
                "run_id": run_id,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "question": state["question"],
                "result": state["result"],
            }
    return None


@app.get("/api/saved")
def get_saved():
    return [
        {
            "run_id": e.get("run_id"),
            "timestamp": e.get("timestamp"),
            "saved_at": e.get("saved_at"),
            "question": e.get("question"),
            "library": (e.get("result") or {}).get("library"),
        }
        for e in reversed(load_saved())
    ]


@app.get("/api/saved/ids")
def get_saved_ids():
    """Just the set of saved run_ids, so the UI can show which answers on
    screen are already bookmarked."""
    return {"run_ids": [e.get("run_id") for e in load_saved()]}


@app.get("/api/saved/{run_id}")
def get_saved_entry(run_id: str):
    for entry in load_saved():
        if entry.get("run_id") == run_id:
            return entry
    raise HTTPException(404, "No saved entry with that run_id.")


@app.post("/api/saved")
def save_entry(body: SaveRequest):
    saved = load_saved()
    if any(e.get("run_id") == body.run_id for e in saved):
        return {"ok": True, "already_saved": True}
    entry = _find_entry(body.run_id)
    if not entry:
        raise HTTPException(404, "No completed answer with that run_id to save.")
    entry = dict(entry)
    entry["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    saved.append(entry)
    _write_saved(saved)
    return {"ok": True, "already_saved": False}


@app.delete("/api/saved/{run_id}")
def delete_saved_entry(run_id: str):
    saved = load_saved()
    remaining = [e for e in saved if e.get("run_id") != run_id]
    if len(remaining) == len(saved):
        raise HTTPException(404, "No saved entry with that run_id.")
    _write_saved(remaining)
    return {"ok": True}


# Serve the frontend last so /api/* routes above take precedence.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
