-- Basic nimble_agent_list patterns. Prereqs:
--   ../01_setup.sql
--   ../tools/nimble_agent_list.sql
--   ../tools/nimble_agent_list_table.sql

-- 1. Simplest TABLE-form call — Nimble-managed catalog, first 100 entries.
SELECT name, display_name, vertical, domain
FROM nimble_integration.tools.nimble_agent_list_table()
ORDER BY name;


-- 2. Filter to a specific vertical / domain client-side (the API has no
--    vertical filter — pull the list, then WHERE).
SELECT name, display_name, description
FROM nimble_integration.tools.nimble_agent_list_table()
WHERE lower(domain) LIKE '%amazon%'
   OR lower(name)   LIKE 'amazon%';


-- 3. Include community + self-managed agents too (managed_by = NULL).
SELECT name, managed_by, is_public
FROM nimble_integration.tools.nimble_agent_list_table('all', NULL, 250, 0)
ORDER BY managed_by, name;


-- 4. Scalar form for SQL composition (e.g. joining against a wanted-agents table).
WITH r AS (
    SELECT nimble_integration.tools.nimble_agent_list() AS items
)
SELECT item.name, item.entity_type, item.vertical
FROM r
LATERAL VIEW EXPLODE(items) t AS item
WHERE item.entity_type IS NOT NULL
ORDER BY item.vertical, item.name;
