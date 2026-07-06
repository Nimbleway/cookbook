#!/usr/bin/env bash
# One-time control-plane setup. Verified against ant v1.16 (Jul 2026).
#
# Prereqs:
#   - ant authed via `ant auth login` to a workspace with the Managed Agents beta
#     (do NOT set ANTHROPIC_API_KEY in .env — a blank/stale value overrides the profile)
#   - gh CLI, python3, curl
#   - .env has NIMBLE_API_KEY + SLACK_BOT_TOKEN
#   - profile/business-profile.json exists (README Step 0)
#
# ant CLI invocation notes (see AGENTS.md "ant CLI — the invocation shapes the scripts use"):
#   vault create takes --display-name (memory-stores create takes --name); credentials take
#   --auth as a flag; skills create sends --file by basename, so we upload via curl with
#   folder-prefixed filenames; agents create takes --model (an object) and --name as flags.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
setid(){ grep -v "^$1=" .env > .env.t && mv .env.t .env; echo "$1=$2" >> .env; }
need(){ [ -n "${!1:-}" ] || { echo "ERROR: $1 not set in .env"; exit 1; }; }
need NIMBLE_API_KEY; need SLACK_BOT_TOKEN
[ -f profile/business-profile.json ] || { echo "ERROR: create profile/business-profile.json first (README Step 0)"; exit 1; }

echo "== 1. Environment (stdin YAML) =="
ENV_ID=$(ant beta:environments create < environment.yaml --transform id -r); setid ENV_ID "$ENV_ID"; echo "$ENV_ID"

echo "== 2. Vault (--display-name) =="
VAULT_ID=$(ant beta:vaults create --display-name "nimble-competitor-intel" --transform id -r); setid VAULT_ID "$VAULT_ID"; echo "$VAULT_ID"

echo "== 3. Credentials (auth object via --auth flag) =="
# Nimble: MCP bearer (the Nimble API key works as a bearer on mcp.nimbleway.com).
NIMBLE_AUTH=$(python3 -c 'import json,os;print(json.dumps({"type":"static_bearer","mcp_server_url":"https://mcp.nimbleway.com/mcp","token":os.environ["NIMBLE_API_KEY"]}))')
ant beta:vaults:credentials create --vault-id "$VAULT_ID" --display-name "Nimble MCP (competitor-intel)" --auth "$NIMBLE_AUTH" --transform id -r
# Slack (Option A, bot token): stored as an environment_variable credential, substituted at
# egress to slack.com so the agent posts via the Slack Web API. For Option B (Slack MCP + OAuth),
# skip this credential and connect Slack via OAuth in the Console instead (see AGENTS.md).
SLACK_AUTH=$(python3 -c 'import json,os;print(json.dumps({"type":"environment_variable","secret_name":"SLACK_BOT_TOKEN","secret_value":os.environ["SLACK_BOT_TOKEN"],"networking":{"type":"limited","allowed_hosts":["slack.com","*.slack.com"]},"injection_location":{"header":True}}))')
ant beta:vaults:credentials create --vault-id "$VAULT_ID" --display-name "Slack bot (competitor-intel)" --auth "$SLACK_AUTH" --transform id -r

echo "== 4. Memory store (--name; mount slug = /mnt/memory/competitor-intel-memory) =="
MEMSTORE_ID=$(ant beta:memory-stores create --name "competitor-intel-memory" \
  --description "Competitor-intel wiki: business-profile.json + memory/ (competitors, reports, synthesis, log). Dedup new findings against this." \
  --transform id -r); setid MEMSTORE_ID "$MEMSTORE_ID"; echo "$MEMSTORE_ID"

echo "== 5. Seed the profile into the store root (--content is text) =="
ant beta:memory-stores:memories create --memory-store-id "$MEMSTORE_ID" \
  --path "/business-profile.json" --content "$(cat profile/business-profile.json)" --transform id -r >/dev/null

echo "== 6. Fetch the skill from github.com/Nimbleway/agent-skills =="
REPO="Nimbleway/agent-skills"; SRC="skills/business-research/competitor-intel"
rm -rf skill/competitor-intel && mkdir -p skill/competitor-intel
gh api "repos/$REPO/git/trees/main?recursive=1" \
  -q ".tree[] | select(.type==\"blob\") | select(.path|startswith(\"$SRC/\")) | .path" \
| while read -r p; do rel="${p#"$SRC"/}"; mkdir -p "skill/competitor-intel/$(dirname "$rel")"; \
    gh api "repos/$REPO/contents/$p" -H "Accept: application/vnd.github.raw" > "skill/competitor-intel/$rel"; done

echo "== 7. Upload the skill via raw API (curl) =="
# ant beta:skills create sends --file by basename; curl lets us set folder-prefixed multipart
# filenames (competitor-intel/…) so SKILL.md lands at the top level of the skill.
TOKEN=$(ant auth print-credentials --access-token)
Fargs=(-F "display_title=nimble-competitor-intel")
while read -r f; do Fargs+=(-F "files[]=@$f;filename=${f#skill/}"); done < <(find skill/competitor-intel -type f)
SKILL_ID=$(curl -sS https://api.anthropic.com/v1/skills \
  -H "Authorization: Bearer $TOKEN" -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: skills-2025-10-02,oauth-2025-04-20" "${Fargs[@]}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin).get("id",""))')
[ -n "$SKILL_ID" ] || { echo "ERROR: skill upload failed"; exit 1; }
setid COMPETITOR_INTEL_SKILL_ID "$SKILL_ID"; echo "$SKILL_ID"

echo "== 8. Create the agent (--model as object + --name as flags; rest via stdin YAML) =="
AGENT_ID=$(envsubst '${COMPETITOR_INTEL_SKILL_ID}' < agent.yaml \
  | ant beta:agents create --model '{id: claude-opus-4-8}' --name nimble-competitor-intel --transform id -r)
[ -n "$AGENT_ID" ] || { echo "ERROR: agent create failed"; exit 1; }
setid AGENT_ID "$AGENT_ID"; echo "$AGENT_ID"

echo; echo "== DONE. IDs saved to .env =="; grep -E '_ID=' .env
echo "Next: bash scripts/10-deploy.sh"
