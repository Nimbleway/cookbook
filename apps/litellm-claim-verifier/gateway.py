"""
Gateway mode: the same app, pointed at a LiteLLM proxy instead of the providers.

Off by default — the app talks straight to Anthropic and Nimble, and needs no proxy
at all. Set `LITELLM_BASE_URL` and both model calls and the search call go through
the proxy instead, which is what makes them show up in its dashboard (Logs, Usage,
Search Tools).

That switch is the whole argument for a gateway, so it is worth being precise about
what changes: nothing in the pipeline. Same prompts, same models, same search. One
credential instead of two, and one ledger to watch.

Models go through the SDK's `litellm_proxy/` prefix. Search goes over plain HTTP to
`/v1/search/<tool>`, because a gateway's contract is an HTTP endpoint any client can
call — which is also how the proxy is documented (see config.yaml).
"""

from __future__ import annotations

import os

BASE = (os.getenv("LITELLM_BASE_URL") or "").rstrip("/")
KEY = os.getenv("LITELLM_MASTER_KEY") or ""
SEARCH_TOOL = os.getenv("LITELLM_SEARCH_TOOL") or "nimble-search"

ENABLED = bool(BASE)

# Proxy-side model names, as registered in config.yaml's model_list.
ALIASES: dict[str, str] = {
    "extractor": os.getenv("LITELLM_EXTRACTOR_ALIAS") or "claim-extractor",
    "adjudicator": os.getenv("LITELLM_ADJUDICATOR_ALIAS") or "claim-adjudicator",
}


def completion_target(role: str) -> tuple[str, dict]:
    """
    (model, extra kwargs) for `litellm.completion` in gateway mode.

    `role` is "extractor" or "adjudicator" — the app's two jobs, not model names, so
    which model serves which job stays the proxy's decision.
    """
    return f"litellm_proxy/{ALIASES[role]}", {"api_base": BASE, "api_key": KEY}


def search_url() -> str:
    return f"{BASE}/v1/search/{SEARCH_TOOL}"


def describe() -> str:
    return (
        f"gateway {BASE} — models as litellm_proxy/{ALIASES['extractor']} + "
        f"litellm_proxy/{ALIASES['adjudicator']}, search via /v1/search/{SEARCH_TOOL}"
    )
