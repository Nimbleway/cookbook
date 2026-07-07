#!/usr/bin/env bash
# Tear down everything 00-setup/10-deploy created, in dependency order. Reads IDs from .env.
# Deleting a skill requires deleting its versions first. Confirm before running.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
echo "This will archive/delete the deployment, agent, skill, memory store, vault, and environment in this .env."
read -r -p "Proceed? [y/N] " ok; [ "$ok" = y ] || { echo "aborted"; exit 0; }

[ -n "${DEPL_ID:-}" ]     && ant beta:deployments archive --deployment-id "$DEPL_ID" 2>/dev/null && echo "archived $DEPL_ID" || true
[ -n "${AGENT_ID:-}" ]    && ant beta:agents archive --agent-id "$AGENT_ID" 2>/dev/null && echo "archived $AGENT_ID" || true
if [ -n "${COMPETITOR_INTEL_SKILL_ID:-}" ]; then
  for v in $(ant beta:skills:versions list --skill-id "$COMPETITOR_INTEL_SKILL_ID" --transform 'version' -r 2>/dev/null); do
    ant beta:skills:versions delete --skill-id "$COMPETITOR_INTEL_SKILL_ID" --version "$v" 2>/dev/null || true
  done
  ant beta:skills delete --skill-id "$COMPETITOR_INTEL_SKILL_ID" 2>/dev/null && echo "deleted skill" || true
fi
[ -n "${MEMSTORE_ID:-}" ] && ant beta:memory-stores delete --memory-store-id "$MEMSTORE_ID" 2>/dev/null && echo "deleted $MEMSTORE_ID" || true
[ -n "${VAULT_ID:-}" ]    && ant beta:vaults delete --vault-id "$VAULT_ID" 2>/dev/null && echo "deleted $VAULT_ID" || true
[ -n "${ENV_ID:-}" ]      && ant beta:environments delete --environment-id "$ENV_ID" 2>/dev/null && echo "deleted $ENV_ID" || true
echo "Teardown done. Clear the *_ID lines from .env if you plan to re-provision."
