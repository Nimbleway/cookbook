# Agent Setup Guide

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/competitor-intelligence-monitor/agent
pip3 install -r requirements.txt
python3 onboard.py   # fills in config.json and .env
python3 agent.py     # run it
```

`onboard.py` walks you through everything interactively. The sections below are reference if you get stuck.

---

## API keys

You need two keys to run the agent. `onboard.py` will ask for these.

**Nimble** (web search — required)
1. Sign up at [nimbleway.com](https://nimbleway.com)
2. Dashboard → API Keys → Create new key
3. Paste it as `NIMBLE_API_KEY` in your `.env`

**Anthropic** (AI synthesis — required)
1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. API Keys → Create Key
3. Paste it as `ANTHROPIC_API_KEY` in your `.env`

**GitHub** (optional — enables GitHub source tracking)
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → Generate new token (classic)
2. No extra scopes needed
3. Paste it as `GH_API_KEY` in your `.env`

---

## Slack

Skip this if you don't want Slack notifications. The agent will still print results to the terminal.

**Create a Slack app**
1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it (e.g. "Competitor Monitor") and pick your workspace

**Set permissions**
3. **OAuth & Permissions** → **Bot Token Scopes** → add `chat:write`, `im:write`, `commands`

**Install and copy tokens**
4. **OAuth & Permissions** → **Install to Workspace** → Authorize
5. Copy the **Bot User OAuth Token** (`xoxb-...`) → paste as `SLACK_BOT_TOKEN`
6. **Basic Information** → **App Credentials** → copy **Signing Secret** → paste as `SLACK_SIGNING_SECRET`

**Get your channel ID**
7. In Slack, right-click the channel you want digests posted to → **Copy Channel ID**
8. Paste it as `SLACK_CHANNEL_ID`

**Invite the bot**
9. In the channel, type `/invite @YourBotName`

---

## Daily runs (GitHub Actions)

This runs the agent automatically every day without you having to do anything.

**Set up a standalone repo**

GitHub Actions only runs workflows from a repo's root, so create a dedicated repo for this — don't run it from the cookbook directly.

1. Create a new GitHub repo (e.g. `my-competitor-monitor`)
2. Copy the `agent/` folder into the root of your new repo
3. Move the workflow file into place:
   ```bash
   mkdir -p .github/workflows
   mv agent/.github/workflows/daily_monitor.yml .github/workflows/
   ```
4. Commit and push everything

**Add secrets**

5. Go to your repo on GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
6. Add each of these:

| Secret | Required |
|---|---|
| `NIMBLE_API_KEY` | Yes |
| `ANTHROPIC_API_KEY` | Yes |
| `SLACK_BOT_TOKEN` | If using Slack |
| `SLACK_CHANNEL_ID` | If using Slack |
| `GH_API_KEY` | Optional |

**Schedule it with cron-job.org**

GitHub's built-in schedule trigger runs 4–10 hours late in practice. Use [cron-job.org](https://cron-job.org) instead — it's free and reliable.

7. Sign up at [cron-job.org](https://cron-job.org) → **CREATE CRONJOB**
8. Set these fields:

| Field | Value |
|---|---|
| URL | `https://api.github.com/repos/{owner}/{repo}/actions/workflows/daily_monitor.yml/dispatches` |
| Method | `POST` |
| Body | `{"ref": "main"}` |
| Header 1 | `Authorization: Bearer {your_github_token}` |
| Header 2 | `Accept: application/vnd.github.v3+json` |
| Schedule | `0 9 * * 1-5` (9am UTC, Mon–Fri) |

The GitHub token needs `workflow` scope — create one at [github.com/settings/tokens](https://github.com/settings/tokens).

---

## Slash command — `/competitor-digest` (optional)

This lets anyone on your team DM the bot to subscribe to a personalized digest. It requires `slack_bot.py` to run as a persistent web service.

**Deploy the bot**

1. Create a new project on [Railway](https://railway.app) → **Deploy from GitHub repo** → select your repo
2. Add the same env vars from your `.env` file in Railway's settings
3. Railway auto-detects the `Procfile` and runs the bot — copy the public URL it assigns

**Wire up the slash command**

4. In your Slack app → **Slash Commands** → **Create New Command**
5. Set **Command** to `/competitor-digest` and **Request URL** to `https://your-railway-url/slack/events`
6. Save → go back to **OAuth & Permissions** → **Reinstall to Workspace**

---

## Troubleshooting

- **Nothing posted to Slack** — make sure the bot is invited to the channel (`/invite @BotName`) and that `SLACK_CHANNEL_ID` is the channel ID (starts with `C`), not the channel name
- **No findings on first run** — this is normal. The agent only looks back 24 hours. Give it a day, or double-check competitor spellings in `config.json`
- **GitHub Actions `git push` step fails** — your repo has branch protection on `main`. Go to **Settings → Branches** → edit the rule → enable "Allow GitHub Actions to bypass"
- **`/competitor-digest` doesn't respond** — confirm the bot server is running and the slash command Request URL points to your live deployment
