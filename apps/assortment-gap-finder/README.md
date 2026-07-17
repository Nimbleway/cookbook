# assortment-gap-finder — Assortment Gap Finder

Retail category in, verified assortment gaps out — filed as Linear tickets a merchandiser can act on. Three research agents built on [Nimble](https://nimbleway.com) Web Search Agents discover the full catalog of a category (300+ SKUs), mine customer reviews for verbatim complaint themes, and verify every hypothesized gap against a retailer's live shelf before anything gets filed. The catalog lives in Databricks Delta tables; a Claude agent loop owns the judgment.

![Built with Nimble + Databricks](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20Databricks-edc602)

## What it does

1. **Discover** — a dataset_building agent enumerates the category on a retailer, chunked by subcategory (6 runs → 300+ distinct SKUs after dedup); a hard source whitelist keeps every run on-shelf
2. **Map whitespace** — pure SQL over the catalog: a subcategory × price-band grid exposing empty cells (assortment gaps) and cells where nothing is well-rated (quality gaps) — zero API calls
3. **Mine demand** — an enrichment agent reads customer reviews for the top products around flagged cells and returns recurring complaint/praise themes with verbatim quotes and review-page URLs
4. **Synthesize & verify** — a Claude agent loop (OpenAI Agent SDK + LiteLLM) proposes gap hypotheses where the math and the complaints agree, then a max-effort research agent searches the retailer's live shelf for counterexamples: one in-stock counterexample refutes the gap
5. **Act** — confirmed and partial gaps are filed as Linear issues with the demand quotes, the live-shelf evidence, and the closest existing products
6. **Learn** — merchandising rules taught in the UI PATCH the verifier agent permanently and steer the synthesis loop

## Stack

- [Nimble Web Search Agents](https://nimbleway.com) — three agents: catalog discovery (dataset_building), review mining (enrichment), whitespace verification (research)
- [Databricks](https://databricks.com) — Delta tables for the catalog, themes, gaps, and run checkpoints
- [OpenAI Agent SDK](https://github.com/openai/openai-agents-python) + [LiteLLM](https://litellm.ai) — the synthesis loop, running [Claude](https://anthropic.com)
- [Linear](https://linear.app) — where verified gaps land as tickets
- [Streamlit](https://streamlit.io) — catalog, gap board, customer evidence, teach page

## Setup

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/assortment-gap-finder
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```

Keys you need: `NIMBLE_API_KEY` ([nimbleway.com](https://nimbleway.com)), Databricks host + personal access token + SQL warehouse HTTP path, a Linear API key + team key, and `ANTHROPIC_API_KEY`. See `.env.example` comments for where each lives.

Then, in order:

```bash
python setup_agents.py   # creates the 3 Web Search Agents (once; ids in agents.json)
python delta.py          # creates the Delta schema + 5 tables (idempotent)
python discover.py       # 6 discovery runs, ~50 min, resumable -> 300+ SKU catalog
python gaps.py           # whitespace report (instant, no API calls)
python mine.py           # review mining on flagged cells, ~15-25 min
python synth.py          # the agent loop: verify gaps live + file Linear tickets, ~30-60 min
streamlit run app.py
```

## Usage

Open the app → **Catalog & whitespace** shows the SKU table and the gap grid. **Customer evidence** shows the verbatim complaints behind each flagged cell. **Gap board** shows every verdict — confirmed/partial gaps link to their Linear tickets; refuted hypotheses show the counterexample that killed them. **Teach the analyst** adds a merchandising rule that permanently updates the verifier agent.

To point it at a different category, change `CATEGORY` and `CHUNKS` in `config.py` and rerun the pipeline.

## Project structure

```
├── config.py          # category, chunk matrix, price bands, env
├── setup_agents.py    # creates the 3 agents (full smoke-validated configs inline)
├── wsa.py             # Web Search Agents client (poll + 408-retry + per-run source overrides)
├── delta.py           # Databricks connection, schema DDL, insert/query helpers
├── discover.py        # chunked catalog discovery: resumable, deduped by canonical product id
├── gaps.py            # whitespace math over the catalog (SQL only)
├── mine.py            # targeted review mining for flagged cells
├── synth.py           # Claude agent loop: synthesize -> verify live -> file tickets
├── linear_client.py   # Linear GraphQL: issue creation with full evidence body
├── app.py             # Streamlit UI (5 pages)
└── data/sample_run/   # verbatim agent results: one discovery chunk + one live verification
```

## Output

`<catalog>.assortment_gap_finder` Delta tables:

| table | contents |
|---|---|
| `catalog` | one row per distinct SKU: name, brand, subcategory, parsed price/rating/reviews + verbatim strings, URLs, provenance |
| `review_themes` | one row per (product, theme): kind, theme, verbatim quote, review-page URL |
| `gaps` | one row per verified hypothesis: statement, verdict, demand evidence, live-shelf evidence, closest matches, Linear issue id/URL, interaction id |
| `discovery_runs` | run checkpoints (the resumable loop reads this) |
| `merch_rules` | taught rules, timestamped |

## Going further

- **Multi-retailer discovery** — the discovery agent takes per-run source overrides; add Walmart/Target chunks to `config.CHUNKS` with their own whitelists
- **Follow-up questions** — each gap stores its verification `interaction_id`; run follow-ups on the verifier agent with `previous_interaction_id` to interrogate a verdict
- **Different category** — the agents are category-agnostic; only `config.py` changes

## Notes

- Verification is deliberately adversarial: the verifier is instructed that a single in-stock counterexample refutes a gap, and to distinguish "not found after thorough search" from "confirmed absent"
- Dataset_building runs occasionally fail with "array output is empty" — the discovery loop retries; rerunning `discover.py` skips completed chunks
- `litellm[proxy]` is required even though the app never runs a proxy: LiteLLM's tool-calling path imports proxy modules it does not declare
- Databricks returns lowercase column names (Snowflake uppercases) — the app normalizes to uppercase internally
