#!/usr/bin/env bash
#
# One-command local dev: boots the Python agent bridge (FastAPI/uvicorn) and the
# SvelteKit web server together, waits for the bridge to be healthy, and tears
# both down cleanly on Ctrl+C.
#
#   ./scripts/dev.sh
#
# Then open the web URL it prints (default http://localhost:5173).
#
# Env overrides:
#   BRIDGE_PORT   bridge port           (default 8787)
#   WEB_PORT      web dev server port   (default 5173)
#
set -euo pipefail

# Resolve repo root regardless of where the script is invoked from.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRIDGE_PORT="${BRIDGE_PORT:-8787}"
WEB_PORT="${WEB_PORT:-5173}"
VENV_PY="$ROOT/agent/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "error: python venv not found at agent/.venv — create it first:" >&2
  echo "  python3 -m venv agent/.venv && agent/.venv/bin/pip install -r agent/requirements.txt" >&2
  exit 1
fi
if [[ ! -d "$ROOT/web/node_modules" ]]; then
  echo "error: web deps not installed — run: (cd web && npm install)" >&2
  exit 1
fi

pids=()
cleanup() {
  echo
  echo "shutting down..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "→ starting agent bridge on :$BRIDGE_PORT"
"$VENV_PY" -m uvicorn agent.server:app --host 127.0.0.1 --port "$BRIDGE_PORT" &
pids+=($!)

# Wait for the bridge to answer /health before starting the web server.
echo -n "→ waiting for bridge"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$BRIDGE_PORT/health" >/dev/null 2>&1; then
    echo " — up"
    break
  fi
  echo -n "."
  sleep 1
done
if ! curl -sf "http://127.0.0.1:$BRIDGE_PORT/health" >/dev/null 2>&1; then
  echo
  echo "error: bridge never became healthy on :$BRIDGE_PORT" >&2
  exit 1
fi

# The web server's proxy targets AGENT_URL; point it at the bridge we just booted.
export AGENT_URL="http://127.0.0.1:$BRIDGE_PORT"

echo "→ starting web on :$WEB_PORT  (proxying to $AGENT_URL)"
( cd web && npm run dev -- --port "$WEB_PORT" ) &
pids+=($!)

echo
echo "ready:"
echo "  web     http://localhost:$WEB_PORT"
echo "  bridge  http://127.0.0.1:$BRIDGE_PORT  (/health /deliver /deliver/stream)"
echo "  Ctrl+C to stop both."
echo

# Block until either child exits (or the user hits Ctrl+C).
wait -n
