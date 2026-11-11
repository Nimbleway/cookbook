# Support Desk (AI SDK 6)

A small Next.js support chat: it answers questions about orders, looks orders up with a tool, triages tickets into a structured shape, and logs token usage.

**It stays on AI SDK 6 on purpose.** This app is the practice target for the [Nimble × eve Software Factory cookbook](https://github.com/Nimbleway/cookbook/tree/main/apps/eve/software-factory): copy it into a repository of your own, point the factory at it, open an issue asking to upgrade the AI SDK to v7, and watch the factory find the migration guide with Nimble, make the change, run these checks and open a draft PR.

## Checks

```bash
npm ci
npm run typecheck
npm test        # Vitest with mock models: no API key needed
npm run build
```

All three pass on AI SDK 6. Upgrading the `ai` package to v7 without migrating the code breaks them.

## Run it locally

```bash
cp .env.example .env.local   # add AI_GATEWAY_API_KEY
npm run dev
```

Try "Where is order A-1001?"

The chat route has no auth and every request spends AI Gateway credits, so it caps the request size and answers from the last 20 messages. Run it locally, or add auth before deploying it publicly.
