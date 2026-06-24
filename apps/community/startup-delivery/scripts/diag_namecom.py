#!/usr/bin/env python3
"""Standalone name.com auth probe — zero deps beyond `requests`.

Parses .env raw (no python-dotenv), shows EXACTLY what each var resolves to,
flags inline-comment contamination, then hits the live API against BOTH the
dev and prod hosts so we can isolate cred-vs-environment-vs-url problems.
"""
import re
import sys
from pathlib import Path

import requests

ENV = Path(__file__).resolve().parents[1] / ".env"


def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v  # keep raw RHS, including any trailing comment/space
    return out


def split_comment(raw: str) -> tuple[str, str | None]:
    """Mimic the SAFE interpretation: value is up to first ' #', stripped."""
    m = re.match(r"\s*(.*?)\s*(\s#.*)?$", raw)
    return (m.group(1) if m else raw.strip()), (m.group(2) if m and m.group(2) else None)


def mask(v: str) -> str:
    v = v.strip()
    return f"len={len(v)} (redacted)"


def hello(base: str, user: str, token: str):
    url = base.rstrip("/") + "/core/v1/hello"
    try:
        r = requests.get(url, auth=(user, token), timeout=25)
        return r.status_code, r.text[:400]
    except Exception as e:  # noqa: BLE001
        return "NET-ERR", f"{type(e).__name__}: {e}"


def main() -> int:
    if not ENV.exists():
        print(f"!! no .env at {ENV}")
        return 2
    env = parse_env(ENV)

    user_raw = env.get("NAMECOM_USERNAME", "")
    token_raw = env.get("NAMECOM_API_TOKEN", "")
    base_raw = env.get("NAMECOM_API_BASE", "")

    user, ucmt = split_comment(user_raw)
    token, tcmt = split_comment(token_raw)
    base, bcmt = split_comment(base_raw)

    print("=== .env values (raw) ===")
    print(f"NAMECOM_USERNAME  raw={user_raw!r}")
    print(f"NAMECOM_API_TOKEN {mask(token_raw)}")
    print(f"NAMECOM_API_BASE  raw={base_raw!r}")
    print()
    print("=== resolved (comment/space stripped) ===")
    print(f"username = {user!r}   ends_with_-test={user.endswith('-test')}")
    print(f"token    = {mask(token)}")
    print(f"base     = {base!r}")
    for name, cmt in (("USERNAME", ucmt), ("TOKEN", tcmt), ("BASE", bcmt)):
        if cmt:
            print(f"  ⚠️  {name} has trailing junk after the value: {cmt!r}")
    print()

    if not user or not token:
        print("!! username or token empty — fill them in .env")
        return 2

    print("=== live /core/v1/hello (basic auth = username:token) ===")
    for label, host in (("DEV ", "https://api.dev.name.com"), ("PROD", "https://api.name.com")):
        sc, body = hello(host, user, token)
        print(f"[{label}] {host}  ->  HTTP {sc}")
        print(f"        {body!r}")
    print()
    print("Read the two results above:")
    print("  • One returns 200 -> creds are VALID for that environment; set NAMECOM_API_BASE to it.")
    print("  • DEV 401/403 but PROD 200 -> you have a PRODUCTION token; drop '-test' + use prod host.")
    print("  • Both 401 -> token typo/extra space, or token not yet active (~15 min after creating).")
    print("  • NET-ERR -> sandboxed network; re-run this script yourself in a normal terminal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
