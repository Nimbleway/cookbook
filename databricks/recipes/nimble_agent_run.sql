-- Basic nimble_agent_run patterns. Prereqs:
--   ../01_setup.sql
--   ../tools/nimble_agent_run.sql
--
-- nimble_agent_run is a table function (UDTF) — call it in the FROM clause.
-- It returns one row: the response envelope plus the parsed payload as a
-- raw JSON STRING (parsing_json).

-- 1. Run an agent, see the envelope.
SELECT status, status_code, driver, query_duration_ms
FROM nimble_integration.tools.nimble_agent_run(
    'amazon_serp',
    '{"keyword":"cookies","page":1}'
);


-- 2. Pull the parsed payload as a raw JSON STRING and inspect length.
SELECT status, length(parsing_json) AS bytes
FROM nimble_integration.tools.nimble_agent_run(
    'amazon_serp',
    '{"keyword":"wireless headphones","page":1}'
);


-- 3. Project the parsed payload into typed columns using the per-agent schema.
--    This is the pattern for any agent driven through the generic runner.
WITH raw AS (
    SELECT parsing_json
    FROM nimble_integration.tools.nimble_agent_run(
        'amazon_serp',
        '{"keyword":"running shoes","page":1}'
    )
),
parsed AS (
    SELECT from_json(
        parsing_json,
        'ARRAY<STRUCT<
            product_name STRING,
            asin STRING,
            price STRING,
            currency STRING,
            rating STRING,
            position STRING
        >>'
    ) AS items
    FROM raw
)
SELECT
    item.product_name,
    item.asin,
    try_cast(item.price    AS DOUBLE) AS price,
    item.currency,
    try_cast(item.rating   AS DOUBLE) AS rating,
    try_cast(item.position AS INT)    AS position
FROM parsed
LATERAL VIEW EXPLODE(items) t AS item
ORDER BY position;


-- 4. Localized request (zip_code-aware agents) — pass localization=TRUE.
SELECT status, status_code
FROM nimble_integration.tools.nimble_agent_run(
    'amazon_serp',
    '{"keyword":"coffee maker","page":1,"zip_code":"94105"}',
    TRUE
);
