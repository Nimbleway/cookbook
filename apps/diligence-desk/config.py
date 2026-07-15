"""Diligence Desk — agent configuration and app constants.

The agent config here is the single source of truth: setup_agent.py POSTs/PATCHes
it, and the Learn feature re-PATCHes domain_expertise with new standing
instructions appended.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR / ".env")

BASE_URL = "https://sdk.nimbleway.com/v1"
NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY", "")
USE_LIVE = os.getenv("USE_LIVE", "true").lower() == "true"

AGENT_FILE = APP_DIR / "agent.json"
SAMPLE_DIR = APP_DIR / "data" / "sample_run"
MEMO_DIR = APP_DIR / "output" / "memos"

CREW_MODEL = "anthropic/claude-sonnet-4-6"

STANDING_INSTRUCTIONS_HEADER = "## Standing instructions from the analyst team"

DOMAIN_EXPERTISE = f"""# Diligence Desk — Analyst Expertise

You are a seasoned M&A analyst and corporate investigator producing an audit-grade
diligence memo. Every material claim you make will be reviewed against its citations.

## Key areas to investigate
- **Financial health**: revenue, growth trajectory, burn rate, funding history and
  valuation, debt obligations.
- **Leadership & personnel**: executive backgrounds, board composition, key
  hires/departures, employee sentiment signals.
- **Legal & regulatory**: litigation history, regulatory filings (SEC EDGAR,
  Companies House), sanctions, lawsuits, court records.
- **Competitive position**: market share, differentiation, main competitors,
  customer concentration.
- **Operational risk**: supply chain dependencies, technology risks, key-person
  dependencies.
- **Reputation**: press coverage sentiment, social signals, analyst reports.

## Verdict duty
Close with an overall_assessment verdict: exactly one of proceed,
proceed_with_conditions, caution, do_not_proceed — plus a rationale tied to
specific findings. Never fence-sit: pick the verdict the evidence supports. If
the verdict is proceed_with_conditions, list the conditions.

## Evidence discipline
- Cross-reference every material claim across at least two independent sources.
- Prefer primary sources (SEC filings, official registries, company statements)
  over aggregators.
- Distinguish "not found in searched records" from "confirmed absent" — say which.
- Never invent names, numbers, or events. Use null, never omit the field.
- Express estimates and ranges as strings with their basis, e.g.
  "$50M-$80M ARR (estimated, press reports)".

## Private-company protocol
When no SEC filings exist, lean on Crunchbase/PitchBook funding data, hiring
signals, press coverage, and litigation databases — and state which lenses were
unavailable.

{STANDING_INSTRUCTIONS_HEADER}
- (none yet)
"""

GOALS = [
    "Delivers an explicit overall_assessment verdict with a rationale referencing at least 3 specific findings",
    "Covers all six investigation areas; any area with no findable data says so explicitly rather than omitting it",
    "Identifies at least 3 concrete risks or red flags, each with a cited source",
    "Lists top executives with backgrounds and LinkedIn URLs when publicly discoverable — never invents a name",
    "Every financial figure is either cited or marked as estimated with its basis",
    "Includes at least 8 cited sources spanning at least 3 source categories",
]

SOURCES = {
    "allow": [
        {"title": "SEC EDGAR", "domains": ["sec.gov", "efts.sec.gov"], "order": 0},
        {"title": "Company Website", "domains": [], "order": 1},
        {"title": "Crunchbase", "domains": ["crunchbase.com", "www.crunchbase.com"], "order": 2},
        {"title": "PitchBook", "domains": ["pitchbook.com"], "order": 3},
        {"title": "LinkedIn", "domains": ["linkedin.com", "www.linkedin.com"], "order": 4},
        {"title": "Litigation & Court Records", "domains": ["courtlistener.com", "www.courtlistener.com"], "order": 5},
        {"title": "Bloomberg", "domains": ["bloomberg.com", "www.bloomberg.com"], "order": 6},
        {"title": "Reuters", "domains": ["reuters.com", "www.reuters.com"], "order": 7},
        {"title": "Glassdoor", "domains": ["glassdoor.com", "www.glassdoor.com"], "order": 8},
        {"title": "OpenCorporates", "domains": ["opencorporates.com"], "order": 9},
        {"title": "Companies House", "domains": ["companieshouse.gov.uk", "find-and-update.company-information.service.gov.uk"], "order": 10},
        {"title": "Tech & Startup Press", "domains": ["techcrunch.com", "www.techcrunch.com", "news.google.com"], "order": 11},
    ],
    "block": [],
    "prioritize": "official filings and registries over news; news over aggregators",
    "avoid": "forums, unverified blogs, and AI-generated content farms",
}

OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["executive_summary", "overall_assessment", "risks", "sources", "data_as_of_date"],
    "additionalProperties": True,
    "properties": {
        "company_name": {"type": "string"},
        "company_domain": {"type": "string", "description": "Bare hostname (acme.ai), no https://"},
        "data_as_of_date": {"type": "string", "description": "ISO 8601 date of research"},
        "executive_summary": {"type": "string"},
        "overall_assessment": {
            "type": "object",
            "required": ["verdict", "rationale"],
            "properties": {
                "verdict": {"type": "string", "enum": ["proceed", "proceed_with_conditions", "caution", "do_not_proceed"]},
                "rationale": {"type": "string"},
                "conditions": {"type": ["array", "null"], "items": {"type": "string"}},
            },
        },
        "financial_health": {
            "type": "object",
            "properties": {
                "revenue": {"type": ["string", "null"], "description": "String with basis, e.g. \"$120M ARR (reported, 2025)\""},
                "growth": {"type": ["string", "null"]},
                "funding_total": {"type": ["string", "null"]},
                "last_round": {"type": ["string", "null"], "description": "Stage, amount, date, lead investor"},
                "burn_or_profitability": {"type": ["string", "null"]},
                "summary": {"type": "string"},
            },
        },
        "leadership": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "title": {"type": "string"},
                    "background": {"type": "string"},
                    "linkedin_url": {"type": ["string", "null"]},
                    "flags": {"type": ["string", "null"], "description": "Departures, controversies, prior failures; null if none found"},
                },
            },
        },
        "legal_regulatory": {
            "type": "object",
            "properties": {
                "litigation": {"type": "string", "description": "Findings, or explicit \"none found in searched records\""},
                "regulatory": {"type": "string"},
                "summary": {"type": "string"},
            },
        },
        "competitive_position": {
            "type": "object",
            "properties": {
                "main_competitors": {"type": "array", "items": {"type": "string"}},
                "differentiation": {"type": "string"},
                "market_position": {"type": "string"},
            },
        },
        "operational_risks": {"type": "array", "items": {"type": "string"}},
        "reputation": {
            "type": "object",
            "properties": {
                "press_sentiment": {"type": "string"},
                "employee_sentiment": {"type": ["string", "null"], "description": "Glassdoor or similar signals"},
                "notable_coverage": {"type": "array", "items": {"type": "string"}},
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["risk", "severity"],
                "properties": {
                    "risk": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "evidence": {"type": "string"},
                },
            },
        },
        "opportunities": {"type": "array", "items": {"type": "string"}},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"url": {"type": "string"}, "title": {"type": "string"}, "relevance": {"type": "string"}},
            },
        },
    },
}

# Minimal schema for follow-up Q&A runs so answers aren't forced into the memo shape
QA_SCHEMA = {
    "type": "object",
    "required": ["answer"],
    "additionalProperties": True,
    "properties": {
        "answer": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": {"type": "object", "properties": {
            "url": {"type": "string"}, "title": {"type": "string"}}}},
    },
}

SUGGESTED_QUESTIONS = [
    "Due diligence on Anthropic (anthropic.com) for a strategic partnership",
    "Full diligence memo on Snowflake ahead of an enterprise contract",
    "Background and risk assessment of Widgets LLC, a private manufacturing target",
    "Diligence on Perplexity AI with emphasis on legal and regulatory exposure",
]
