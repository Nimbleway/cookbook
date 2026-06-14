-- Basic nimble_agent_describe patterns. Prereqs:
--   ../01_setup.sql
--   ../tools/nimble_agent_describe.sql
--
-- nimble_agent_describe is a table function (UDTF) — call it in the FROM clause.
-- It returns one row per INPUT parameter of a single agent, so you know what to
-- pass to nimble_agent_run (param names differ per agent).

-- 1. All input params for one agent.
SELECT param_name, required, type, is_localization_param
FROM nimble_integration.tools.nimble_agent_describe('amazon_pdp');


-- 2. Just the required params — the minimum you must supply to run it.
SELECT param_name, type
FROM nimble_integration.tools.nimble_agent_describe('amazon_serp')
WHERE required;
