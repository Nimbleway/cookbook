"""Create the MCM Seller Discovery agent (idempotent via agents.json)."""
import json
import sys

import requests

import config as C
from agent_config import SELLER_DISCOVERY


def create(cfg: dict) -> str:
    r = requests.post(f"{C.BASE_URL}/task-agents", headers=C.HEADERS, json=cfg, timeout=120)
    r.raise_for_status()
    return r.json()["id"]


def main() -> None:
    if not C.NIMBLE_API_KEY:
        sys.exit("NIMBLE_API_KEY not set")
    if C.AGENTS_FILE.exists():
        ids = json.loads(C.AGENTS_FILE.read_text())
        print(f"agents.json exists — reusing {ids}")
        return
    ids = {"seller_discovery": create(SELLER_DISCOVERY)}
    C.AGENTS_FILE.write_text(json.dumps(ids, indent=2))
    print("created:", ids)


if __name__ == "__main__":
    main()
