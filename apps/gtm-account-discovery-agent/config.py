"""Use-case configuration for the GTM account discovery agent.

The ICP is defined once here and used by both patterns in ``agent.py``:

  Pattern A (Search API)        DISCOVERY, LEGAL_PRESS, ATS, FIRMOGRAPHIC_SEARCH,
                                HIRING_SEARCH, plus the ICP constants for the LLM
                                judges and the code-side decision rules
  Pattern B (Web Search Agent)  AGENT_*, GOALS, SOURCES, OUTPUT_SCHEMA, agent_input(),
                                HEADCOUNT_SEARCH for the trust gate

The values below are the ones used for the US legal AI runs on 2026-10-07.
"""

import os
from datetime import date

# Date the ICP is evaluated against. Defaults to today. Set AS_OF_DATE=2026-10-07 to
# send the exact Pattern B input used for the committed example.
AS_OF = os.getenv("AS_OF_DATE") or date.today().isoformat()

# --- the ICP (hard constraints) ---------------------------------------------

TARGET_COUNT = 15
MIN_EMPLOYEES = 50
MAX_EMPLOYEES = 500
ROUND_WINDOW_START = "2025-04-01"  # most recent priced round closed on or after this date
HEADCOUNT_MAX_AGE_DAYS = 365       # trust gate ignores headcount figures older than this

ICP_CRITERIA = {
    "hq": "Headquartered in the United States.",
    "product": ("Builds AI software for legal work, sold to law firms or in-house legal teams "
                "(not a law firm or legal services provider itself)."),
    "size": f"{MIN_EMPLOYEES} to {MAX_EMPLOYEES} employees today.",
    "stage": ("Most recent priced funding round is a Series A, B or C that closed on or after "
              f"{ROUND_WINDOW_START}."),
    "sales_hiring": ("Currently hiring at least one quota-carrying sales role (Account Executive, "
                     "SDR/BDR or sales leadership) located in the US."),
}

# Firmographic criteria are checked first (one cheap search per candidate); the hiring
# search is spent only on companies that pass all of them.
FIRMOGRAPHIC_CRITERIA = ["hq", "product", "stage", "size"]

# --- Pattern A: Search API ---------------------------------------------------

ATS = ["jobs.ashbyhq.com", "job-boards.greenhouse.io", "boards.greenhouse.io",
       "jobs.lever.co", "apply.workable.com"]
LEGAL_PRESS = ["artificiallawyer.com", "lawnext.com", "legaltechnology.com", "abovethelaw.com"]

# 1. Broaden: cheap lite passes from different angles, limited to the funding window.
DISCOVERY = [
    {"query": "legal AI startup raises Series A funding"},
    {"query": "legal AI company raises Series B 2026"},
    {"query": "AI for in-house legal teams startup funding round led by"},
    {"query": "AI plaintiff personal injury law firm startup raises million"},
    {"query": "legal tech AI Series C funding 2026 contract"},
    {"query": "raises Series funding legal AI law firms", "include_domains": LEGAL_PRESS},
]
DISCOVERY_PARAMS = dict(start_date=ROUND_WINDOW_START, search_depth="lite", max_results=10)

# 3. Narrow: per-candidate searches. {name} and {domain} are filled per company.
FIRMOGRAPHIC_SEARCH = dict(query="{name} {domain} latest funding round headquarters employees",
                           search_depth="lite", max_results=5)
HIRING_SEARCH = dict(query="{name} account executive sales jobs",
                     search_depth="lite", max_results=6)  # include_domains = ATS + [domain]

# Characters of result text passed to the LLM per result.
EVIDENCE_CHARS = 800

# --- Pattern B: Web Search Agent (verbatim from the 2026-10-07 run 3) ----------

AGENT_NAME = "gtm-icp-discovery-verified"
AGENT_DISPLAY_NAME = "GTM ICP Discovery (verified)"
AGENT_DESCRIPTION = ("Discovers companies that match a GTM ICP and returns only rows where every "
                     "hard constraint is backed by a cited page, plus near-misses.")
USE_CASE = "dataset_building"
# high is the tested tier. dataset_building needs high or above; an x-high run of this
# task was cancelled server-side after 10 minutes with no output.
EFFORT = "high"

GOALS = [
    "Return a company in companies only when every ICP criterion is directly supported by a "
    "cited page; if any criterion cannot be verified, put the company in near_misses with "
    "failed_criterion 'Unverified: <criterion>' instead.",
    "Never add rows to reach the requested count; returning fewer rows is correct when fewer "
    "companies qualify.",
    "sales_role_url must be a live posting on the company's careers page or ATS board "
    "(Greenhouse, Ashby, Lever, Workable, Gem) for a US-located Account Executive, SDR/BDR or "
    "sales leadership role.",
    "employee_count must come from a dated source (company statement, LinkedIn, Built In, "
    "Tracxn, PitchBook); never infer headcount from funding size or number of open jobs.",
    "Resolve domain to the bare public hostname and confirm it belongs to the named company.",
    "Mix recognizable companies with credible under-the-radar ones found through funding "
    "announcements, investor portfolios and legal-tech press.",
]

SOURCES = {
    "prioritize": ("Company websites, newsrooms and careers pages; ATS boards (Greenhouse, Ashby, "
                   "Lever, Workable, Gem); funding press releases; legal-tech press (Artificial "
                   "Lawyer, LawSites, Legal IT Insider, Law.com)"),
    "avoid": "Using SEO listicles or vendor 'top 10' posts as evidence for a criterion",
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "domain": {"type": "string", "description": "Bare hostname, no protocol"},
                    "hq": {"type": "string", "description": "City, State"},
                    "customer_segment": {"type": "string"},
                    "employee_count": {"type": "string",
                                       "description": "Number or band with source and as-of date"},
                    "latest_round": {"type": "string",
                                     "description": "Series, amount, month and year, lead investor"},
                    "sales_role": {"type": "string",
                                   "description": "Title and US location of one open sales role"},
                    "sales_role_url": {"type": "string"},
                    "recognizability": {"type": "string", "enum": ["Well-known", "Under-the-radar"]},
                    "why_it_fits": {"type": "string"},
                    "evidence_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["company", "domain", "hq", "employee_count", "latest_round",
                             "sales_role", "sales_role_url"],
            },
        },
        "near_misses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "domain": {"type": "string"},
                    "failed_criterion": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["company", "failed_criterion", "reason"],
            },
        },
    },
    "required": ["companies", "near_misses"],
}


def agent_input(today: str = AS_OF) -> str:
    """The run input: the ICP as hard constraints."""
    criteria = "\n".join(f"- {c}" for c in ICP_CRITERIA.values())
    return (
        f"Find up to {TARGET_COUNT} companies that match ALL of these criteria "
        f"(today is {today}):\n{criteria}\n"
        "Treat every criterion as a hard constraint. List near-misses with the criterion they failed."
    )


# Trust gate: one search per row whose employee_count claim came back low confidence.
HEADCOUNT_SEARCH = dict(query="{company} {domain} employees headcount team size",
                        search_depth="lite", max_results=5)
