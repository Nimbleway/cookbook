#!/usr/bin/env bash
# Demo driver. `./demo.sh` prints the architecture; `./demo.sh run` runs the verifier
# through the gateway so the calls appear at http://127.0.0.1:4000/ui → Logs.
set -euo pipefail
cd "$(dirname "$0")"

# Prefer the project venv, fall back to whatever python3 is on PATH.
PY=./.venv/bin/python
[ -x "$PY" ] || PY=python3

# Gateway mode is this demo's default, because watching all three calls land on one
# ledger is the point. An UNSET LITELLM_BASE_URL therefore means "use the local proxy";
# setting it EMPTY (`LITELLM_BASE_URL= ./demo.sh run`) selects direct-provider mode,
# which needs ANTHROPIC_API_KEY + NIMBLE_API_KEY in .env and no master key.
if [ -z "${LITELLM_BASE_URL+x}" ]; then
  LITELLM_BASE_URL="http://127.0.0.1:4000"
fi
export LITELLM_BASE_URL
export USE_LIVE="${USE_LIVE:-true}"

# The diagram must describe the transport this run actually uses, not the default one.
if [ -n "$LITELLM_BASE_URL" ]; then
  TRANSPORT="  ALL THREE CALLS LEAVE THROUGH ONE GATEWAY

        extract ──┐
        search  ──┼──▶  litellm proxy         ──▶  Anthropic Messages API
        judge   ──┘         │                └─▶  Nimble Search
                            │
                            └─▶  one ledger · one credential · /ui

     models   litellm_proxy/claim-extractor · litellm_proxy/claim-adjudicator
     search   POST /v1/search/nimble-search
     watch    ${LITELLM_BASE_URL}/ui  →  Logs"
else
  TRANSPORT="  DIRECT MODE — NO GATEWAY (LITELLM_BASE_URL is empty)

        extract ──┐
        search  ──┼──▶  Anthropic Messages API
        judge   ──┘  └─▶  Nimble Search

     models   anthropic/claude-haiku-4-5 · anthropic/claude-opus-5
     search   litellm.asearch(custom_llm_provider=\"nimble\")
     keys     ANTHROPIC_API_KEY + NIMBLE_API_KEY from .env
     watch    console output only — set LITELLM_BASE_URL to get one ledger and /ui"
fi

arch() {
  clear
  # Unquoted delimiter so ${TRANSPORT} interpolates: the diagram must describe the
  # transport this script actually uses.
  cat <<EOF

  CLAIM VERIFIER — document in, per-claim verdicts out
  ═══════════════════════════════════════════════════════════════════════════

   samples/sports_draft.md
            │
            ▼
   ┌──────────────────┐   1. EXTRACT        claim-extractor
   │  extract.py      │   ─────────────     claude-haiku-4-5
   │                  │   pull every checkable claim, drop opinion
   └────────┬─────────┘   → [Claim{id, text, kind, time_sensitive}]
            │
            ▼
   ┌──────────────────┐   2. RETRIEVE       nimble-search
   │  retrieve.py     │   ─────────────     one query per claim, concurrent
   │                  │   full-page markdown → claim-relevant window
   └────────┬─────────┘   → [Evidence{url, title, text, date}]
            │
            ▼
   ┌──────────────────┐   3. ADJUDICATE     claim-adjudicator
   │  adjudicate.py   │   ─────────────     claude-opus-5
   │                  │   supported │ contradicted │ unverifiable + citation
   └────────┬─────────┘   → [Verdict{status, rationale, correction}]
            │
            ▼
   report.html · report.md          cheap model extracts, strong model judges

  ═══════════════════════════════════════════════════════════════════════════
${TRANSPORT}

EOF
}

case "${1:-arch}" in
  arch) arch ;;
  run)
    # Only a gateway run needs the proxy credential; direct mode uses the provider keys
    # in .env, and printing the diagram needs neither.
    if [ -n "$LITELLM_BASE_URL" ]; then
      : "${LITELLM_MASTER_KEY:?set LITELLM_MASTER_KEY, or run \`LITELLM_BASE_URL= ./demo.sh run\` to call the providers directly}"
    fi
    exec "$PY" verify.py samples/sports_draft.md --no-cache ;;
  *)    echo "usage: ./demo.sh [arch|run]" >&2; exit 2 ;;
esac
