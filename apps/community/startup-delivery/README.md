# Startup.Delivery 📦

> Describe a business idea in one sentence. An agent runs **live market recon**, names it,
> checks **real domain availability + pricing** against the **name.com production Core API**,
> and delivers a launch-ready startup — domain, brand, cited competitor brief, and an optional
> one-click landing page — in a single streamed run (under a minute on the warm/cached path).

**Live:** https://startup-delivery.vercel.app

The `.delivery` TLD *is* the thesis: it doesn't suggest a startup, it **delivers** one.

---

## How it's different from Lovable / Bolt / v0

> *"Lovable builds your app **after** you've decided. Startup.Delivery is the step **before** — it
> tells you if the idea's open, what to call it, and hands you a one-click path to claim the domain,
> all from the live web. It doesn't build the thing. It makes sure the thing is worth building and
> the name is yours to grab."*

Code generators hallucinate freely. This does two things they structurally don't:

1. **Live, cited market recon** (Nimble) → output is real, not made up.
2. **Real-time domain availability + price** (name.com production Core API) → domain-native by design.

---

## The flow (4 steps)

```
idea (one sentence)
  → STEP 1  SEE    (Nimble)      live competitor recon, cited
  → STEP 2  THINK  (OpenRouter)  find the positioning gap + invent names
  → STEP 3  CHECK  (name.com)    reject taken names, keep buyable ones (loop)
  → STEP 4  BUILD  (OpenRouter)  optional landing page grounded in real recon
  → output: DeliveryPackage { domain, brand, cited brief, optional live URL }
```

## Architecture

| Layer | Choice | Role |
|---|---|---|
| Frontend | **SvelteKit on Vercel** (`web/`) | the app surface |
| API | SvelteKit **routes** (`web/src/routes/api/`) proxy a **FastAPI bridge** (`agent/server.py`) | SSE streaming |
| Agent / compute | **Python** (`agent/`), packaged as a **Tower app** (runnable on demand) | the pipeline |
| Storage | **Local JSONL deliveries log** = the live system of record; **Tower Iceberg `deliveries` table** as the on-demand lakehouse mirror | persistence + analytics |
| LLM | **OpenRouter** (swap models via `OPENROUTER_MODEL`) | one key, many models |
| Live web | **Nimble** (SERP + Extract), synthesized into a cited brief | market recon |
| Domain check | **name.com production Core API** (live availability + pricing, `.delivery`-first across 6 TLDs) | domain truth |

## File map

```
agent/
  schemas.py          # data contracts — the spine (Competitor, DomainOption, Verdict, DeliveryPackage…)
  orchestrator.py     # deliver_startup(): the 4-step pipeline + tracking id + verdict + cross-idea learning
  server.py           # FastAPI bridge: POST /deliver, GET /deliver/stream (SSE), GET /deliveries
  tower_app.py        # Tower app entrypoint + Iceberg `deliveries` upsert (runnable on demand; off the live critical path)
  saturated_niches.py # scheduled crowded-market signal (Market Heat)
  deliveries_store.py # local JSONL mirror of deliveries (powers the Dock + cross-idea learning)
  clients/
    nimble.py         # Step 1 — live web recon (SERP + Extract) + junk filter + freshness
    namecom.py        # Step 3 — availability + price + renewal + premium across TLDs
    llm.py            # Steps 2 & 4 — gap, names, verdict, landing copy via OpenRouter
    _openrouter.py    # thin OpenRouter client — chat + chat_json
web/
  src/routes/+page.svelte            # the single screen + streaming pipeline + unbox
  src/routes/dock/+page.svelte       # the public "Loading Dock" gallery
  src/routes/api/deliver/…           # proxy → bridge (one-shot + SSE), MOCK fallback
  src/routes/api/deliveries/+server.ts  # proxy → bridge GET /deliveries
  src/lib/components/                 # Pipeline, DeliveryUnbox, TldGrid, VerdictCard, MarketHeat, Receipt…
  src/lib/types.ts                   # TS mirror of schemas.py
  SETUP.md                           # how to spin up the web app
scripts/dev.sh        # one command: boots the bridge + web together (see Setup)
```

---

## How each integration works

No integration is decoration — pull any one and the product stops doing its job.

- **name.com (production Core API)** — the load-bearing domain integration. Every candidate is
  checked for **live availability + real first-year/renewal pricing** (with a premium/aftermarket
  flag) via the name.com **production** Core API, batched across the `.delivery`-first TLD set.
  A boot **control-check** probes a known-taken control (`google.com`) and a known-open nonsense
  domain at startup, classifies the backend as production vs sandbox, and surfaces an honest
  **provenance badge** (`domainSource` on `/health` + `/debug`) — so you can verify it's on the
  real registry, not the sandbox (which would report registered names as buyable). **Claim it**
  deep-links the winner into the name.com cart. (It surfaces live availability + price; it doesn't
  register the domain for you.)
- **Nimble** — the live-web eyes. Step 1 runs **Nimble SERP** to find real competitors and
  **Nimble Extract** to read their positioning/pricing pages; an LLM then synthesizes a **cited
  brief over those real results**, and a grounding verifier catches and minimizes ungrounded
  citations. Without Nimble there is no evidence, so the gap, names, verdict, and landing page
  would all be guesses.
- **OpenRouter** — the brain and copywriter behind one key. Steps 2 + 4 (find the positioning gap,
  invent brandable names, write the verdict, draft the landing copy) and the recon synthesis all run
  through OpenRouter, so the model is swappable via `OPENROUTER_MODEL` without code changes. It turns
  the live evidence into decisions and language.
- **Tower** — the data-to-AI layer. The Python agent is packaged as a **Tower app** that, on demand,
  upserts each delivery into a managed **Iceberg `deliveries` table** for queryable analytics; a
  scheduled job refreshes the `saturated_niches` signal the recon reads. Tower is **off the live
  critical path** — the local JSONL deliveries log is the system of record powering the Dock and
  cross-idea learning — so the app never depends on a Tower round-trip, but the lakehouse pipeline
  is real and runnable.

---

## Scoring: a deterministic, cited verdict

The 0–100 opportunity score is **not** an LLM's mood. It's a deterministic anchor built from signed,
capped, **cited** evidence factors (demand, pain, monetization, differentiation, contestability,
`.com`-scarcity) — each sourced from data already fetched. The model extracts signals and can nudge
the final number ±15 within an evidence-backed band, but it never authors the call. The engine is
built to say **no**: zero real competitors hard-caps the score at recon-failure, and a "build" verdict
requires ≥2 independent positive signals. A fully offline eval (`python -m agent.eval`) checks
grounding, score anchoring, and ownability with no network or keys.

---

## Features

The core 4-step pipeline plus the depth that turns it from a demo into a product.

**Branch, explore, and a wink**
- **Wedge map** — a 2-axis positioning scatter (price × audience) plotting the live
  competitors and dropping your brand in the open space the market leaves uncovered.
- **Remix** — one click suggests 3 adjacent angles (narrower audience / different model /
  opposite price tier); pick one to branch into a fresh delivery.
- **Tracking-number easter egg** — type a `DEL-…` into the idea box to pull up that
  delivery; type `startup.delivery` and the agent delivers itself.

**Delight + personality**
- **Desk lamp glow** — a warm pool that clicks on behind the idle hero and breathes, making
  the "Night Shift Parcel" thesis literal.
- **Rubber-stamp rejections** — a name taken on every TLD gets a worn, rotated "TAKEN" stamp
  slammed over it (synced to the thunk). The domain moment, made visceral.
- **Verdict-aware shipment stamp + graceful Pass** — the box stamps "Delivered" / "Re-routed"
  / "Returned" by verdict; a Pass is honest and routes you into the refine loop, not dressed
  up as a win.

**Deliveries as a dataset (data-to-AI made visible)**
- **Aggregate stats panel** on the Loading Dock — build/pivot/pass split, avg opportunity
  score, total $/yr secured, most-claimed TLD, and recurring "contested themes" across all
  deliveries. The deliveries dataset *doing* dataset-level work, not just storing — the same
  aggregation the Tower Iceberg `deliveries` table runs when you mirror to it.
- **Cross-idea learning, made visible** — the unbox shows which prior deliveries in the
  niche shaped the names ("avoided N names already delivered"), linking to them.
- **Machine-readable delivery JSON** (`/api/deliveries/{id}`) — each row is an addressable,
  reusable asset, surfaced as a "JSON" link on every permalink.

**Polish + reach**
- **Recently shipped** peek on the idle hero (links to permalinks) + a favicon (the box mark).
- **Open Graph / Twitter cards** with a generated 1200×630 image, so shared permalinks and
  the homepage preview properly; permalinks set per-delivery OG title/description.

**Workspace + takeaway**
- **Compare deliveries** — pick up to 3 in the Loading Dock and compare them side-by-side
  (verdict, score, price, competitors, market). Turns the deliveries dataset into a workspace.
- **Complete brief** — the downloadable one-pager carries the verdict, tracking number,
  market heat, complaints, competitor types, the launch kit, and name.com suggestions.

**More depth**
- **Launch kit** — a "lock the brand" defensive bundle (the .com + get-/try- prefixes),
  batch-checked on name.com, with a yearly total.
- **Competitor types** — one cheap LLM pass tags each incumbent (saas / marketplace /
  agency / …), so "all B2B SaaS, no consumer play" reads at a glance and sharpens the gap.
- **Name memorability** — a subtle "easy to say" marker on strong brand names (heuristic).

**Credibility + a11y**
- **Wedge confidence** — a High / Worth-testing / Speculative badge on the gap, derived
  from how many live competitors + mined complaints back it (honest, distinct from heat).
- **Accessibility** — focus moves to the delivered result, screen-reader `h1`s on every
  view, labelled refine input + dock links.

**Shareability + craft**
- **Delivery permalinks** (`/d/{tracking-id}`) — every delivery is a shareable, read-only
  page from the deliveries log; the Dock links to them and the unbox has a "Copy link".
- **Pricing benchmark** — a "they charge $X–$Y" strip from competitor prices the recon
  already extracts.
- **Keyboard** — `/` focuses the idea field from anywhere.

**Validation depth + reliability**
- **Review-mining** — targeted live-web search of incumbent complaints, distilled into
  "what users hate about the incumbents" and fed into the gap, so the wedge is backed by
  real user pain (not the model's guess).
- **Refine-the-gap loop** — "not the gap you see? describe the angle" + "more names",
  re-running naming for the founder's steer without re-burning the (cached) recon.
- **Speed + robustness** — competitor page extracts run in parallel (the biggest live-run
  speedup), Nimble calls retry with jittered backoff on 429/5xx/timeout, and competitors
  dedupe by registrable host.

**Sound, replay & suggestions**
- **`searchStream` suggestions** — for the winning brand, name.com's *own* suggestion
  engine streams alternative TLDs/variants with prices (`More ways to own it`). Uses
  name.com as an active suggester, not just an availability check.
- **Sound design** — synthesized Web Audio cues (no asset files): tick per domain check,
  thunk on a taken-everywhere name, chime on secured, whoosh on unbox. Off by default,
  toggle in the header (🔊).
- **`?demo=1` replay mode** — a scripted, perfectly-paced run that bypasses the network
  (`?demo=loop` loops it); works fully offline, with a visible "scripted replay" chip.
- **Bold tally** — a loud `N checked · M taken · 1 secured` counter during the check phase.

**The `.delivery` thesis (name.com depth)**
- **`.delivery` is the hero TLD** — every name is checked on **`.delivery` first**, it leads
  the TLD grid, and the winner is promoted to (and Claim-it'd on) `.delivery` whenever it's
  available. The product doesn't suggest a startup, it *delivers* one onto its own namesake
  TLD (the whole thesis).
- **Multi-TLD domain check** — every name is checked across `.delivery / .com / .app / .ai /
  .io / .co` in one batched name.com call; the winner is promoted to the best *available* TLD
  (preferring `.delivery`). The `.delivery` renewal jump ($8.99 → $77.99/yr) doubles as a live
  demo of the premium/renewal intelligence.
- **Premium + renewal pricing** — TLD chips show the real renewal price and flag premium /
  aftermarket domains (the price trap), not just a green check.
- **Shipment tracking number** (`DEL-YYYYMMDD-XXXX`) stamped on every package, the pipeline
  framed as a tracker, `DELIVERED` stamp on the unbox.
- **Claim it** deep-links into name.com's cart on the exact domain.

**Build / Pivot / Pass verdict**
- A real decision (`build` / `pivot` / `pass`) + a 0-100 opportunity score + concrete risks
  + a first-week action list, grounded in the live recon. Leads the box.

**Shareable receipt**
- One click renders a crisp PNG share-card of the delivery (brand, domain + price, verdict,
  the gap, tracking number) via `html-to-image`, plus a prefilled tweet.

**Tower, made visible**
- **The Loading Dock** (`/dock`) — a public gallery of past deliveries read from the local
  JSONL deliveries log (the live system of record), which the Tower Iceberg `deliveries`
  table mirrors when persistence is turned on.
- **Cross-idea learning** — past deliveries in overlapping niches are fed back into naming, so
  the dataset sharpens its naming over time (a data edge prompt-only tools lack — they keep no
  delivery corpus).
- Widened `deliveries` Iceberg schema (verdict, market heat, tracking, TLD-open count) for
  queryable analytics when the Tower app runs.

**Recon credibility (Nimble depth)**
- **Live SERP + Extract → a cited brief** — the agent pulls real competitors with Nimble SERP
  and reads the top pages with Nimble Extract, then synthesizes the market summary with an LLM
  *over those real results* (Nimble's own answer engine is enterprise-gated, so we don't lean
  on it — the brief is grounded in the SERP/Extract evidence we actually fetched).
- **Grounding verifier** — a pure, offline check runs over the agent's prose: if it cites a
  company the live recon never surfaced, the call is retried once with a grounding steer and the
  cleaner result is kept. Any citation that still isn't backed is flagged in the logs (not silently
  passed) — so hallucinated competitors are caught and minimized, not quietly shipped.
- **Junk filter** — drops social / directories / listicles (Facebook, G2, GetApp…) so the
  competitor set reads like real competition.
- **Market Heat** — a structured crowded-space signal (`N live competitors · crowded`), from
  the Tower `saturated_niches` table with a live SERP-count fallback.
- **"Found live" freshness** — a relative timestamp on the recon, never stale-looking.

**Live theatre**
- Streaming pipeline (`see → think → verdict → check → secured → build`), a live
  "checking X of Y" counter, a coral flash when a domain is secured, inline rejection reasons.

> **Note on `tower_app.py` schema:** the widened `deliveries` columns are additive/nullable
> (safe Iceberg evolution), but if you redeploy onto the *existing* table you may want to drop
> and recreate it so the new columns appear.

---

## Setup

**Agent (Python):**
```bash
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -U tower && tower login          # serverless + lakehouse
cp ../.env.example ../.env                    # then fill in keys
python -m agent.orchestrator "an app that books last-minute dog groomers"   # full local run
```

**Web (SvelteKit):** see `web/SETUP.md`.

**Run everything (one command):** once the venv exists and `web` deps are installed,
```bash
./scripts/dev.sh
```
This boots the Python agent bridge (uvicorn on :8787), waits for it to be healthy, then starts
the web server (:5173) with `AGENT_URL` pointed at the bridge. Open http://localhost:5173.
Ctrl+C stops both. Override ports with `BRIDGE_PORT` / `WEB_PORT`.

**Offline eval:**
```bash
source agent/.venv/bin/activate && python -m agent.eval
```
Runs the grounding / score-anchoring / ownability checks with no network or API keys.
