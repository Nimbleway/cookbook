"""name.com = the reality check (Step 3) — THE load-bearing integration.

Uses Core API v1 (preferred) with legacy v4 fallback.
Test env: https://api.dev.name.com + username suffixed `-test` + sandbox token.
"""
from __future__ import annotations

import os
import random
import time
from typing import Any

import requests
from dotenv import load_dotenv

import json as _json

from .._env import env_int
from ..schemas import DomainOption, NameCandidate
from ._cache import cached_json

load_dotenv()

CORE_PATH = "/core/v1/domains:checkAvailability"
V4_PATH = "/v4/domains:checkAvailability"
# name.com's own suggestion engine: streams alternative TLDs/variants for a keyword.
SEARCH_STREAM_PATH = "/v4/domains:searchStream"


class NameComError(RuntimeError):
    pass


def _base_url() -> str:
    return os.environ.get("NAMECOM_API_BASE", "https://api.dev.name.com").rstrip("/")


def _credentials() -> tuple[str, str]:
    username = os.environ.get("NAMECOM_USERNAME", "").strip()
    token = os.environ.get("NAMECOM_API_TOKEN", "").strip()
    if not username or not token:
        raise NameComError("NAMECOM_USERNAME and NAMECOM_API_TOKEN must be set in .env")
    return username, token


def _session() -> requests.Session:
    username, token = _credentials()
    session = requests.Session()
    session.auth = (username, token)
    session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
    return session


# What we extract per domain from name.com: (purchasable, price, renewal_price, premium).
DomainStatus = tuple[bool, float | None, float | None, bool]

# Availability TTL: domains change hands fast enough that a permanently-pinned cache
# would eventually serve a lie ("available" for a name someone just registered), but
# the free quota is small — so re-check at most a couple times a day. 12h is the
# balance: fresh enough to be honest, cheap enough not to burn the quota on reruns.
# Overridable via NAMECOM_CACHE_TTL_SECONDS for the demo/tests.
_AVAILABILITY_TTL_SECONDS = env_int("NAMECOM_CACHE_TTL_SECONDS", 12 * 3600)

# name.com standard registrations sit well under this; premium/aftermarket names
# (e.g. a $2,500 .com) sit far above. Used as a fallback premium signal when the
# API doesn't return an explicit purchaseType.
_PREMIUM_PRICE_FLOOR = 100.0


def _parse_results(payload: dict[str, Any]) -> dict[str, DomainStatus]:
    """Normalize Core v1 / v4 checkAvailability payloads.

    Surfaces the full pricing truth name.com returns: first-year price, the
    separate renewal price, and whether the name is premium/aftermarket (priced
    far above a standard registration) — so the UI can flag the premium trap.
    """
    rows = payload.get("results")
    if rows is None and isinstance(payload.get("domains"), list):
        rows = payload["domains"]
    if not isinstance(rows, list):
        raise NameComError(f"Unexpected name.com response shape: {list(payload.keys())}")

    out: dict[str, DomainStatus] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        domain = (row.get("domainName") or row.get("domain") or "").lower()
        if not domain:
            continue
        purchasable = bool(row.get("purchasable", False))
        price_raw = row.get("purchasePrice")
        price = float(price_raw) if price_raw is not None else None
        renewal_raw = row.get("renewalPrice")
        renewal = float(renewal_raw) if renewal_raw is not None else None
        purchase_type = str(row.get("purchaseType") or "").strip().lower()
        premium = bool(row.get("premium")) or purchase_type in {"premium", "aftermarket"}
        if not premium and price is not None and price >= _PREMIUM_PRICE_FLOOR:
            premium = True
        out[domain] = (purchasable, price, renewal, premium)
    return out


# Transient HTTP statuses worth retrying (rate limit + upstream wobble). Mirrors
# nimble.py's resilience: the name.com check is the load-bearing step, so a single
# 429/5xx or a dropped connection must not sink the whole delivery.
_RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with jitter: ~0.4s, ~0.8s, ~1.6s (+/- jitter)."""
    return (0.4 * (2 ** attempt)) + random.uniform(0, 0.3)


def _post_check(session: requests.Session, path: str, domains: list[str]) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    body: dict[str, Any] = {"domainNames": domains}
    if path.startswith("/core/"):
        body["purchaseType"] = "registration"

    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = session.post(url, json=body, timeout=30)
        except requests.RequestException as exc:  # timeout / connection reset
            last_error = exc
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_backoff_seconds(attempt))
                continue
            raise NameComError(f"name.com request failed after retries: {exc}") from exc

        # Retry transient statuses before treating them as fatal.
        if response.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS - 1:
            time.sleep(_backoff_seconds(attempt))
            continue

        if response.status_code == 401:
            raise NameComError(
                "name.com Unauthorized — use sandbox token + username-test on api.dev.name.com "
                "(https://www.name.com/account/settings/api). New tokens can take ~15 min."
            )
        if response.status_code == 403:
            raise NameComError(
                "name.com Permission Denied — likely prod token on dev host (or vice versa). "
                "Match Development/Test token with api.dev.name.com and *-test username."
            )
        if not response.ok:
            raise NameComError(f"name.com HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        if not isinstance(data, dict):
            raise NameComError("name.com returned non-object JSON")
        return data

    # Loop only falls through here if every attempt hit a retryable status.
    raise NameComError(
        f"name.com unavailable after {_MAX_ATTEMPTS} attempts"
        + (f": {last_error}" if last_error else " (transient errors)")
    )


def check_domains(domains: list[str], *, use_cache: bool = True) -> dict[str, DomainStatus]:
    """Batch availability + price (+ renewal + premium flag) for up to 50 domains."""
    cleaned = [d.strip().lower() for d in domains if d.strip()]
    if not cleaned:
        return {}
    if len(cleaned) > 50:
        raise ValueError("name.com supports at most 50 domains per request")

    # v2 key: the cached value shape changed (4-tuple), so bust the old 2-tuple cache.
    cache_key = f"namecom:v2:{_base_url()}:{','.join(sorted(cleaned))}"

    def fetch() -> dict[str, DomainStatus]:
        session = _session()
        try:
            payload = _post_check(session, CORE_PATH, cleaned)
        except NameComError as core_err:
            if "HTTP 404" in str(core_err) or "HTTP 405" in str(core_err):
                payload = _post_check(session, V4_PATH, cleaned)
            else:
                # v4 often returns 403 when creds are wrong; try anyway for older accounts
                try:
                    payload = _post_check(session, V4_PATH, cleaned)
                except NameComError:
                    raise core_err from None
        return _parse_results(payload)

    # force=True bypasses the cached read for a live check but still writes the
    # fresh result back (so the on-camera demo can recompute without going stale).
    # max_age_seconds expires a stale availability entry so "available" never
    # silently means "available 3 weeks ago".
    return cached_json(
        cache_key, fetch, force=not use_cache, max_age_seconds=_AVAILABILITY_TTL_SECONDS
    )


def check_domain(candidate: NameCandidate, *, use_cache: bool = True) -> NameCandidate:
    """Set candidate.available + candidate.price_usd from name.com."""
    results = check_domains([candidate.domain], use_cache=use_cache)
    available, price, _renewal, _premium = results.get(candidate.domain.lower(), (False, None, None, False))
    return candidate.model_copy(update={"available": available, "price_usd": price})


def suggest_domains(
    keyword: str, *, max_results: int = 9, timeout_ms: int = 3000, use_cache: bool = True
) -> list[DomainOption]:
    """name.com's OWN suggestions for a keyword (alternative TLDs + variants).

    Uses the v4 searchStream endpoint (the agent's check uses checkAvailability;
    this uses name.com as an active *suggester*). Best-effort: any failure returns
    an empty list so a flaky suggestion call never sinks a delivery.
    """
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return []
    cache_key = f"namecom:suggest:v1:{_base_url()}:{keyword}"

    def fetch() -> list[dict[str, Any]]:
        session = _session()
        url = f"{_base_url()}{SEARCH_STREAM_PATH}"
        rows: list[dict[str, Any]] = []
        try:
            with session.post(
                url, json={"keyword": keyword, "timeout": timeout_ms}, timeout=20, stream=True
            ) as resp:
                if not resp.ok:
                    return []
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        obj = _json.loads(line.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if isinstance(obj, dict) and obj.get("purchasable") and obj.get("domainName"):
                        rows.append(obj)
        except requests.RequestException:
            return []
        return rows

    try:
        rows = cached_json(
            cache_key, fetch, force=not use_cache, max_age_seconds=_AVAILABILITY_TTL_SECONDS
        )
    except Exception:
        return []

    options: list[DomainOption] = []
    seen: set[str] = set()
    for obj in rows:
        domain = str(obj.get("domainName", "")).lower()
        if not domain or domain in seen:
            continue
        seen.add(domain)
        price = obj.get("purchasePrice")
        renewal = obj.get("renewalPrice")
        ptype = str(obj.get("purchaseType") or "").lower()
        premium = ptype in {"premium", "aftermarket"} or (
            isinstance(price, (int, float)) and price >= _PREMIUM_PRICE_FLOOR
        )
        options.append(
            DomainOption(
                domain=domain,
                tld=str(obj.get("tld", domain.rsplit(".", 1)[-1])),
                available=True,
                price_usd=float(price) if price is not None else None,
                renewal_price_usd=float(renewal) if renewal is not None else None,
                premium=bool(premium),
            )
        )

    # Cheapest first; standard registrations before premium. Cap the list.
    options.sort(key=lambda o: (o.premium, o.price_usd if o.price_usd is not None else 9_999))
    return options[:max_results]


# ---------------------------------------------------------------------------
# Boot CONTROL-CHECK: is the name.com we're pointed at TELLING THE TRUTH?
#
# The sandbox (api.dev.name.com) cheerfully reports registered companies
# (google.com, vetted.com, concur.com) as buyable for ~$13. That is a
# credibility-ending lie if it ever shows up as "live availability" in the UI.
# This control-check probes a KNOWN-TAKEN control domain (google.com) and a
# KNOWN-OPEN nonsense domain, classifies the environment, and caches the verdict
# in-memory so the cheap /health and /debug handlers can read it with zero I/O.
#
# It is BEST-EFFORT and must NEVER raise: any failure classifies as "unverified".
# ---------------------------------------------------------------------------

# Household-name domains that are unquestionably registered on the real registry.
# If a backend reports ANY of them as purchasable, it is not real-world truth.
# A basket (not a single domain) because the sandbox's behavior drifts — it may
# report one of these as taken yet still sell another registered company's domain.
_CONTROL_TAKEN_DOMAINS = ("google.com", "facebook.com", "amazon.com", "apple.com")

# A long random-looking label nobody has registered. On a TRUTHFUL backend this
# comes back available; pairing it with the taken basket distinguishes
# "production telling the truth" from "everything looks taken / errored".
_CONTROL_OPEN_DOMAIN = "zqxw7n3k9plv2mtq8rhd4f6bjs1delivery.com"

# Module-level in-memory verdict cache. Populated once at boot (see
# run_control_check); read by domain_source_status() and the /health, /debug
# handlers. Never persisted, never contains secrets — only base url + verdict.
_DOMAIN_SOURCE_STATUS: dict[str, Any] | None = None


def _safe_status(env: str, *, trustworthy: bool, detail: str, checked_at: str | None) -> dict[str, Any]:
    """Shape the SHARED CONTRACT object (matched by the frontend badge)."""
    return {
        "env": env,
        "base": _base_url(),
        "trustworthy": trustworthy,
        "detail": detail,
        "checkedAt": checked_at,
    }


def _sandbox_config_signal() -> tuple[bool, str]:
    """Deterministic sandbox signal from CONFIG alone (no network).

    The name.com test environment is the host ``api.dev.name.com`` with a username
    suffixed ``-test``. Either is a definitive sandbox marker, and we trust it OVER
    any live probe: the sandbox's per-domain behavior drifts (it may report
    google.com as taken one day) while STILL selling a real registered company's
    domain — so a probe alone can be fooled, but the host/username cannot. We never
    classify a dev host as trustworthy production.
    """
    base = _base_url().lower()
    username = os.environ.get("NAMECOM_USERNAME", "").strip().lower()
    if "dev.name.com" in base:
        return True, "NAMECOM_API_BASE points at the name.com sandbox (api.dev.name.com)"
    if username.endswith("-test"):
        return True, "NAMECOM_USERNAME is a -test sandbox account"
    return False, ""


def run_control_check() -> dict[str, Any]:
    """Best-effort: classify the configured name.com backend and cache the verdict.

    Classification (per the SHARED CONTRACT), in priority order:
      - dev host / -test username           -> env="sandbox",      trustworthy=false (config signal, beats any probe)
      - creds missing                       -> env="unconfigured", trustworthy=false
      - call errors / times out             -> env="unverified",   trustworthy=false
      - prod host sells a known-taken brand -> env="sandbox",      trustworthy=false (lying backend)
      - known-taken all TAKEN + open avail  -> env="production",   trustworthy=true
      - anything else                       -> env="unverified",   trustworthy=false

    NEVER raises. Stores the result in the module-level cache and returns it.
    The live probe uses use_cache=False so a poisoned disk cache can't mask it.
    """
    global _DOMAIN_SOURCE_STATUS
    from datetime import datetime, timezone

    checked_at = datetime.now(timezone.utc).isoformat()

    # 1) CONFIG signal first. The sandbox host/username is a hard, deterministic
    #    sandbox marker — never classify a dev host as trustworthy production, even
    #    if a live probe happens to look correct (the sandbox's behavior drifts).
    is_sandbox, why = _sandbox_config_signal()
    if is_sandbox:
        status = _safe_status(
            "sandbox",
            trustworthy=False,
            detail=f"{why} — prices are NOT real-world availability",
            checked_at=checked_at,
        )
        _DOMAIN_SOURCE_STATUS = status
        return status

    # 2) Creds absent => unconfigured (don't even attempt a call).
    try:
        _credentials()
    except NameComError:
        status = _safe_status(
            "unconfigured",
            trustworthy=False,
            detail="NAMECOM_USERNAME / NAMECOM_API_TOKEN not set",
            checked_at=checked_at,
        )
        _DOMAIN_SOURCE_STATUS = status
        return status

    # 3) Live probe (prod host + real creds): a basket of always-registered brands
    #    plus the open nonsense control, in one call.
    probe = list(_CONTROL_TAKEN_DOMAINS) + [_CONTROL_OPEN_DOMAIN]
    try:
        results = check_domains(probe, use_cache=False)
    except Exception as exc:  # any error/timeout => unverified, never fatal
        status = _safe_status(
            "unverified",
            trustworthy=False,
            detail=f"control-check could not reach name.com: {exc!r}"[:200],
            checked_at=checked_at,
        )
        _DOMAIN_SOURCE_STATUS = status
        return status

    sold_brands = [d for d in _CONTROL_TAKEN_DOMAINS if bool(results.get(d, (False,))[0])]
    open_available = bool(results.get(_CONTROL_OPEN_DOMAIN, (False,))[0])

    # THE BUG WE ARE CATCHING: a backend selling a registered company's domain is
    # not real-world truth — even on the prod host.
    if sold_brands:
        status = _safe_status(
            "sandbox",
            trustworthy=False,
            detail=(
                "backend reported registered domains as purchasable ("
                + ", ".join(sold_brands)
                + ") — NOT real availability"
            ),
            checked_at=checked_at,
        )
    elif open_available:
        status = _safe_status(
            "production",
            trustworthy=True,
            detail=(
                "known-taken control domains correctly taken and an open control is "
                "available — live availability is trustworthy"
            ),
            checked_at=checked_at,
        )
    else:
        status = _safe_status(
            "unverified",
            trustworthy=False,
            detail=f"control-check inconclusive (open_available={open_available})",
            checked_at=checked_at,
        )

    _DOMAIN_SOURCE_STATUS = status
    return status


def domain_source_status() -> dict[str, Any]:
    """Return the cached control-check verdict (SHARED CONTRACT shape).

    Safe to call from a cheap request handler: pure in-memory read, no I/O. Before
    the boot control-check has run, returns a safe default with env="unverified"
    and checkedAt=null so callers always get the full contract shape.
    """
    if _DOMAIN_SOURCE_STATUS is None:
        return _safe_status(
            "unverified",
            trustworthy=False,
            detail="control-check has not run yet",
            checked_at=None,
        )
    # Refresh `base` from the live env each read so a mid-process base change is
    # reflected even if the cached verdict predates it (cheap, no I/O).
    out = dict(_DOMAIN_SOURCE_STATUS)
    out["base"] = _base_url()
    return out


def verify_auth() -> None:
    """Verify credentials against a real API endpoint (not the public HTML landing page).

    Note: GET https://api.dev.name.com/ (no path) returns 200 HTML without auth — that is NOT
    a successful API login. Only JSON endpoints count.
    """
    session = _session()
    hello = session.get(f"{_base_url()}/core/v1/hello", timeout=20)
    if hello.status_code == 200:
        return

    # Fall back to the endpoint we actually need for the product.
    try:
        check_domains(["google.com"], use_cache=False)
        return
    except NameComError:
        pass

    if hello.status_code == 401:
        raise NameComError(
            "Core API auth failed (401 Unauthorized). Your username/token are rejected by "
            "api.dev.name.com. If 2FA is on: Account Settings → Security → enable "
            "'API Access'. Regenerate the Development/Test token, wait ~15 min, retry. "
            "Hitting https://api.dev.name.com/ without a path only returns public HTML."
        )
    if hello.status_code == 403:
        raise NameComError("Auth failed (403). Token/environment mismatch.")
    raise NameComError(f"Auth check failed: HTTP {hello.status_code} {hello.text[:200]}")


if __name__ == "__main__":
    import json
    import sys

    test_domains = sys.argv[1:] or ["google.com", "freshpawsxyz123.app", "startupdeliverytest999.io"]
    print(f"Base: {_base_url()}")
    print(f"User: {_credentials()[0]}")
    verify_auth()
    print("Auth: OK")
    results = check_domains(test_domains, use_cache=False)
    print(
        json.dumps(
            {
                d: {
                    "available": available,
                    "price_usd": price,
                    "renewal_price_usd": renewal,
                    "premium": premium,
                }
                for d, (available, price, renewal, premium) in results.items()
            },
            indent=2,
        )
    )
