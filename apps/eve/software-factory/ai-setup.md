# AI setup: eve Software Factory + Nimble

You are helping the user set up and run the eve Software Factory with Nimble: an eve agent that turns a GitHub issue into a reviewed draft pull request, using Nimble to read current migration guides. The demo upgrades a small app from AI SDK 6 to 7. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

Run each check. If one fails, tell the user how to fix it and wait.

- **Node.js 24:** `node --version` should print `v24.x`. If not, install it from https://nodejs.org or with nvm (`nvm install 24`).
- **pnpm:** `pnpm --version`. If missing: `corepack enable`.
- **GitHub CLI:** `gh auth status`. If not signed in, ask the user to run `gh auth login`.
- **Vercel CLI:** `vercel whoami`. If missing: `npm i -g vercel`, then ask the user to run `vercel login`.
- **AI Gateway credits:** ask the user to confirm their Vercel team has paid AI Gateway credits (Vercel dashboard → AI Gateway). The free tier blocks the models the factory uses.
- **Nimble API key:** ask whether they have one. If not: sign up at https://nimbleway.com.

---

## Step 2: Create the demo repository

The factory works on a whole GitHub repository. Ask the user for their GitHub username (or organization), then:

```bash
npx degit Nimbleway/cookbook/apps/eve/software-factory-demo-app ai-sdk-demo
cd ai-sdk-demo
git init -b main && git add -A && git commit -m "Support desk demo app on AI SDK 6"
gh repo create <owner>/ai-sdk-demo --public --source . --push
gh label create factory --description "Hand this issue to the eve Software Factory"
cd ..
```

Optional check: in `ai-sdk-demo`, `npm ci && npm run typecheck && npm test && npm run build` should all pass on AI SDK 6.

---

## Step 3: Get the factory

```bash
if [ -d cookbook ]; then git -C cookbook pull; else git clone https://github.com/Nimbleway/cookbook; fi
cd cookbook/apps/eve/software-factory
pnpm install
pnpm validate
vercel link
```

`pnpm validate` runs lint, typecheck and eve's discovery check. It needs `FACTORY_REPO` set; if it fails on that, run it as `FACTORY_REPO=<owner>/ai-sdk-demo pnpm validate`. For `vercel link`, let the user create a new project (for example `software-factory`).

---

## Step 4: Connect GitHub and storage

This step happens in the browser. Tell the user:

1. In the Vercel dashboard, open the team's **Connect** page, add a **GitHub** connector, and install its GitHub App on the `ai-sdk-demo` repository. Note the connector UID (for example `github/my-factory`).
2. In GitHub, open the App's settings (Settings → Developer settings → GitHub Apps → the app → **Permissions & events**) and subscribe to these events: **Issues**, **Issue comment**, **Pull request**, **Pull request review comment**, **Check suite**. Save.

Ask for the connector UID, then:

```bash
vercel connect attach <github-connector-uid> --triggers --trigger-path /eve/v1/github --yes
vercel blob create-store factory-brain --access public --yes
```

---

## Step 5: Configure the environment

Tell the user: the Nimble key powers the researcher step's web search and page reading. `FACTORY_REPO` is the repository the factory works on; `FACTORY_SETUP_COMMAND` installs its dependencies in the sandbox.

Add each to Production, Preview and Development. Ask the user to paste the values into the prompts; never ask them to paste keys into the chat.

```bash
vercel env add NIMBLE_API_KEY
vercel env add GITHUB_CONNECTOR        # the connector UID
vercel env add FACTORY_REPO            # <owner>/ai-sdk-demo
vercel env add FACTORY_SETUP_COMMAND   # npm ci
```

---

## Step 6: Deploy

```bash
vercel traces config set 100 --environment production
npx eve deploy
curl -s https://<deployment>/eve/v1/health
```

The deploy takes 2 to 4 minutes. The health check should return `{"ok":true,"status":"ready",...}`. Ask the user to confirm before continuing.

---

## Step 7: Run the migration

```bash
gh issue create -R <owner>/ai-sdk-demo --title "Upgrade to AI SDK 7" --label factory --body "Upgrade the \`ai\` package from v6 to v7.

- Follow the official AI SDK 7 migration guide.
- The app should behave the same after the upgrade.
- \`npm run typecheck\`, \`npm test\` and \`npm run build\` must pass."
```

Tell the user what happens next: the factory comments on the issue as it classifies, plans, implements and reviews, then links a draft PR. This typically takes 10 to 20 minutes. Check progress with:

```bash
gh issue view <number> -R <owner>/ai-sdk-demo --comments
gh pr list -R <owner>/ai-sdk-demo
```

---

## Step 8: Orient the user

When the draft PR is open, walk the user through it:

1. **Sources** at the end of the PR body: the migration guide pages the plan relied on, found and read through Nimble.
2. **The diff**, especially how token usage is reported. AI SDK 7 changed `usage` to total every step, so a cost log that should report one step needs `finalStep.usage`.
3. **CI** on the PR: the demo app's typecheck, tests and build.
4. **Vercel → the project → Observability → Agent Runs**: the run, including every station's `web_search` and `web_fetch` calls, all served by Nimble.

Ideas to try next:
- Mention the bot on the PR with a follow-up question.
- Point `FACTORY_REPO` at a real repository and ask for another SDK upgrade.

---

## Notes

- **To run again, file a new issue.** Each issue thread is one session; relabeling resumes it with its earlier decisions, including a "duplicate" verdict. Close the old issue and PR first, or the classifier flags the new issue as a duplicate.
- **"Cannot access <owner/repo>"** means the GitHub App isn't installed on `FACTORY_REPO`.
- **No comments after a minute:** check that the App is subscribed to the events in step 4 and that `vercel logs` shows the webhook arriving. "Free tier users do not have access to this model" means the team needs paid AI Gateway credits.
- **Results vary between runs.** Read the PR's Sources and diff rather than expecting a specific change set.
- **Linear is optional.** Leave `LINEAR_CONNECTOR` unset for GitHub only.
