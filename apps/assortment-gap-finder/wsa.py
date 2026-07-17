"""Thin client for Nimble Web Search Agents runs."""
import time

import requests

import config as C

H = {"Authorization": f"Bearer {C.NIMBLE_API_KEY}"}


class RunFailed(Exception):
    def __init__(self, msg, payload=None):
        super().__init__(msg)
        self.payload = payload


def start_run(agent_id, input_text, previous_interaction_id=None, sources=None, effort="high"):
    body = {"input": input_text, "effort": effort}  # never below high (planner bug)
    if previous_interaction_id:
        body["previous_interaction_id"] = previous_interaction_id
    if sources:
        body["sources"] = sources
    r = requests.post(f"{C.BASE_URL}/task-agents/{agent_id}/runs", json=body, headers=H, timeout=120)
    r.raise_for_status()
    return r.json()


def poll_run(agent_id, run_id):
    r = requests.get(f"{C.BASE_URL}/task-agents/{agent_id}/runs/{run_id}", headers=H, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_result(agent_id, run_id):
    r = requests.get(f"{C.BASE_URL}/task-agents/{agent_id}/runs/{run_id}/result", headers=H, timeout=120)
    if r.status_code == 408:
        return None
    r.raise_for_status()
    return r.json()


def wait_for_result(agent_id, run_id, on_tick=None, poll_seconds=20, timeout_seconds=1500):
    t0 = time.time()
    while True:
        run = poll_run(agent_id, run_id)
        elapsed = int(time.time() - t0)
        if on_tick:
            on_tick(elapsed, run["status"])
        if not run["is_active"]:
            break
        if elapsed > timeout_seconds:
            raise RunFailed(f"run {run_id} timed out after {elapsed}s")
        time.sleep(poll_seconds)

    # the result endpoint can still 408 briefly after the run turns terminal
    result = fetch_result(agent_id, run_id)
    for _ in range(5):
        if result is not None:
            break
        time.sleep(15)
        result = fetch_result(agent_id, run_id)
    if run["status"] != "completed":
        msg = (run.get("error") or {}).get("message") or run["status"]
        raise RunFailed(f"run {run['status']}: {msg}", payload=result)
    if result is None:
        raise RunFailed(f"run {run_id} completed but the result never became available")
    return result, run
