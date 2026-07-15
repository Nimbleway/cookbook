"""Create (or update) the two Market Mapper agents on Web Search Agents.

Idempotent: finds agents by display name, creates from gallery templates if missing,
then PATCHes them to the desired configuration. Writes agent ids to agents.json.

Run: python3 setup_agents.py
"""
import json
import os
import pathlib

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://sdk.nimbleway.com/v1"
HEADERS = {"Authorization": f"Bearer {os.environ['NIMBLE_API_KEY']}"}

MAPPER_NAME = "Market Mapper — Mapper"
ENRICHER_NAME = "Market Mapper — Enricher"

MAPPER_SCHEMA = {
    "type": "array",
    "description": "Companies matching the ICP described in the prompt.",
    "items": {
        "type": "object",
        "required": ["company_name", "domain", "icp_fit_reason", "source_url"],
        "additionalProperties": True,
        "properties": {
            "company_name": {"type": "string"},
            "domain": {"type": "string", "description": "Bare public hostname (acme.ai), no protocol."},
            "website": {"type": ["string", "null"]},
            "linkedin_url": {"type": ["string", "null"]},
            "industry": {"type": "string"},
            "employee_count": {"type": "string", "description": "Band, e.g. \"11-50\", \"51-200\""},
            "headquarters": {"type": "string", "description": "City, Country"},
            "recent_funding": {"type": ["string", "null"], "description": "Most recent round + year; null if unknown. Never guess."},
            "icp_fit_reason": {"type": "string", "description": "The 2-3 strongest qualification signals."},
            "source_url": {"type": "string", "description": "URL where this company was discovered."},
        },
    },
}

MAPPER_GOALS = [
    "Return only companies that match every ICP criterion in the prompt — treat size, geography, funding stage, and vertical as hard constraints; never dilute them to inflate volume",
    "Exclude any company whose domain appears in the exclusion list provided in the input",
    "Provide a concise icp_fit_reason per company naming the 2-3 strongest qualification signals",
    "Resolve domain to the bare public hostname (e.g. acme.ai), no protocol",
    "Include a linkedin_url or website for every company",
    "Cite the source_url where each company was discovered",
    "Mix recognizable companies with credible under-the-radar ones; do not return well-known enterprises unless the prompt explicitly includes them",
]

MAPPER_EXPERTISE = """\
# Market Mapper — Domain Expertise

You are a B2B market analyst mapping the universe of companies that fit an
Ideal Customer Profile (ICP). Your output feeds a market-mapping dataset, so
coverage and constraint fidelity matter more than speed.

## Filters are hard constraints
- Location, vertical, company size, and funding stage supplied by the user are
  hard constraints. Do not dilute or ignore them to inflate volume. Within the
  constraints, maximize genuine discovery.

## Exclusion list
- The input may include a list of domains to exclude (companies already known
  to the user). Never return a company whose domain is on that list.

## Discovery strategy
- Combine LinkedIn company search, Crunchbase, Wellfound, TechCrunch funding
  coverage, Product Hunt, and startup directories. Expand through investor
  portfolios and accelerator batches to reach under-the-radar companies.
- Do not stop at the obvious names; the value of the map is its long tail.

## Field rules
- `domain`: bare hostname only, resolved from the official site or the
  company's LinkedIn/Crunchbase page.
- `recent_funding`: most recent round with year. Never guess funding — use
  null when no defensible fact exists.
- `employee_count`: a band (e.g. "51-200"), from LinkedIn where possible.
"""

MAPPER_SOURCES = {
    "allow": [
        {"title": "LinkedIn", "domains": ["linkedin.com", "www.linkedin.com"], "order": 0},
        {"title": "Crunchbase", "domains": ["crunchbase.com", "www.crunchbase.com"], "order": 1},
        {"title": "Wellfound", "domains": ["wellfound.com", "angel.co"], "order": 2},
        {"title": "TechCrunch", "domains": ["techcrunch.com"], "order": 3},
        {"title": "Product Hunt", "domains": ["producthunt.com", "www.producthunt.com"], "order": 4},
        {"title": "Google News", "domains": ["news.google.com"], "order": 5},
        {"title": "Company Websites", "domains": [], "order": 6},
        {"title": "Startup Directories", "domains": [], "order": 7},
    ],
    "block": [],
    "prioritize": "official company sites and primary startup directories",
}


def api(method, path, body=None, content_type="application/json"):
    r = requests.request(method, f"{BASE}{path}", headers={**HEADERS, "Content-Type": content_type},
                         data=json.dumps(body) if body is not None else None, timeout=60)
    r.raise_for_status()
    return r.json() if r.text else {}


def find_agent(display_name):
    agents = api("GET", "/task-agents?limit=200")
    return next((a for a in agents if a["display_name"] == display_name and a["is_active"]), None)


def patch(agent_id, fields):
    ops = [{"op": "replace", "path": f"/{k}", "value": v} for k, v in fields.items()]
    return api("PATCH", f"/task-agents/{agent_id}", ops, content_type="application/json-patch+json")


def ensure_mapper():
    agent = find_agent(MAPPER_NAME)
    if agent is None:
        agent = api("POST", "/task-agents", {"template": "gtm-lead-discovery", "display_name": MAPPER_NAME,
                                             "effort": "max"})
        print(f"created mapper {agent['id']}")
    patch(agent["id"], {
        "effort": "max",
        "use_case": "dataset_building",
        "description": "Maps the universe of companies fitting an ICP, with per-row provenance.",
        "domain_expertise": MAPPER_EXPERTISE,
        "goals": MAPPER_GOALS,
        "output_schema": MAPPER_SCHEMA,
        "sources": MAPPER_SOURCES,
        "suggested_questions": [
            "AI-powered vertical SaaS companies in healthcare, 11-200 employees, US or Israel, Series A or later",
            "Fintech infrastructure startups in Europe, seed to Series B, founded 2021 or later",
            "Robotics companies in Japan or South Korea with 51-500 employees",
        ],
    })
    print(f"mapper configured: {agent['id']}")
    return agent["id"]


def ensure_enricher():
    agent = find_agent(ENRICHER_NAME)
    if agent is None:
        agent = api("POST", "/task-agents", {"template": "lead-enrichment", "display_name": ENRICHER_NAME,
                                             "effort": "high"})
        print(f"created enricher {agent['id']}")
    patch(agent["id"], {
        "effort": "high",
        "description": "Enriches a discovered company with firmographics, funding, contacts, and buying signals.",
    })
    print(f"enricher configured: {agent['id']}")
    return agent["id"]


if __name__ == "__main__":
    ids = {"mapper": ensure_mapper(), "enricher": ensure_enricher()}
    out = pathlib.Path(__file__).parent / "agents.json"  # next to the scripts, wherever setup runs from
    out.write_text(json.dumps(ids, indent=2))
    print(f"wrote {out}: {ids}")
