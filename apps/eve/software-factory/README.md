# eve Software Factory + Nimble — Tested SDK migrations from current docs

eve's Software Factory turns a GitHub issue into a reviewed draft pull request. In this version every step reaches the web through [Nimble](https://nimbleway.com). When an issue asks for a dependency upgrade, the factory reads the official, version-specific migration guide with Nimble Extract (finding it with Nimble Search when the URL isn't known), plans the change from it, edits the code in a sandbox, runs the repository's own checks, and opens a draft PR that links the docs it used.

![Built with Nimble + eve](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20eve-edc602)

Why it matters: a new SDK major is often newer than the model's training data. The codemod handles renames, but behavior changes live in the migration guide. The included demo app shows one: AI SDK 7 changed `usage` to total every step, which silently changes a cost log. The checks only pass when the change follows the guide.

## What it does

1. **Classify.** A fast model triages the issue: type, complexity, actionable or not, duplicate or not.
2. **Research.** For a dependency upgrade, the researcher station reads the official migration guide for the exact version pair with Nimble Extract (`web_fetch`), using Nimble Search (`web_search`) to find it when needed. Every finding cites the guide.
3. **Plan.** The analyst turns the findings into a plan with acceptance criteria, from a live checkout of the repository.
4. **Implement.** The implementer edits the code in its own Vercel Sandbox, runs the repository's checks, and pushes a `factory/*` branch.
5. **Review.** A reviewer on a different model vendor judges the pushed diff against the acceptance criteria.
6. **Draft PR.** The orchestrator opens a draft PR with a **Sources** section listing every URL the plan relied on. Merging stays with a person.

## What changed from Vercel's template

This folder is a fork of [vercel-labs/eve-software-factory-template](https://github.com/vercel-labs/eve-software-factory-template) (MIT, see [LICENSE](./LICENSE)). Vercel's original README is kept as [TEMPLATE-README.md](./TEMPLATE-README.md).

| Change | Where |
|---|---|
| All web access goes through Nimble: in the orchestrator and every station, `web_search` = Nimble Search and `web_fetch` = Nimble Extract. The extension is mounted once (in the researcher); the namespaced duplicates and Web Search Agent tools are disabled, since an approval prompt would stall an unattended run | `agent/tools/`, `agent/subagents/*/tools/`, `agent/subagents/researcher/extensions/nimble/` |
| Dependency upgrades are research-first; the researcher reads the official migration guide for the exact version pair | `agent/instructions.ts`, `agent/subagents/researcher/instructions.md` |
| PR bodies end with a **Sources** section | `agent/instructions.ts` |
| Upgraded from eve 0.67 to eve 1.0 (`limits.sessionUsage`, `defineInstructions({ content })`, `ctx.agent(name).send()`, v27 eval events, Biome pinned to `~2.5`) | `agent/`, `evals/`, `package.json` |
| Linear is optional: with no `LINEAR_CONNECTOR`, the factory takes work from GitHub only | `agent/lib/constants.ts`, `agent/connections/linear.ts` |

## Stack

- [Nimble](https://nimbleway.com) Search and Extract, through the [`@nimble-way/eve`](https://www.npmjs.com/package/@nimble-way/eve) extension, for every web lookup
- [eve](https://eve.dev) 1.0: durable sessions, subagent stations, GitHub channel, Vercel Sandbox
- [Vercel AI Gateway](https://vercel.com/ai-gateway): OpenAI `gpt-5.6-terra-fast` for most stations, Anthropic `claude-fable-5` for the implementer
- [Vercel Connect](https://vercel.com/kb/guide/vercel-connect) (GitHub App) and Vercel Blob (the factory's memory)
- TypeScript, Node.js 24

## Setup

Requirements: Node.js 24 and pnpm (`corepack enable`), the GitHub CLI, a Vercel account with **paid AI Gateway credits** (the free tier doesn't allow these models), and a Nimble API key from [nimbleway.com](https://nimbleway.com).

### 1. Create the demo repository

The factory works on a whole repository, so copy the demo app into one of your own:

```bash
npx degit Nimbleway/cookbook/apps/eve/software-factory-demo-app ai-sdk-demo
cd ai-sdk-demo
git init -b main && git add -A && git commit -m "Support desk demo app on AI SDK 6"
gh repo create <your-user>/ai-sdk-demo --public --source . --push
gh label create factory --description "Hand this issue to the eve Software Factory"
cd ..
```

### 2. Install the factory

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/eve/software-factory
pnpm install
vercel link          # create or pick a Vercel project
```

### 3. Connect GitHub and storage

1. In the Vercel dashboard, open your team's **Connect** page and add a **GitHub** connector. Install its GitHub App on the demo repository.
2. In the GitHub App's settings, under **Permissions & events**, subscribe to **Issues**, **Issue comment**, **Pull request**, **Pull request review comment** and **Check suite**.
3. Attach the connector to the project and route its webhooks to the agent:

```bash
vercel connect attach <github-connector-uid> --triggers --trigger-path /eve/v1/github --yes
vercel blob create-store factory-brain --access public --yes
```

### 4. Set the environment

```bash
vercel env add FACTORY_REPO            # <your-user>/ai-sdk-demo
vercel env add GITHUB_CONNECTOR        # the connector UID, e.g. github/my-factory
vercel env add FACTORY_SETUP_COMMAND   # npm ci
vercel env add NIMBLE_API_KEY          # your Nimble API key
```

Add each to Production, Preview and Development. See [.env.example](./.env.example) for every option.

### 5. Deploy

```bash
vercel traces config set 100 --environment production   # so runs appear in Observability → Agent Runs
npx eve deploy
```

## Usage

Open an issue on the demo repository with the `factory` label:

> **Upgrade to AI SDK 7**
>
> Upgrade the `ai` package from v6 to v7.
> - Follow the official AI SDK 7 migration guide.
> - The app should behave the same after the upgrade.
> - `npm run typecheck`, `npm test` and `npm run build` must pass.

The factory comments on the issue as each station finishes and ends with a link to a draft PR, typically in 10 to 20 minutes. Read the PR's **Sources** section to see which guide pages the plan relied on, and the diff to see how the change follows them. Results vary between runs.

## Project structure

```
software-factory/
├── agent/
│   ├── agent.ts, instructions.ts      # orchestrator (Foreman) and the pipeline
│   ├── channels/                      # github, linear (optional), eve
│   ├── subagents/
│   │   ├── classifier/  analyst/  implementer/  reviewer/   # each: tools/web_search.ts, web_fetch.ts
│   │   └── researcher/
│   │       ├── extensions/nimble/     # the one @nimble-way/eve mount + disabled duplicates
│   │       └── tools/web_search.ts, web_fetch.ts
│   ├── tools/                         # run_<station> wrappers, brain, artifacts, web_search.ts, web_fetch.ts
│   └── lib/models.ts                  # every station's model in one place
├── evals/                             # eve eval suite (routing, safety, pipeline)
├── TEMPLATE-README.md                 # Vercel's original README
└── LICENSE                            # MIT, Vercel
```

## Going further

- **Other upgrades.** Point `FACTORY_REPO` at a real repository and file an issue for any SDK major (for example `openai` 6 to 7 or `stripe` 22 to 23). The researcher looks up that version pair's guide.
- **Research beyond migrations.** Any issue that needs outside facts (an API's current limits, a library's recommended pattern) goes through the same Nimble-backed web tools.
- **Linear.** Set `LINEAR_CONNECTOR` and attach a Linear connector with `--trigger-path /eve/v1/linear` to delegate work from Linear.

## Notes

- **Start over with a new issue.** Each issue thread is one session. Relabeling an issue resumes its earlier session and keeps what it decided, including a "duplicate" verdict. To run the upgrade again, close the old issue and PR and file a new issue.
- **Duplicates.** The classifier checks for open issues and PRs covering the same work and closes the new issue as a duplicate when it finds one.
- **AI Gateway free tier.** A run that stops at its first step with "Free tier users do not have access to this model" needs paid AI Gateway credits on the Vercel team.
- **Cost.** Each run makes several model calls across six agents, runs a sandbox, and makes a handful of Nimble Search and Extract calls.
