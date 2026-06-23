"""
fetch.py — Pre-fetch AI responses for all 100 questions.

Uses nimble-python SDK. LLM agents do NOT work with the Nimble batch or async
APIs — they are headful browser sessions that stall in the async queue.
ThreadPoolExecutor with synchronous SDK calls is the correct approach.

Each call takes 30–90s. With MAX_WORKERS=9, expect ~25–35 min for 300 calls.

Re-runnable: skips questions already fully cached. Saves each response
immediately as it arrives — a crash loses at most the in-flight calls.

Usage:
    python3 fetch.py              # fetch all missing questions
    python3 fetch.py --id q_005  # fetch a single question
    python3 fetch.py --dry-run   # preview without API calls
"""

import json
import time
import threading
import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from nimble_python import Nimble

load_dotenv()

API_KEY = os.getenv("NIMBLE_API_KEY")

AGENTS = ["chatgpt", "perplexity", "gemini"]

AGENT_FORMAT = {
    "chatgpt":    "structured",
    "perplexity": "structured",
    "gemini":     "freeform",
}

MAX_WORKERS   = 9    # 3 concurrent calls per model
CALL_TIMEOUT  = 120  # seconds — hard limit via future.result(timeout=)
WARN_AFTER    = 90   # log a warning if a call hasn't returned in this many seconds
MONITOR_EVERY = 30   # how often the monitor thread prints a status line

QUESTIONS_FILE = Path(__file__).parent / "questions.json"
RESPONSES_DIR  = Path(__file__).parent / "data" / "responses"
RESPONSES_DIR.mkdir(parents=True, exist_ok=True)


# ── Thread-safe state ─────────────────────────────────────────────────────────

_lock         = threading.Lock()
_in_flight    = {}   # future -> (agent, question_id, start_time)
_completed    = 0
_failed       = 0
_total_calls  = 0


def _log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ── Monitor thread ────────────────────────────────────────────────────────────

def _monitor(stop_event):
    """Prints a status line every MONITOR_EVERY seconds. Warns on slow calls."""
    while not stop_event.is_set():
        time.sleep(MONITOR_EVERY)
        if stop_event.is_set():
            break

        now = time.time()
        with _lock:
            c = _completed
            f = _failed
            t = _total_calls
            in_flight = list(_in_flight.values())

        slow = [(agent, qid, now - t0) for agent, qid, t0 in in_flight if now - t0 > WARN_AFTER]

        _log(f"── STATUS  completed={c}/{t}  failed={f}  in-flight={len(in_flight)} ──")
        for agent, qid, age in slow:
            _log(f"   ⚠ SLOW ({age:.0f}s)  [{agent}] {qid}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_questions(only_id=None):
    with open(QUESTIONS_FILE) as f:
        questions = json.load(f)
    if only_id:
        questions = [q for q in questions if q["id"] == only_id]
    return questions


def already_complete(question_id):
    path = RESPONSES_DIR / f"{question_id}.json"
    if not path.exists():
        return False
    with open(path) as f:
        data = json.load(f)
    return all(agent in data.get("responses", {}) for agent in AGENTS)


def agent_cached(question_id, agent):
    path = RESPONSES_DIR / f"{question_id}.json"
    if not path.exists():
        return False
    with open(path) as f:
        data = json.load(f)
    return agent in data.get("responses", {})


def extract_text(parsing, agent):
    if not isinstance(parsing, dict):
        return ""
    if agent == "gemini":
        return (parsing.get("markdown") or parsing.get("answer") or "").strip()
    return (parsing.get("answer") or parsing.get("markdown") or "").strip()


def save_response(question, agent, text):
    path = RESPONSES_DIR / f"{question['id']}.json"
    if path.exists():
        with open(path) as f:
            payload = json.load(f)
    else:
        payload = {
            "id":        question["id"],
            "category":  question["category"],
            "question":  question["question"],
            "prompt":    question["prompt"],
            "responses": {},
        }
    payload["responses"][agent] = {
        "raw":    text,
        "format": AGENT_FORMAT[agent],
    }
    payload["fetched_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


# ── Worker ────────────────────────────────────────────────────────────────────

def call_agent(nimble, agent, question):
    """Single SDK call. Registers itself in _in_flight for monitoring."""
    future_key = threading.current_thread()
    t0 = time.time()

    with _lock:
        _in_flight[future_key] = (agent, question["id"], t0)

    _log(f"  → START  [{agent:<10}] {question['id']}")

    try:
        result = nimble.agent.run(
            agent=agent,
            params={"prompt": question["prompt"]},
        )
        text = extract_text(result.data.parsing, agent)
        if not text:
            raise ValueError("Empty response text")

        elapsed = time.time() - t0
        return question["id"], agent, text, elapsed

    finally:
        with _lock:
            _in_flight.pop(future_key, None)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global _total_calls, _completed, _failed

    parser = argparse.ArgumentParser()
    parser.add_argument("--id",      help="Fetch a single question ID (e.g. q_005)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    questions = load_questions(only_id=args.id)
    pending   = [q for q in questions if not already_complete(q["id"])]

    if not pending:
        _log("All questions already cached. Nothing to fetch.")
        return

    pending_jobs  = [(agent, q) for q in pending for agent in AGENTS
                     if not agent_cached(q["id"], agent)]
    total_calls   = len(pending_jobs)
    _total_calls  = total_calls

    _log(f"Questions : {len(pending)} pending / {len(questions)} total")
    _log(f"Models    : {', '.join(AGENTS)}")
    _log(f"Calls     : {total_calls}  ({MAX_WORKERS} workers, {CALL_TIMEOUT}s timeout each)")

    if args.dry_run:
        for agent, q in pending_jobs:
            _log(f"  [{agent:<10}] {q['id']} — {q['question'][:60]}")
        return

    if not API_KEY:
        _log("ERROR: NIMBLE_API_KEY not set. Aborting.")
        return

    nimble = Nimble(api_key=API_KEY)

    # Start monitor thread
    stop_monitor = threading.Event()
    monitor = threading.Thread(target=_monitor, args=(stop_monitor,), daemon=True)
    monitor.start()

    wall_start = time.time()
    _log(f"\n── Fetching ({'dry run' if args.dry_run else 'live'}) ─────────────────────────────────────────")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(call_agent, nimble, agent, q): (agent, q)
            for agent, q in pending_jobs
        }

        for future in as_completed(futures):
            agent, q = futures[future]
            try:
                qid, agent_name, text, call_elapsed = future.result(timeout=CALL_TIMEOUT)
                save_response(q, agent_name, text)
                with _lock:
                    _completed += 1
                    c = _completed
                pct = c / total_calls * 100
                _log(f"  ✓ DONE   [{agent_name:<10}] {qid}  {call_elapsed:.0f}s  ({c}/{total_calls} · {pct:.0f}%)")

            except TimeoutError:
                with _lock:
                    _failed += 1
                _log(f"  ✗ TIMEOUT [{agent:<10}] {q['id']}  — exceeded {CALL_TIMEOUT}s")

            except Exception as e:
                with _lock:
                    _failed += 1
                _log(f"  ✗ FAILED  [{agent:<10}] {q['id']}  — {e}")

    stop_monitor.set()

    wall_elapsed = time.time() - wall_start
    fully_cached = sum(1 for q in questions if already_complete(q["id"]))

    _log(f"\n── Done ─────────────────────────────────────────────────────────────")
    _log(f"Completed : {_completed} / {total_calls}  (wall time: {wall_elapsed:.0f}s)")
    _log(f"Failed    : {_failed}")
    _log(f"Cache     : {fully_cached} / {len(questions)} questions fully cached")

    if _failed > 0:
        _log(f"\n⚠  {_failed} calls failed. Re-run fetch.py to retry missing responses.")


if __name__ == "__main__":
    main()
