"""Web Search Agents run lifecycle for Diligence Desk.

Live mode drives /v1/task-agents; replay mode (USE_LIVE=false) serves the
verbatim raw responses in data/sample_run/ through the same code paths.
"""
import json
import time

import requests

import config as C

H = {"Authorization": f"Bearer {C.NIMBLE_API_KEY}"}
PATCH_H = {**H, "Content-Type": "application/json-patch+json"}


class RunFailed(Exception):
    def __init__(self, message, payload=None):
        super().__init__(message)
        self.payload = payload


def _agent_id():
    return json.loads(C.AGENT_FILE.read_text())["agent_id"]


def get_agent():
    r = requests.get(f"{C.BASE_URL}/task-agents/{_agent_id()}", headers=H, timeout=60)
    r.raise_for_status()
    return r.json()


def start_run(input_text, *, effort=None, output_schema=None, previous_interaction_id=None):
    """POST a run; returns the run object (202)."""
    body = {"input": input_text}
    if effort:
        body["effort"] = effort
    if output_schema is not None:
        body["output_schema"] = output_schema
    if previous_interaction_id:
        body["previous_interaction_id"] = previous_interaction_id
    r = requests.post(f"{C.BASE_URL}/task-agents/{_agent_id()}/runs", headers=H,
                      json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def poll_run(run_id):
    r = requests.get(f"{C.BASE_URL}/task-agents/{_agent_id()}/runs/{run_id}",
                     headers=H, timeout=60)
    r.raise_for_status()
    return r.json()


def cancel_run(run_id):
    requests.post(f"{C.BASE_URL}/task-agents/{_agent_id()}/runs/{run_id}/cancel",
                  headers=H, timeout=60)


def fetch_result(run_id):
    """GET the result; retries through 408 (still active)."""
    r = requests.get(f"{C.BASE_URL}/task-agents/{_agent_id()}/runs/{run_id}/result",
                     headers=H, timeout=120)
    if r.status_code == 408:
        return None
    r.raise_for_status()
    return r.json()


def wait_for_result(run_id, on_tick=None, poll_seconds=20, timeout_seconds=2400):
    """Poll until terminal, then return the verbatim AgentRunResult.

    on_tick(elapsed_seconds, status) fires every poll — the UI progress banner.
    Raises RunFailed on failed/cancelled runs.
    """
    t0 = time.time()
    while True:
        run = poll_run(run_id)
        elapsed = int(time.time() - t0)
        if on_tick:
            on_tick(elapsed, run["status"])
        if not run["is_active"]:
            break
        if elapsed > timeout_seconds:
            raise RunFailed(f"run {run_id} timed out after {elapsed}s")
        time.sleep(poll_seconds)

    result = fetch_result(run_id)
    if run["status"] != "completed":
        msg = (result or {}).get("output", {}).get("content") or \
              (run.get("error") or {}).get("message") or run["status"]
        raise RunFailed(f"run {run['status']}: {msg}", payload=result)
    return result


# --- high-level flows (replay-aware) ---

def _replay(name):
    return json.loads((C.SAMPLE_DIR / name).read_text())


def _slug(text):
    import re
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def run_memo(company_prompt, on_tick=None, cache_key=None):
    """Full memo run. Returns (raw_result, run_obj).

    Replay mode serves a company-keyed cache (memo_result_<slug>.json) when one
    exists, falling back to the default sample memo.
    """
    if not C.USE_LIVE:
        if on_tick:
            on_tick(0, "running (replay)")
        key = _slug(cache_key) if cache_key else None
        if key and (C.SAMPLE_DIR / f"memo_result_{key}.json").exists():
            return _replay(f"memo_result_{key}.json"), _replay(f"memo_run_{key}.json")
        return _replay("memo_result.json"), _replay("memo_run.json")
    run = start_run(company_prompt)
    result = wait_for_result(run["id"], on_tick=on_tick)
    run = poll_run(run["id"])  # refresh for interaction_id/timestamps
    return result, run


def run_followup(question, previous_interaction_id, followup_index=0, on_tick=None):
    """Follow-up Q&A run at high effort with the minimal QA schema."""
    if not C.USE_LIVE:
        if on_tick:
            on_tick(0, "running (replay)")
        return _replay(f"followup_{followup_index}_result.json"), \
               _replay(f"followup_{followup_index}_run.json")
    run = start_run(question, effort="high", output_schema=C.QA_SCHEMA,
                    previous_interaction_id=previous_interaction_id)
    result = wait_for_result(run["id"], on_tick=on_tick)
    run = poll_run(run["id"])
    return result, run


def teach(instruction):
    """Append a standing instruction to the agent's domain_expertise via PATCH.

    Returns (expertise_before, expertise_after). Replay mode simulates locally.
    """
    if not C.USE_LIVE:
        pair = _replay("teach_before_after.json")
        return pair["before"], pair["after"]
    agent = get_agent()
    before = agent["domain_expertise"]
    placeholder = "- (none yet)"
    bullet = f"- {instruction.strip()}"
    if placeholder in before:
        after = before.replace(placeholder, bullet)
    elif C.STANDING_INSTRUCTIONS_HEADER in before:
        head, _, tail = before.partition(C.STANDING_INSTRUCTIONS_HEADER)
        after = head + C.STANDING_INSTRUCTIONS_HEADER + tail.rstrip() + f"\n{bullet}\n"
    else:
        after = before.rstrip() + f"\n\n{C.STANDING_INSTRUCTIONS_HEADER}\n{bullet}\n"
    r = requests.patch(f"{C.BASE_URL}/task-agents/{_agent_id()}", headers=PATCH_H,
                       json=[{"op": "replace", "path": "/domain_expertise", "value": after}],
                       timeout=60)
    r.raise_for_status()
    return before, after
