#!/usr/bin/env python3
"""Live Docs Grounding Agent — answers software library/API questions by
grounding them in current official docs, changelogs, and release notes via
Nimble's Task Agents API.

Run with:
  python agent.py                    first-run setup, then an interactive question loop
  python agent.py "your question"    ask one question directly and exit
  python agent.py history            list past questions
  python agent.py history <n>        view one in full
  python agent.py history delete <n> delete one
  python agent.py --reset            force re-prompt for the API key and recreate the agent

Everything the agent knows about its domain (expertise, goals, allowed
sources, effort tier, output schema) lives in agent_config.json, not in this
file — edit that file and re-run with --reset to point this same code at a
different domain.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import sys
import textwrap
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
CONFIG_PATH = ROOT / "agent_config.json"
AGENT_ID_PATH = ROOT / ".agent_id"
HISTORY_PATH = ROOT / "history.jsonl"
DEFAULT_BASE_URL = "https://sdk.nimbleway.com"

load_dotenv(dotenv_path=ENV_PATH)


# ============================================================================
# UI — terminal rendering. Colors degrade to plain text automatically when
# stdout isn't a real terminal (e.g. piped output, CI logs).
# ============================================================================

IS_TTY = sys.stdout.isatty()
_SUPPORTS_COLOR = IS_TTY
CLEAR_LINE = "\033[K" if IS_TTY else ""
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
_BOLD_SPAN_RE = re.compile(r"\*\*(.+?)\*\*")
_BOLD_NUM_HEADER_RE = re.compile(r"^\*\*(\d+)\.\s*(.+?)\*\*\s*(.*)$")
_NUMBERED_RE = re.compile(r"^(\d+)[.)]\s+(.*)$")
_PAREN_NUMBERED_RE = re.compile(r"^\((\d+)\)\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*•]\s+(.*)$")


def _wrap(code: str, text: str) -> str:
    if not _SUPPORTS_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(text: str) -> str:
    return _wrap("1", text)


def dim(text: str) -> str:
    return _wrap("2", text)


def cyan(text: str) -> str:
    return _wrap("36", text)


def green(text: str) -> str:
    return _wrap("32", text)


def yellow(text: str) -> str:
    return _wrap("33", text)


def blue(text: str) -> str:
    return _wrap("34", text)


def width(cap: int = 96) -> int:
    """Terminal width, capped so prose doesn't stretch unreadably wide on
    huge monitors. Falls back to 80 when stdout isn't a real terminal."""
    try:
        return min(shutil.get_terminal_size().columns, cap)
    except OSError:
        return 80


def rule(char: str = "─") -> str:
    return dim(char * width())


def section(label: str, icon: str = "") -> str:
    return bold(cyan(f"{icon} {label}".strip()))


def _get(d: dict, key: str, default: str = "unknown") -> str:
    """Like dict.get, but also falls back on explicit null/empty values —
    the API can return {"field": null} rather than omitting the key."""
    return d.get(key) or default


def print_intro(effort: str) -> None:
    print()
    print(bold("📚 LIVE DOCS GROUNDING AGENT"))
    print(rule())
    for line in textwrap.wrap(
        "Ask any question about how to use a software library, framework, "
        "or API. It grounds its answer in current official docs, "
        "changelogs, and release notes — always with a working code "
        "snippet and a real citation URL.",
        width=width(),
    ):
        print(line)
    print(yellow(f"⚙ Powered by the Nimble Task Agents API — effort: {effort}"))
    print(dim("📜 Past questions/answers: python agent.py history  (add 'delete <n>' to remove one)"))
    print(rule())
    print()


def _visible_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


def _visible_wrap(text: str, width_: int) -> list:
    """Word-wrap text that may contain ANSI escape codes (e.g. from bold()),
    measuring line length by visible characters only."""
    words = text.split(" ")
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if _visible_len(candidate) > width_ and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _bold_inline(text: str) -> str:
    return _BOLD_SPAN_RE.sub(lambda m: bold(m.group(1)), text)


def _format_answer_line(stripped: str) -> tuple:
    """Returns (formatted_text_with_ansi, is_list_item)."""
    m = _BOLD_NUM_HEADER_RE.match(stripped)
    if m:
        num, label, rest = m.groups()
        head = bold(f"{num}. {label.strip()}")
        rest = _bold_inline(rest.strip())
        return (f"{head}  {rest}".rstrip() if rest else head), True

    for pattern in (_NUMBERED_RE, _PAREN_NUMBERED_RE):
        m = pattern.match(stripped)
        if m:
            num, rest = m.groups()
            return f"{num}. {_bold_inline(rest.strip())}", True

    m = _BULLET_RE.match(stripped)
    if m:
        return f"• {_bold_inline(m.group(1).strip())}", True

    return _bold_inline(stripped), False


def _normalize_answer(text: str) -> str:
    """The agent usually separates multi-part answers with real newlines,
    but sometimes flattens them into one line with inline "(1) ... (2) ..."
    or "**1. ... **2. ..." markers instead. Break those onto their own
    lines so they render as a real list rather than one wall of text."""
    if not text or "\n" in text:
        return text or ""
    for pattern in (r"\*\*\d+\.\s", r"\(\d+\)\s"):
        matches = list(re.finditer(pattern, text))
        if len(matches) >= 2:
            pieces, last = [], 0
            for m in matches:
                if m.start() > last:
                    pieces.append(text[last : m.start()])
                last = m.start()
            pieces.append(text[last:])
            pieces = [p.strip() for p in pieces if p.strip()]
            intro, items = (pieces[0], pieces[1:]) if not re.match(pattern, pieces[0]) else ("", pieces)
            body = "\n".join(items)
            return f"{intro}\n\n{body}" if intro else body
    return text


def _render_answer(answer: str, width_: int) -> list:
    out = []
    for raw in _normalize_answer(answer).split("\n"):
        stripped = raw.strip()
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue
        formatted, is_item = _format_answer_line(stripped)
        indent = "  " if is_item else ""
        wrapped = _visible_wrap(formatted, width_ - len(indent))
        out.append(wrapped[0])
        out.extend(indent + cont for cont in wrapped[1:])
    return out


def print_result(question: str, result: dict) -> None:
    w = width()
    library = _get(result, "library")
    version = result.get("version") or ""
    citations = result.get("citation_urls") or []
    code = result.get("code_snippet") or ""

    print()
    print(rule("═"))
    print(bold(f"❓ {question}"))
    print(rule())

    print(section("LIBRARY", "📦") + f"  {library}" + (f"  ·  {version}" if version else ""))
    print()

    print(section("ANSWER", "💡"))
    for line in _render_answer(_get(result, "answer"), w) or ["(no answer returned)"]:
        print(line)
    print()

    print(section("CODE", "🧩"))
    if code.strip():
        for line in code.rstrip("\n").split("\n"):
            print(dim("  | ") + line)
    else:
        print(dim("  (none returned)"))
    print()

    print(section("CITATIONS", "🔗"))
    if citations:
        for i, url in enumerate(citations, 1):
            print(f"  [{i}] {blue(url)}")
    else:
        print(dim("  (none found)"))

    print(rule("═"))
    print()


def prompt_yes_no(question: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    answer = input(f"{question} {suffix} ").strip().lower()
    if not answer:
        return default_yes
    return answer.startswith("y")


# ============================================================================
# History — local log of past questions/answers, one JSON object per line.
# ============================================================================

def append_entry(timestamp: str, question: str, effort: str, run_id: str, result: dict) -> None:
    entry = {"timestamp": timestamp, "question": question, "effort": effort, "run_id": run_id, "result": result}
    with HISTORY_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def load_entries() -> list:
    if not HISTORY_PATH.exists():
        return []
    return [json.loads(line) for line in HISTORY_PATH.read_text().splitlines() if line.strip()]


def delete_entry(index: int) -> dict:
    """Delete entry #index (1-based, as shown in print_list). Returns the
    removed entry. Raises IndexError if out of range."""
    entries = load_entries()
    if not (1 <= index <= len(entries)):
        raise IndexError(no_entry_message(index, len(entries)))
    removed = entries.pop(index - 1)
    if entries:
        with HISTORY_PATH.open("w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
    elif HISTORY_PATH.exists():
        HISTORY_PATH.unlink()
    return removed


def no_entry_message(index: int, count: int) -> str:
    noun = "question" if count == 1 else "questions"
    return f"No entry #{index} — there {'is' if count == 1 else 'are'} {count} {noun} in history."


def print_list(entries: list) -> None:
    if not entries:
        print(dim('No questions asked yet — ask one with: python agent.py "your question"'))
        return
    count = len(entries)
    print(bold(f"📜 HISTORY ({count} question{'s' if count != 1 else ''})"))
    for i, entry in enumerate(entries, 1):
        library = (entry.get("result") or {}).get("library", "?")
        print(f"  [{i}] {entry.get('timestamp', '?')}  ·  {library}  ·  {entry.get('question', '?')}")
    print()
    print(dim("View one in full:  python agent.py history <number>"))
    print(dim("Delete one:        python agent.py history delete <number>"))


# ============================================================================
# Nimble Task Agents API client
# ============================================================================

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class NimbleAgentRunFailed(RuntimeError):
    pass


class NimbleAgentRunTimeout(RuntimeError):
    pass


class NimbleAgentRunCancelled(RuntimeError):
    pass


class TaskAgentsClient:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL):
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    # --- agent management ----------------------------------------------

    def list_agents(self) -> list:
        resp = self._client.get("/v1/task-agents")
        resp.raise_for_status()
        return resp.json()

    def get_agent(self, agent_id: str) -> dict:
        resp = self._client.get(f"/v1/task-agents/{agent_id}")
        resp.raise_for_status()
        return resp.json()

    def find_agent_by_name(self, agent_name: str):
        for agent in self.list_agents():
            if agent["agent_name"] == agent_name:
                return agent
        return None

    def create_agent(self, config: dict) -> dict:
        resp = self._client.post("/v1/task-agents", json=config)
        resp.raise_for_status()
        return resp.json()

    def update_agent(self, agent_id: str, config: dict) -> dict:
        """Update an existing agent via JSON Patch: one 'replace' op per
        top-level field in `config` (agent_name is immutable, so it's skipped)."""
        patch_ops = [
            {"op": "replace", "path": f"/{field}", "value": value}
            for field, value in config.items()
            if field != "agent_name"
        ]
        resp = self._client.patch(f"/v1/task-agents/{agent_id}", json=patch_ops)
        resp.raise_for_status()
        return resp.json()

    def deactivate_agent(self, agent_id: str) -> None:
        resp = self._client.delete(f"/v1/task-agents/{agent_id}")
        resp.raise_for_status()

    # --- runs -------------------------------------------------------------

    def create_run(self, agent_id: str, question: str) -> dict:
        """POST /v1/task-agents/{agent_id}/runs -> run object with an "id" and
        initial "status"."""
        resp = self._client.post(f"/v1/task-agents/{agent_id}/runs", json={"input": question})
        resp.raise_for_status()
        return resp.json()

    def get_run(self, agent_id: str, run_id: str) -> dict:
        resp = self._client.get(f"/v1/task-agents/{agent_id}/runs/{run_id}")
        resp.raise_for_status()
        return resp.json()

    def cancel_run(self, agent_id: str, run_id: str) -> None:
        resp = self._client.post(f"/v1/task-agents/{agent_id}/runs/{run_id}/cancel")
        resp.raise_for_status()

    def poll_run(
        self,
        agent_id: str,
        run_id: str,
        poll_interval_seconds: float = 5.0,
        timeout_seconds: float = 300.0,
        on_tick=None,
        cancel_event=None,
    ) -> dict:
        """Poll GET .../runs/{run_id} until status is "completed" or "failed"
        (or "cancelled"), then return the final run object.

        If given, on_tick(elapsed_seconds, status) is called after every
        poll so callers can render progress without duplicating the loop.

        If given, cancel_event (a threading.Event) is checked cooperatively:
        the wait between polls is interruptible, and setting it raises
        NimbleAgentRunCancelled. This does not cancel the run on Nimble's
        side by itself — call cancel_run for that."""
        start = time.monotonic()
        run = self.get_run(agent_id, run_id)
        if on_tick:
            on_tick(0.0, run["status"])
        deadline = start + timeout_seconds

        while run["status"] not in TERMINAL_STATUSES:
            if cancel_event is not None and cancel_event.is_set():
                raise NimbleAgentRunCancelled(f"Run {run_id} cancelled by user")
            if time.monotonic() > deadline:
                raise NimbleAgentRunTimeout(f"Run {run_id} did not finish within {timeout_seconds}s")
            if cancel_event is not None:
                if cancel_event.wait(timeout=poll_interval_seconds):
                    raise NimbleAgentRunCancelled(f"Run {run_id} cancelled by user")
            else:
                time.sleep(poll_interval_seconds)
            run = self.get_run(agent_id, run_id)
            if on_tick:
                on_tick(time.monotonic() - start, run["status"])

        return run

    def get_result(self, agent_id: str, run_id: str) -> dict:
        """GET .../runs/{run_id}/result and return the parsed output_schema
        fields (library, version, answer, code_snippet, citation_urls)."""
        resp = self._client.get(f"/v1/task-agents/{agent_id}/runs/{run_id}/result")
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise NimbleAgentRunFailed(f"Run {run_id} failed: {body['error']}")
        return body["output"]["content"]


def create_or_update(client: TaskAgentsClient) -> str:
    """Idempotently create (or update) the agent from agent_config.json, and
    cache its agent id in .agent_id. Returns the agent id."""
    config = json.loads(CONFIG_PATH.read_text())

    existing = client.find_agent_by_name(config["agent_name"])
    if existing:
        agent = client.update_agent(existing["id"], config)
        print(f"Updated existing agent: {agent['id']} ({agent['agent_name']})")
    else:
        agent = client.create_agent(config)
        print(f"Created agent: {agent['id']} ({agent['agent_name']})")

    AGENT_ID_PATH.write_text(agent["id"])
    print(f"Agent id cached at {AGENT_ID_PATH}")
    return agent["id"]


# ============================================================================
# Ask — run a single question through the agent, with a live progress bar
# and mid-run cancellation ('quit' + Enter, or Ctrl+C).
# ============================================================================

# Real end-to-end latency measured for this agent on a sample question, used
# to render a progress bar. Tiers without a benchmark yet just show elapsed
# time with no percentage claim. Canonical effort enum is low/medium/high/
# x-high/max.
EFFORT_BENCHMARK_SECONDS = {"low": 24, "high": 200}
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
BAR_WIDTH = 24
QUIT_WORDS = {"quit", "q", "cancel"}
NON_TTY_LOG_INTERVAL_SECONDS = 20


def _watch_for_quit(cancel_event: threading.Event) -> None:
    """Background thread: block on stdin and set cancel_event if the user
    types one of QUIT_WORDS. Only started on a real terminal — on piped
    input there's no live user typing, and reading stdin here could race
    with a caller that also reads it."""
    while not cancel_event.is_set():
        try:
            line = input()
        except EOFError:
            return
        if line.strip().lower() in QUIT_WORDS:
            cancel_event.set()
            return


def _format_elapsed(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m{secs:02d}s" if minutes else f"{secs}s"


def _render_progress(elapsed: float, status: str, effort: str) -> str:
    """Render one progress line's content (no cursor-control characters)."""
    frame = SPINNER_FRAMES[int(elapsed * 2) % len(SPINNER_FRAMES)]
    benchmark = EFFORT_BENCHMARK_SECONDS.get(effort)
    if benchmark:
        pct = min(99, int(elapsed / benchmark * 100))
        filled = int(BAR_WIDTH * pct / 100)
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        return f"  {frame} {_format_elapsed(elapsed)}  [{bar}] ~{pct}% of typical  ({status})"
    return f"  {frame} {_format_elapsed(elapsed)} elapsed  ({status})"


def ask(client: TaskAgentsClient, agent_id: str, question: str, effort: str) -> dict:
    benchmark = EFFORT_BENCHMARK_SECONDS.get(effort)
    eta_note = f"typically ~{_format_elapsed(benchmark)} at this effort tier" if benchmark else "no timing benchmark yet for this effort tier"
    print(dim(f"Effort: {effort} ({eta_note})."))

    run = client.create_run(agent_id, question)
    print(dim(f"Run created ({run['id']}). Waiting for it to finish..."))
    if IS_TTY:
        print(dim("Type 'quit' + Enter, or press Ctrl+C, to cancel this run."))

    last_logged = [-NON_TTY_LOG_INTERVAL_SECONDS]

    def on_tick(elapsed: float, status: str) -> None:
        line = _render_progress(elapsed, status, effort)
        if IS_TTY:
            sys.stdout.write("\r" + line + CLEAR_LINE)
            sys.stdout.flush()
        elif elapsed - last_logged[0] >= NON_TTY_LOG_INTERVAL_SECONDS:
            print(line)
            last_logged[0] = elapsed

    cancel_event = threading.Event()
    if IS_TTY:
        threading.Thread(target=_watch_for_quit, args=(cancel_event,), daemon=True).start()

    start = time.monotonic()
    try:
        run = client.poll_run(
            agent_id, run["id"],
            poll_interval_seconds=5.0, timeout_seconds=600.0,
            on_tick=on_tick, cancel_event=cancel_event,
        )
    except (NimbleAgentRunCancelled, KeyboardInterrupt):
        if IS_TTY:
            sys.stdout.write("\r" + CLEAR_LINE)
        print(yellow("\nCancelling run..."))
        try:
            client.cancel_run(agent_id, run["id"])
            print(yellow("Run cancelled."))
        except Exception as exc:
            print(yellow(f"Cancel request failed ({exc}); the run may keep going on Nimble's side."))
        raise NimbleAgentRunCancelled(f"Run {run['id']} was cancelled by user") from None
    elapsed = time.monotonic() - start

    if IS_TTY:
        sys.stdout.write("\r" + CLEAR_LINE)
    if run["status"] == "completed":
        print(green(f"  done in {_format_elapsed(elapsed)}"))
    else:
        print(f"  ended with status={run['status']} after {_format_elapsed(elapsed)}")

    if run["status"] != "completed":
        raise NimbleAgentRunFailed(f"Run {run['id']} ended with status={run['status']}: {run.get('error')}")

    result = client.get_result(agent_id, run["id"])
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    append_entry(timestamp, question, effort, run["id"], result)
    return result


# ============================================================================
# First-run setup: validate/save the API key, create the agent if needed.
# ============================================================================

def read_env() -> dict:
    if not ENV_PATH.exists():
        return {}
    values = {}
    for line in ENV_PATH.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_env(values: dict) -> None:
    lines = []
    if ENV_EXAMPLE_PATH.exists():
        for line in ENV_EXAMPLE_PATH.read_text().splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                lines.append(line)
                continue
            key, _, _ = line.partition("=")
            key = key.strip()
            lines.append(f"{key}={values.get(key, '')}")
    else:
        lines = [f"{k}={v}" for k, v in values.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")


def validate_key(api_key: str, base_url: str) -> bool:
    request = urllib.request.Request(
        f"{base_url}/v1/task-agents?limit=1",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False
        raise
    except urllib.error.URLError as exc:
        print(f"  Could not reach Nimble to validate the key ({exc}). Continuing anyway.")
        return True


def get_api_key(existing: dict, base_url: str) -> str:
    if existing.get("NIMBLE_API_KEY"):
        print(f"Found an existing NIMBLE_API_KEY in .env (ends in ...{existing['NIMBLE_API_KEY'][-4:]}).")
        if prompt_yes_no("Use this key?", default_yes=True):
            return existing["NIMBLE_API_KEY"]

    print(
        "\nTo get your Nimble API key:\n"
        "  1. Go to https://online.nimbleway.com and log in (or sign up free).\n"
        "  2. Click your profile icon -> Account Settings -> API Keys.\n"
        "  3. Click 'Create New API Key' and copy it (it's shown only once).\n"
    )
    while True:
        api_key = getpass.getpass("Paste your Nimble API key here (input hidden): ").strip()
        if not api_key:
            print("  That was empty — try again.")
            continue
        print("Validating key against Nimble...")
        if validate_key(api_key, base_url):
            print("  Key looks valid.\n")
            return api_key
        print("  That key was rejected (401 unauthorized). Double-check and try again.\n")


# ============================================================================
# Interactive question loop
# ============================================================================

def agent_loop(client: TaskAgentsClient, agent_id: str, effort: str) -> None:
    """Keep asking for a question and running it against the live agent
    until the user quits. 'history' (optionally with a number or 'delete
    <n>' attached) is handled in-loop."""
    entries = load_entries()
    if entries:
        count = len(entries)
        print(dim(f"You have {count} past question{'s' if count != 1 else ''} — type 'history' to browse them.\n"))

    while True:
        question = input("Question ('history' to browse past Q&A, 'quit' to exit): ").strip()
        if not question or question.lower() in ("quit", "exit", "q"):
            return

        lower = question.lower()
        if lower == "history":
            browse_history()
            continue
        if lower.startswith("history "):
            rest = question.split(None, 1)[1]
            parts = rest.split(None, 1)
            if parts and parts[0].lower() in ("delete", "rm", "remove") and len(parts) > 1:
                handle_history_delete(parts[1].strip())
            else:
                handle_history_lookup(rest)
            continue

        try:
            result = ask(client, agent_id, question, effort)
            print_result(question, result)
        except NimbleAgentRunCancelled:
            pass
        except NimbleAgentRunFailed as exc:
            print(str(exc))
        print()


def browse_history() -> None:
    """Sub-loop entered by typing 'history': shows the list once, then lets
    the user just type a bare number to view it (or 'delete <n>' to remove
    one) without re-typing 'history' each time."""
    print()
    entries = load_entries()
    print_list(entries)
    if not entries:
        print()
        return

    while True:
        print()
        choice = input("Enter a number to view, 'delete <n>' to remove, or press Enter to go back: ").strip()
        if not choice or choice.lower() in ("back", "quit", "exit", "q"):
            print()
            return

        parts = choice.split(None, 1)
        if parts[0].lower() in ("delete", "rm", "remove") and len(parts) > 1:
            handle_history_delete(parts[1].strip())
            entries = load_entries()
            if not entries:
                return
            print_list(entries)
            continue

        handle_history_lookup(choice)


def handle_history_lookup(arg: str) -> None:
    entries = load_entries()
    try:
        index = int(arg)
    except ValueError:
        print(f'  "{arg}" isn\'t a valid history number. Type "history" to see the list.\n')
        return
    if not (1 <= index <= len(entries)):
        print(f"  {no_entry_message(index, len(entries))}\n")
        return
    entry = entries[index - 1]
    print(dim(f"Asked {entry.get('timestamp', '?')}  ·  effort={entry.get('effort', '?')}  ·  run={entry.get('run_id', '?')}"))
    print_result(entry["question"], entry["result"])


def handle_history_delete(arg: str) -> None:
    entries = load_entries()
    try:
        index = int(arg)
    except ValueError:
        print(f'  "{arg}" isn\'t a valid history number.\n')
        return
    if not (1 <= index <= len(entries)):
        print(f"  {no_entry_message(index, len(entries))}\n")
        return
    entry = entries[index - 1]
    if not prompt_yes_no(f'  Delete entry #{index}: "{entry["question"]}"?', default_yes=False):
        print("  Cancelled — nothing deleted.\n")
        return
    delete_entry(index)
    print(f"  Deleted entry #{index}.\n")


# ============================================================================
# Entry point
# ============================================================================

def _handle_history_cli(args: list) -> None:
    entries = load_entries()
    if not args:
        print_list(entries)
        return
    if args[0] in ("delete", "rm", "remove"):
        if len(args) < 2:
            print("Usage: python agent.py history delete <number>")
            sys.exit(1)
        try:
            index = int(args[1])
        except ValueError:
            print(f'"{args[1]}" is not a valid history number.')
            sys.exit(1)
        if not (1 <= index <= len(entries)):
            print(no_entry_message(index, len(entries)))
            sys.exit(1)
        entry = entries[index - 1]
        if not prompt_yes_no(f'Delete entry #{index}: "{entry["question"]}"?', default_yes=False):
            print("Cancelled — nothing deleted.")
            return
        delete_entry(index)
        print(f"Deleted entry #{index}.")
        return

    try:
        index = int(args[0])
    except ValueError:
        print(f'"{args[0]}" is not a valid history number.')
        sys.exit(1)
    if not (1 <= index <= len(entries)):
        print(no_entry_message(index, len(entries)))
        sys.exit(1)
    entry = entries[index - 1]
    print(dim(f"Asked {entry.get('timestamp', '?')}  ·  effort={entry.get('effort', '?')}  ·  run={entry.get('run_id', '?')}"))
    print_result(entry["question"], entry["result"])


def main() -> None:
    args = sys.argv[1:]
    reset = "--reset" in args
    args = [a for a in args if a != "--reset"]

    if args and args[0] == "history":
        _handle_history_cli(args[1:])
        return

    config = json.loads(CONFIG_PATH.read_text())
    effort = config.get("effort", "unknown")

    values = read_env()
    base_url = values.get("NIMBLE_BASE_URL") or os.environ.get("NIMBLE_BASE_URL") or DEFAULT_BASE_URL
    have_key = bool(values.get("NIMBLE_API_KEY")) and not reset

    if not have_key:
        print_intro(effort)
        api_key = get_api_key(values, base_url)
        values["NIMBLE_API_KEY"] = api_key
        values.setdefault("NIMBLE_BASE_URL", base_url)
        write_env(values)
        print(f"Saved to {ENV_PATH} (this file is gitignored — your key stays local).\n")
    else:
        api_key = values["NIMBLE_API_KEY"]

    client = TaskAgentsClient(api_key=api_key, base_url=base_url)

    have_agent = AGENT_ID_PATH.exists() and not reset
    if not have_agent:
        create_or_update(client)
    agent_id = AGENT_ID_PATH.read_text().strip()

    if args:
        question = " ".join(args)
        try:
            result = ask(client, agent_id, question, effort)
        except NimbleAgentRunCancelled:
            sys.exit(130)
        print_result(question, result)
        return

    if have_key and have_agent:
        print_intro(effort)
        print("Already set up — jumping straight in. (Run 'python agent.py --reset' to redo setup.)\n")

    agent_loop(client, agent_id, effort)

    print(
        "\nExited. Ask a question any time with:\n"
        '  python agent.py "your question here"\n\n'
        "See past questions/answers with:\n"
        "  python agent.py history\n\n"
        "Edit agent_config.json to change its domain, sources, effort, or "
        "output fields, then re-run with --reset to push the change."
    )


if __name__ == "__main__":
    main()
