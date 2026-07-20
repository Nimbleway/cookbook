# AI Setup — MAP Compliance Monitor

You are helping the user set up and run MAP Compliance Monitor: a Nimble Web Search Agents app that discovers every online seller of a brand's SKUs across the open web, flags anyone selling below the Minimum Advertised Price, ranks repeat offenders, and files the violations into a Google Sheets tracker with a Google Doc notice per case (local fallback when Google isn't configured). Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1 — Check prerequisites

```bash
python3 --version    # need 3.10+
git --version
```

Account-level prerequisites — confirm with the user:
- **Nimble API key** (nimbleway.com) — powers the seller-discovery agent. Required.
- **Google Workspace** (optional) — to write the enforcement tracker to Google Sheets and notices to Google Docs. If the user skips this, the app writes local `.md` notices + a CSV tracker instead. Only Workspace accounts can create the **Shared Drive** the Doc notices need (a service account has no personal Drive storage).

---

## Step 2 — Clone the repo

```bash
if [ -d cookbook ]; then cd cookbook && git pull; else git clone https://github.com/Nimbleway/cookbook && cd cookbook; fi
cd apps/map-compliance-monitor
```

---

## Step 3 — Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

1–2 minutes. The Google client libraries are only needed if the user wants the Google action layer; they install regardless and are harmless if unused.

---

## Step 4 — Decide the fast path

Tell the user they have two options:
- **Just explore the results** — the repo ships a full 50-SKU demo cache. Skip to Step 8 and launch the dashboard now; no keys needed.
- **Run it live** — continue with Step 5 to run discovery against the live web.

Ask which they want.

---

## Step 5 — Get credentials

1. **NIMBLE_API_KEY** — "This runs the seller-discovery agent: one open-web run per SKU." From the Nimble dashboard at nimbleway.com.
2. **Google (optional)** — "This is where the enforcement tracker and violation notices get written. Skip it and the app writes local files instead." If the user wants it, walk them through:
   - In Google Cloud Console: create a project, enable the **Sheets**, **Docs**, and **Drive** APIs.
   - Create a **service account**, add a **JSON key**, save it as `service-account.json` in this folder.
   - Create a Google **Sheet** (the tracker) and a **Shared Drive** folder (the notices). Share **both** with the service account's email (found in the JSON as `client_email`) as **Editor / Content manager**. Shared Drive matters: a service account cannot create Docs in a normal My-Drive folder (no storage quota).
   - Grab the Sheet ID (from its URL) and the Drive folder ID (from its URL).

---

## Step 6 — Configure environment

```bash
cp .env.example .env
```

Set `NIMBLE_API_KEY`. If using Google, also set `GOOGLE_SA_JSON=./service-account.json`, `GOOGLE_SHEET_ID`, and `GOOGLE_DRIVE_FOLDER_ID`. Show the user the file and confirm before continuing.

If Google is configured, verify it before running anything:

```bash
python test_google.py    # read-only: prints the service-account email, checks the Sheet + folder are reachable
```

It must print **PREFLIGHT PASSED**. If a resource is unreachable, the user hasn't shared it with the service-account email — have them share it and rerun.

---

## Step 7 — Run the pipeline

```bash
python setup_agent.py        # ~10s; creates the agent, id saved to agents.json (idempotent)
python discover.py           # one run per SKU; resumable
```

`discover.py` is the long step: open-web discovery averages **~15–25 min per SKU**, run concurrently (default 8 at a time). The full 50-SKU catalog takes **~45–60 min**. It is resumable — if interrupted, rerun it and it re-attaches to in-flight runs and skips completed SKUs (no wasted credits). Tell the user they can run `--limit 3` first to see it work quickly. When it finishes it prints how many SKUs completed and flags any "thin" SKUs (few sellers found).

Then:

```bash
python compute_violations.py # instant: parses prices, flags below-MAP violations, builds the seller rollup
python actions.py            # writes the tracker + notices (Google if configured, else local files)
```

`compute_violations.py` prints the headline totals (listings, sellers, violations, top offender). `actions.py` prints where it wrote (Google Sheet/Docs, or `data/enforcement_tracker.csv` + `notices/`).

---

## Step 8 — Launch and orient the user

```bash
streamlit run app.py
```

Walk them through the dashboard, top to bottom:
1. **Headline KPIs** — listings scanned, unique sellers, violations, sellers in violation, and the top offender. This is the discovery fan-out: one SKU explodes into dozens of sellers
2. **Violation severity** — every violation tiered Mild (<10%) / Moderate (10–25%) / Severe (≥25%) below MAP
3. **Top 10 repeat offenders** — sellers (by domain) ranked by how many of the brand's SKUs they undercut; the enforcement priority list
4. **Violations table** — filter by brand and severity; every row links to the live listing
5. **Evidence drill-down** — pick a source (seller) then a violation; see the advertised price vs MAP, the gap, and the cited evidence excerpt behind the claim

If Google was configured, also open the user's Google Sheet (the filled tracker) and the Shared Drive folder (the Doc notices).

---

## Notes

- **Live runs vary** — which sellers surface and their prices differ run to run; the deterministic parts (price parsing, the below-MAP math, the rollup) do not
- **MAP vs MSRP** — the demo uses each product's MSRP as its MAP, so ordinary promotional pricing registers as a "violation." For real enforcement, drop in the brand's actual MAP values in `data/skus.csv`
- **Thin SKUs** — kits and bundles find fewer sellers; `discover.py` flags them. Re-run just those at higher effort: `python discover.py --skus <ids> --effort max --force`
- **Cost** — one agent run per SKU (50 for the full demo). `--limit` keeps a trial cheap
- **Seller identity is the domain** — marketplace third-party seller names are inconsistent free-text, so violations roll up per domain (the real takedown unit)
