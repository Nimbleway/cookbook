#!/usr/bin/env python3
"""Try plausible name.com username forms against dev+prod to find the 200."""
import re
from pathlib import Path

import requests

ENV = Path(__file__).resolve().parents[1] / ".env"


def parse_env(path):
    out = {}
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = re.match(r"\s*(.*?)\s*(\s#.*)?$", v).group(1)
    return out


env = parse_env(ENV)
token = env.get("NAMECOM_API_TOKEN", "").strip()
raw_user = env.get("NAMECOM_USERNAME", "").strip()

# Derive candidate account handles from whatever they put in.
local = raw_user.split("@")[0].replace("-test", "")  # 'rahimiarya05'
bases = []
for b in (local, raw_user.replace("-test", "")):
    if b and b not in bases:
        bases.append(b)

print(f"token len={len(token)} (redacted)")
print(f"candidate handles: {bases}\n")

attempts = []
for base in bases:
    attempts.append(("https://api.dev.name.com", f"{base}-test", "DEV "))
    attempts.append(("https://api.name.com", base, "PROD"))
# also the literal raw username already failed, skip re-testing it

for host, user, label in attempts:
    try:
        r = requests.get(host.rstrip("/") + "/core/v1/hello", auth=(user, token), timeout=25)
        sc, body = r.status_code, r.text[:200]
    except Exception as e:  # noqa: BLE001
        sc, body = "NET-ERR", repr(e)
    flag = "  ✅ THIS ONE" if sc == 200 else ""
    print(f"[{label}] user={user!r:42} -> HTTP {sc}{flag}")
    if sc == 200:
        print(f"        body: {body}")
