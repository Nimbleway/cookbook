#!/usr/bin/env python3
"""Endpoint matrix: exact creds from the page, every endpoint + headers, dev & prod."""
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
user = env["NAMECOM_USERNAME"].strip()
token = env["NAMECOM_API_TOKEN"].strip()
print(f"user={user!r}  token=len{len(token)} (redacted)\n")

DEV = "https://api.dev.name.com"
PROD = "https://api.name.com"

CALLS = [
    ("GET", DEV, "/core/v1/hello", None),
    ("GET", DEV, "/v4/hello", None),
    ("GET", DEV, "/core/v1/domains", None),
    ("GET", DEV, "/v4/domains", None),
    ("POST", DEV, "/core/v1/domains:checkAvailability", {"domainNames": ["example-xyz-123.com"], "purchaseType": "registration"}),
    ("POST", DEV, "/v4/domains:checkAvailability", {"domainNames": ["example-xyz-123.com"]}),
    # prod, same creds, to compare gateway behavior
    ("GET", PROD, "/core/v1/hello", None),
    ("GET", PROD, "/v4/hello", None),
]

s = requests.Session()
s.auth = (user, token)
s.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

for method, host, path, body in CALLS:
    url = host + path
    try:
        r = s.request(method, url, json=body, timeout=25)
        srv = r.headers.get("server", "?")
        cf = r.headers.get("cf-ray", "")
        wa = r.headers.get("www-authenticate", "")
        extra = f" server={srv}" + (f" cf-ray={cf}" if cf else "") + (f" WWW-Auth={wa!r}" if wa else "")
        print(f"{method:4} {path:38} -> {r.status_code}  {r.text[:160]!r}")
        print(f"      {extra}")
    except Exception as e:  # noqa: BLE001
        print(f"{method:4} {path:38} -> NET-ERR {type(e).__name__}: {e}")

# Sanity: does the dev host even answer WITHOUT auth (to see if 401 is gateway-wide)?
print("\n-- no-auth control (should differ from authed if creds matter) --")
for host in (DEV, PROD):
    try:
        r = requests.get(host + "/core/v1/hello", timeout=20)
        print(f"GET {host}/core/v1/hello (no auth) -> {r.status_code} {r.text[:120]!r}")
    except Exception as e:  # noqa: BLE001
        print(f"GET {host} (no auth) -> NET-ERR {e}")
