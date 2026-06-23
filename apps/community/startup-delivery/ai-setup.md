# AI Setup Instructions — Startup.Delivery

You are helping the user set up and run Startup.Delivery — a 4-step AI pipeline that takes a startup idea and returns a brand name, a real available domain, a live competitor brief, and a go/no-go verdict. Follow these steps in order. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

Run each of the following checks. If any fail, install the missing dependency before continuing.

**Python 3.11+**
```bash
python3 --version
```
If missing or below 3.11: direct the user to https://python.org/downloads

**Node.js 18+** (required for the web frontend)
```bash
node --version
```
If missing: direct the user to https://nodejs.org

**git**
```bash
git --version
```
If missing: direct the user to https://git-scm.com

---

## Step 2: Clone the repo

Check whether the repo is already cloned locally:

```bash
ls startup-delivery
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd startup-delivery
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/aryarahimi1/startup-delivery
cd startup-delivery
```

---

## Step 3: Set up the Python agent

```bash
cd agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## Step 4: Get API keys

Ask the user which keys they already have. They need all three to run the full pipeline.

**Nimble API key** — used for live competitor recon (Step 1: SERP + Extract)
Get one at: https://nimbleway.com

**name.com credentials** — used for real domain availability + pricing (Step 3)
The app requires a name.com account with a **production** API token (not the sandbox).
Get one at: https://www.name.com/reseller (or their existing account settings)
Tell the user: the production API is required — the sandbox reports registered domains like google.com as available, which defeats the purpose.

**OpenRouter API key** — used for gap analysis, name generation, and the verdict (Steps 2 and 4)
Get one at: https://openrouter.ai/keys

---

## Step 5: Configure environment

From the repo root:

```bash
cp .env.example .env
```

Open `.env` and fill in the user's keys:
```
NIMBLE_API_KEY=their_nimble_key_here
NAMECOM_USERNAME=their_namecom_username_here
NAMECOM_API_TOKEN=their_namecom_token_here
NAMECOM_API_BASE=https://api.name.com
OPENROUTER_API_KEY=their_openrouter_key_here
OPENROUTER_MODEL=anthropic/claude-sonnet-4
```

Tell the user: `NAMECOM_API_BASE` must be `https://api.name.com` (production). If they see a warning about the domain source being "sandbox", their token or username is pointed at the test environment.

---

## Step 6: Choose a path

Ask the user:

> "You can run the agent from the command line to test a single idea, or spin up the full web app with the streaming pipeline UI. Which would you prefer?
>
> A) Command-line: test one idea, see the full JSON output
> B) Full web app: streaming UI with domain check visualization, delivery history, and the Loading Dock"

**If they choose A** — go to Step 7 (CLI run).

**If they choose B** — go to Step 8 (Full web app).

---

## Step 7: CLI run (Path A)

Make sure the venv is active, then run:

```bash
source agent/.venv/bin/activate
python -m agent.orchestrator "your startup idea here"
```

Replace the idea with anything — for example:
```bash
python -m agent.orchestrator "an app that books last-minute dog groomers"
```

Tell the user: the pipeline will print live progress (see → think → check → secured) and output the full `DeliveryPackage` JSON. Nimble results are cached — re-running the same idea skips the live web calls and uses the disk cache.

To run the offline eval (no network or API keys needed):
```bash
python -m agent.eval
```
This checks grounding, score anchoring, and domain ownability logic offline.

---

## Step 8: Full web app (Path B)

Install web dependencies:
```bash
cd web
npm install
cd ..
```

Copy the web environment file:
```bash
cp web/.env.example web/.env
```

Open `web/.env` and set:
```
AGENT_URL=http://127.0.0.1:8787
```

Start everything with one command (from the repo root, with the venv active):
```bash
source agent/.venv/bin/activate
./scripts/dev.sh
```

This boots the Python agent bridge on port 8787 and the SvelteKit web app on port 5173. Open http://localhost:5173.

To stop both: Ctrl+C.

**UI-only mode** (no agent bridge — demo/scripted replay only):
```bash
cd web && MOCK=1 npm run dev
```
Add `?demo=1` to the URL for a scripted replay that runs without any API calls.

---

## Step 9: Orient the user

Walk the user through the main features:

**Main page** — enter a one-sentence startup idea (up to 300 characters). The pipeline streams live: competitor recon → gap analysis → name generation → domain checks (with a live "N checked · M taken · 1 secured" counter) → verdict.

**The delivery package** — after the run:
- **Verdict** — build / pivot / pass + a 0-100 opportunity score at the top
- **Domain** — the secured domain (`.delivery`-first across 6 TLDs) with real price and renewal cost
- **Competitor brief** — live competitors with positioning, detected pricing, and a cited market summary
- **Positioning gap** — what the market is missing
- **TLD grid** — all checked TLDs per name: green (available + price) or TAKEN stamp
- **Launch kit** — defensive domain bundle (.com + get-/try- prefixes)
- **Landing page** — click "Build landing page" to generate one from the real recon

**Remix** — one click suggests 3 adjacent angles to explore (narrower audience, different model, opposite price tier).

**Loading Dock** (`/dock`) — a public gallery of all past deliveries from the local JSONL log.

**Delivery permalinks** — every delivery has a shareable URL (`/d/{tracking-id}`) and a copyable JSON receipt.

**Receipt** — one click generates a PNG share card (brand, domain, verdict, tracking number).

---

## Notes

- Nimble results are cached to disk by a stable key (hash of the idea and URL). Reruns within 7 days hit disk and never re-burn quota. Override TTL with `NIMBLE_CACHE_TTL_SECONDS`.
- The LLM model is swappable: change `OPENROUTER_MODEL` in `.env` to any OpenRouter-supported model (e.g. `google/gemini-2.5-pro-preview`, `openai/gpt-4.1`).
- To enable an experimental agentic loop mode where the LLM drives the pipeline with tool calls, set `AGENT_LOOP=1`. It falls back to the deterministic pipeline automatically on any failure.
- The agent bridge can be deployed to Fly.io (`fly.toml` is included) and the web frontend to Vercel (`web/svelte.config.js` uses the Vercel adapter).
