### Nimble Web Search Integration

This workspace provides Nimble's live-web capabilities through Unity Catalog **table functions**. Call them in the FROM clause.

#### Discovering Functions

**Always check function details first:**

    DESCRIBE FUNCTION EXTENDED function_name

This shows input parameters (with allowed values, examples, defaults) and return columns with descriptions.

#### Core Functions

**1. General Web Search**

    SELECT * FROM nimble_integration.tools.nimble_search('query', 10, 'general', 'lite')

Parameters: query, max_results (1-100), focus (general|news|shopping|academic|social|coding|geo|location), search_depth (lite|fast|deep). Returns: `title`, `description`, `url`, `content`.

**2. Extract a Page**

    SELECT * FROM nimble_integration.tools.nimble_extract('https://example.com', TRUE, 'markdown')

Parameters: url, render (boolean), format (markdown|html|links). Returns one row: `url`, `format`, `content`.

**3. List Available Agents**

    SELECT * FROM nimble_integration.tools.nimble_agent_list()

Returns the Nimble agent catalog (e-commerce, Google Maps, LinkedIn, etc.), one row per agent: `name`, `display_name`, `description`, `vertical`, `entity_type`, `domain`, `managed_by`, `is_public`.

**4. Describe an Agent's Inputs**

    SELECT param_name, required, type, is_localization_param
    FROM nimble_integration.tools.nimble_agent_describe('amazon_serp')

Returns one row per input parameter of a single agent: `param_name`, `required`, `type`, `description`, `is_localization_param`, `is_pagination_param`, `default_value`, `examples_json`, plus the agent's `vertical`/`entity_type`/`domain` and `is_localization_supported`/`is_pagination_supported` repeated on each row. Use it to build a valid `nimble_agent_run` `params_json` without guessing param names (they differ per agent — Amazon search wants `keyword`, not `query`). Output fields are not returned here — run the agent once and inspect `to_json(parsing[0])` for those.

**5. Run Any Agent**

    SELECT * FROM nimble_integration.tools.nimble_agent_run('agent_name', '{"param":"value"}', FALSE)

Parameters: agent name, params as JSON string, optional localization boolean. Returns one row: `status`, `status_code`, `url`, `parsing_json` (the per-agent payload as raw JSON), `query_time`, `driver`, `query_duration_ms`, `warnings`.

#### Parsing Agent Results

`parsing_json` from `nimble_agent_run()` holds the per-agent payload. Parse it with `from_json` against an agent-specific schema, then `LATERAL VIEW explode()` to flatten arrays:

    WITH raw AS (
      SELECT parsing_json
      FROM nimble_integration.tools.nimble_agent_run('amazon_serp', '{"keyword":"cookies","page":1}')
    )
    SELECT from_json(parsing_json, 'array<struct<product_name:string, price:string>>') AS data
    FROM raw

#### Best Practices

1. Run `DESCRIBE FUNCTION EXTENDED` first to see parameter options and examples.
2. Use `nimble_search` for open-web questions; `nimble_extract` when you already have a URL.
3. Check `nimble_agent_list()` to discover agents, then `nimble_agent_describe('<agent>')` to learn its exact input params, before calling `nimble_agent_run()`.
4. Parse `parsing_json` carefully — schemas are agent-specific.
