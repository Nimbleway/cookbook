# AI Setup — Influencer Finder

You are helping the user set up and run Influencer Finder: a Nimble Web Search Agents app that discovers influencers matching a niche + platform + follower band + geography, accumulates them into a Supabase table across queries, and shows a filterable dashboard with CSV export. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1 — Check prerequisites

```bash
python3 --version    # need 3.10+
git --version
```

Credentials:
- **Nimble API key** (nimbleway.com) — required, runs the discovery agent.
- **Supabase** (optional) — a project URL + service_role key to use the live backend. Without it, the app uses the local cache.

---

## Step 2 — Clone the repo

```bash
if [ -d cookbook ]; then cd cookbook && git pull; else git clone https://github.com/Nimbleway/cookbook && cd cookbook; fi
cd apps/influencer-finder
```

---

## Step 3 — Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## Step 4 — Fast path vs live

Tell the user:
- **Just explore the dataset** — the repo ships 120 cached influencers. Skip to Step 8 and launch the dashboard now; no keys needed.
- **Run discovery live** — continue with Step 5.

---

## Step 5 — Get the Nimble key (and optionally Supabase)

```bash
cp .env.example .env
```

Set `NIMBLE_API_KEY`. For the live Supabase backend, also:
1. Create the table: open the Supabase SQL editor and run the contents of `schema.sql` (creates the `influencers` table). Show the user the file to paste.
2. Set `SUPABASE_URL` and `SUPABASE_KEY` (service_role) in `.env`.

If the user skips Supabase, the app uses `data/influencers.json` automatically.

---

## Step 6 — Create the agent

```bash
python setup_agent.py    # ~10s; id saved to agents.json (idempotent)
```

---

## Step 7 — Run discovery

Edit `data/queries.txt` (one query per line: niche + platform + follower band + geography), then:

```bash
python discover.py
```

Each query runs ~15-20 min and returns ~5-15 creators; the app accumulates and dedupes across queries. It is resumable (reruns skip completed queries, retry failed ones). Tell the user a single query is a good quick test: `python discover.py --query "..."`. When it finishes it reports the total distinct influencers and whether they went to Supabase or the local cache.

---

## Step 8 — Launch the dashboard

```bash
streamlit run app.py
```

Walk the user through it:
1. The header shows total influencers, platforms, and categories
2. Filter by **platform**, **category**, and a **min-followers (K)** slider
3. Every row links to the creator's profile; the current view exports to CSV with the download button

---

## Notes

- **A single query returns ~5-15 creators** — the dataset grows by running many queries; the shipped cache is 15 queries → 120 creators
- **Supabase optional** — the app falls back to the local cache if the table or creds are missing; run `schema.sql` once to enable the live backend
- **Standardized** — follower counts render in K/M form, platform casing is normalized
- **Public contact only** — a business email appears only when the creator lists one publicly
- **Live runs vary** — which creators surface differs run to run; dedup and parsing are deterministic
