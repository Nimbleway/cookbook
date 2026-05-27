/*
 * 01_setup.sql — Nimble × Databricks integration scaffolding
 *
 * Privileges: metastore admin (or a principal with CREATE CATALOG +
 *             CREATE CONNECTION privileges).
 * Creates:    nimble_integration catalog, tools + examples schemas,
 *             nimble_api UC HTTP CONNECTION bound to the secret.
 * Prereq:     The `nimble` secret scope and `api_key` secret exist —
 *             see 00_prereqs.md.
 * Runtime:    ~5 seconds.
 *
 * Re-runnable. Every statement is `CREATE ... IF NOT EXISTS` so a
 * second run is a no-op.
 *
 * Run order: 01 → 02 → (optional) examples/*. Customize the catalog
 * name if you already have a preferred home — just replace
 * `nimble_integration` with your catalog throughout.
 */

/*
 * Catalog creation. The plain form below works when your metastore has a
 * managed storage root configured at the metastore level.
 *
 * If your workspace uses Unity Catalog "Default Storage" (account-level)
 * but no metastore-level managed root, this SQL form returns:
 *
 *   "Metastore storage root URL does not exist. Default Storage is
 *    enabled in your account. You can use the UI to create a new catalog
 *    using Default Storage, or please provide a storage location for
 *    the catalog (MANAGED LOCATION '<location-path>')."
 *
 * In that case you have two equivalent options:
 *   1. Catalog Explorer UI -> Create Catalog -> "Default Storage" -> name
 *      it `nimble_integration`.
 *   2. Use the explicit form: CREATE CATALOG nimble_integration
 *        MANAGED LOCATION 's3://<bucket>/<prefix>/nimble_integration'
 *      (or the equivalent abfss:// / gs:// URI). The location must be
 *      one of your UC external locations (`SHOW EXTERNAL LOCATIONS`).
 */
CREATE CATALOG IF NOT EXISTS nimble_integration
    COMMENT 'Nimble web-data integration: UC SQL functions wrapping Nimble agents.';

CREATE SCHEMA IF NOT EXISTS nimble_integration.tools
    COMMENT 'SQL functions wrapping Nimble agents. Callable from Genie, agents, dashboards.';

CREATE SCHEMA IF NOT EXISTS nimble_integration.examples
    COMMENT 'Sample inputs / outputs and example queries against the tools schema.';

/*
 * UC HTTP connection. One per integration; every function picks the right
 * `path` argument when calling http_request(). Bearer token is resolved
 * at request time from the secret — values never appear in plan output
 * or function source.
 *
 * Egress for HTTP connections is governed by the workspace's serverless
 * network policy (account-level); on a default workspace, no extra
 * allow-listing is needed for connections.
 */
CREATE CONNECTION IF NOT EXISTS nimble_api TYPE HTTP
OPTIONS (
    host         'https://sdk.nimbleway.com',
    port         '443',
    base_path    '/',
    bearer_token secret('nimble', 'api_key')
);

-- Verify (optional):
-- DESCRIBE CONNECTION nimble_api;
