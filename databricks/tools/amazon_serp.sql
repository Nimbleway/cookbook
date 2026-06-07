/*
 * tools/amazon_serp.sql — wraps Nimble's amazon_serp agent as a UC SQL function.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools, plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.amazon_serp(keyword STRING)
 *             RETURNS ARRAY<STRUCT<...>>
 * Prereq:     01_setup.sql has run successfully.
 * Runtime:    ~5 seconds to create; ~5-15s per call depending on Amazon.
 *
 * Agent docs: https://docs.nimbleway.com/api-reference/agents/run-agent
 *
 * The COMMENT below is the Nimble-provided agent description, verbatim.
 * LLM-driven Genie / Mosaic-AI agents read this string to decide whether
 * to call the function. Keep it accurate when refreshing.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.amazon_serp(
    keyword STRING COMMENT 'Amazon search keyword, e.g. "wireless headphones"'
)
RETURNS ARRAY<STRUCT<
    product_name:   STRING,
    asin:           STRING,
    price:          DOUBLE,
    currency:       STRING,
    rating:         DOUBLE,
    product_url:    STRING,
    image_url:      STRING,
    prime_eligible: BOOLEAN,
    amazons_choice: BOOLEAN,
    sponsored:      BOOLEAN,
    store_location: STRING,
    position:       INT,
    agent_zip_code: STRING
>>
COMMENT 'The Amazon Search agent extracts structured data from Amazon''s search results pages based on a given keyword. This agent is ideal for search visibility analysis, assortment tracking, and keyword-based product monitoring across Amazon''s marketplace.'
RETURN (
    /*
     * Nimble ships every field as a JSON string ("price":"23.76",
     * "sponsored":"true"). We parse with an all-STRING from_json schema
     * and try_cast into the declared numeric / boolean return types so
     * callers see proper SQL types.
     *
     * http_request() does NOT raise on non-2xx — it returns the status
     * code in response.status_code and the error body in response.text.
     * Gate on a 2xx status, raise_error otherwise, so a failed Nimble
     * call surfaces as a real query error instead of an empty array.
     */
    SELECT CASE
        WHEN response.status_code BETWEEN 200 AND 299 THEN
            COALESCE(
                transform(
                    from_json(
                        response.text,
                        'STRUCT<data: STRUCT<parsing: ARRAY<STRUCT<
                            product_name STRING,
                            asin STRING,
                            price STRING,
                            currency STRING,
                            rating STRING,
                            product_url STRING,
                            image_url STRING,
                            prime_eligible STRING,
                            amazons_choice STRING,
                            sponsored STRING,
                            store_location STRING,
                            position STRING,
                            agent_zip_code STRING
                        >>>>'
                    ).data.parsing,
                    x -> named_struct(
                        'product_name',   x.product_name,
                        'asin',           x.asin,
                        'price',          try_cast(x.price          AS DOUBLE),
                        'currency',       x.currency,
                        'rating',         try_cast(x.rating         AS DOUBLE),
                        'product_url',    x.product_url,
                        'image_url',      x.image_url,
                        'prime_eligible', try_cast(x.prime_eligible AS BOOLEAN),
                        'amazons_choice', try_cast(x.amazons_choice AS BOOLEAN),
                        'sponsored',      try_cast(x.sponsored      AS BOOLEAN),
                        'store_location', x.store_location,
                        'position',       try_cast(x.position       AS INT),
                        'agent_zip_code', x.agent_zip_code
                    )
                ),
                ARRAY()
            )
        ELSE raise_error(concat(
            'Nimble /v1/agents/run (amazon_serp) failed with status ',
            cast(response.status_code AS STRING), ': ', response.text
        ))
    END
    FROM (
        SELECT http_request(
            conn    => 'nimble_api',
            method  => 'POST',
            path    => '/v1/agents/run',
            headers => map(
                'Content-Type',    'application/json',
                'X-Client-Source', 'nimble-dbx-udf'
            ),
            json    => to_json(named_struct(
                'agent',  'amazon_serp',
                'params', named_struct('keyword', keyword, 'page', 1)
            ))
        ) AS response
    )
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT size(nimble_integration.tools.amazon_serp('cookies')) AS n;
