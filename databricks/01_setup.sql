/*
 * 01_setup.sql — Nimble × Databricks integration scaffolding
 *
 * Privileges: a principal with CREATE CATALOG (or an existing catalog) +
 *             CREATE SCHEMA. Deploying the tools additionally needs
 *             CREATE FUNCTION on nimble_integration.tools.
 * Creates:    nimble_integration catalog, tools + recipes schemas.
 * Prereq:     The `nimble` secret scope + `api_key` secret exist, and the
 *             serverless networking Preview is enabled — see INSTALL.md.
 * Runtime:    ~5 seconds.
 *
 * Re-runnable. Every statement is `CREATE ... IF NOT EXISTS` so a second run
 * is a no-op.
 *
 * Run order: 01 → tools/* → (optional) recipes/*. Customize the catalog name
 * if you already have a preferred home — just replace `nimble_integration`
 * with your catalog throughout.
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
    COMMENT 'Nimble web-data integration: UC table functions wrapping Nimble APIs and agents.';

CREATE SCHEMA IF NOT EXISTS nimble_integration.tools
    COMMENT 'Table functions wrapping Nimble APIs / agents. Callable from Genie, agents, dashboards.';

CREATE SCHEMA IF NOT EXISTS nimble_integration.recipes
    COMMENT 'Sample inputs and end-to-end recipe outputs (Delta tables) built on the tools schema.';

/*
 * Note: the tools are Python UDTFs that call the Nimble API directly (the key
 * is injected from secret('nimble','api_key')), so no UC HTTP CONNECTION is
 * needed here. The optional http_request() fallback — for workspaces that
 * can't enable the serverless networking Preview — sets up its own CONNECTION;
 * see the "Optional fallback" section in ADDING_A_TOOL.md.
 */
