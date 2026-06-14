# Deliverables — what to tell Genie's native dashboard agent and AppsAgent

Genie Code builds both deliverables **natively** from plain-English intent — you describe **what**,
the specialized agents assemble it. **Do not hand-write Lakeview JSON or scaffold app files yourself.**

- **Dashboard** → Genie's built-in **dashboard agent**: creates the dashboard, builds datasets from a
  UC table, adds widgets, renders them, and publishes.
- **App** → Genie's **AppsAgent**: `create a Databricks App`, then the AppsAgent scaffolds and
  deploys it. **Default to a Python framework** (Streamlit / Dash / Gradio) — the native path for Genie
  Code apps, fast and reliable for a demo. React is supported too and runs build-less (React from a
  CDN, inline) — choose it only when the user wants a richer UI.

## Per-vertical widget / view sets

Pick by the matched agents' `vertical` / `entity_type` — this drives both the dashboard widgets and
the app's views:

| Vertical | Views to request |
|----------|------------------|
| **Ecommerce** (SERP/PDP/CLP) | KPIs (product count, avg price); avg price & listing count by source/keyword; sponsored share; price-vs-rating scatter; product table with Open links; **multi-source → comparison bars + best-effort item-level price gap** |
| **Social** | volume/engagement by account/post; top-content table; like/follower distributions |
| **Real Estate** | price & price/sqft; listings by location; beds/baths breakdowns |
| **Maps / Local** | avg rating; review counts; places table with links |
| **LLM / AEO** | source/answer presence; share-of-voice; citation table |
| **_fallback_** | KPIs + 2 categorical bars + the raw table (works off any schema) |

**Comparison depth (multi-source):** always include the aggregate comparison (avg price/rating by
source); *additionally* attempt item-level matching (normalize brand + key tokens) and, if confident,
add a "same-product price gap" view — otherwise keep the aggregate and note matching wasn't confident.

## Dashboard — how to hand it off

Instruct the dashboard agent with the **source table**, the **widgets** (above), and **branding**.
Example:

> Build an AI/BI dashboard named "🐶 Dog Products: Amazon vs Walmart · Powered by Nimble" on
> `users.<me>.dog_products`. Add: KPI counters for product count and average price; a bar of average
> price by source; a price-vs-rating scatter colored by source; a comparison bar of average price per
> keyword across sources; and a product table (name, source, price, rating) with the URL as a
> clickable Open link. Add a markdown text widget at the top reading "_Live web data · **Powered by
> Nimble**_". Use Nimble yellow (#F2F23B) as the primary series accent on a light theme. Then publish.

The agent reads the table schema itself — don't pre-declare datasets. Confirm it published; grab the link.

## App — how to hand it off

Only if the user chose the **+app** deliverable. Create the app, then let the AppsAgent scaffold +
deploy. Example:

> Create a Databricks App named "nimble-dog-products". Scaffold a minimal Streamlit (or Dash) app that
> queries `users.<me>.dog_products` and shows: KPI metrics (product count, avg price), an average-price-
> by-source bar, a price-vs-rating scatter, and a searchable product table with clickable URLs. Brand
> it "Powered by Nimble" — light theme, a header with the wordmark, Nimble yellow (#F2F23B) accent.
> Deploy it and give me the URL.

The AppsAgent owns the scaffold (`app.py`, `app.yaml`), the SQL-warehouse wiring, and the deploy — you
supply the table, the views (per-vertical, above), and the branding (`references/branding.md`).
Confirm it reached **RUNNING** and collect the URL.

**Framework note:** default to **Python** (Streamlit / Dash / Gradio) — the native path, fastest and
most reliable for a demo. React is supported too and runs build-less (CDN-inline); choose it only when
the user wants a richer UI.

## Notes

- If a widget/view comes out wrong (e.g. a currency-string price treated as text), the fix is upstream:
  the defensive numeric cast in the ingest (`references/nimble-agents.md` §4), not the deliverable.
- App vs dashboard is the user's per-run choice (Phase 1). A dashboard is the fast default; an app is
  the richer, interactive "never leave Databricks" deliverable.
