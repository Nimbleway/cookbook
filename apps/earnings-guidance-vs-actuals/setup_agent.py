"""Create the Guidance Scorecard Agent (idempotent - reuses agents.json if present)."""
import json

import requests

import config as C

DOMAIN_EXPERTISE = """# Earnings Guidance vs Actuals — Domain Expertise

You are a sell-side equity research analyst reconstructing a public company's
guidance-vs-delivery track record from archived public sources.

## Task shape
Given a ticker and a set of fiscal quarters, produce one row per quarter containing:
1. What management GUIDED for that quarter — issued on the PRIOR quarter's earnings
   call or release: revenue, EPS, gross margin, opex, and any segment or full-year
   outlooks restated at that time.
2. What the company ACTUALLY reported for that quarter (earnings release / 10-Q / 10-K).
3. A verdict: beat, miss, inline, or not_guided.

## Where to search
- Company investor relations press-release archives (outlook/guidance sections).
- SEC EDGAR: 8-K earnings releases and exhibits, 10-Q, 10-K.
- Earnings call transcripts: The Motley Fool, Seeking Alpha, company IR.
- Financial press coverage of guidance: Reuters, CNBC, Bloomberg.

## Rules
- Guidance for quarter N is issued with quarter N-1 results — attribute it to the
  correct target quarter.
- Report guided ranges as strings exactly as stated, e.g. "$26.0B–$26.5B" or
  "$45.0 billion, plus or minus 2%".
- Some companies (banks, Tesla) do not issue formal quarterly revenue/EPS guidance —
  capture whatever forward outlook management DID give (e.g. full-year NII, expense
  targets, delivery growth) and mark strictly quarterly metrics not_guided.
- Never invent a number — omit rather than guess. Distinguish "not guided"
  (management did not guide this metric) from "not found" (guidance may exist but
  was not located); record which case applies in notes.
- Every numeric value must be traceable to the cited source_url, and source_url
  must be the full public https:// URL of the document — never an internal,
  cached, or relative path.
- Use the company's own fiscal calendar labels (e.g. NVIDIA Q1 FY2027) plus the
  calendar report_date (ISO 8601).
"""

GOALS = [
    "For every requested quarter, capture the guidance issued with the prior quarter's results for revenue and at least one profitability metric (EPS or gross margin), each with a full public source_url",
    "Capture the actually reported value for each guided metric from the earnings release, 10-Q, or 10-K, each with a full public source_url",
    "Score a verdict of exactly beat, miss, inline, or not_guided per quarter, judged on revenue vs the guided range (inline = within the range)",
    "Never invent numbers - omit rather than guess, and distinguish 'not guided' from 'not found' in notes",
    "Report guided ranges as strings exactly as stated by management (e.g. '$26.0B-$26.5B')",
    "For companies without formal quarterly guidance, capture the forward outlook management did give (full-year NII, expense targets, delivery growth) rather than returning empty guidance_metrics",
]

SOURCES = {
    "allow": [
        {"title": "SEC EDGAR", "domains": ["sec.gov", "www.sec.gov", "efts.sec.gov"], "order": 0},
        {"title": "Company Investor Relations Pages", "domains": [], "order": 1},
        {"title": "Earnings Call Transcripts", "domains": ["fool.com", "www.fool.com", "seekingalpha.com", "www.seekingalpha.com"], "order": 2},
        {"title": "Financial Press", "domains": ["reuters.com", "www.reuters.com", "cnbc.com", "www.cnbc.com", "bloomberg.com", "www.bloomberg.com"], "order": 3},
        {"title": "Financial Data Aggregators", "domains": ["finance.yahoo.com", "macrotrends.net", "www.macrotrends.net"], "order": 4},
    ],
    "block": [],
    "avoid": "forums, message boards, and unsourced blog commentary",
    "prioritize": "official earnings releases and SEC filings for actuals; earnings call transcripts and IR releases for guidance",
}

OUTPUT_SCHEMA = {
    "type": "array",
    "description": "One row per requested fiscal quarter, most recent first.",
    "items": {
        "type": "object",
        "required": ["fiscal_quarter", "report_date", "guidance_metrics", "actual_metrics", "verdict"],
        "properties": {
            "fiscal_quarter": {"type": "string", "description": "Company fiscal label, e.g. 'Q1 FY2027'"},
            "report_date": {"type": "string", "description": "ISO 8601 calendar date results were reported"},
            "guidance_metrics": {
                "type": "array",
                "description": "Metrics management guided for this quarter (issued with the prior quarter's results)",
                "items": {
                    "type": "object",
                    "required": ["metric", "guided_value", "source_url"],
                    "properties": {
                        "metric": {"type": "string", "description": "e.g. revenue, EPS (non-GAAP), gross margin (non-GAAP)"},
                        "guided_value": {"type": "string", "description": "Point value or range midpoint, as a string"},
                        "guided_range": {"type": ["string", "null"], "description": "Full range as stated, e.g. '$26.0B-$26.5B'; null if point guidance"},
                        "source_url": {"type": "string", "description": "Full public https:// URL - never an internal or relative path"},
                    },
                    "additionalProperties": True,
                },
            },
            "actual_metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["metric", "actual_value", "source_url"],
                    "properties": {
                        "metric": {"type": "string", "description": "Must reuse the exact metric name from guidance_metrics when the same metric"},
                        "actual_value": {"type": "string"},
                        "source_url": {"type": "string", "description": "Full public https:// URL - never an internal or relative path"},
                    },
                    "additionalProperties": True,
                },
            },
            "verdict": {"type": "string", "enum": ["beat", "miss", "inline", "not_guided"]},
            "notes": {"type": "string", "description": "Context; must state 'not guided' vs 'not found' where applicable"},
        },
        "additionalProperties": True,
    },
}

SUGGESTED_QUESTIONS = [
    "NVDA - guidance vs actuals for the last 4 reported fiscal quarters",
    "Build the 8-quarter guidance-vs-delivery scorecard for MSFT",
    "JPM - did management deliver on its NII outlook over the last 4 quarters?",
    "TSLA quarters 5-8 back - what did management promise and what landed?",
]


def main():
    if C.AGENTS_FILE.exists():
        print(f"agents.json exists - reusing {C.agent_id()}")
        return
    r = requests.post(f"{C.BASE_URL}/task-agents", headers={"Authorization": f"Bearer {C.NIMBLE_API_KEY}"}, json={
        "display_name": "Guidance Scorecard Agent",
        "description": "Reconstructs a public company's guidance-vs-actuals record per fiscal quarter from archived earnings releases, SEC filings, and call transcripts.",
        "icon": "📊",
        "use_case": "research",
        "effort": "high",
        "domain_expertise": DOMAIN_EXPERTISE,
        "goals": GOALS,
        "sources": SOURCES,
        "output_schema": OUTPUT_SCHEMA,
        "suggested_questions": SUGGESTED_QUESTIONS,
    }, timeout=120)
    r.raise_for_status()
    agent = r.json()
    C.AGENTS_FILE.write_text(json.dumps({"scorecard_agent": agent["id"]}, indent=2))
    print(f"created {agent['id']} -> agents.json")


if __name__ == "__main__":
    main()
