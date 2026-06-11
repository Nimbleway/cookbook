-- Basic nimble_agent_list patterns. Prereqs:
--   ../01_setup.sql
--   ../tools/nimble_agent_list.sql
--
-- nimble_agent_list is a table function (UDTF) — call it in the FROM clause.

-- 1. Nimble-managed catalog (defaults), sorted by name.
SELECT name, display_name, vertical, domain
FROM nimble_integration.tools.nimble_agent_list()
ORDER BY name;


-- 2. Filter to a specific vertical / domain client-side (the API has no
--    vertical filter — pull the list, then WHERE).
SELECT name, display_name, description
FROM nimble_integration.tools.nimble_agent_list()
WHERE lower(domain) LIKE '%amazon%'
   OR lower(name)   LIKE 'amazon%';


-- 3. Include community + self-managed agents too (managed_by = NULL).
SELECT name, managed_by, is_public
FROM nimble_integration.tools.nimble_agent_list('all', NULL, 250, 0)
ORDER BY managed_by, name;


-- 4. Join the catalog against a table of agents you care about.
WITH wanted AS (
    SELECT explode(array('amazon_serp', 'google_maps_search', 'linkedin_company_details')) AS name
)
SELECT a.name, a.vertical, a.entity_type
FROM nimble_integration.tools.nimble_agent_list('all', NULL, 250, 0) a
JOIN wanted w USING (name)
ORDER BY a.name;
