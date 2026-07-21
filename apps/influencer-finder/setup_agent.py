"""Create the Influencer Finder agent (idempotent via agents.json)."""
import json
import sys

import requests

import config as C
from agent_config import INFLUENCER_FINDER


def main():
    if not C.NIMBLE_API_KEY:
        sys.exit("NIMBLE_API_KEY not set")
    if C.AGENTS_FILE.exists():
        try:
            existing = json.loads(C.AGENTS_FILE.read_text())
        except json.JSONDecodeError:
            existing = None
        if isinstance(existing, dict) and existing.get("influencer_finder"):
            print("agents.json valid — reusing", existing)
            return
        print("agents.json present but missing a valid 'influencer_finder' id — recreating")
    r = requests.post(f"{C.BASE_URL}/task-agents", headers=C.HEADERS, json=INFLUENCER_FINDER, timeout=120)
    r.raise_for_status()
    ids = {"influencer_finder": r.json()["id"]}
    C.AGENTS_FILE.write_text(json.dumps(ids, indent=2))
    print("created:", ids)


if __name__ == "__main__":
    main()
