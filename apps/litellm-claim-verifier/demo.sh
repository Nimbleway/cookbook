#!/usr/bin/env bash
# Demo driver. `./demo.sh` prints the architecture; `./demo.sh run` runs the verifier
# through the gateway so the calls appear at http://127.0.0.1:4111/ui → Logs.
set -euo pipefail
cd "$(dirname "$0")"

# Prefer the project venv, fall back to whatever python3 is on PATH.
PY=./.venv/bin/python
[ -x "$PY" ] || PY=python3

# Gateway mode: point at your running proxy. Unset LITELLM_BASE_URL to call the
# providers directly instead.
export LITELLM_BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000}"
export USE_LIVE="${USE_LIVE:-true}"

arch() {
  clear
  # Unquoted delimiter so ${LITELLM_BASE_URL} interpolates: the diagram must name the
  # endpoint this script actually talks to.
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
  ALL THREE CALLS LEAVE THROUGH ONE GATEWAY

        extract ──┐
        search  ──┼──▶  litellm proxy         ──▶  Anthropic Messages API
        judge   ──┘         │                └─▶  Nimble Search
                            │
                            └─▶  one ledger · one credential · /ui

     models   litellm_proxy/claim-extractor · litellm_proxy/claim-adjudicator
     search   POST /v1/search/nimble-search
     watch    ${LITELLM_BASE_URL}/ui  →  Logs

EOF
}

case "${1:-arch}" in
  arch) arch ;;
  run)
    # Only the run needs to authenticate; printing the diagram does not.
    : "${LITELLM_MASTER_KEY:?set LITELLM_MASTER_KEY, or unset LITELLM_BASE_URL to call the providers directly}"
    exec "$PY" verify.py samples/sports_draft.md --no-cache ;;
  *)    echo "usage: ./demo.sh [arch|run]" >&2; exit 2 ;;
esac
