"""Use-case configuration for the GTM account enrichment agent.

Everything that defines the account and the research lives here, so both patterns
in ``agent.py`` stay generic:

  Pattern A (Search API)        COMPANY_NAME, DOMAIN, ATS, PASSES, SOURCE_TIERS,
                                FRESHEST_WINS
  Pattern B (Web Search Agent)  AGENT_NAME, USE_CASE, EFFORT, AGENT_INPUT,
                                INPUT_DATA, PROFILE_OUTPUT_SCHEMA

The values below are the ones used for the eve.legal runs on 2026-10-07.
To enrich a different account, change COMPANY_NAME, DOMAIN, the query strings in
PASSES, and the domain named in AGENT_INPUT.
"""

# --- the account -----------------------------------------------------------

COMPANY_NAME = "Eve"
DOMAIN = "eve.legal"  # resolve from the domain: several unrelated companies are called Eve

# Applicant tracking systems the hiring pass is scoped to.
ATS = ["job-boards.greenhouse.io", "jobs.ashbyhq.com", "jobs.lever.co"]

# --- Pattern A: one focused Search API pass per attribute group --------------
#
# Each pass picks its own sources and depth: first-party pages get include_domains,
# job data is scoped to ATS boards, news gets a time_range.

PASSES = {
    "identity": dict(query="Eve legal AI platform plaintiff law firms what it does products",
                     include_domains=[DOMAIN], search_depth="standard", max_results=5),
    "funding": dict(query="Eve legal AI plaintiff firms raises funding round valuation investors",
                    search_depth="standard", max_results=6),
    "leadership": dict(query="Eve legal AI founders CEO Jay Madheswaran leadership team headquarters employees",
                       search_depth="standard", max_results=5),
    "hiring": dict(query="Eve legal jobs", include_domains=ATS,
                   search_depth="lite", max_results=20),
    "signals": dict(query="Eve plaintiff legal AI 2026 news", time_range="year",
                    search_depth="lite", max_results=8),
}

# Characters of result text passed to the extraction model per result.
EVIDENCE_CHARS = 1500

# --- Pattern A: your precedence rules -----------------------------------------
#
# The extraction step does not pick a winner when sources disagree. It records every
# value with its source URL and date in `conflicts`, and resolve_conflicts() in
# agent.py applies these rules. Edit them to match your CRM's policy.

# Source tiers, most trusted first. A host matches a tier if it equals or ends with
# one of the listed domains. Hosts that match no tier rank between press and
# aggregators.
SOURCE_TIERS = [
    ("first_party", [DOMAIN, *ATS]),
    ("press", ["prnewswire.com", "businesswire.com", "reuters.com", "bloomberg.com",
               "techcrunch.com", "law.com", "lawnext.com", "legaltechnology.com",
               "artificiallawyer.com"]),
    ("other", []),
    ("aggregator", ["tracxn.com", "crunchbase.com", "getlatka.com", "pitchbook.com",
                    "cbinsights.com"]),
]

# Fields where the most recent dated value wins before source tier is considered.
# For every other field, the most trusted tier wins and recency breaks ties.
FRESHEST_WINS = {"employee_count", "customer_count", "open_roles_summary"}

# --- Pattern B: Web Search Agent parameters (verbatim from the 2026-10-07 run) ----

AGENT_NAME = "gtm-account-enrichment"
USE_CASE = "enrichment"
EFFORT = "high"  # low | medium | high | x-high | max

AGENT_INPUT = (
    "Enrich this CRM account into a current company profile. Resolve the company from "
    "its domain (eve.legal), not its name: several unrelated companies are called Eve. "
    "Use the company's own website, newsroom and careers/ATS pages first for identity, "
    "products, headquarters, leadership and hiring. Use press releases and reputable "
    "business or legal-industry news for funding and recent announcements. Treat data "
    "aggregators (Crunchbase, Tracxn, PitchBook, GetLatka, CB Insights) as secondary "
    "corroboration only. When sources disagree on a field, pick the best-supported value, "
    "and record the disagreement in data_conflicts. Leave a field null rather than guess."
)

# The CRM record to enrich. The agent researches the null fields and returns the
# filled-in values marked `pre_existing` in the trust block.
INPUT_DATA = {
    "company_name": COMPANY_NAME,
    "domain": DOMAIN,
    "description": None,
    "vertical": None,
    "products": None,
    "target_customer": None,
    "headquarters": None,
    "founded_year": None,
    "employee_count": None,
    "funding_stage": None,
    "total_funding_usd": None,
    "last_round": None,
    "investors": None,
    "leadership": None,
    "customer_count": None,
    "currently_hiring": None,
    "open_roles_summary": None,
    "recent_signals": None,
    "data_conflicts": None,
}

PROFILE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "domain": {"type": "string", "description": "Bare hostname, no protocol"},
        "description": {"type": ["string", "null"],
                        "description": "One or two sentences on what the company sells and to whom"},
        "vertical": {"type": ["string", "null"]},
        "products": {"type": ["array", "null"], "items": {"type": "string"}},
        "target_customer": {"type": ["string", "null"]},
        "headquarters": {"type": ["string", "null"], "description": "City, State, Country"},
        "founded_year": {"type": ["integer", "null"]},
        "employee_count": {"type": ["string", "null"],
                           "description": "Best current estimate with as-of date and source type"},
        "funding_stage": {"type": ["string", "null"]},
        "total_funding_usd": {"type": ["number", "null"]},
        "last_round": {"type": ["string", "null"], "description": "Round, amount, date, lead investor"},
        "investors": {"type": ["array", "null"], "items": {"type": "string"}},
        "leadership": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "title": {"type": "string"}},
                "required": ["name", "title"],
            },
        },
        "customer_count": {"type": ["string", "null"],
                           "description": "Most recent publicly stated customer count with date"},
        "currently_hiring": {"type": ["string", "null"], "enum": ["Yes", "No", None]},
        "open_roles_summary": {"type": ["string", "null"],
                               "description": "Approximate number of open roles and which functions they are in"},
        "recent_signals": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "signal": {"type": "string"},
                    "source_url": {"type": "string"},
                },
                "required": ["date", "signal"],
            },
        },
        "data_conflicts": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "values_found": {"type": "string"},
                    "resolution": {"type": "string"},
                },
                "required": ["field", "values_found", "resolution"],
            },
        },
    },
    "required": ["company_name", "domain"],
}
