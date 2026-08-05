"""The two Web Search Agent configs, per DESIGN.md §3.

Single source of truth: `setup_agents.py` provisions from these, and the runtime
reuses the schemas for validation. Two agents, not one, because smoke runs showed
a single broad task lets base-rate retrieval degrade silently into `unverified`
(see LOG.md 2026-08-05).

Note the v2 field name: the system prompt is `skill`, not `domain_expertise`.
"""

# --- tariff-schedule-rate -------------------------------------------------
# Stable facts. TTL measured in months.

RATE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "hts_code": {
            "type": "string",
            "description": "HTS subheading as supplied, e.g. 8507.60.00",
        },
        "general_rate": {
            "type": "string",
            "description": (
                "Column 1 General (MFN) rate quoted exactly as the schedule states "
                "it, e.g. '3.4%' or 'Free'. Always a string, never a number."
            ),
        },
        "htsus_revision": {
            "type": ["string", "null"],
            "description": (
                "Revision the rate was read from, as the document self-identifies "
                "it. null, never omit."
            ),
        },
        "source_url": {
            "type": ["string", "null"],
            "description": "URL of the schedule page or chapter PDF the rate was read from.",
        },
        "verified_against_official_schedule": {"type": "boolean"},
        "retrieval_notes": {"type": ["string", "null"]},
        "data_as_of_date": {
            "type": "string",
            "description": "ISO 8601 date the rate was read.",
        },
    },
}

RATE_SKILL = """You are a licensed customs broker reading tariff schedules for a compliance team \
that will be audited on your answer.

## Where to search
The official Harmonized Tariff Schedule of the United States published by the USITC at
hts.usitc.gov, including its chapter PDFs, is the only acceptable source for a base rate.
CBP publications may be used to confirm a reading, never to substitute for it.

## Field rules
Report the Column 1 General (MFN) rate only. Section 301, Section 232, IEEPA, and reciprocal
tariffs are policy overlays handled by a different agent — never fold them into this rate.
Quote the rate exactly as the schedule states it, including "Free". Name the HTSUS revision the
document self-identifies as.

## Methodology
Read the rate in context and sanity-check it against neighbouring subheadings in the same
chapter before reporting it.

## Missing data
If the official schedule cannot be retrieved, set verified_against_official_schedule to false,
leave general_rate as "not verified", and state in retrieval_notes which official mirrors were
attempted. Never estimate a rate and never substitute a broker or forwarder figure. Use null,
never omit a field."""

RATE_GOALS = [
    "Reports the Column 1 General (MFN) rate exactly as the official schedule states it, as a string",
    "Sets verified_against_official_schedule to true only when the rate was read from a usitc.gov document",
    "Names the HTSUS revision the source document self-identifies as",
    "Excludes all Section 301, Section 232, IEEPA and reciprocal duties from general_rate",
    "On retrieval failure, reports 'not verified' and lists the mirrors attempted rather than estimating",
]

RATE_SOURCES = {
    "allow": [
        {
            "title": "USITC Harmonized Tariff Schedule",
            "domains": ["hts.usitc.gov", "usitc.gov", "www.usitc.gov"],
            "order": 0,
        },
        {
            "title": "US Customs and Border Protection",
            "domains": ["cbp.gov", "www.cbp.gov", "rulings.cbp.gov"],
            "order": 1,
        },
    ],
    "block": [],
    "prioritize": "the official HTSUS chapter documents published by the USITC",
    "avoid": "customs-broker blogs, freight-forwarder marketing pages, and news summaries",
}

RATE_QUESTIONS = [
    "What is the Column 1 General rate for HTS 8507.60.00?",
    "What is the base MFN duty rate for HTS 6109.10.00?",
    "What is the Column 1 General rate for HTS 4901.99.00?",
    "What is the base rate for the statistical suffix 8507.60.0020, and which 8-digit rate line does it fall under?",
]

RATE_AGENT = {
    "display_name": "Tariff Schedule Rate",
    "description": "Reads the Column 1 General (MFN) rate for an HTS subheading from the official HTSUS.",
    "icon": "🧾",
    "use_case": "enrichment",
    "effort": "medium",
    "skill": RATE_SKILL,
    "goals": RATE_GOALS,
    "sources": RATE_SOURCES,
    "output_schema": RATE_SCHEMA,
    "suggested_questions": RATE_QUESTIONS,
}

# --- tariff-policy-overlay -----------------------------------------------
# Volatile facts. TTL measured in days.

OVERLAY_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "hts_code": {"type": "string"},
        "origin": {"type": "string"},
        "destination": {"type": "string"},
        "additional_duties": {
            "type": "array",
            "description": (
                "ONLY overlays in force on the research date. Terminated, expired "
                "and out-of-scope instruments belong in confirmed_absent, never here."
            ),
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["authority", "rate", "in_force"],
                "properties": {
                    "authority": {
                        "type": "string",
                        "description": (
                            "The legal instrument only, e.g. 'EO 14326' or 'Section 301 "
                            "List 3'. Instrument name and citation, no commentary."
                        ),
                    },
                    "rate": {
                        "type": "string",
                        "description": (
                            "The bare rate, e.g. '25%' or '7.5%'. No prose, no "
                            "parenthetical explanation, no status text."
                        ),
                    },
                    "in_force": {
                        "type": "boolean",
                        "description": (
                            "True only if this duty is collectible on the research "
                            "date. If it was terminated, has expired, or does not "
                            "cover this product, it is not in force and does not "
                            "belong in this array."
                        ),
                    },
                    "effective_date": {"type": "string"},
                    "ends": {
                        "type": ["string", "null"],
                        "description": (
                            "Date the instrument stops applying, if it has one. "
                            "null when open-ended."
                        ),
                    },
                    "source_url": {"type": "string"},
                },
            },
        },
        "exclusions_in_force": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "description": {"type": "string"},
                    "expires": {"type": ["string", "null"]},
                    "source_url": {"type": "string"},
                },
            },
        },
        "origin_rules_notes": {"type": ["string", "null"]},
        "last_changed": {
            "type": ["string", "null"],
            "description": "Most recent action affecting this lane, with its instrument and date.",
        },
        "unverified": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Components that could not be confirmed against an official source.",
        },
        "confirmed_absent": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Overlays checked and confirmed NOT to apply. Distinct from unverified.",
        },
        "data_as_of_date": {"type": "string"},
    },
}

OVERLAY_SKILL = """You are a trade-policy analyst tracking duty overlays for an importer who will \
make sourcing decisions from your answer.

## Where to search
Federal Register notices, USTR publications, White House presidential actions and executive
orders, and CBP guidance. An overlay is only in force if an official instrument says so.

## Field rules
Report each duty component separately with the instrument that created it and its effective
date. Never blend components into a single percentage. Do not report the Column 1 General (MFN)
base rate — a different agent owns it.

additional_duties is a list of duties an importer actually pays on the research date. Nothing
else goes in it. Before adding an entry, apply all three tests:
  1. Is the instrument still operative, or was it terminated or superseded?
  2. Has its effective window ended? Compare its end date to the research date — an
     instrument whose window closed yesterday is not in force today.
  3. Does it cover this product and this origin, by its own stated scope?
An instrument failing any test goes in confirmed_absent, naming the instrument and what
disqualified it. Never record it as an additional duty with a 0% rate or an explanatory note.

rate holds a bare percentage and nothing else. authority holds the instrument and its citation
and nothing else. Status belongs in in_force and ends, never in prose inside another field.

## Methodology
Establish current state, not history: where an instrument has been modified or terminated by a
later one, report the latest state and cite both. Compute absolute dates from any relative
reference, and state the research date you are reasoning from. Use ISO 8601.

## Missing data
Distinguish three cases explicitly and never collapse them: (a) an overlay in force, which goes
in additional_duties with in_force true, (b) an overlay checked and confirmed not to apply —
terminated, expired, or out of scope — which goes in confirmed_absent, and (c) an overlay you
could not verify, which goes in unverified with what you attempted. Never invent an instrument,
a rate, or a date. Use null, never omit a field.

An empty additional_duties list is a legitimate, complete answer when only the base rate
applies. Do not pad it with instruments you ruled out."""

OVERLAY_GOALS = [
    "Every entry in additional_duties is collectible on the research date, with in_force true — terminated, expired and out-of-scope instruments appear in confirmed_absent instead",
    "Each additional_duties entry carries a bare rate and a bare instrument citation, with no status prose inside either field",
    "Sets ends to the date an instrument stops applying, or null when open-ended, and never lists an instrument whose window has already closed",
    "Never blends overlay components into a single combined rate, and never includes the MFN base rate",
    "Places unverifiable overlays in unverified with what was attempted — never conflated with confirmed_absent",
    "Cites an official instrument for every overlay claimed to be in force",
]

OVERLAY_SOURCES = {
    "allow": [
        {
            "title": "Federal Register",
            "domains": ["federalregister.gov", "www.federalregister.gov"],
            "order": 0,
        },
        {"title": "USTR", "domains": ["ustr.gov", "www.ustr.gov"], "order": 1},
        {
            "title": "White House presidential actions",
            "domains": ["whitehouse.gov", "www.whitehouse.gov"],
            "order": 2,
        },
        {
            "title": "US Customs and Border Protection",
            "domains": ["cbp.gov", "www.cbp.gov", "rulings.cbp.gov"],
            "order": 3,
        },
        {
            "title": "USITC",
            "domains": ["hts.usitc.gov", "usitc.gov", "www.usitc.gov"],
            "order": 4,
        },
    ],
    "block": [],
    "prioritize": "official instruments — register notices, executive orders, and agency determinations",
    "avoid": "news summaries, law-firm marketing posts, and broker commentary",
}

OVERLAY_QUESTIONS = [
    "Which duty overlays are currently in force for HTS 8507.60.00 imported from Vietnam into the United States?",
    "Which duty overlays apply to HTS 8507.60.00 from China into the United States?",
    "Is any exclusion still in force for HTS 7604.29.10 from Mexico into the United States?",
    "Which overlays apply to HTS 4901.99.00 from the United Kingdom into the United States?",
]

OVERLAY_AGENT = {
    "display_name": "Tariff Policy Overlay",
    "description": "Establishes which duty overlays (301/232/IEEPA/reciprocal) are in force for a lane, with instruments and dates.",
    "icon": "⚖️",
    "use_case": "enrichment",
    "effort": "high",
    "skill": OVERLAY_SKILL,
    "goals": OVERLAY_GOALS,
    "sources": OVERLAY_SOURCES,
    "output_schema": OVERLAY_SCHEMA,
    "suggested_questions": OVERLAY_QUESTIONS,
}

AGENTS = {"rate": RATE_AGENT, "overlay": OVERLAY_AGENT}

# Effort per fact class, chosen from measurement rather than preference.
#
# rate    = medium. Correct and `verified_against_official_schedule: true` on every
#           run; one official source, one number. Higher tiers buy nothing.
# overlay = high.   At medium the agent was confidently wrong three ways: expired
#           instruments listed as in force, a duty asserted while its own
#           terminating order sat in `unverified`, and duties described in prose
#           while the structured array was empty. At high (2026-08-05 test) it
#           structured the China duties correctly and found the terminating order
#           medium had missed across three runs. Cost ~2.4x (≈220s vs ≈95s).
EFFORT = {"rate": "medium", "overlay": "high"}

# TTLs per DESIGN.md §2 — the reason there are two agents at all.
TTL_DAYS = {"rate": 90, "overlay": 7}


# --- hts-code-candidates --------------------------------------------------
# A lookup helper, not a corpus fact class. Answers "which tariff codes might
# cover this product?" so a reader who doesn't know HTS notation can get started.
# Deliberately returns CANDIDATES with citations: classification is a human
# decision and a wrong code yields a confidently wrong duty for the wrong product.

HTS_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "candidates": {
            "type": "array",
            "description": "Plausible subheadings, most likely first. 2-5 entries.",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["hts_code", "description"],
                "properties": {
                    "hts_code": {
                        "type": "string",
                        "description": (
                            "A full statistical line in dotted form — 8 or 10 digits, "
                            "e.g. '6404.11.20' or '8507.60.0020'. A duty rate only "
                            "exists at this level. Return a 4-digit heading or 6-digit "
                            "subheading ONLY when the description is too vague to reach "
                            "a line, and then set is_full_rate_line to false."
                        ),
                    },
                    "is_full_rate_line": {
                        "type": "boolean",
                        "description": (
                            "True only for an 8- or 10-digit line that carries its own "
                            "Rates of Duty entry. False for a heading or subheading, "
                            "whose rate columns are blank."
                        ),
                    },
                    "narrowing_needed": {
                        "type": ["string", "null"],
                        "description": (
                            "When is_full_rate_line is false, the specific detail needed "
                            "to reach a rate line — e.g. 'upper material and whether it "
                            "is sports footwear'. null when the line is already full."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": "The schedule's own wording for this line, quoted.",
                    },
                    "why_it_might_fit": {
                        "type": "string",
                        "description": "One sentence tying the product to this line.",
                    },
                    "chapter": {"type": ["string", "null"]},
                    "source_url": {"type": "string"},
                },
            },
        },
        "what_would_settle_it": {
            "type": ["string", "null"],
            "description": (
                "What a person would need to check or decide to choose between the "
                "candidates — material, function, end use, or a CBP ruling."
            ),
        },
        "data_as_of_date": {"type": "string"},
    },
}

HTS_SKILL = """You are a customs classification assistant helping someone who does not \
know tariff notation find where their product might sit in the schedule.

## Where to search
Only the official Harmonized Tariff Schedule of the United States published by the
USITC at hts.usitc.gov, including its chapter documents. Quote the schedule's own
wording for each line.

## Field rules
Return 2 to 5 candidates, most likely first, and prefer **full statistical lines** — 8
or 10 digits, the level that actually carries a Rates of Duty entry. A 4-digit heading
or 6-digit subheading has blank rate columns, so returning one gives the reader a code
no rate can be attached to.

If the description is too vague to reach a line, you may return the heading, but set
is_full_rate_line to false and put the missing detail in narrowing_needed. Prefer to
offer full lines for the most likely readings — for footwear described only as
"sneakers", give the specific lines for textile-upper and for rubber-upper sports
footwear rather than the headings that contain them.

Quote each line's description verbatim from the schedule rather than paraphrasing it.
Give the URL of the chapter document you read it from.

## Methodology
Work from what the product is made of and what it does. Where the schedule
distinguishes lines by material, end use, or a statistical suffix, surface the
distinction as separate candidates rather than picking one.

## The boundary you must not cross
You are NOT classifying the product. You are showing a person where to look. Never
present one candidate as the answer, never say a code "is" the correct one, and always
fill what_would_settle_it with what a human still has to decide. If the product
description is too vague to narrow down, return the broader headings and say so."""

HTS_GOALS = [
    "Returns 2 to 5 candidates, most likely first, never a single answer",
    "Prefers full 8- or 10-digit statistical lines, which are the only level carrying a duty rate",
    "Sets is_full_rate_line false for any heading or subheading returned, with the missing detail in narrowing_needed",
    "Quotes each candidate's description verbatim from the official schedule",
    "Cites the usitc.gov chapter document each candidate was read from",
    "Fills what_would_settle_it with the distinction a human still has to decide",
    "Surfaces material, end-use and statistical-suffix distinctions as separate candidates",
]

HTS_SOURCES = {
    # Wider than the rate agent's allow list, and for a specific reason: the schedule
    # is organised BY CODE, so it answers "what is the rate for 8507.60.00" well and
    # "which code covers a drinks bottle" badly. CBP's ruling database is searchable by
    # product description and every ruling names the subheading it classified under —
    # which is the resource a person would actually use for a reverse lookup.
    "allow": [
        {
            "title": "USITC Harmonized Tariff Schedule",
            "domains": ["hts.usitc.gov", "usitc.gov", "www.usitc.gov"],
            "order": 0,
        },
        {
            "title": "CBP rulings (CROSS) and classification guidance",
            "domains": ["rulings.cbp.gov", "cbp.gov", "www.cbp.gov"],
            "order": 1,
        },
    ],
    "block": [],
    "prioritize": "the official HTSUS chapter documents published by the USITC",
    "avoid": "customs-broker blogs, freight-forwarder marketing pages, and news summaries",
}

HTS_QUESTIONS = [
    "Which tariff lines might cover canvas sneakers with rubber soles?",
    "Which tariff codes might cover lithium-ion battery packs?",
    "Which tariff codes might cover cotton knit t-shirts?",
    "Which tariff codes might cover aluminium extrusions for window frames?",
    "Which tariff codes might cover a stainless steel insulated drinks bottle?",
]

HTS_AGENT = {
    "display_name": "HTS Code Candidates",
    "description": "Suggests candidate HTS subheadings for a plain-language product description, with citations.",
    "icon": "🔍",
    "use_case": "research",
    "effort": "medium",
    "skill": HTS_SKILL,
    "goals": HTS_GOALS,
    "sources": HTS_SOURCES,
    "output_schema": HTS_SCHEMA,
    "suggested_questions": HTS_QUESTIONS,
}

AGENTS["hts"] = HTS_AGENT
EFFORT["hts"] = "medium"
