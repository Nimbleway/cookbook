/*
 * tools/nimble_agent_list.sql — wraps Nimble's GET /v1/agents listing endpoint
 * as a UC SQL function. Returns the catalog of agents available to the
 * caller's API key, filtered by `managed_by` / `privacy`.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools, plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.nimble_agent_list(privacy, managed_by, max_results, offset)
 *             RETURNS ARRAY<STRUCT<...>>
 * Prereq:     01_setup.sql has run successfully.
 * Runtime:    ~5 seconds to create; ~1-3s per call.
 *
 * API docs:   https://docs.nimbleway.com/api-reference/agents/list-agents
 *             (append `.md` to the URL for the plain-text spec)
 *
 * Notes on parameters:
 *   - privacy:     public | private | all. Default `public`.
 *   - managed_by:  nimble | community | self_managed. Defaults to `nimble`
 *                  because the typical "what agents can I call?" question
 *                  means the Nimble-managed catalog. Pass NULL to disable
 *                  the filter (returns every visibility).
 *   - max_results: 1..250, default 250 (API max). The API default is 100;
 *                  we widen it so a single call covers the typical catalog.
 *   - offset:      pagination offset, default 0.
 *
 * The endpoint returns a bare JSON array (no envelope). Fields come back
 * as their native JSON types (string / boolean), but we parse via the
 * all-STRING + try_cast pattern that the rest of the cookbook uses, so
 * a future server-side change to stringified booleans does not break us.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_agent_list(
    privacy     STRING DEFAULT 'public'
        COMMENT 'Privacy filter: public | private | all. Default `public`.',
    managed_by  STRING DEFAULT 'nimble'
        COMMENT 'Filter by who manages the agent: nimble | community | self_managed. Default `nimble` (Nimble-managed catalog).',
    max_results INT    DEFAULT 250
        COMMENT 'Results per page (1-250). Default 250 (API max).',
    page_offset INT    DEFAULT 0
        COMMENT 'Pagination offset (>=0). Default 0. Maps to the API `offset` query param.'
)
RETURNS ARRAY<STRUCT<
    name:         STRING,
    display_name: STRING,
    description:  STRING,
    vertical:     STRING,
    entity_type:  STRING,
    domain:       STRING,
    managed_by:   STRING,
    is_public:    BOOLEAN
>>
COMMENT 'Lists the Nimble agents available to the caller. Each entry describes one agent (name, display name, description, vertical, target entity / domain, managed_by, is_public). Useful to discover what `agent` names can be passed to /v1/agents/run, or to enumerate the catalog for a Genie space.'
RETURN (
    SELECT COALESCE(
        transform(
            from_json(
                response.text,
                'ARRAY<STRUCT<
                    name STRING,
                    is_public STRING,
                    display_name STRING,
                    description STRING,
                    vertical STRING,
                    entity_type STRING,
                    domain STRING,
                    managed_by STRING
                >>'
            ),
            x -> named_struct(
                'name',         x.name,
                'display_name', x.display_name,
                'description',  x.description,
                'vertical',     x.vertical,
                'entity_type',  x.entity_type,
                'domain',       x.domain,
                'managed_by',   x.managed_by,
                'is_public',    try_cast(x.is_public AS BOOLEAN)
            )
        ),
        ARRAY()
    )
    FROM (
        SELECT http_request(
            conn    => 'nimble_api',
            method  => 'GET',
            path    => '/v1/agents',
            /*
             * GET query params go through the dedicated `params` map,
             * not the path. Embedding `?foo=bar` directly in `path`
             * makes the UC HTTP connection return 404. NULLs are
             * dropped via map_filter so callers can omit a filter
             * (e.g. managed_by => NULL to list every catalog).
             */
            params  => map_filter(
                map(
                    'privacy',    privacy,
                    'managed_by', managed_by,
                    'limit',      cast(max_results AS STRING),
                    'offset',     cast(page_offset AS STRING)
                ),
                (k, v) -> v IS NOT NULL
            ),
            headers => map('Content-Type', 'application/json')
        ) AS response
    )
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT size(nimble_integration.tools.nimble_agent_list()) AS n;
