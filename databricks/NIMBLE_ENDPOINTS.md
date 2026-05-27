# Nimble API endpoints — tool status

Map of public Nimble endpoints to the UC tools in this directory. Update when you add or plan a new tool.

Tool status: **shipped** (`.sql` file present + smoke-tested) · **planned** (intend to add) · **n/a** (not a fit for a UC tool).

## Agents

Live web extraction agents executed via `POST /v1/agents/run`. Full catalog at `GET /v1/agents?managed_by=nimble`. Each agent has its own input/output schema visible at `GET /v1/agents/{name}`.

| Agent              | Domain                | Status   | UC tool                                |
|--------------------|-----------------------|----------|----------------------------------------|
| `amazon_serp`      | Amazon search SERP    | shipped  | `tools/amazon_serp.sql` + `_table`     |
| `amazon_pdp`       | Amazon product page   | planned  | `tools/amazon_pdp.sql` + `_table`      |
| `amazon_plp`       | Amazon category list  | planned  | `tools/amazon_plp.sql` + `_table`      |
| `homedepot_pdp`    | Home Depot product    | planned  |                                        |
| `homedepot_serp`   | Home Depot search     | planned  |                                        |
| `kroger_pdp`       | Kroger product        | planned  |                                        |
| `kroger_serp`      | Kroger search         | planned  |                                        |
| `linkedin_company_details` | LinkedIn company  | planned  |                                        |
| `instagram_post`   | Instagram post        | planned  |                                        |
| `instagram_profile_by_account` | Instagram profile | planned |                                       |
| `instagram_reel`   | Instagram reel        | planned  |                                        |
| `iga_categories` / `iga_clp` | IGA grocery     | n/a      | low priority                          |
| `kroger_categories_extraction`, `kroger_clp`, `kroger_pdp_localization` | Kroger extras | n/a | low priority |

Each entry corresponds to a unique sub-agent — see `GET /v1/agents/{name}` for required params + output schema before writing the wrapper.

## Top-level APIs

| Endpoint                  | Purpose                              | Status  | UC tool                                  |
|---------------------------|--------------------------------------|---------|------------------------------------------|
| `POST /v1/search`         | General web search                   | shipped | `tools/nimble_search.sql` + `_table`     |
| `POST /v1/extract`        | Extract structured content from URLs | planned | `tools/nimble_extract.sql` + `_table`    |
| `POST /v1/crawl`          | Crawl a site / section               | planned | `tools/nimble_crawl.sql` (TBD signature) |
| `GET  /v1/agents`         | List available Nimble agents         | planned | `tools/nimble_agent_list.sql`            |
| `GET  /v1/agents/{name}`  | Describe one agent (input/output)    | planned | `tools/nimble_agent_describe.sql`        |
| `POST /v1/agents/batch`   | Batch agent runs                     | n/a     | needs a different table shape; defer    |
| `GET  /v1/batches/{id}`   | Batch details                        | n/a     | depends on batch tool                   |
| `GET  /v1/batches/{id}/progress` | Batch progress                | n/a     | depends on batch tool                   |

## Picking the next addition

Good rules of thumb when choosing what to add next:

1. **Pairs first**: `amazon_pdp` + `amazon_plp` round out the Amazon trio (already have `amazon_serp`); a Genie space about Amazon then has full coverage.
2. **Agent-list utility**: `nimble_agent_list` returns useful metadata — agents register more easily when Genie can introspect what's available.
3. **Search-family completeness**: `nimble_extract` is a natural companion to `nimble_search` — search returns URLs, extract returns rendered content per URL.
4. **Defer batch**: `agents/batch` doesn't fit cleanly into a single SQL function (async + later polling). Open a separate Notebook recipe under `recipes/` instead.
