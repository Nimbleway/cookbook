#!/usr/bin/env python3
"""Deploy a multi-statement SQL file to a Databricks SQL warehouse.

The Statement Execution API (POST /api/2.0/sql/statements) accepts one
statement per call. SQL files in this cookbook contain multiple
statements and rich function COMMENTs that include `;` inside string
literals, so a naive `;`-split corrupts them. This helper strips
comments, splits while respecting `'...'` string literals (including
the `''` escape), and posts each statement in order.

Usage
-----
    python databricks/helpers/deploy_sql.py \\
        --file databricks/01_setup.sql \\
        --warehouse <warehouse-id>             # default profile

    python databricks/helpers/deploy_sql.py \\
        --file databricks/tools/amazon_serp.sql \\
        --warehouse <warehouse-id> \\
        --profile my-profile

Deploy a whole directory in one shot:

    for f in databricks/01_setup.sql databricks/tools/*.sql; do
        python databricks/helpers/deploy_sql.py --file "$f" --warehouse "$WH"
    done

Requirements: Python 3.9+, the `databricks` CLI on $PATH and
authenticated (`databricks auth login --profile <name>`). No third-party
Python packages are imported.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import List


def strip_comments(text: str) -> str:
    """Remove /* ... */ block comments and -- line comments, but leave
    string literals untouched (the SQL function COMMENT strings can
    legitimately contain `--`)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    out: List[str] = []
    in_str = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == "'":
            # SQL `''` is an escaped apostrophe inside a string literal.
            if in_str and i + 1 < len(text) and text[i + 1] == "'":
                out.append("''")
                i += 2
                continue
            in_str = not in_str
            out.append(c)
        elif not in_str and c == "-" and i + 1 < len(text) and text[i + 1] == "-":
            # Skip to end of line.
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def split_statements(text: str) -> List[str]:
    """Split on `;` while honoring `'...'` string literals (with `''`
    escapes). Returns non-empty, whitespace-stripped statements."""
    out: List[str] = []
    cur: List[str] = []
    in_str = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == "'":
            if in_str and i + 1 < len(text) and text[i + 1] == "'":
                cur.append("''")
                i += 2
                continue
            in_str = not in_str
            cur.append(c)
        elif c == ";" and not in_str:
            s = "".join(cur).strip()
            if s:
                out.append(s)
            cur = []
        else:
            cur.append(c)
        i += 1
    last = "".join(cur).strip()
    if last:
        out.append(last)
    return out


def run_statement(
    statement: str,
    warehouse_id: str,
    profile: str | None,
    wait_timeout: str = "50s",
) -> dict:
    """POST one statement to /api/2.0/sql/statements via the CLI and
    return the parsed JSON response. Raises on non-zero CLI exit."""
    payload = json.dumps(
        {
            "warehouse_id": warehouse_id,
            "statement": statement,
            "wait_timeout": wait_timeout,
        }
    )
    cmd = ["databricks"]
    if profile:
        cmd += ["--profile", profile]
    cmd += ["api", "post", "/api/2.0/sql/statements", "--json", payload]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"databricks CLI exited {result.returncode}: {result.stderr.strip()}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"non-JSON response from CLI: {e}\n{result.stdout[:500]}")


def deploy(
    sql_path: str,
    warehouse_id: str,
    profile: str | None = None,
    wait_timeout: str = "50s",
) -> int:
    """Read sql_path, split, post each statement. Returns the number of
    statements run on success; raises on any FAILED/CANCELED state."""
    with open(sql_path, encoding="utf-8") as fh:
        raw = fh.read()
    stmts = split_statements(strip_comments(raw))
    print(f"{sql_path}: {len(stmts)} statement(s)")
    for idx, stmt in enumerate(stmts, 1):
        head = re.sub(r"\s+", " ", stmt)[:80]
        response = run_statement(stmt, warehouse_id, profile, wait_timeout)
        status = response.get("status", {})
        state = status.get("state", "?")
        if state != "SUCCEEDED":
            err = status.get("error", {}).get("message", "")
            raise RuntimeError(
                f"statement {idx}/{len(stmts)} failed [{state}]: {err}\n"
                f"  statement head: {head}"
            )
        print(f"  [{idx}/{len(stmts)}] {state}  {head}")
    return len(stmts)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--file", "-f", required=True, help="Path to .sql file")
    p.add_argument(
        "--warehouse",
        "-w",
        required=True,
        help="Databricks SQL warehouse ID (databricks warehouses list)",
    )
    p.add_argument("--profile", "-p", default=None, help="Databricks CLI profile name")
    p.add_argument(
        "--wait-timeout",
        default="50s",
        help="Per-statement synchronous wait (5s-50s). Default 50s.",
    )
    args = p.parse_args()
    try:
        deploy(args.file, args.warehouse, args.profile, args.wait_timeout)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
