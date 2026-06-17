# Nimble agents — discover, introspect, ingest (Genie Code, SQL-native)

The heart of the skill: find the right agents, learn their exact I/O at runtime, and load their
output into a Delta table — all via SQL against `nimble_integration.tools`. **Never hardcode an
agent's params or output from memory** — read them live. (Example trap: Amazon search wants
`keyword`, not `query`.)

## 1. Discover agents

> Agent names here (`amazon_serp`, `walmart_serp`, …) are illustrative. The catalog evolves — always
> discover names at runtime with `nimble_agent_list()` and introspect with `nimble_agent_describe`.

```sql
SELECT name, display_name, vertical, entity_type, domain
FROM nimble_integration.tools.nimble_agent_list()
WHERE lower(domain) LIKE '%amazon%' OR lower(name) LIKE '%amazon%'
ORDER BY name;
```
Match the brief's **sources** against `name`/`domain`, and pick the `entity_type` that fits the goal:
**SERP** (keyword → many product rows, best for assortment/pricing), **PDP** (per-URL detail),
**CLP/best_sellers** (category pages). For "analysis on X from <retailers>", `*_serp` is usually right.

## 2. Introspect the chosen agents — read the INPUTS

```sql
SELECT param_name, required, type, is_localization_param, is_pagination_param, default_value, examples_json
FROM nimble_integration.tools.nimble_agent_describe('amazon_serp')
ORDER BY required DESC;
```
- **The required param is your search term** — e.g. `keyword`, not `query`. Use its exact `param_name`
  when you build `params_json` in §3/§4.
- **`is_localization_param`** flags the localization input (e.g. `zip_code`); **`is_pagination_param`**
  the pagination input (e.g. `page`). `default_value` / `examples_json` give sane starting values.

Do this for **every** chosen source — param names differ across agents.

> **Output fields come from a probe, not from `describe`** (which returns inputs only). Learn the
> emitted fields by running the agent once and inspecting the payload — see §2.5.

## 2.5 Probe ONE call per source before fanning out (fail fast)

Before seeding the control table, run **one** call per source and inspect three things — it surfaces
the surprises in ~40s instead of after a wasted full round:

```sql
SELECT status,
       to_json(parsing[0]) AS first_item,            -- see the REAL field names
       parsing[0]:price, parsing[0]:product_price     -- which price field exists?
FROM nimble_integration.tools.nimble_agent_run('walmart_serp', to_json(named_struct('keyword','dog food')), true);
```
Decide, per source: (1) **localization flag** — per-agent; if `parsing` is empty, flip it and re-probe;
(2) **field names** — they vary (`price` vs `product_price`); (3) **value format** — sample a price;
some are plain numbers, others currency strings like `"$125.99"` (a bare `CAST` rejects those).

## 3. Two tables: a control table + the unified results table

Drive everything from a **control (queries) table** so the run is set-based, reproducible, and
expandable — add a row, re-run.

```sql
CREATE OR REPLACE TABLE <schema>.<table>_queries (
  source STRING, agent STRING, keyword STRING,
  params_json STRING, localization BOOLEAN, enabled BOOLEAN
);

INSERT INTO <schema>.<table>_queries VALUES
  -- localization is PER-AGENT (from the §2.5 probe): e.g. amazon_serp=true, walmart_serp=false.
  ('amazon','amazon_serp','dog food',  to_json(named_struct('keyword','dog food')),  true,  true),
  ('walmart','walmart_serp','dog food',to_json(named_struct('keyword','dog food')),  false, true);
  -- … one row per (source × term). params_json uses each agent's REAL param name.

CREATE OR REPLACE TABLE <schema>.<table> (
  source STRING, search_keyword STRING, position INT,
  product_name STRING, brand STRING, price DOUBLE, currency STRING,
  rating DOUBLE, review_count INT, sponsored BOOLEAN,
  product_url STRING, image_url STRING,
  raw VARIANT, ingested_at TIMESTAMP
) COMMENT 'Nimble demo — <brief>. Powered by Nimble.';
```
Adjust the results columns to the vertical (social → `account, post_url, likes, …`; real estate →
`address, price, beds, baths, sqft, …`). Always keep `source`, `raw`, `ingested_at`.

## 4. One set-based ingest (correlated LATERAL)

A **single INSERT** runs the agent for every enabled control row and explodes the results. Coalesce
field-name variants and use defensive numeric casts so one INSERT serves all sources.

```sql
INSERT INTO <schema>.<table>
SELECT /*+ REPARTITION(8) */   -- ≈ number of enabled rows; keep modest (high parallelism can trip 429s)
  q.source,
  q.keyword AS search_keyword,
  try_cast(v.value:position AS INT),
  CAST(coalesce(v.value:product_name, v.value:title) AS STRING) AS product_name,
  initcap(split(trim(CAST(coalesce(v.value:product_name, v.value:title) AS STRING)), ' ')[0]) AS brand,
  try_cast(regexp_replace(CAST(coalesce(v.value:price, v.value:product_price) AS STRING), '[^0-9.]', '') AS DOUBLE) AS price,
  CAST(coalesce(v.value:currency, '$') AS STRING) AS currency,
  try_cast(regexp_replace(CAST(coalesce(v.value:rating, v.value:product_rating) AS STRING), '[^0-9.]', '') AS DOUBLE) AS rating,
  try_cast(regexp_replace(CAST(coalesce(v.value:review_count, v.value:ratings_count) AS STRING), '[^0-9]', '') AS INT) AS review_count,
  try_cast(v.value:sponsored AS BOOLEAN) AS sponsored,
  CAST(coalesce(v.value:product_url, v.value:url) AS STRING) AS product_url,
  CAST(coalesce(v.value:image_url, v.value:image) AS STRING) AS image_url,
  v.value AS raw,
  current_timestamp()
FROM <schema>.<table>_queries q,
LATERAL nimble_integration.tools.nimble_agent_run(q.agent, q.params_json, q.localization) AS r,
LATERAL variant_explode(r.parsing) AS v
WHERE q.enabled AND r.status = 'success';
```
Adjust the coalesced field names to whatever §2.5 actually showed.

**Running it in Genie:** this is one long statement — **run it directly** (Genie executes it inline; no
async wrapper or CLI needed). The live agent calls take ~30–40s each; `/*+ REPARTITION(N) */` spreads
them across N Spark tasks so they run in parallel (set N ≈ enabled rows, kept modest — each task is a
live call, so very high parallelism can trip HTTP 429). For hundreds of terms, batch across runs.
A bare `CAST(v.value:price AS DOUBLE)` throws `INVALID_VARIANT_CAST` on a currency string — the
`try_cast(regexp_replace(...))` form is harmless on numeric data and saves a wasted round.

## 5. Reconcile against the control table

A term that yields no items returns an empty result, and a correlated inner `LATERAL` drops empty
rows — so reconcile to confirm every source is covered:
```sql
SELECT q.source, q.keyword, COALESCE(r.n, 0) AS rows
FROM (SELECT source, keyword FROM <schema>.<table>_queries WHERE enabled) q
LEFT JOIN (SELECT source, search_keyword AS keyword, COUNT(*) n
           FROM <schema>.<table> GROUP BY source, search_keyword) r USING (source, keyword)
ORDER BY rows;   -- any 0 = that (source,keyword) landed no items
```
If one source is 0 while another is healthy, work through: (1) **localization** flag (most common —
flip per-agent and re-run); (2) **cast failure** on a currency string; (3) **field-name mismatch**
(widen the coalesce). Re-run is cheap: fix the control row or cast and re-run the ingest (optionally
`DELETE FROM <table> WHERE source = '<that source>'` first to avoid double-counting).

## Search-term expansion
If the brief names a domain but not terms (e.g. "dog products"), expand to ~8–10 sensible
subcategories (food, treats, toys, beds, leashes, collars, crates, harness) and confirm with the user
in Phase 1 before seeding the control table.
