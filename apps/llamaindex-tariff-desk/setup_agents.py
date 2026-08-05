"""Provision the two Web Search Agents once, then verify them.

Idempotent: if the ids are already in .env, this reports and exits without
creating duplicates. Only ever creates; never deletes anything it did not create.

The connector (`NimbleAgentToolSpec`) is execution-only by design and cannot do
this — agent administration stays off the LLM surface. That is why provisioning
is a separate one-time script.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from nimble_python import Nimble

sys.path.insert(0, str(Path(__file__).parent))
from desk.agents_config import AGENTS  # noqa: E402

ENV_PATH = Path(__file__).parent / ".env"
ENV_KEYS = {"rate": "NIMBLE_RATE_AGENT_ID",
            "overlay": "NIMBLE_OVERLAY_AGENT_ID",
            "hts": "NIMBLE_HTS_AGENT_ID"}


def write_env(key: str, value: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    lines = [ln for ln in lines if not ln.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    load_dotenv(ENV_PATH)
    if not os.environ.get("NIMBLE_API_KEY"):
        print("NIMBLE_API_KEY is not set", file=sys.stderr)
        return 2

    client = Nimble(api_key=os.environ["NIMBLE_API_KEY"])

    for kind, cfg in AGENTS.items():
        env_key = ENV_KEYS[kind]
        existing = os.environ.get(env_key)
        if existing:
            print(f"[{kind}] already provisioned: {existing} — skipping create")
            agent_id = existing
        else:
            agent = client.agents.create(
                display_name=cfg["display_name"],
                description=cfg["description"],
                icon=cfg["icon"],
                use_case=cfg["use_case"],
                effort=cfg["effort"],
                skill=cfg["skill"],
                goals=cfg["goals"],
                sources=cfg["sources"],
                output_schema=cfg["output_schema"],
                suggested_questions=cfg["suggested_questions"],
            )
            agent_id = agent.id
            print(f"[{kind}] created {agent_id}")
            write_env(env_key, agent_id)

        # Verify: created-from-scratch agents keep inline fields (quirk 6a), but
        # a GET is cheap and source enforcement depends on sources.allow landing.
        got = client.agents.get(agent_id)
        allow = (getattr(got.sources, "allow", None) or []) if got.sources else []
        goals = getattr(got, "goals", None) or []
        schema = getattr(got, "output_schema", None)
        skill = getattr(got, "skill", None) or ""
        sq = getattr(got, "suggested_questions", None) or []

        print(
            f"[{kind}] verify: effort={got.effort} use_case={got.use_case} "
            f"skill={len(skill)}ch goals={len(goals)} "
            f"sources.allow={len(allow)} schema={'Y' if schema else 'N'} "
            f"suggested_questions={len(sq)}"
        )
        problems = []
        if not allow:
            problems.append("sources.allow is EMPTY — no whitelist landed")
        if not goals:
            problems.append("goals are EMPTY — no acceptance criteria")
        if not schema:
            problems.append("output_schema is EMPTY")
        if not skill:
            problems.append("skill is EMPTY")
        for p in problems:
            print(f"[{kind}] !! {p}")
        if problems:
            return 1

    print(f"\nall {len(AGENTS)} agents provisioned and verified; ids written to .env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
