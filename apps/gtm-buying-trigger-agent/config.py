"""Use-case configuration for the GTM buying trigger agent.

The watchlist, the monitoring window and the trigger definition live here and are
shared by both patterns in ``agent.py``:

  Pattern A (Search API)        WATCHLIST, QUERY_TEMPLATES, SEARCH_PARAMS
  Pattern B (Web Search Agent)  AGENT_*, GOALS, SOURCES, OUTPUT_SCHEMA, run_prompt()
  Both (post_process)           window(), TRIGGER_TYPES, STRENGTHS

The values below are the ones used for the B2B software watchlist runs on 2026-10-12.
"""

import os
from datetime import date, timedelta

# --- watchlist ---------------------------------------------------------------
#
# descriptor      added to every query so news about the account is found among
#                 market roundups
# prompt_note     optional description passed to the Web Search Agent next to the domain

WATCHLIST = [
    {"name": "Cato Networks", "domain": "catonetworks.com", "descriptor": "SASE"},
    {"name": "Mark43", "domain": "mark43.com", "descriptor": "public safety software"},
    {"name": "Veylo", "domain": "veylo.com", "descriptor": "AI modernization",
     "prompt_note": "formerly BlueGenAI"},
    {"name": "BlueVoyant", "domain": "bluevoyant.com", "descriptor": "cybersecurity"},
    {"name": "commercetools", "domain": "commercetools.com", "descriptor": "commerce platform"},
]

# --- monitoring window ---------------------------------------------------------

WINDOW_DAYS = 30


def window() -> tuple[str, str]:
    """(start, end) as YYYY-MM-DD. End is today, or AS_OF_DATE when set.

    AS_OF_DATE=2026-10-12 reproduces the committed example: 2026-09-12 to 2026-10-12.
    """
    end = date.fromisoformat(os.getenv("AS_OF_DATE") or date.today().isoformat())
    return (end - timedelta(days=WINDOW_DAYS)).isoformat(), end.isoformat()


# --- what counts as a trigger ------------------------------------------------------

SELLER_CONTEXT = ("the seller offers revenue and go-to-market software to fast-growing "
                  "B2B software companies.")
TRIGGER_DEFINITION = (
    "A buying trigger is a company event that changes the account's go-to-market "
    "priorities, budget or team: a funding round, a new executive (especially sales, "
    "marketing, revenue or operations leadership), a new office, market or hiring push, "
    "a major product launch, a partnership, an acquisition, or a large customer win."
)
TRIGGER_TYPES = ["funding_round", "leadership_hire", "expansion", "product_launch",
                 "partnership", "acquisition", "customer_win", "other"]
STRENGTHS = ["High", "Medium", "Low"]  # strongest first

# --- Pattern A: Search API -----------------------------------------------------------

# One query per trigger family, per account.
QUERY_TEMPLATES = [
    "{name} {descriptor} funding round acquisition",
    "{name} {descriptor} appoints executive hire chief",
    "{name} {descriptor} launches expansion partnership",
]

# start_date is set to the window start at run time.
SEARCH_PARAMS = dict(focus="news", search_depth="lite", max_results=8)

# Characters of result text passed to the extraction model per result.
EVIDENCE_CHARS = 600

# --- Pattern B: Web Search Agent (definition from the live API, 2026-10-12) ----------

AGENT_NAME = "gtm-buying-trigger-monitor"
AGENT_DISPLAY_NAME = "GTM Buying Trigger Monitor"
AGENT_DESCRIPTION = ("Monitors a watchlist of accounts for recent company news that signals a "
                     "buying trigger, and returns dated, typed, cited trigger events plus the "
                     "events it excluded.")
USE_CASE = "research"
EFFORT = "high"  # low | medium | high | x-high | max

GOALS = [
    "Report only events whose own date (not the article's publish date) falls inside the "
    "monitoring window; put older events that were republished or re-covered in excluded_events.",
    "Resolve each account by its domain and ignore news about other companies with similar names.",
    "Return exactly one entry in accounts per watchlist company, with that company's triggers "
    "nested inside it.",
    "Classify every event into exactly one trigger_type and grade strength by how directly it "
    "changes the account's go-to-market priorities or budget.",
    "Cite the page that reports the event itself: the company newsroom, blog or press release "
    "when one exists; otherwise reputable press.",
    "Return one trigger per underlying event, even when many outlets covered it.",
    "Write the outreach angle only from facts stated in that account's triggers.",
    "Return accounts with no qualifying event with trigger_count 0 instead of padding with weak events.",
]

# The API stored the goals inside the skill text in this form on 2026-10-12. Used only
# if agents.create rejects the goals parameter.
DEFAULT_SKILL = "General research"


def skill_with_goals() -> str:
    return f"{DEFAULT_SKILL}\n\nGoals:\n- " + "\n- ".join(GOALS)


SOURCES = {
    "prioritize": ("Company newsrooms and blogs, press releases (PR Newswire, Business Wire, "
                   "GlobeNewswire), reputable business and technology press (Bloomberg, Reuters, "
                   "TechCrunch, CRN, SiliconANGLE, Government Technology)"),
    "avoid": ("Vendor comparison listicles, aggregator pages that re-date old news, and "
              "job-board pages as evidence of an event"),
}

TRIGGER_ITEM = {
    "type": "object",
    "required": ["event_date", "trigger_type", "headline", "strength", "source_url"],
    "properties": {
        "event_date": {"type": "string",
                       "description": "Date the event happened or was announced, YYYY-MM-DD"},
        "trigger_type": {"type": "string", "enum": TRIGGER_TYPES},
        "headline": {"type": "string"},
        "why_it_is_a_trigger": {"type": "string"},
        "strength": {"type": "string", "enum": STRENGTHS},
        "source_url": {"type": "string"},
    },
}

OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["window_start", "window_end", "accounts", "excluded_events"],
    "properties": {
        "window_start": {"type": "string"},
        "window_end": {"type": "string"},
        "accounts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["company", "domain", "trigger_count", "triggers"],
                "properties": {
                    "company": {"type": "string"},
                    "domain": {"type": "string"},
                    "trigger_count": {"type": "integer"},
                    "strongest_trigger": {
                        "type": ["string", "null"],
                        "description": "Headline of the trigger that most changes the account's go-to-market priorities",
                    },
                    "outreach_angle": {
                        "type": ["string", "null"],
                        "description": "One sentence a rep could open with, using only facts from this account's triggers",
                    },
                    "triggers": {"type": "array", "items": TRIGGER_ITEM},
                },
            },
        },
        "excluded_events": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["company", "headline", "reason"],
                "properties": {
                    "company": {"type": "string"},
                    "headline": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}


def run_prompt() -> str:
    """The Web Search Agent run input, built from the watchlist, window and context."""
    start, end = window()
    accounts = "\n".join(
        f"- {a['name']} ({a['domain']})" + (f", {a['prompt_note']}" if a.get("prompt_note") else "")
        for a in WATCHLIST
    )
    return (
        f"Monitor these accounts for buying triggers in the window {start} to {end} "
        f"(today is {end}):\n{accounts}\n"
        f"Context: {SELLER_CONTEXT} {TRIGGER_DEFINITION}\n"
        "For each account, return every qualifying event in the window with its event date, "
        "trigger type, strength, why it is a trigger and a source URL, plus a one-sentence "
        "outreach angle based on the strongest trigger. List events you rejected (outside the "
        "window, about a different company, or not a trigger) in excluded_events with the reason."
    )
