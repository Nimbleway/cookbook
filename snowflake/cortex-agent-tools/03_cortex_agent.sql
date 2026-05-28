/*
 * cortex-agent-tools/03_cortex_agent.sql — registers a Cortex Agent backed by NIMBLE_SEARCH + NIMBLE_EXTRACT
 *
 * Role:        NIMBLE_ROLE
 * Creates:     NIMBLE_INTEGRATION.AGENTS.NIMBLE_WEB_RESEARCH_AGENT
 * Prereq:      setup/setup.sql plus 01_nimble_search.sql and 02_nimble_extract.sql in this directory.
 *              SNOWFLAKE.CORTEX_USER granted to NIMBLE_ROLE.
 * Runtime:     ~3 seconds.
 *
 * Reference:   https://docs.snowflake.com/en/sql-reference/sql/create-agent
 *              https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api
 *
 * Usage (via Cortex Agents REST API or Snowsight UI):
 *   - Ask a research question; the agent decides whether to call NIMBLE_SEARCH
 *     to find sources, then NIMBLE_EXTRACT to read individual pages.
 *   - Outputs cite source URLs from the tool responses.
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;
USE SCHEMA NIMBLE_INTEGRATION.AGENTS;

CREATE OR REPLACE AGENT NIMBLE_INTEGRATION.AGENTS.NIMBLE_WEB_RESEARCH_AGENT
WITH PROFILE = '{ "display_name": "Nimble Web Research Agent" }'
COMMENT = 'Live-web research agent powered by Nimble Search + Extract.'
-- NOTE: tool_resources is a TOP-LEVEL field per the CREATE AGENT spec, not nested under each tools[] entry.
FROM SPECIFICATION $$
{
  "models": {
    "orchestration": "auto"
  },
  "instructions": {
    "response": "You are a research assistant with live access to the public web through two tools: nimble_search (finds relevant URLs and snippets) and nimble_extract (reads full page content from a single URL). For any factual question, plan with nimble_search first, then read the most promising 1-3 results with nimble_extract before answering. Always cite source URLs inline.",
    "orchestration": "Prefer nimble_search for discovery and recency-sensitive queries. Use nimble_extract only when the search snippets are insufficient. Do not call nimble_extract on more than 3 URLs per question."
  },
  "tools": [
    {
      "tool_spec": {
        "type": "generic",
        "name": "nimble_search",
        "description": "Search the live web for pages relevant to a query. Returns titles, URLs, and content snippets.",
        "input_schema": {
          "type": "object",
          "properties": {
            "query":         { "type": "string",  "description": "The search query." },
            "max_results":   { "type": "integer", "description": "How many results to return.", "default": 10 },
            "focus":         { "type": "string",  "description": "general | news | location | coding | geo | shopping | social | academic" },
            "search_depth":  { "type": "string",  "description": "lite | fast | deep", "default": "fast" }
          },
          "required": ["query"]
        }
      }
    },
    {
      "tool_spec": {
        "type": "generic",
        "name": "nimble_extract",
        "description": "Fetch and parse the full content of a single public URL. Use after nimble_search when you need the underlying page body.",
        "input_schema": {
          "type": "object",
          "properties": {
            "url":    { "type": "string",  "description": "The URL to extract." },
            "render": { "type": "boolean", "description": "JS-render the page (slower, needed for SPAs).", "default": true }
          },
          "required": ["url"]
        }
      }
    }
  ],
  "tool_resources": {
    "nimble_search": {
      "type": "function",
      "identifier": "NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "NIMBLE_AGENT_WH"
      }
    },
    "nimble_extract": {
      "type": "function",
      "identifier": "NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "NIMBLE_AGENT_WH"
      }
    }
  }
}
$$;

GRANT USAGE ON AGENT NIMBLE_INTEGRATION.AGENTS.NIMBLE_WEB_RESEARCH_AGENT TO ROLE NIMBLE_ROLE;

-- Sanity check
SHOW AGENTS LIKE 'NIMBLE_WEB_RESEARCH_AGENT' IN SCHEMA NIMBLE_INTEGRATION.AGENTS;
