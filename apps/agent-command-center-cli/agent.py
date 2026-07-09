"""Agent Command Center — a conversational Claude agent for managing a fleet
of Nimble Web Search Agents through the Nimble Task Agents API.

Docs: https://nimble-f5a8283f-docs-task-agents-api.mintlify.app/api-reference/web-search-agents

Run it with `python agent.py`. See README.md for what it does and
ai-setup.md for setup instructions.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

import anthropic
import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

load_dotenv()

# --------------------------------------------------------------------------
# Nimble Task Agents API client
#
# Mostly scoped to agent configuration and lifecycle (list/get/create/
# update/deactivate, templates) — there's no general run browsing/
# cancellation here. The one exception is `run_and_wait`, used narrowly by
# the "test this agent" tool to ground improvement suggestions in a real
# result instead of guessing from static config alone.
# --------------------------------------------------------------------------

TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


class NimbleApiError(RuntimeError):
    def __init__(self, status_code: int, body: object):
        super().__init__(f"Nimble API error {status_code}: {body}")
        self.status_code = status_code
        self.body = body


class TaskAgentsClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        api_key = api_key or os.environ.get("NIMBLE_API_KEY")
        base_url = base_url or os.environ.get("NIMBLE_BASE_URL", "https://sdk.nimbleway.com")
        if not api_key:
            raise ValueError(
                "NIMBLE_API_KEY is not set. Copy .env.example to .env and add your key "
                "from online.nimbleway.com -> Account Settings -> API Keys."
            )
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    def _request(self, method: str, path: str, **kwargs) -> object:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code == 204:
            return None
        try:
            data = resp.json() if resp.content else None
        except ValueError:
            data = resp.text
        if resp.is_error:
            raise NimbleApiError(resp.status_code, data)
        return data

    def list_agents(self, use_case: str | None = None, effort: str | None = None) -> list[dict]:
        params = {"limit": 200}
        if use_case:
            params["use_case"] = use_case
        if effort:
            params["effort"] = effort
        return self._request("GET", "/v1/task-agents", params=params)

    def get_agent(self, agent_id: str) -> dict:
        return self._request("GET", f"/v1/task-agents/{agent_id}")

    def create_agent(self, config: dict) -> dict:
        return self._request("POST", "/v1/task-agents", json=config)

    def update_agent(self, agent_id: str, updates: dict) -> dict:
        """Translates a partial update into the JSON Patch array the API
        expects — one "replace" op per top-level field. `agent_name` is
        immutable and is silently dropped if present."""
        patch_ops = [
            {"op": "replace", "path": f"/{field}", "value": value}
            for field, value in updates.items()
            if field != "agent_name" and value is not None
        ]
        return self._request("PATCH", f"/v1/task-agents/{agent_id}", json=patch_ops)

    def deactivate_agent(self, agent_id: str) -> None:
        self._request("DELETE", f"/v1/task-agents/{agent_id}")

    def list_templates(self, use_case: str | None = None, effort: str | None = None) -> list[dict]:
        params = {"limit": 200}
        if use_case:
            params["use_case"] = use_case
        if effort:
            params["effort"] = effort
        return self._request("GET", "/v1/task-agents/templates", params=params)

    def get_template(self, template_name: str) -> dict:
        return self._request("GET", f"/v1/task-agents/templates/{template_name}")

    def create_run(self, agent_id: str, input_text: str) -> dict:
        return self._request("POST", f"/v1/task-agents/{agent_id}/runs", json={"input": input_text})

    def get_run(self, agent_id: str, run_id: str) -> dict:
        return self._request("GET", f"/v1/task-agents/{agent_id}/runs/{run_id}")

    def get_run_result(self, agent_id: str, run_id: str) -> dict:
        return self._request("GET", f"/v1/task-agents/{agent_id}/runs/{run_id}/result")

    def run_and_wait(
        self,
        agent_id: str,
        input_text: str,
        timeout_seconds: float = 120.0,
        poll_interval_seconds: float = 4.0,
    ) -> dict:
        """Create a run and poll until it reaches a terminal status.

        Returns a plain dict rather than raising, so a failed/timed-out test
        run is still useful diagnostic information to hand back to the
        model: {status, run_id, input, output?, error?}.

        A run can legitimately fail even when every API call succeeds (e.g.
        a DegradedRunError when the agent can't produce a confident report)
        — GET .../result returns 422 for a non-completed run, so this only
        ever calls it once status == "completed".
        """
        run = self.create_run(agent_id, input_text)
        run_id = run["id"]

        deadline = time.monotonic() + timeout_seconds
        while run["status"] not in TERMINAL_RUN_STATUSES:
            if time.monotonic() > deadline:
                return {
                    "status": "timeout",
                    "run_id": run_id,
                    "input": input_text,
                    "note": f"Still running after {timeout_seconds:.0f}s; gave up waiting.",
                }
            time.sleep(poll_interval_seconds)
            run = self.get_run(agent_id, run_id)

        if run["status"] != "completed":
            return {
                "status": run["status"],
                "run_id": run_id,
                "input": input_text,
                "error": run.get("error"),
            }

        result = self.get_run_result(agent_id, run_id)
        return {
            "status": "completed",
            "run_id": run_id,
            "input": input_text,
            "output": result.get("output"),
        }


# --------------------------------------------------------------------------
# Tool definitions + dispatcher
#
# Deliberately scoped to configuration and lifecycle (list/get/create/
# update/deactivate agents, list/get templates), plus one narrow, purpose-
# built way to trigger a real run: test_agent, used specifically to ground
# improvement suggestions in real output.
# --------------------------------------------------------------------------

VALID_USE_CASES = ["research", "enrichment", "dataset_building"]
VALID_EFFORTS = ["low", "medium", "high", "x-high", "max"]
VALID_FIELD_TYPES = ["string", "number", "boolean", "array", "object"]

_SCHEMA_FIELDS = {
    "type": "array",
    "description": "Simple output-schema field builder: each entry becomes a property "
    "on the generated JSON Schema object.",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"type": "string", "enum": VALID_FIELD_TYPES},
            "required": {"type": "boolean"},
        },
        "required": ["name", "type"],
    },
}

_SOURCES = {
    "type": "array",
    "description": "Allow-listed sources to steer the agent's research.",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "domains": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title"],
    },
}

TOOLS = [
    {
        "name": "list_agents",
        "description": (
            "List agents in the fleet as a condensed summary (id, names, use case, effort, "
            "active status, goal/source counts, whether an output schema is set, last updated). "
            "Note: Nimble's list endpoint only ever returns ACTIVE agents — a deactivated agent "
            "won't appear here even though get_agent can still fetch it directly by id. "
            "Use this first to find an agent's id before calling get_agent/update_agent/"
            "deactivate_agent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "use_case": {"type": "string", "enum": VALID_USE_CASES},
                "effort": {"type": "string", "enum": VALID_EFFORTS},
            },
        },
    },
    {
        "name": "get_agent",
        "description": "Get the full configuration of one agent by id (goals, sources, output schema, domain expertise, suggested questions).",
        "input_schema": {
            "type": "object",
            "properties": {"agent_id": {"type": "string"}},
            "required": ["agent_id"],
        },
    },
    {
        "name": "create_agent",
        "description": "Create a new web search agent from scratch. agent_name must be a unique, url-safe, kebab-case identifier.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string"},
                "display_name": {"type": "string"},
                "description": {"type": "string"},
                "use_case": {"type": "string", "enum": VALID_USE_CASES},
                "effort": {"type": "string", "enum": VALID_EFFORTS},
                "domain_expertise": {
                    "type": "string",
                    "description": "Detailed instructions for how the agent should approach its research.",
                },
                "goals": {"type": "array", "items": {"type": "string"}},
                "sources": _SOURCES,
                "output_schema_fields": _SCHEMA_FIELDS,
                "suggested_questions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["agent_name"],
        },
    },
    {
        "name": "create_agent_from_template",
        "description": (
            "Create a new agent pre-filled from an existing template (see list_templates/"
            "get_template for template_name values), optionally overriding any field. "
            "Prefer this over create_agent when the user's ask matches an existing template."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "template_name": {"type": "string"},
                "agent_name": {"type": "string", "description": "Unique kebab-case identifier for the new agent."},
                "display_name": {"type": "string"},
                "description": {"type": "string"},
                "use_case": {"type": "string", "enum": VALID_USE_CASES},
                "effort": {"type": "string", "enum": VALID_EFFORTS},
                "domain_expertise": {"type": "string"},
                "goals": {"type": "array", "items": {"type": "string"}},
                "sources": _SOURCES,
                "output_schema_fields": _SCHEMA_FIELDS,
                "suggested_questions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["template_name", "agent_name"],
        },
    },
    {
        "name": "update_agent",
        "description": "Update an existing agent's goals, sources, output schema, effort, or description. Only include fields that should change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "display_name": {"type": "string"},
                "description": {"type": "string"},
                "effort": {"type": "string", "enum": VALID_EFFORTS},
                "domain_expertise": {"type": "string"},
                "goals": {"type": "array", "items": {"type": "string"}},
                "sources": _SOURCES,
                "output_schema_fields": _SCHEMA_FIELDS,
                "suggested_questions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "deactivate_agent",
        "description": (
            "Deactivate an agent. This does NOT delete it — its configuration is preserved and "
            "still reachable via get_agent, but it stops running and drops out of list_agents. "
            "ALWAYS confirm with the user in plain language before calling this with confirmed=true; "
            "calling it with confirmed=false (or omitted) is a safe dry run that returns what would "
            "happen without doing it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "confirmed": {
                    "type": "boolean",
                    "description": "Set true only after the user has explicitly confirmed the deactivation.",
                },
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "list_templates",
        "description": "List available agent templates (condensed: name, display name, description, use case, effort).",
        "input_schema": {
            "type": "object",
            "properties": {
                "use_case": {"type": "string", "enum": VALID_USE_CASES},
                "effort": {"type": "string", "enum": VALID_EFFORTS},
            },
        },
    },
    {
        "name": "get_template",
        "description": "Get the full configuration of one template by template_name (goals, sources, output schema, suggested questions).",
        "input_schema": {
            "type": "object",
            "properties": {"template_name": {"type": "string"}},
            "required": ["template_name"],
        },
    },
    {
        "name": "test_agent",
        "description": (
            "Run a REAL, live test of an agent and wait for the result — not just a look at its "
            "static config. Creates a real Nimble run (consumes real quota, typically takes "
            "10-90 seconds, waits up to 2 minutes) and returns the actual output, or the actual "
            "error if the run failed/degraded. If test_question is omitted, uses one of the "
            "agent's own suggested_questions (fetch the agent first if you don't already know "
            "them), falling back to a generic sanity check if it has none. ALWAYS tell the user "
            "this will take up to ~2 minutes and uses a real run before calling it. Use the real "
            "result (or real failure) to ground concrete improvement suggestions — e.g. a source "
            "that clearly isn't producing citations, an output field the run left empty, or a "
            "DegradedRunError suggesting the goals/sources don't match what's realistically "
            "findable — rather than guessing improvements from the config alone."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "test_question": {
                    "type": "string",
                    "description": "Optional custom test input; defaults to one of the agent's suggested_questions.",
                },
            },
            "required": ["agent_id"],
        },
    },
]


def _fields_to_schema(fields: list[dict] | None) -> dict | None:
    if not fields:
        return None
    properties = {}
    required = []
    for f in fields:
        name = f.get("name")
        if not name:
            continue
        properties[name] = {"type": f.get("type", "string")}
        if f.get("required"):
            required.append(name)
    if not properties:
        return None
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _sources_payload(sources: list[dict] | None) -> dict | None:
    if sources is None:
        return None
    allow = [
        {"title": s["title"], "domains": s.get("domains", []), "order": i}
        for i, s in enumerate(sources)
    ]
    return {"allow": allow, "block": []}


def _summarize_agent(a: dict) -> dict:
    return {
        "id": a["id"],
        "agent_name": a["agent_name"],
        "display_name": a.get("display_name"),
        "description": a.get("description"),
        "use_case": a.get("use_case"),
        "effort": a.get("effort"),
        "is_active": a.get("is_active"),
        "goal_count": len(a.get("goals") or []),
        "source_count": len((a.get("sources") or {}).get("allow") or []),
        "has_output_schema": bool(a.get("output_schema")),
        "updated_at": a.get("updated_at"),
    }


def _summarize_template(t: dict) -> dict:
    return {
        "template_name": t["template_name"],
        "display_name": t.get("display_name"),
        "description": t.get("description"),
        "use_case": t.get("use_case"),
        "effort": t.get("effort"),
    }


class ToolRunner:
    def __init__(self, client: TaskAgentsClient):
        self.client = client

    def run(self, name: str, tool_input: dict) -> str:
        try:
            result = self._dispatch(name, tool_input)
        except NimbleApiError as e:
            return json.dumps({"error": str(e), "status_code": e.status_code})
        except Exception as e:  # noqa: BLE001 - surfaced to the model as a tool error
            return json.dumps({"error": str(e)})
        return json.dumps(result, default=str)

    def _dispatch(self, name: str, i: dict) -> object:
        if name == "list_agents":
            agents = self.client.list_agents(use_case=i.get("use_case"), effort=i.get("effort"))
            return {"count": len(agents), "agents": [_summarize_agent(a) for a in agents]}

        if name == "get_agent":
            return self.client.get_agent(i["agent_id"])

        if name == "create_agent":
            config = {
                "agent_name": i["agent_name"],
                "display_name": i.get("display_name"),
                "description": i.get("description"),
                "use_case": i.get("use_case"),
                "effort": i.get("effort"),
                "domain_expertise": i.get("domain_expertise"),
                "goals": i.get("goals"),
                "sources": _sources_payload(i.get("sources")),
                "output_schema": _fields_to_schema(i.get("output_schema_fields")),
                "suggested_questions": i.get("suggested_questions"),
            }
            config = {k: v for k, v in config.items() if v is not None}
            return self.client.create_agent(config)

        if name == "create_agent_from_template":
            template = self.client.get_template(i["template_name"])
            config = {
                "agent_name": i["agent_name"],
                "display_name": i.get("display_name", template.get("display_name")),
                "description": i.get("description", template.get("description")),
                "use_case": i.get("use_case", template.get("use_case")),
                "effort": i.get("effort", template.get("effort")),
                "domain_expertise": i.get("domain_expertise", template.get("domain_expertise")),
                "goals": i.get("goals")
                or [g["goal"] for g in sorted(template.get("goals", []), key=lambda g: g["order"])],
                "sources": _sources_payload(i.get("sources"))
                or {
                    "allow": [
                        {"title": s["title"], "domains": s.get("domains", []), "order": s.get("order", idx)}
                        for idx, s in enumerate(
                            sorted(template.get("sources", []), key=lambda s: s.get("order", 0))
                        )
                    ],
                    "block": [],
                },
                "output_schema": _fields_to_schema(i.get("output_schema_fields"))
                or template.get("output_schema"),
                "suggested_questions": i.get("suggested_questions")
                or [
                    q["question"]
                    for q in sorted(template.get("suggested_questions", []), key=lambda q: q["order"])
                ],
            }
            config = {k: v for k, v in config.items() if v is not None}
            return self.client.create_agent(config)

        if name == "update_agent":
            agent_id = i["agent_id"]
            updates = {
                "display_name": i.get("display_name"),
                "description": i.get("description"),
                "effort": i.get("effort"),
                "domain_expertise": i.get("domain_expertise"),
                "goals": i.get("goals"),
                "sources": _sources_payload(i.get("sources")),
                "output_schema": _fields_to_schema(i.get("output_schema_fields")),
                "suggested_questions": i.get("suggested_questions"),
            }
            updates = {k: v for k, v in updates.items() if v is not None}
            return self.client.update_agent(agent_id, updates)

        if name == "deactivate_agent":
            if not i.get("confirmed"):
                return {
                    "dry_run": True,
                    "message": "Not deactivated. Ask the user to confirm, then call again with confirmed=true.",
                }
            self.client.deactivate_agent(i["agent_id"])
            return {"deactivated": True, "agent_id": i["agent_id"]}

        if name == "list_templates":
            templates = self.client.list_templates(use_case=i.get("use_case"), effort=i.get("effort"))
            return {"count": len(templates), "templates": [_summarize_template(t) for t in templates]}

        if name == "get_template":
            return self.client.get_template(i["template_name"])

        if name == "test_agent":
            agent_id = i["agent_id"]
            question = i.get("test_question")
            if not question:
                agent = self.client.get_agent(agent_id)
                questions = sorted(
                    agent.get("suggested_questions", []), key=lambda q: q["order"]
                )
                question = (
                    questions[0]["question"]
                    if questions
                    else "Give me a sample result to sanity check this agent's configuration."
                )
            return self.client.run_and_wait(agent_id, question)

        raise ValueError(f"Unknown tool: {name}")


# --------------------------------------------------------------------------
# System prompt
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the Agent Command Center — a conversational assistant for managing a \
fleet of Nimble Web Search Agents through the Nimble Task Agents API.

You can list, inspect, create (from scratch or from a template), edit, and deactivate agents. \
You also have one narrow, purpose-built way to trigger a real run: test_agent, used specifically \
to ground improvement suggestions in real output. You do NOT have general run browsing, polling, \
or result-retrieval tools beyond that — if asked for something broader (e.g. "show me all runs \
of X" or "cancel run Y"), say plainly that's out of scope for this tool.

Guidelines:
- "Test and improve" workflow: when asked to test an agent, improve one, or check if it actually \
works, use test_agent to get a REAL result, then critique the agent's current config against that \
real output — call out things like a source that produced no citations, an output field that came \
back empty/null, or a failed/degraded run suggesting the goals or sources don't match what's \
realistically findable on the web. Propose concrete diffs (specific new goals, sources, or output \
schema fields) grounded in what you actually observed, then offer to apply them via update_agent — \
don't apply changes without the user agreeing to the specific proposal first.
- Always tell the user before calling test_agent that it triggers a real run, consumes real quota, \
and can take up to ~2 minutes — this is not free or instant like the config-only tools.
- Prefer list_agents/list_templates before assuming an id or template_name — don't guess ids.
- When the user's request matches an existing template well, suggest it and use \
create_agent_from_template rather than building from scratch.
- Before calling deactivate_agent with confirmed=true, always state in plain language which \
agent you're about to deactivate and get explicit confirmation from the user first. A dry-run \
call (confirmed omitted or false) is safe and returns what would happen without doing it — use \
that to double check the agent_id resolves to the right agent before asking for confirmation.
- Nimble's list endpoint only returns ACTIVE agents. If asked about a deactivated agent, you need \
its id (from prior context) to fetch it directly with get_agent — mention this limitation if it's \
relevant to what the user asked.
- When presenting a list of agents or templates, use a compact markdown table (name, use case, \
effort, active status, source/goal counts) rather than dumping raw JSON.
- Ask a clarifying question when a request is genuinely ambiguous (e.g. which agent, when several \
share a similar name) instead of guessing.
- Deactivating is reversible in spirit (config is preserved, nothing is deleted) but stops the \
agent from running — still treat it as a real action worth confirming, not a no-op.
"""

MODEL = "claude-sonnet-5"
MAX_TOKENS = 4096


# --------------------------------------------------------------------------
# Anthropic tool-use loop
# --------------------------------------------------------------------------


class AgentCommandCenter:
    def __init__(self, on_tool_call: Callable[[str, dict], None] | None = None):
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key "
                "from console.anthropic.com."
            )
        self.client = anthropic.Anthropic(api_key=anthropic_key)
        self.runner = ToolRunner(TaskAgentsClient())
        self.messages: list[dict] = []
        self.on_tool_call = on_tool_call

    def send(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.messages,
            )
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return "".join(block.text for block in response.content if block.type == "text")

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if self.on_tool_call:
                    self.on_tool_call(block.name, block.input)
                result = self.runner.run(block.name, block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )
            self.messages.append({"role": "user", "content": tool_results})


# --------------------------------------------------------------------------
# First-run key onboarding
#
# Shows the user which API keys were found (from .env / the environment),
# lets them accept each one or paste a replacement, and optionally persists
# a replacement back to .env for next time.
# --------------------------------------------------------------------------

ENV_PATH = Path(__file__).parent / ".env"


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}…{key[-4:]}"


def _update_env_file(env_var: str, value: str) -> None:
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    updated = False
    for idx, line in enumerate(lines):
        if line.strip().startswith(f"{env_var}="):
            lines[idx] = f"{env_var}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{env_var}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def resolve_key(console: Console, env_var: str, label: str, where_to_get: str) -> str:
    """Ask the user to accept the key found in the environment, or paste a
    different one. Returns the key to use; also sets it back into
    os.environ so TaskAgentsClient/AgentCommandCenter pick it up without
    changes."""

    existing = os.environ.get(env_var)

    if existing:
        console.print(f"Found [bold]{label}[/bold]: [dim]{mask_key(existing)}[/dim]")
        choice = console.input("Use this key? [Y/n] ").strip().lower()
        if choice in ("", "y", "yes"):
            return existing
    else:
        console.print(f"No [bold]{label}[/bold] found in .env or your environment.")

    while True:
        new_key = console.input(
            f"Paste your {label} ({where_to_get}): ", password=True
        ).strip()
        if new_key:
            break
        console.print("[red]A key is required to continue.[/red]")

    save = console.input("Save this to .env for next time? [Y/n] ").strip().lower()
    if save in ("", "y", "yes"):
        _update_env_file(env_var, new_key)
        console.print(f"[dim]Saved to {ENV_PATH}[/dim]")

    os.environ[env_var] = new_key
    return new_key


def resolve_all_keys(console: Console) -> None:
    console.print("[bold]Setup[/bold]")
    resolve_key(
        console,
        "NIMBLE_API_KEY",
        "Nimble API key",
        "online.nimbleway.com → Account Settings → API Keys",
    )
    resolve_key(
        console,
        "ANTHROPIC_API_KEY",
        "Anthropic API key",
        "console.anthropic.com",
    )
    console.print()


# --------------------------------------------------------------------------
# Terminal REPL
# --------------------------------------------------------------------------

console = Console()


def print_welcome():
    console.print(
        Panel.fit(
            "[bold]Agent Command Center[/bold]\n"
            "Manage your Nimble Web Search Agent fleet in plain English.\n\n"
            "[dim]Try: \"list my agents\", \"show me anything with no sources configured\", "
            "\"make a lead-enrichment agent from the template for SaaS companies\", "
            "\"deactivate the one called debug-test\"[/dim]",
            title="🤖 Nimble Task Agents",
            border_style="cyan",
        )
    )


def on_tool_call(name: str, tool_input: dict) -> None:
    console.print(f"[dim]→ {name}({tool_input})[/dim]")
    if name == "test_agent":
        console.print("[dim]  (this triggers a real run — can take up to ~2 minutes)[/dim]")


def main() -> None:
    print_welcome()
    resolve_all_keys(console)

    try:
        agent = AgentCommandCenter(on_tool_call=on_tool_call)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    while True:
        try:
            user_input = console.input("\n[bold cyan]you>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            console.print("[dim]Goodbye.[/dim]")
            break

        try:
            with console.status("[dim]thinking…[/dim]", spinner="dots"):
                reply = agent.send(user_input)
        except Exception as e:  # noqa: BLE001 - keep the REPL alive on API errors
            console.print(f"[red]Error: {e}[/red]")
            continue

        console.print(Markdown(reply))


if __name__ == "__main__":
    main()
