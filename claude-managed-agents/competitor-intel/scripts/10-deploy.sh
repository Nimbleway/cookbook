#!/usr/bin/env bash
# Create the weekly scheduled deployment. Verified against ant v1.16.
# ant beta:deployments create takes typed flags (not a stdin body): --agent, --environment-id,
# --vault-id, --initial-event, --resource, --schedule. Objects are passed as JSON strings.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
setid(){ grep -v "^$1=" .env > .env.t && mv .env.t .env; echo "$1=$2" >> .env; }
for v in AGENT_ID ENV_ID VAULT_ID MEMSTORE_ID; do [ -n "${!v:-}" ] || { echo "ERROR: $v missing (run 00-setup.sh)"; exit 1; }; done

DEPL_ID=$(ant beta:deployments create \
  --name "Weekly competitor digest" \
  --agent "$AGENT_ID" \
  --environment-id "$ENV_ID" \
  --vault-id "$VAULT_ID" \
  --initial-event '{"type":"user.message","content":[{"type":"text","text":"Run this weeks competitor-intel pass."}]}' \
  --resource "{\"type\":\"memory_store\",\"memory_store_id\":\"$MEMSTORE_ID\",\"access\":\"read_write\"}" \
  --schedule '{"type":"cron","expression":"0 8 * * 1","timezone":"America/New_York"}' \
  --transform id -r)
[ -n "$DEPL_ID" ] || { echo "ERROR: deployment create failed"; exit 1; }
setid DEPL_ID "$DEPL_ID"; echo "DEPL_ID=$DEPL_ID"

# Pause the schedule so you can smoke-test on demand (manual run works while paused).
ant beta:deployments pause --deployment-id "$DEPL_ID" >/dev/null 2>&1 || true
echo "Created (paused). Smoke-test now:  ant beta:deployments run --deployment-id $DEPL_ID"
echo "When happy:                        ant beta:deployments unpause --deployment-id $DEPL_ID"
