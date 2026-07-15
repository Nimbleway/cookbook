"""Create or update the production Diligence Analyst agent.

Idempotent: first run clones the due-diligence template and applies the full
config from config.py; later runs re-PATCH the same agent (so config edits are
re-appliable). The agent id lives in agent.json.

Usage: python setup_agent.py
"""
import json
import sys

import requests

import config as C

H = {"Authorization": f"Bearer {C.NIMBLE_API_KEY}"}
PATCH_H = {**H, "Content-Type": "application/json-patch+json"}


def patch_config(agent_id, expertise=None):
    """Apply the config.py agent definition (optionally with a custom expertise string)."""
    ops = [
        {"op": "replace", "path": "/domain_expertise", "value": expertise or C.DOMAIN_EXPERTISE},
        {"op": "replace", "path": "/goals", "value": C.GOALS},
        {"op": "replace", "path": "/sources", "value": C.SOURCES},
        {"op": "replace", "path": "/output_schema", "value": C.OUTPUT_SCHEMA},
        {"op": "replace", "path": "/suggested_questions", "value": C.SUGGESTED_QUESTIONS},
        {"op": "replace", "path": "/effort", "value": "max"},
    ]
    r = requests.patch(f"{C.BASE_URL}/task-agents/{agent_id}", headers=PATCH_H,
                       json=ops, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    agent_id = None
    if C.AGENT_FILE.exists():
        agent_id = json.loads(C.AGENT_FILE.read_text()).get("agent_id")
        r = requests.get(f"{C.BASE_URL}/task-agents/{agent_id}", headers=H, timeout=60)
        if r.status_code == 200 and r.json().get("is_active"):
            print(f"existing agent {agent_id} — re-applying config")
        else:
            print(f"agent {agent_id} missing/inactive — creating fresh")
            agent_id = None

    if agent_id is None:
        r = requests.post(f"{C.BASE_URL}/task-agents", headers=H, timeout=60, json={
            "template": "due-diligence",
            "display_name": "Diligence Desk — Analyst",
            "description": "Audit-grade company diligence memos with per-claim citations",
            "effort": "max",  # spec default is buggy; always explicit
        })
        r.raise_for_status()
        agent_id = r.json()["id"]
        C.AGENT_FILE.write_text(json.dumps({"agent_id": agent_id}, indent=2))
        print(f"created agent {agent_id}")

    agent = patch_config(agent_id)

    # Level-1 verify on the instance
    assert agent["effort"] == "max"
    assert agent["output_schema"]["properties"]["overall_assessment"], "schema not applied"
    assert len(agent["goals"]) == len(C.GOALS), "goals not applied"
    allow_titles = [g["title"] for g in agent["sources"]["allow"]]
    assert "Litigation & Court Records" in allow_titles, "sources not applied"
    assert C.STANDING_INSTRUCTIONS_HEADER in agent["domain_expertise"]
    print(f"config verified: {len(agent['goals'])} goals, "
          f"{len(allow_titles)} source groups, effort=max")
    return 0


if __name__ == "__main__":
    sys.exit(main())
