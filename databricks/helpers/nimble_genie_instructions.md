### Nimble Web Data Integration

This workspace provides Nimble's web scraping capabilities through SQL functions.

#### Discovering Functions

**Always check function details first:**

    DESCRIBE FUNCTION EXTENDED function_name

This shows:
- Input parameters with comments explaining allowed values, examples, and defaults
- Return columns with descriptions
- Overall usage guidance and example questions

#### Core Functions

**1. List Available Agents**

    SELECT * FROM nimble_integration.tools.nimble_agent_list_table()

Returns the full Nimble catalog (dozens of agents) covering e-commerce (Amazon, Walmart, Target, Best Buy), Google Maps, LinkedIn, etc.

**2. Get Agent Details**

    SELECT * FROM nimble_integration.tools.nimble_agent_describe_table('agent_name')

Returns input parameters and output schema for a specific agent.

**3. Run Any Agent**

    SELECT * FROM nimble_integration.tools.nimble_agent_run_table('agent_name', '{"param":"value"}', FALSE)

Parameters: agent name, params as JSON string, optional localization boolean.
Returns: `status`, `url`, `parsing_json` (contains results as JSON), `query_time`, etc.

**4. General Web Search**

    SELECT * FROM nimble_integration.tools.nimble_search_table('query', 10, 'general', 'fast')

Parameters: query string, max_results (1-100), focus (general|news|shopping|academic|etc), search_depth (lite|fast|deep).
Returns: `title`, `description`, `url`, `content`

**5. Amazon Search (Typed)**

    SELECT * FROM nimble_integration.tools.amazon_serp_table('keyword')

Returns structured results with SQL types (no JSON parsing): `product_name`, `asin`, `price`, `rating`, etc.

#### Key Agents

- **google_maps_search**: Local businesses, schools, restaurants by location
- **google_maps_reviews**: Extract Google Maps reviews
- **amazon_pdp**: Amazon product detail pages
- **google_search**: General Google search results

#### Parsing Agent Results

Results from `nimble_agent_run_table()` are in `parsing_json` as `{"entities": {"SearchResult": [...]}}`:

    WITH parsed AS (
      SELECT get_json_object(`parsing_json`, '$.entities.SearchResult') as results
      FROM nimble_integration.tools.nimble_agent_run_table('agent_name', '{"param":"value"}')
    )
    SELECT from_json(results, 'array<struct<field1:string, field2:string>>') as data
    FROM parsed

Use `LATERAL VIEW explode()` to flatten arrays.

#### Best Practices

1. Run `DESCRIBE FUNCTION EXTENDED` first to see parameter options and examples
2. Use typed wrappers (like `amazon_serp_table`) when available - they return SQL types instead of JSON
3. Check `nimble_agent_list_table()` to discover available agents
4. Parse `parsing_json` carefully - schemas are agent-specific
