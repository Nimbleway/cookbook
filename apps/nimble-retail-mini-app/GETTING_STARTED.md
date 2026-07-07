# 🚀 Getting Started — Nimble Retail Intelligence app

A Next.js app that pulls **live** Amazon / Walmart / Target shelf data (via Nimble + Claude) and captures leads into HubSpot. Built for Shoptalk outbound.

- **Live site:** https://nimble-retail.vercel.app
- **Repo:** https://github.com/aaronw-tech/nimble-retail-mini-app *(you're a collaborator)*
- **Deeper docs:** see [`ONBOARDING.md`](./ONBOARDING.md) — architecture, file map, and key decisions.

---

## 1. Set up locally (VS Code)

```bash
git clone https://github.com/aaronw-tech/nimble-retail-mini-app.git
cd nimble-retail-mini-app
npm install
cp .env.example .env.local
npm run dev          # → http://localhost:3000
```

Open the folder in VS Code and you're ready.

> **It runs in Demo Mode with no keys** — rich sample data for 5 categories, perfect for building UI. You only need real keys for *live* data or HubSpot testing (next section).

## 2. Keys (optional — only for live data)

Demo Mode needs nothing. To pull **live** Nimble data or test HubSpot capture on your machine, ask Aaron for the `.env.local` values (they're secret, not in the repo). `.env.example` lists exactly which ones. Paste them into `.env.local` and restart `npm run dev`.

## 3. Make changes & ship

The repo is connected to Vercel, so **deploys are automatic — you don't need a Vercel account.**

- **Push to `main`** → auto-deploys to **production** (https://nimble-retail.vercel.app) in ~30s.
- **Push a branch / open a Pull Request** → a **preview link appears right in the PR** so you can test before merging.

```bash
git checkout -b my-change
# ...edit in VS Code...
git add -A && git commit -m "describe the change"
git push origin my-change       # preview URL shows up in the GitHub PR
# open a PR on GitHub → review the preview → merge to main → it goes live
```

You can also commit straight to `main` for small changes — it deploys immediately.

## 4. ⚠️ Read before writing framework code

- **This is Next.js 16** — it has breaking changes vs older versions you may know. Before touching framework-level code (routing, config, middleware/"proxy", etc.), check the guides in `node_modules/next/dist/docs/`. This is also noted in `AGENTS.md`.
- **`ONBOARDING.md`** is the source of truth for how the app is structured and why.

## 5. House rules (please keep these)

- **Demo Mode must always work with no keys** — it's what we demo from.
- **Never fake data** — no invented trends, history, or numbers. The "track over time" panel is a *locked teaser* on purpose (we have no history).
- **No internal jargon in user-facing copy** — say "the shelf", "retailer data", "live". Never "SERP", "agent", "Web Search Agent".
- **One conversion path** — every CTA opens the in-app lead form → HubSpot. Don't add `mailto:` CTAs or new capture flows.

## 6. Handy commands

```bash
npm run dev                 # local dev (Demo Mode if no keys)
npm run build               # production build — good sanity check before pushing
npm run lint                # eslint
npm run health              # checks the live Nimble agents are responding
FORCE_DEMO=1 npm run dev     # force Demo Mode even with keys (QA / screenshots)
```

## 7. Where things live (quick map)

| Area | File |
| --- | --- |
| Homepage hero | `src/components/hero-search.tsx` |
| The report (sections, nav, CTAs) | `src/components/results-experience.tsx` |
| Cross-retailer table (the centerpiece) | `src/components/cross-retailer-diff.tsx` |
| Lead form (the one conversion path) | `src/components/lead-modal.tsx` |
| Lead → HubSpot/Slack | `src/app/api/lead/route.ts` |
| Live search (parallel, streaming) | `src/app/api/search/route.ts` + `src/services/nimble-serp.ts` |
| Rule-based insights | `src/lib/insight-engine.ts` |
| Demo data + brand logos | `src/lib/mock-data.ts` |
| Conference/contact config | `src/lib/config.ts` |

---

Questions → ping Aaron (aaronw@nimbleway.com). Full details in [`ONBOARDING.md`](./ONBOARDING.md).
