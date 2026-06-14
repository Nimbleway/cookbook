#!/usr/bin/env python3
"""Create a Databricks AI/BI Genie space via the workspace REST API.

The public Genie API exposes POST /api/2.0/genie/spaces, but the body
requires a stringified `serialized_space` JSON whose schema is not
documented externally. This helper builds a minimal valid v2 space from
a list of SQL function identifiers, a list of optional UC table
identifiers, and a markdown instructions string, then posts it.

Discovery of the schema:
    - `databricks api patch /api/2.0/genie/spaces/<id> --json '{}'`
      returns the full `serialized_space` of an existing space (acts as
      the de-facto export endpoint — there is no GET /export).
    - `version: 2` is the current accepted format. Mismatch produces
      "The export format has changed since this export was taken."
    - Every `sql_function` and `text_instruction` entry needs an `id`
      field — a lowercase 32-hex UUID with no hyphens.

Usage
-----
    python databricks/helpers/create_genie_space.py \\
        --title "Nimble Web Data" \\
        --warehouse <warehouse-id> \\
        --parent-path "/Users/<you>@<domain>" \\
        --instructions-file path/to/instructions.md \\
        --function nimble_integration.tools.nimble_search \\
        --function nimble_integration.tools.nimble_extract \\
        --function nimble_integration.tools.nimble_agent_list \\
        --function nimble_integration.tools.nimble_agent_describe \\
        --function nimble_integration.tools.nimble_agent_run

Requirements: Python 3.9+, the `databricks` CLI on $PATH and
authenticated.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import List


def hex_id() -> str:
    """32-hex lowercase UUID with no hyphens — the format Genie expects."""
    return uuid.uuid4().hex


def split_instructions(text: str) -> List[str]:
    """Genie stores text_instructions[].content as an array of lines, each
    ending in `\\n`. Mirror that to keep the export round-trippable."""
    return [line + "\n" for line in text.splitlines()]


def build_serialized_space(
    instructions_text: str,
    sql_function_idents: List[str],
    table_idents: List[str],
) -> dict:
    return {
        "version": 2,
        "data_sources": {
            "tables": [{"identifier": ident} for ident in table_idents],
        },
        "instructions": {
            "text_instructions": [
                {
                    "id": hex_id(),
                    "content": split_instructions(instructions_text),
                },
            ],
            # Genie enforces sql_functions be sorted by (id, identifier);
            # assign hex ids then sort before emitting.
            "sql_functions": sorted(
                [
                    {"id": hex_id(), "identifier": ident}
                    for ident in sql_function_idents
                ],
                key=lambda f: (f["id"], f["identifier"]),
            ),
        },
    }


def create_space(
    title: str,
    warehouse_id: str,
    parent_path: str,
    serialized_space: dict,
    profile: str | None = None,
) -> dict:
    body = {
        "title": title,
        "warehouse_id": warehouse_id,
        "parent_path": parent_path,
        "serialized_space": json.dumps(serialized_space),
    }
    cmd = ["databricks"]
    if profile:
        cmd += ["--profile", profile]
    cmd += ["api", "post", "/api/2.0/genie/spaces", "--json", json.dumps(body)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        raise SystemExit(res.returncode)
    return json.loads(res.stdout)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--title", required=True)
    ap.add_argument("--warehouse", required=True, help="SQL warehouse id")
    ap.add_argument("--parent-path", required=True,
                    help='Workspace folder, e.g. "/Users/you@example.com"')
    ap.add_argument("--instructions-file", required=True, type=Path,
                    help="Markdown file with the Genie system prompt")
    ap.add_argument("--function", action="append", default=[],
                    metavar="catalog.schema.func",
                    help="UC SQL function identifier (TABLE-returning). "
                         "Repeat per function.")
    ap.add_argument("--table", action="append", default=[],
                    metavar="catalog.schema.table",
                    help="UC table identifier to register as a data source. "
                         "Repeat per table. Optional.")
    ap.add_argument("--profile", help="Databricks CLI profile name (optional)")
    args = ap.parse_args()

    instructions_text = args.instructions_file.read_text()
    serialized = build_serialized_space(
        instructions_text=instructions_text,
        sql_function_idents=args.function,
        table_idents=args.table,
    )
    result = create_space(
        title=args.title,
        warehouse_id=args.warehouse,
        parent_path=args.parent_path,
        serialized_space=serialized,
        profile=args.profile,
    )
    space_id = result.get("space_id", "<unknown>")
    print(f"Created space_id={space_id} title={args.title!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
