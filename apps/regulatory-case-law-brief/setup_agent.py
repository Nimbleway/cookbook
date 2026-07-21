"""Create the Regulatory & Case-Law Brief agent (idempotent via agents.json)."""
import json
import sys

import requests

import config as C
from agent_config import LEGAL_BRIEF


def main():
    if not C.NIMBLE_API_KEY:
        sys.exit("NIMBLE_API_KEY not set")
    if C.AGENTS_FILE.exists():
        print("agents.json exists — reusing", json.loads(C.AGENTS_FILE.read_text()))
        return
    r = requests.post(f"{C.BASE_URL}/task-agents", headers=C.HEADERS, json=LEGAL_BRIEF, timeout=120)
    r.raise_for_status()
    ids = {"legal_brief": r.json()["id"]}
    C.AGENTS_FILE.write_text(json.dumps(ids, indent=2))
    print("created:", ids)


if __name__ == "__main__":
    main()
