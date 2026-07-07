# Onboarding — Nimble Retail Intelligence (Shoptalk app)

A conference lead-gen app that proves **Nimble's live retail data beats static Digital Shelf Analytics**. A prospect types a category/brand/keyword → we pull **Amazon, Walmart & Target live**, show who owns the shelf and how it differs across retailers, and convert them into a lead for our CRO to meet at Shoptalk.

**Live:** https://nimble-retail.vercel.app
**Stack:** Next.js 16 (App Router, Turbopack) · Nimble SERP agents · Claude (Anthropic) · Tailwind · deployed on Vercel.

---

## ⚠️ Read this first (it'll save you)

1. **This is Next.js 16 — not the version you remember.** APIs, conventions, and file layout have breaking changes (e.g. middleware was renamed to "proxy"). **Before writing framework code, read the relevant guide in `node_modules/next/dist/docs/`.** This is also enforced in `AGENTS.md`.
2. **Demo Mode is the default and needs zero keys.** `npm run dev` works offline with rich mock data for 5 categories. Live Mode turns on only when Nimble keys are set.
3. **Never fake data.** No invented trends/history/numbers. The "track over time" panel is intentionally a locked teaser because we have no history — don't "fill it in."
4. **No internal jargon in UI copy.** Users never see "SERP", "agent", "Web Search Agent", etc. Say "retailer data", "the shelf", "live".

---

## Quick start

```bash
npm install
cp .env.example .env.local     # Demo Mode needs nothing; add ANTHROPIC_API_KEY for the AI copy
npm run dev                    # → http://localhost:3000
```

Useful scripts:
```bash
npm run build      # production build (run before deploying)
npm run lint       # eslint
npm run health     # scripts/health-check.mjs — checks the live Nimble agents respond
FORCE_DEMO=1 npm run dev   # force Demo Mode even with Nimble keys (great for QA / screenshots)
```

See `.env.example` for the full, current list of env vars (AI, Nimble, HubSpot lead capture, Conference Mode).

---

## How it works

```
User search
   ↓
/api/search → 3 Nimble SERP agents IN PARALLEL → normalizer (streams each retailer as NDJSON)
   ↓
insight-engine.ts (rule-based) → instant insights + cross-retailer matrix   ← renders in seconds
   ↓ (async, never blocks)
Claude → streaming hero summary + "Ask Nimble"   (deterministic fallback if AI_ENRICH=off or no key)
```

**Design principles enforced in code (keep them):**
- **Insights before analytics** — hero answer first; raw numbers last and collapsed.
- **Never block on Claude** — rule-based insights render immediately; AI streams in after.
- **Fault tolerant** — if one retailer fails, the other two still render.
- **One conversion path** — see Lead capture below.

---

## Where things live

```
src/
  app/
    page.tsx                  # server: detects Live vs Demo, renders <ExperienceApp>
    api/search/route.ts       # streaming NDJSON search (parallel, fault-tolerant)
    api/ask/route.ts          # Claude streaming (hero summary + Ask Nimble)
    api/lead/route.ts         # LEAD CAPTURE → HubSpot + optional Slack webhook
    api/insights|paid-organic|monitoring|brand-signature/  # per-module enrichment endpoints
  components/
    experience-app.tsx        # top-level: header, hero/results switch, lead modal provider
    hero-search.tsx           # homepage hero (headline, search, examples, retailer cluster)
    results-experience.tsx    # THE REPORT — section order, nav, top frame, closing CTA
    cross-retailer-diff.tsx   # "What changes across retailers" matrix (the centerpiece)
    run-my-brand.tsx          # personalized "where does my brand stand"
    paid-organic.tsx          # "earned vs bought"
    localization-teaser.tsx   # "by market" (locked teaser)
    monitoring-teaser.tsx     # "over time" (locked teaser)
    lead-modal.tsx            # the ONE lead form (useLeadModal().open()) + provider
    lead-capture.tsx          # floating launcher that opens the modal
    site-header.tsx           # Nimble logo (home) + "Meet us at [Shoptalk]" pill
  lib/
    insight-engine.ts         # rule-based insights + cross-retailer matrix (no AI)
    mock-data.ts              # deterministic Demo Mode data + brand→logo domains
    retailers.ts              # Nimble agent config + retailer metadata/colors
    config.ts                 # Conference Mode (NEXT_PUBLIC_*)
    use-search.ts             # client hook: streams results, recomputes insights
  services/nimble-serp.ts     # live Nimble agent calls + tolerant normalizer
```

---

## Lead capture (the money path)

Every "Get in touch / Meet us / Start tracking / Get my brand's review" CTA opens **one** in-app form (`lead-modal.tsx`, via `useLeadModal().open()`). There are **no `mailto:` CTAs** anymore (except the small "Prefer email?" link inside the form).

Submitting posts to **`src/app/api/lead/route.ts`**, which:
1. Logs the lead, then
2. Forwards the contact to **HubSpot** via the Forms Submission API (auth = portal + form GUID, no API key), and
3. Optionally pings **`LEAD_WEBHOOK_URL`** (Slack/Pipedream) — currently **left unset** because HubSpot runs a HubSpot→Slack workflow (avoids duplicate pings).

Form fields → HubSpot standard contact properties: `firstname`, `lastname`, `company`, `email` (all required in the form). HubSpot env vars (`HUBSPOT_PORTAL_ID/FORM_GUID/REGION`) live in Vercel Production. If you fork for another client, swap those.

---

## Deploy

Currently deployed via the **Vercel CLI** (see "Recommended next step" below to move to Git-based deploys):

```bash
npm run build
vercel --prod --yes
# ⚠️ The clean URL is a manual alias — RE-RUN THIS AFTER EVERY PROD DEPLOY:
vercel alias set <new-deployment-url> nimble-retail.vercel.app
```

> **Gotcha:** because there's no Git connection yet, the `nimble-retail.vercel.app` alias does **not** auto-update — you must re-alias each deploy. Connecting GitHub (below) removes this chore entirely.

Env vars are set in the Vercel **Production** scope (`vercel env ls production`). Demo Mode works on a fresh deploy with no keys.

### Recommended next step: GitHub + Vercel git integration
Once this repo is on GitHub and connected to the Vercel project (Settings → Git), you get: push a branch → automatic **preview URL**; merge to main → **auto-deploy to production** with the domain updating automatically (no manual alias). Add the env vars to the **Preview** scope too so previews light up.

---

## Recent decisions (so you don't undo them)
- **Headline:** "Your shelf looks different on every retailer." (insight hook, not salesy). Subline: "Get fresh digital shelf data for any retailer in 30 seconds."
- **One conversion path:** all CTAs → the lead form → HubSpot. The old "email me this report" feature was removed (it never actually emailed and bypassed HubSpot).
- **Cross-retailer table** shows inline (no expand); divergence notes are directional ("21% cheaper on Walmart"). The "Out of stock" row was removed (Walmart-only, low signal).
- **Report framing:** a slim "you're seeing a sample" line up top; the full CTA lives once, in the closing "This is just a glimpse" banner.
- **Header** keeps the branded "Meet us at [Shoptalk]" pill (it opens the form).

## Spec / deeper docs
`PRD.md`, `UI_UX_GUIDELINES.md`, `TECHNICAL_ARCHITECTURE.md`, `NIMBLE_AGENT_INTEGRATION.md`. Note: some `docs/*audit*.md` files predate recent changes (they reference a removed `/api/report` email feature) — trust the code and this file over those.

---

Built by Solutions Consulting @ Nimble. Questions → Aaron (aaronw@nimbleway.com).
