# Nimble × eve

Cookbooks for [eve](https://eve.dev), Vercel's framework for durable production agents, with [Nimble](https://nimbleway.com) as the agent's live web layer through the [`@nimble-way/eve`](https://www.npmjs.com/package/@nimble-way/eve) extension.

| Cookbook | What it shows | eve features |
|---|---|---|
| [pricing-brief](./pricing-brief) | A Slack agent that checks competitors' pricing pages every day and posts only real price changes, with sources | Schedules, Slack channel, `no_reply`, durable thread sessions |
| [software-factory](./software-factory) | Vercel's Software Factory with a Nimble-backed research step: an issue asking for an SDK upgrade becomes a tested draft PR that cites the official migration guide | Subagent stations, Vercel Sandbox, GitHub channel, human review |
| [software-factory-demo-app](./software-factory-demo-app) | A small Next.js app pinned to AI SDK 6, the practice target for the factory | |

## The extension

```bash
eve add extension/nimble
```

It mounts Nimble's tools under the `nimble` namespace: `nimble__search`, `nimble__extract`, and `nimble__agent_start` / `nimble__agent_result` for Web Search Agent runs. Both cookbooks mount it inside the agent that needs it and turn off the tools that agent doesn't use. The key comes from `NIMBLE_API_KEY`.

Requires eve 1.0 and `@nimble-way/eve` 0.2.0 or later.
