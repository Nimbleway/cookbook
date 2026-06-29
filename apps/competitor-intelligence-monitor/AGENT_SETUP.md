# Agent Setup Guide

## 1. Quick setup

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/competitor-intelligence-monitor/agent
pip install -r requirements.txt
python onboard.py   # interactive wizard — fills in config.json and .env
python agent.py     # run it
```

The wizard covers everything. This doc fills in details for each step.

---

## 2. API keys

### Nimble (required — powers all web search)
1. Sign up at [nimbleway.com](https://nimbleway.com)
2. Dashboard → API Keys → Create new key
3. Paste into `.env` as `NIMBLE_API_KEY`

### Anthropic (required — runs the AI synthesis)
1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. API Keys → Create Key
3. Paste into `.env` as `ANTHROPIC_API_KEY`

### GitHub (optional — improves search rate limits)
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → Generate new token (classic)
2. No extra scopes needed
3. Paste into `.env` as `GH_API_KEY`

---

## 3. Slack

Skip this section if you don't want Slack notifications.

### Create a Slack app
1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it (e.g. "Competitor Monitor") and select your workspace

### Set permissions
In **OAuth & Permissions** → **Bot Token Scopes**, add: `chat:write`, `commands`

### Install and get tokens
1. **OAuth & Permissions** → **Install to Workspace** → Authorize
2. Copy the **Bot User OAuth Token** (starts with `xoxb-`) → paste into `.env` as `SLACK_BOT_TOKEN`
3. **Basic Information** → **App Credentials** → copy **Signing Secret** → paste as `SLACK_SIGNING_SECRET`

### Get the channel ID
1. Open the channel in Slack → right-click the channel name → **Copy channel ID**
2. Paste into `.env` as `SLACK_CHANNEL_ID`

### Invite the bot
In the channel, type: `/invite @YourBotName`

---

## 4. Automated daily runs

This runs the agent on a schedule via GitHub Actions.

### Set up the repo
1. Fork or clone this repo to your own GitHub account
2. Commit your `agent/config.json` (it has no secrets — just competitor names)
3. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
4. Add these secrets:

| Secret | Required |
|---|---|
| `NIMBLE_API_KEY` | Yes |
| `ANTHROPIC_API_KEY` | Yes |
| `SLACK_BOT_TOKEN` | If using Slack |
| `SLACK_CHANNEL_ID` | If using Slack |
| `GH_API_KEY` | Optional |

### Schedule with cron-job.org (free, reliable)
GitHub's built-in schedule runs hours late. Use [cron-job.org](https://cron-job.org) instead:

1. Sign up → New cron job
2. URL: `https://api.github.com/repos/{owner}/{repo}/actions/workflows/daily_monitor.yml/dispatches`
3. Method: `POST`
4. Headers:
   - `Authorization: Bearer {your_github_token}`
   - `Accept: application/vnd.github.v3+json`
5. Body: `{"ref": "main"}`
6. Schedule: e.g. `0 9 * * 1-5` (9am UTC weekdays)

The GitHub token needs `workflow` scope. Create one at [github.com/settings/tokens](https://github.com/settings/tokens).

---

## Troubleshooting

- **Agent posts nothing to Slack** — confirm the bot is invited to the channel (`/invite @BotName`) and `SLACK_CHANNEL_ID` is the ID (e.g. `C0123456789`), not the channel name
- **"No findings" on first run** — normal; the agent only shows results from the past 24 hours. Wait a day or check that competitors are spelled correctly in `config.json`
- **GitHub Actions not triggering** — confirm `agent/config.json` is committed and all secrets are added under Settings → Secrets
