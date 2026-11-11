# AI setup: pricing-brief (Nimble × eve)

You are helping the user set up and run the pricing-brief cookbook: an eve agent that checks competitors' pricing pages every day with Nimble and posts real price changes to Slack. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

Run each check. If one fails, tell the user how to fix it and wait.

- **Node.js 24:** `node --version` should print `v24.x`. If not, install Node 24 from https://nodejs.org or with nvm (`nvm install 24`).
- **Vercel CLI:** `vercel --version`. If missing: `npm i -g vercel`. Then `vercel whoami`; if not signed in, ask the user to run `vercel login`.
- **AI Gateway credits:** ask the user to confirm their Vercel team has paid AI Gateway credits (Vercel dashboard → AI Gateway). The free tier blocks the model this agent uses (`anthropic/claude-sonnet-5.5`).
- **Slack:** ask the user to confirm they can install apps in a Slack workspace.
- **Nimble API key:** ask whether they have one. If not: sign up at https://nimbleway.com.

---

## Step 2: Get the code

```bash
if [ -d cookbook ]; then git -C cookbook pull; else git clone https://github.com/Nimbleway/cookbook; fi
cd cookbook/apps/eve/pricing-brief
npm install
```

`npm install` takes about a minute.

---

## Step 3: Link a Vercel project

```bash
vercel link
```

Let the user pick their team and create a new project (for example `pricing-brief`) or choose an existing one.

---

## Step 4: Connect Slack

This step happens in the browser. Tell the user:

1. In the Vercel dashboard, open the team's **Connect** page, add a **Slack** connector, and install it in the Slack workspace. Note the connector UID shown for it (for example `slack/pricing-brief`).
2. In Slack, create a channel for alerts (for example `#pricing-alerts`) and type `/invite @<bot name>` in it.
3. Open the channel's name → **About**; the channel ID (starts with `C`) is at the bottom.

Ask the user for the connector UID and the channel ID. Then attach the connector so Slack events reach the agent:

```bash
vercel connect attach <slack-connector-uid> --triggers --trigger-path /eve/v1/slack --yes
```

---

## Step 5: Add Postgres and Blob

```bash
vercel integration add neon
vercel blob create-store pricing-brief-blob --access public --yes
```

If the Neon command asks for terms to be accepted, tell the user to open the link it prints, accept, and then run the command again. Neon sets `DATABASE_URL`; the Blob store sets `BLOB_READ_WRITE_TOKEN`. The tables are created on first use.

---

## Step 6: Configure the environment

Tell the user: the Nimble key lets the agent find pricing pages (Search) and read them (Extract). The Slack values tell it where to post.

Add each variable to Production, Preview and Development. Ask the user to paste the values into the prompts; never ask them to paste keys into the chat.

```bash
vercel env add NIMBLE_API_KEY
vercel env add SLACK_CONNECTOR
vercel env add SLACK_CHANNEL_ID
vercel env pull .env.local
```

Confirm `.env.local` now contains `NIMBLE_API_KEY`, `SLACK_CONNECTOR`, `SLACK_CHANNEL_ID`, `DATABASE_URL` and `BLOB_READ_WRITE_TOKEN` (check the names only; don't print the values).

---

## Step 7: Test and deploy

```bash
npm test
vercel traces config set 100 --environment production
npx eve deploy
```

`npm test` runs the comparison rules with no network calls and should report every test passing. The deploy takes 2 to 3 minutes and prints the deployment URL. Check it:

```bash
curl -s https://<deployment>/eve/v1/health
```

It should return `{"ok":true,"status":"ready",...}`. Ask the user to confirm before continuing.

---

## Step 8: Orient the user

Tell the user to go to the alerts channel and try:

1. `@<bot name> track Postmark, SendGrid and Resend`: the bot finds each official pricing page, reads it, and replies with the plans it saved. This takes about a minute.
2. `@<bot name> track Acme Mail at https://<deployment>/demo/acme-mail/pricing`: the built-in demo page, labeled as not a real company.
3. Change the demo price and run a check:
   ```bash
   npm run demo:price -- 29
   ```
   Then run the daily check from the Vercel dashboard (**Settings → Cron Jobs → Run**), or wait for 13:00 UTC. The channel should get one alert for the Growth plan going from $25/mo to $29/mo, with the page link and read time.
4. Reply in that alert's thread: "what does the Growth plan include now?"
5. `@<bot name> what are you tracking?`

---

## Notes

- **No alert means no change.** The agent posts only when a price, billing period, usage limit or plan changed. Otherwise it calls `no_reply` and stays silent.
- **Missing fields aren't changes.** A field a page didn't show on one read (a plan name, a limit behind a slider) is logged and never alerted on.
- **Live pages vary.** What Extract sees depends on the page that day; read the bot's baseline reply to see what was captured for each competitor.
- **"Free tier users do not have access to this model"** in the logs (`vercel logs`) means the team needs paid AI Gateway credits.
- **Cost.** Each check makes one Nimble Extract call per competitor plus a few model calls.
- **Schedule.** The cron is in `agent/schedules/daily-check.ts`, in UTC. Redeploy after changing it.
