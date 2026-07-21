"""Canonical production agent config — the exact config validated in the design smoke.

One research agent: given an activity + jurisdiction, returns a cited compliance brief
(applicable regulations + key case law + recent changes). Sources use empty-domain
category groups + a prioritize steer toward primary/official sources, so it reaches any
jurisdiction's official sites (state statutes, agency pages) without a hard host whitelist.
"""

LEGAL_BRIEF = {
    "display_name": "Regulatory & Case-Law Brief",
    "description": "Cited compliance brief: applicable regulations + key case law + recent changes for an activity in a jurisdiction.",
    "icon": "⚖️",
    "use_case": "research",
    "effort": "high",
    "domain_expertise": """# Regulatory & Case-Law Research — Domain Expertise

You are a regulatory and legal research analyst preparing a compliance brief for a business
activity in a specific jurisdiction. Your reader is a founder or compliance lead, not a lawyer;
be precise but plain.

## Method
- Identify the governing statutes and regulations for the activity in the stated jurisdiction
  (federal and state/regional as relevant).
- Identify the key case law or enforcement actions that shape how those rules are applied.
- Note recent or pending changes (last ~24 months) with dates.
- Cite every claim to a PRIMARY source (official code/regulation text, the court opinion, or the
  agency page). Prefer primary sources over secondary summaries.

## Rules
- Never invent a statute, citation, or case name. If a point cannot be sourced, say so.
- Distinguish binding authority from persuasive/secondary commentary.
- Distinguish "no requirement found after search" from "confirmed no requirement".
- This is research, not legal advice; note that in the summary.""",
    "goals": [
        "Lists the applicable statutes/regulations for the activity + jurisdiction, each with a primary-source citation URL",
        "Identifies key case law or enforcement actions with case name, court/agency, date, and a one-line holding",
        "Summarizes concrete obligations the activity must meet",
        "Notes recent or pending changes with dates (last ~24 months) when any exist",
        "Every claim carries a primary-source URL; never invents a citation",
        "Distinguishes 'not found' from 'confirmed none'",
    ],
    "sources": {
        "allow": [
            {"title": "Official Statutes & Regulations (federal, state, agency)", "domains": [], "order": 0},
            {"title": "Court Opinions & Dockets", "domains": [], "order": 1},
            {"title": "Regulators & Government Agencies", "domains": [], "order": 2},
            {"title": "EU & UK Official Law", "domains": [], "order": 3},
        ],
        "block": [],
        "avoid": "law-firm marketing blogs and unofficial summaries when a primary source exists",
        "prioritize": "primary sources: official statute and regulation text (e.g. Cornell LII, eCFR, congress.gov, state legislature sites), the court opinion itself (e.g. CourtListener), and agency pages (SEC, FTC, state financial regulators like the Texas OCCC)",
    },
    "output_schema": {
        "type": "object",
        "required": ["subject", "jurisdiction", "summary"],
        "properties": {
            "subject": {"type": "string"},
            "jurisdiction": {"type": "string"},
            "summary": {"type": "string", "description": "Plain-language compliance overview; note this is research, not legal advice"},
            "applicable_regulations": {"type": "array", "items": {"type": "object",
                "required": ["name", "citation_url"],
                "properties": {"name": {"type": "string"}, "jurisdiction": {"type": ["string", "null"]},
                    "requirement": {"type": ["string", "null"]}, "citation_url": {"type": "string"}},
                "additionalProperties": True}},
            "key_cases": {"type": "array", "items": {"type": "object",
                "properties": {"case_name": {"type": "string"}, "court": {"type": ["string", "null"]},
                    "date": {"type": ["string", "null"]}, "holding": {"type": ["string", "null"]},
                    "citation_url": {"type": ["string", "null"]}}, "additionalProperties": True}},
            "recent_changes": {"type": "array", "items": {"type": "object",
                "properties": {"change": {"type": "string"}, "date": {"type": ["string", "null"]},
                    "source_url": {"type": ["string", "null"]}}, "additionalProperties": True}},
            "sources": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": True,
    },
    "suggested_questions": [
        "Compliance requirements for launching a consumer fintech lending product in Texas",
        "What regulations and case law govern selling CBD cosmetics in California?",
        "Data privacy obligations for a US SaaS company serving EU customers",
    ],
}
