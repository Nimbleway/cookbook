# pricing-brief — Competitor pricing monitor on eve

A Slack agent that watches competitors' pricing pages and posts only when a price really changes. [Nimble](https://nimbleway.com) finds each official pricing page and reads it; an eve schedule runs the check every morning; application code compares the read against yesterday's snapshot in Postgres; and a change alert lands in Slack with the source link and the time the page was read. Reply in the alert's thread to ask about it.

![Built with Nimble + eve](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20eve-edc602)

## What it does

1. **Track.** Mention the bot in Slack ("@pricing track Postmark"). Nimble Search finds the official pricing page, Nimble Extract reads it, and the plans are saved as the baseline.
2. **Check daily.** An eve schedule (`agent/schedules/daily-check.ts`, 13:00 UTC) starts a session in the Slack channel. The agent reads every tracked page with Nimble Extract.
3. **Compare in code.** The agent passes the plans it read to `record_snapshot` as typed fields. Application code normalizes them, stores a snapshot in Postgres, and compares it with the previous one. The model never decides whether a price changed.
4. **Alert or stay quiet.** Changes are posted as one Slack message, each with its source link and read time. When nothing changed, the agent calls `no_reply` and posts nothing.
5. **Answer in the thread.** A reply in an alert thread continues the same session. The agent re-reads the page when it needs current details.

What counts as a change: a price, a billing period, a usage limit, or a plan added or removed. Wording, ordering and fields the page didn't show on one read never trigger an alert.

## Stack

- [Nimble](https://nimbleway.com) Search and Extract, through the [`@nimble-way/eve`](https://www.npmjs.com/package/@nimble-way/eve) extension
- [eve](https://eve.dev) 1.0: schedules, the Slack channel, durable sessions, `no_reply`
- [Vercel AI Gateway](https://vercel.com/ai-gateway) with `anthropic/claude-sonnet-5.5`
- Postgres ([Neon](https://neon.com) through the Vercel Marketplace) for competitors and snapshots
- [Vercel Connect](https://vercel.com/kb/guide/vercel-connect) for Slack, Vercel Blob for the demo page's price
- TypeScript, Node.js 24

## Setup

Requirements: Node.js 24, the [Vercel CLI](https://vercel.com/docs/cli), a Vercel account with **paid AI Gateway credits** (the free tier doesn't allow this model), a Slack workspace where you can install apps, and a Nimble API key from [nimbleway.com](https://nimbleway.com).

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/eve/pricing-brief
npm install
vercel link                      # create or pick a Vercel project
```

**Slack.** In the Vercel dashboard, open your team's **Connect** page, add a **Slack** connector and install it in your workspace. Then attach it to the project, create a channel for alerts (for example `#pricing-alerts`) and invite the bot with `/invite @<bot name>`. The channel ID is at the bottom of the channel's **About** tab.

```bash
vercel connect attach <slack-connector-uid> --triggers --trigger-path /eve/v1/slack --yes
```

**Postgres and Blob.** The tables are created on first use, so there's no migration step.

```bash
vercel integration add neon      # accept Neon's terms in the browser if asked
vercel blob create-store pricing-brief-blob --access public --yes
```

**Environment.** Add each to Production, Preview and Development, then pull them locally:

```bash
vercel env add NIMBLE_API_KEY
vercel env add SLACK_CONNECTOR   # the connector UID, e.g. slack/pricing-brief
vercel env add SLACK_CHANNEL_ID  # e.g. C0123456789
vercel env pull .env.local
```

**Deploy.**

```bash
npm test                                                 # unit tests for the comparison code
vercel traces config set 100 --environment production    # so runs appear in Observability → Agent Runs
npx eve deploy
```

## Usage

In the alerts channel:

```
@<bot name> track Postmark, SendGrid and Resend
@<bot name> track Acme Mail at https://<your-deployment>/demo/acme-mail/pricing
```

The bot replies in a thread with the plans it saved for each competitor.

**See a change alert.** Acme Mail is a demo pricing page served by this app (it's labeled as not a real company). Its Growth plan starts at $25/month. Change it, then run the daily check:

```bash
npm run demo:price -- 29
```

Run the check from the Vercel dashboard (**Settings → Cron Jobs → Run**), or wait for the next 13:00 UTC run. The channel should get:

> *Acme Mail* (pricing page, read 2026-11-11 13:01 UTC)
> • Growth plan: price $25/mo → $29/mo

Reply in the thread, for example "what does the Growth plan include now?", and the bot reads the page again and answers with the link.

## Project structure

```
pricing-brief/
├── agent/
│   ├── agent.ts                       # model; default tools off
│   ├── instructions.md                # tracking, daily check, alert format, thread answers
│   ├── channels/slack.ts              # Slack via Vercel Connect
│   ├── channels/acme-demo.ts          # GET /demo/acme-mail/pricing
│   ├── extensions/nimble/             # @nimble-way/eve: Search + Extract (Web Search Agent tools disabled)
│   ├── schedules/daily-check.ts       # cron "0 13 * * *" → "Run the daily pricing check" in Slack
│   ├── tools/
│   │   ├── add_competitor.ts, list_competitors.ts, remove_competitor.ts
│   │   ├── record_snapshot.ts         # normalize → store → compare, in code
│   │   └── no_reply.ts                # eve's opt-in "post nothing"
│   └── lib/
│       ├── plans.ts                   # plan schema (the tool's input)
│       ├── normalize.ts, diff.ts      # the comparison rules
│       ├── db.ts                      # Postgres
│       ├── acme.ts                    # demo page's price in Blob
│       └── acme-page.ts               # demo page HTML
├── scripts/demo-price.ts              # change the demo page's Growth price
└── tests/diff.test.ts                 # comparison rules, no network
```

## Output

Postgres, created on first use:

**`competitors`**

| Column | Type | Description |
|---|---|---|
| `id` | `SERIAL` | Primary key |
| `name` | `TEXT` | Competitor name, unique |
| `pricing_url` | `TEXT` | Official pricing page |
| `added_at` | `TIMESTAMPTZ` | When tracking started |

**`snapshots`**

| Column | Type | Description |
|---|---|---|
| `id` | `SERIAL` | Primary key |
| `competitor_id` | `INTEGER` | References `competitors(id)`, deleted with it |
| `read_at` | `TIMESTAMPTZ` | When the page was read |
| `source_url` | `TEXT` | The URL that was read |
| `plans` | `JSONB` | Normalized plans: `name`, `price` (`amount`, `currency`, `period`), `starting_at`, `limits` (`metric`, `amount`, `per`). Fields a read missed keep their last known value |

## Going further

- **Your competitors.** Track any SaaS pricing page; Search finds the official one from a name.
- **Schedule.** Change the cron in `agent/schedules/daily-check.ts`. Times are UTC.
- **What counts as a change.** The rules live in `agent/lib/diff.ts`, with tests in `tests/diff.test.ts`.
- **Deeper follow-ups.** Re-enable the extension's `agent_start` tool so a thread reply like "why did Resend change pricing?" starts a Nimble Web Search Agent run, approved with eve's buttons in Slack.

## Notes

- **Missing fields aren't changes.** Some pages hide details from a page read: plan names, or limits set by a slider. A field that's missing on one read is logged and never alerted on, and the snapshot keeps its last known value, so the next real change still alerts. A plan missing from one read is kept the same way; it counts as removed only when two reads in a row miss it.
- **Plans without names** are matched by their position on the page and labeled by their previous price ("$15/mo plan").
- **A run that stops at its first model call** with "Free tier users do not have access to this model" needs paid AI Gateway credits on the Vercel team.
- **Cost.** Each daily check makes one Nimble Extract call per competitor plus a few model calls. A run with no changes posts nothing but still costs those calls.
