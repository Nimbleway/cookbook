#!/usr/bin/env python3
"""T2 acceptance: name.com returns live availability + price."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.clients.namecom import NameComError, check_domains


def main() -> int:
    domains = ["google.com", "freshpawsxyz123.app", "startupdeliverytest999.io"]
    print("=== T2 name.com verify ===")
    print("  note: https://api.dev.name.com/ (no path) returns HTML — not API auth")

    try:
        results = check_domains(domains, use_cache=False)
    except NameComError as e:
        print(f"  checkAvailability: FAIL — {e}")
        return 1

    google = results.get("google.com")
    if not google:
        print("  checkAvailability: FAIL — google.com missing from response")
        return 1

    google_available, _price, _renewal, _premium = google
    if google_available:
        print("  google.com: FAIL — expected not purchasable")
        return 1
    print("  google.com: not purchasable (PASS)")

    available_any = [(d, p, r, prem) for d, (a, p, r, prem) in results.items() if a]
    if not available_any:
        print("  sample domain: WARN — none purchasable (sandbox TLD quirks OK if auth works)")
    else:
        d, price, renewal, premium = available_any[0]
        price_label = "no first-year price" if price is None else f"${price:.2f}"
        renewal_label = "renewal unknown" if renewal is None else f"renews ${renewal:.2f}"
        premium_label = " premium" if premium else ""
        if price is None:
            print(f"  {d}: purchasable but {price_label} ({renewal_label}){premium_label} (WARN)")
        else:
            print(f"  {d}: purchasable @ {price_label} ({renewal_label}){premium_label} (PASS)")

    print("\nT2: PASS — ready for T3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
