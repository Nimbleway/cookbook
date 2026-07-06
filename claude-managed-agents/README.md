# Claude Managed Agents

Recipes for running Nimble agent-skills as **autonomous, scheduled Claude Managed Agents** —
the agent loop runs on Anthropic's platform, Nimble supplies the live web data via MCP, and the
work runs on a cron without anyone at the keyboard.

Each recipe is a self-contained template: hand the folder to a coding agent, have it follow the
`AGENTS.md` runbook to provision everything (agent, environment, vault, memory store, skill,
scheduled deployment) with the `ant` CLI, and you get a hands-off workflow.

## Recipes

| Recipe | What it does |
|---|---|
| [`competitor-intel/`](competitor-intel/) | Runs the `competitor-intel` skill weekly, dedups against persistent memory, and posts a "what's new" digest to Slack. |

## The shared pattern

1. **Skill** — a Nimble agent-skill (from [`Nimbleway/agent-skills`](https://github.com/Nimbleway/agent-skills)) uploaded as a custom Skill.
2. **Nimble MCP** — live web data (`mcp.nimbleway.com/mcp`), credential in a Vault.
3. **Memory store** — persists the skill's working memory between runs (via the `memory_*` tools).
4. **Scheduled deployment** — a cron that fires an unattended session each period.
5. **Delivery** — the result goes to Slack (bot-token Web API, or the Slack MCP with OAuth).

To adapt a recipe to a different skill, swap the skill and the profile; the rest of the pattern
carries over.
