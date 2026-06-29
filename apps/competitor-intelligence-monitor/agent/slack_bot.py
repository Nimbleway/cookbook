"""
Slack bot for /competitor-digest personalized onboarding.
Runs as a standalone service — separate from the daily GitHub Actions agent.

Required env vars:
  SLACK_BOT_TOKEN         (same as agent)
  SLACK_SIGNING_SECRET    (Slack App > Basic Information > App Credentials)
"""

import os
import json
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

from user_prefs import load_all_prefs, save_prefs

load_dotenv(override=True)

# ─── Load config ─────────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent / "config.json"
with open(_CONFIG_PATH) as _f:
    _CONFIG = json.load(_f)
YOUR_COMPANY = _CONFIG["your_company"]["name"]

bolt_app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
)


# ─── Static data ─────────────────────────────────────────────────────────────

ALL_CATEGORIES = [
    "Funding",
    "Product Launch",
    "Reliability",
    "Customer Feedback",
    "Hiring",
    "Pricing",
    "Partnership",
    "Community",
    "Positioning",
]

CATEGORY_DESCRIPTIONS = {
    "Funding":           "Rounds, acquisitions, and valuation signals",
    "Product Launch":    "New features, releases, and API updates",
    "Reliability":       "Outages, incidents, and stability reports",
    "Customer Feedback": "Reviews, Reddit threads, and user sentiment",
    "Hiring":            "Job postings and team growth signals",
    "Pricing":           "Price changes, tier updates, and packaging shifts",
    "Partnership":       "Integrations, co-marketing, and ecosystem moves",
    "Community":         "Developer discussions, HN, and forum activity",
    "Positioning":       "Messaging changes and direct comparisons",
}

TEAMS = [
    "Sales",
    "Marketing",
    "Product",
    "Engineering",
    "Executive",
    "Growth",
    "Other",
]

TEAM_DESCRIPTIONS = {
    "Sales":       "Competitive weaknesses and deal intelligence",
    "Marketing":   "Positioning, messaging, and share of voice",
    "Product":     "Feature launches and developer community feedback",
    "Engineering": "GitHub activity, HN threads, and API changes",
    "Executive":   "Strategic moves and the signal of the day",
    "Growth":      "Community growth and developer adoption signals",
    "Other":       "Full digest — all categories included",
}

TEAM_DEFAULTS = {
    "Sales": {
        "categories": ["Customer Feedback", "Pricing", "Hiring", "Reliability", "Funding"],
        "include_nimble": False,
        "format": "detailed",
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "headline": "Your competitive edge in every deal",
        "rationale": (
            "Customer complaints and reliability incidents are the strongest data points "
            "in a live deal. Hiring spikes predict competitive pressure 90 days out. "
            "Pricing changes open windows to lock in long-term contracts."
        ),
    },
    "Marketing": {
        "categories": ["Positioning", "Community", "Product Launch", "Partnership"],
        "include_nimble": True,
        "format": "brief",
        "days": ["monday", "wednesday", "friday"],
        "headline": "Your market intelligence lens",
        "rationale": (
            "Positioning shifts and community sentiment shape how the market perceives "
            "competitors vs. Nimble. Product launches and partnerships signal new angles "
            "to monitor in messaging and channel strategy."
        ),
    },
    "Product": {
        "categories": ["Product Launch", "Community", "Customer Feedback", "Reliability"],
        "include_nimble": True,
        "format": "detailed",
        "days": ["monday", "wednesday", "friday"],
        "headline": "Roadmap fuel, delivered on your schedule",
        "rationale": (
            "Competitor launches and developer community discussions directly inform "
            "your roadmap. Customer sentiment and reliability incidents reveal the gaps "
            "you can address in your next sprint."
        ),
    },
    "Engineering": {
        "categories": ["Product Launch", "Community", "Reliability"],
        "include_nimble": False,
        "format": "detailed",
        "days": ["monday", "friday"],
        "headline": "Ground-level developer signal",
        "rationale": (
            "GitHub activity, Hacker News threads, and technical blog posts give you "
            "the unfiltered view of what developers actually think — the signal most "
            "correlated with real adoption trends."
        ),
    },
    "Executive": {
        "categories": ["Funding", "Product Launch", "Partnership", "Positioning"],
        "include_nimble": True,
        "format": "brief",
        "days": ["monday"],
        "headline": "The view from 30,000 feet",
        "rationale": (
            "Funding rounds, major launches, and strategic partnerships signal direction "
            "changes that affect Nimble's market position. One signal of the day and the "
            "top move per competitor — highest-signal items only."
        ),
    },
    "Growth": {
        "categories": ["Community", "Funding", "Partnership", "Product Launch", "Hiring"],
        "include_nimble": True,
        "format": "brief",
        "days": ["monday", "wednesday", "friday"],
        "headline": "Where competitors are building pipeline",
        "rationale": (
            "Community growth signals and new partnerships reveal where competitors are "
            "investing in developer acquisition. Hiring volume shows growth capacity "
            "building before it shows up in revenue or market share."
        ),
    },
    "Other": {
        "categories": ALL_CATEGORIES[:],
        "include_nimble": True,
        "format": "detailed",
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "headline": "The full picture",
        "rationale": "You'll receive every data category — nothing filtered out.",
    },
}

TEAM_DM_BULLETS = {
    "Sales": [
        "🔴  Customer complaints and reliability incidents — shareable in deals",
        "💰  Pricing changes that open competitive windows",
        "📈  Hiring spikes — 90-day competitive pressure forecast",
        "💸  Funding rounds and their implications for deal urgency",
    ],
    "Marketing": [
        "📣  Competitor positioning and messaging shifts",
        "📊  Community sentiment and organic share of voice data",
        "🚀  Product launches that affect your narrative",
        "🤝  New partnerships entering your competitive landscape",
    ],
    "Product": [
        "🚀  Competitor feature launches and API changes",
        "💬  Developer community feedback and adoption signals",
        "🗣️  Customer sentiment across review platforms",
        "⚡  Reliability incidents that reveal competitive gaps",
    ],
    "Engineering": [
        "🚀  New releases, SDKs, and API updates",
        "💬  HN, Reddit, and developer forum discussions",
        "⚡  Outages and reliability incidents across all APIs",
    ],
    "Executive": [
        "🎯  Signal of the day — the single most important move",
        "💸  Funding rounds and strategic acquisitions",
        "🤝  Partnerships that shift the competitive landscape",
        "📣  Positioning changes affecting Nimble's market position",
    ],
    "Growth": [
        "💬  Community growth and developer adoption data",
        "💸  Funding rounds and growth investment signals",
        "🤝  New partnerships expanding competitor distribution",
        "🚀  Product launches affecting developer acquisition",
        "📈  Hiring signals showing growth investment",
    ],
    "Other": [
        "📊  Full competitive intelligence — all categories",
        "🎯  Signal of the day — highest-impact move each morning",
        "📣  Positioning alerts and direct Nimble comparisons",
    ],
}

TEAM_SAMPLE_FINDING = {
    "Sales": (
        "🔴  *Firecrawl*  `High`  `Customer Feedback`\n"
        "_Developers reporting 3× rate limit errors on the free tier — multiple Reddit threads this week._\n"
        "↳ _Support tickets up 40% YoY. Prospects who mention Firecrawl are now more receptive to switching._\n"
        "`Customer Feedback · Reddit · Organic`"
    ),
    "Marketing": (
        "🟢  *Exa*  `High`  `Positioning`\n"
        "_Exa repositioned from 'neural search' to 'the web API for AI agents' across all channels._\n"
        "↳ _Direct overlap with Nimble's agent-data positioning — new tagline already appearing in developer comparisons._\n"
        "`Positioning · Blog · Self-Promoted`"
    ),
    "Product": (
        "🟢  *Firecrawl*  `Medium`  `Product Launch`\n"
        "_Firecrawl shipped async batch scraping with JSON schema extraction in a single API call._\n"
        "↳ _Directly competes with Nimble's batch pipeline. Developers comparing both APIs side by side in community threads._\n"
        "`Product Launch · GitHub · Self-Promoted`"
    ),
    "Engineering": (
        "🔴  *Brave AI*  `Medium`  `Reliability`\n"
        "_Brave Search API returned empty results for 6 hours on June 4 — HN thread reached #12._\n"
        "↳ _Community trust in Brave Search as an API dependency is declining. Developers actively discussing alternatives._\n"
        "`Reliability · Hacker News · Organic`"
    ),
    "Executive": (
        "🟢  *Tavily*  `High`  `Funding`\n"
        "_Tavily confirmed acquisition by Nebius — deal closes Q3 2026._\n"
        "↳ _Nebius brings EU distribution. Nimble's enterprise positioning in that region is now under direct pressure._\n"
        "`Funding · News · Organic`"
    ),
    "Growth": (
        "🟢  *Tavily*  `High`  `Community`\n"
        "_Tavily crossed 2 million registered developers — announced on X with strong organic amplification._\n"
        "↳ _Developer mindshare is compounding. Nimble's community volume is significantly lower — this widens the awareness gap._\n"
        "`Community · Twitter/X · Self-Promoted`"
    ),
    "Other": (
        "🟢  *Exa*  `High`  `Funding`\n"
        "_Exa raised $250M Series C at a $1.2B valuation — confirmed by TechCrunch._\n"
        "↳ _Now the best-funded pure-play web search API. Expect aggressive pricing and sales hiring in the next 90 days._\n"
        "`Funding · News · Organic`"
    ),
}

TEAM_DESCRIPTIONS = {k: v.replace("Nimble", YOUR_COMPANY) for k, v in TEAM_DESCRIPTIONS.items()}
TEAM_DEFAULTS = {
    k: {**v, "rationale": v["rationale"].replace("Nimble", YOUR_COMPANY), "headline": v["headline"].replace("Nimble", YOUR_COMPANY)}
    for k, v in TEAM_DEFAULTS.items()
}
TEAM_DM_BULLETS = {k: [s.replace("Nimble", YOUR_COMPANY) for s in v] for k, v in TEAM_DM_BULLETS.items()}
TEAM_SAMPLE_FINDING = {k: v.replace("Nimble", YOUR_COMPANY) for k, v in TEAM_SAMPLE_FINDING.items()}

ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

FORMAT_OPTIONS = [
    {
        "text": {"type": "plain_text", "text": "Detailed"},
        "description": {"type": "plain_text", "text": "Full findings with context — ~5 min read"},
        "value": "detailed",
    },
    {
        "text": {"type": "plain_text", "text": "Brief"},
        "description": {"type": "plain_text", "text": "Top signal per competitor — ~60 seconds"},
        "value": "brief",
    },
]

OUTPUT_OPTIONS = [
    {
        "text": {"type": "plain_text", "text": "Slack DM"},
        "description": {"type": "plain_text", "text": "Delivered here in Slack"},
        "value": "slack",
    },
]


# ─── Modal builders ───────────────────────────────────────────────────────────

def _initial_option(opts: list, val: str) -> dict | None:
    return next((o for o in opts if o["value"] == val), None)


def _step1_view(existing: dict = None) -> dict:
    is_update = bool(existing)

    team_opts = [
        {
            "text": {"type": "plain_text", "text": t},
            "description": {"type": "plain_text", "text": TEAM_DESCRIPTIONS[t]},
            "value": t,
        }
        for t in TEAMS
    ]

    team_element = {
        "type": "static_select",
        "action_id": "team_select",
        "placeholder": {"type": "plain_text", "text": "Choose your team"},
        "options": team_opts,
    }
    if existing and existing.get("team") in TEAMS:
        team_element["initial_option"] = _initial_option(team_opts, existing["team"])

    fmt_element = {
        "type": "static_select",
        "action_id": "format_select",
        "placeholder": {"type": "plain_text", "text": "Choose format"},
        "options": FORMAT_OPTIONS,
    }
    if existing and existing.get("format"):
        fmt_element["initial_option"] = _initial_option(FORMAT_OPTIONS, existing["format"])

    output_element = {
        "type": "static_select",
        "action_id": "output_select",
        "placeholder": {"type": "plain_text", "text": "Where should we send it?"},
        "options": OUTPUT_OPTIONS,
    }
    if existing and existing.get("output"):
        output_element["initial_option"] = _initial_option(OUTPUT_OPTIONS, existing["output"])

    existing_days = set(existing.get("days", [])) if existing else set()
    day_opts = [{"text": {"type": "plain_text", "text": d.capitalize()}, "value": d} for d in ALL_DAYS]
    initial_days = [{"text": {"type": "plain_text", "text": d.capitalize()}, "value": d}
                    for d in ALL_DAYS if d in existing_days] if existing else []

    days_element = {
        "type": "checkboxes",
        "action_id": "days_select",
        "options": day_opts,
    }
    if initial_days:
        days_element["initial_options"] = initial_days

    if is_update:
        intro = (
            "*Step 1 of 2  ●──○*\n\n"
            "Updating your preferences — changes take effect on the next digest run."
        )
    else:
        intro = (
            "*Step 1 of 2  ●──○*\n\n"
            "You're 60 seconds away from a daily feed of competitor intelligence "
            "filtered to exactly what matters for you."
        )

    return {
        "type": "modal",
        "callback_id": "onboarding_step1",
        "title": {"type": "plain_text", "text": "Competitor Digest"},
        "submit": {"type": "plain_text", "text": "Next  →"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": intro},
            },
            {"type": "divider"},
            # Name
            {
                "type": "input",
                "block_id": "name_block",
                "label": {"type": "plain_text", "text": "Your first name"},
                "hint": {"type": "plain_text", "text": "Used to personalize your digest — Hi [Name], …"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "name_input",
                    "placeholder": {"type": "plain_text", "text": "e.g. Sarah"},
                    **({"initial_value": existing["name"]} if existing and existing.get("name") else {}),
                },
            },
            # Team
            {
                "type": "input",
                "block_id": "team_block",
                "label": {"type": "plain_text", "text": "What team are you on?"},
                "hint": {
                    "type": "plain_text",
                    "text": "Sets your default data categories — you'll fine-tune exactly what you see in the next step.",
                },
                "element": team_element,
            },
            # Days
            {
                "type": "input",
                "block_id": "days_block",
                "label": {"type": "plain_text", "text": "Which days do you want your digest?"},
                "element": days_element,
                "optional": True,
            },
            # Format
            {
                "type": "input",
                "block_id": "format_block",
                "label": {"type": "plain_text", "text": "Format"},
                "element": fmt_element,
            },
        ],
    }


def _step2_view(name: str, team: str, days: list, fmt: str,
                output: str = "slack", email: str = "",
                existing_cats: list = None, existing_nimble: bool = None) -> dict:
    defaults = TEAM_DEFAULTS.get(team, TEAM_DEFAULTS["Other"])
    selected_cats = existing_cats if existing_cats is not None else defaults["categories"]
    include_nimble = existing_nimble if existing_nimble is not None else defaults.get("include_nimble", True)

    cat_opts = [
        {
            "text": {"type": "plain_text", "text": c},
            "description": {"type": "plain_text", "text": CATEGORY_DESCRIPTIONS[c]},
            "value": c,
        }
        for c in ALL_CATEGORIES
    ]
    initial_cats = [
        {
            "text": {"type": "plain_text", "text": c},
            "description": {"type": "plain_text", "text": CATEGORY_DESCRIPTIONS[c]},
            "value": c,
        }
        for c in selected_cats if c in ALL_CATEGORIES
    ]

    nimble_opt = {
        "text": {"type": "plain_text", "text": f"Include {YOUR_COMPANY}'s own market mentions"},
        "description": {"type": "plain_text", "text": f"What people are saying about {YOUR_COMPANY} across the web"},
        "value": "yes",
    }
    nimble_block = {
        "type": "input",
        "block_id": "nimble_block",
        "label": {"type": "plain_text", "text": f"{YOUR_COMPANY} mentions"},
        "element": {
            "type": "checkboxes",
            "action_id": "nimble_select",
            "options": [nimble_opt],
        },
        "optional": True,
    }
    if include_nimble:
        nimble_block["element"]["initial_options"] = [nimble_opt]

    sample = TEAM_SAMPLE_FINDING.get(team, TEAM_SAMPLE_FINDING["Other"])

    return {
        "type": "modal",
        "callback_id": "onboarding_step2",
        "private_metadata": json.dumps({"name": name, "team": team, "days": days, "format": fmt, "output": output, "email": email}),
        "title": {"type": "plain_text", "text": "Competitor Digest"},
        "submit": {"type": "plain_text", "text": "Save  ✓"},
        "close": {"type": "plain_text", "text": "Back"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Step 2 of 2  ●──●*\n\n"
                        f"*{defaults['headline']}*\n"
                        f"{defaults['rationale']}"
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "categories_block",
                "label": {"type": "plain_text", "text": "Data categories to include"},
                "hint": {
                    "type": "plain_text",
                    "text": "Pre-selected for your team. Uncheck anything you don't need.",
                },
                "element": {
                    "type": "checkboxes",
                    "action_id": "categories_select",
                    "options": cat_opts,
                    "initial_options": initial_cats,
                },
                "optional": True,
            },
            {"type": "divider"},
            nimble_block,
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Here's what a finding looks like in your digest:*",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": sample},
            },
        ],
    }


# ─── Confirmation DM ──────────────────────────────────────────────────────────

def _confirmation_dm(prefs: dict) -> list:
    name      = prefs.get("name", "")
    team      = prefs.get("team", "")
    days      = prefs.get("days", [])
    fmt       = prefs.get("format", "detailed")
    output    = prefs.get("output", "slack")
    email     = prefs.get("email", "")
    categories = prefs.get("categories", [])
    include_nimble = prefs.get("include_nimble", True)

    greeting  = f"Hi {name}! 👋\n\n" if name else ""
    days_str  = ", ".join(d.capitalize() for d in days) if days else "Every day"
    cat_chips = "  ".join(f"`{c}`" for c in categories) if categories else "_all categories_"
    fmt_label = "Detailed digest" if fmt == "detailed" else "Brief highlights"
    output_label = {"slack": "Slack DM", "email": f"Email ({email})" if email else "Email", "both": f"Slack + Email ({email})" if email else "Slack + Email"}.get(output, "Slack DM")
    bullets   = TEAM_DM_BULLETS.get(team, TEAM_DM_BULLETS["Other"])
    sample    = TEAM_SAMPLE_FINDING.get(team, TEAM_SAMPLE_FINDING["Other"])

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{greeting}*You're in.*\n\n"
                    f"Your competitor intelligence digest is set up. "
                    f"Here's exactly what you'll receive."
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Team*\n{team}"},
                {"type": "mrkdwn", "text": f"*Format*\n{fmt_label}"},
                {"type": "mrkdwn", "text": f"*Days*\n{days_str}"},
                {"type": "mrkdwn", "text": f"*Delivery*\n{output_label}"},
                {"type": "mrkdwn", "text": f"*{YOUR_COMPANY}*\n{'Included' if include_nimble else 'Excluded'}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Categories*\n{cat_chips}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*What you'll receive:*\n" + "\n".join(bullets),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Every finding looks like this:*"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": sample},
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Run `/competitor-digest` at any time to update your name, team, days, or categories.",
                }
            ],
        },
    ]


# ─── Slack handlers ───────────────────────────────────────────────────────────

@bolt_app.command("/competitor-digest")
def handle_command(ack, body, client):
    ack()
    user_id = body["user_id"]
    existing = load_all_prefs().get(user_id)
    client.views_open(trigger_id=body["trigger_id"], view=_step1_view(existing))


@bolt_app.view("onboarding_step1")
def handle_step1(ack, body, view):
    values = view["state"]["values"]
    name   = values["name_block"]["name_input"].get("value", "").strip()
    team   = values["team_block"]["team_select"]["selected_option"]["value"]
    fmt    = values["format_block"]["format_select"]["selected_option"]["value"]
    output = "slack"
    email  = ""

    selected_day_opts = values.get("days_block", {}).get("days_select", {}).get("selected_options", [])
    days = [opt["value"] for opt in selected_day_opts]
    if not days:
        days = TEAM_DEFAULTS.get(team, TEAM_DEFAULTS["Other"])["days"]

    user_id = body["user"]["id"]
    existing = load_all_prefs().get(user_id)
    existing_cats   = existing.get("categories") if existing else None
    existing_nimble = existing.get("include_nimble") if existing else None

    ack(response_action="push",
        view=_step2_view(name, team, days, fmt, output, email, existing_cats, existing_nimble))


@bolt_app.view("onboarding_step2")
def handle_step2(ack, body, view, client):
    ack(response_action="clear")

    user_id = body["user"]["id"]
    meta    = json.loads(view.get("private_metadata", "{}"))
    values  = view["state"]["values"]

    selected_cats = [opt["value"] for opt in
                     values.get("categories_block", {})
                     .get("categories_select", {})
                     .get("selected_options", [])]

    nimble_opts = (values.get("nimble_block", {})
                   .get("nimble_select", {})
                   .get("selected_options", []))

    prefs = {
        "name":           meta.get("name", ""),
        "team":           meta.get("team", ""),
        "days":           meta.get("days", []),
        "format":         meta.get("format", "detailed"),
        "output":         meta.get("output", "slack"),
        "email":          meta.get("email", ""),
        "categories":     selected_cats,
        "include_nimble": len(nimble_opts) > 0,
    }

    save_error = None
    try:
        save_prefs(user_id, prefs)
    except Exception as e:
        save_error = str(e)
        print(f"[Bot] save_prefs failed for {user_id}: {e}")

    if save_error:
        client.chat_postMessage(
            channel=user_id,
            text=f":warning: Preferences couldn't be saved — please check your configuration.\nError: `{save_error}`",
        )
    else:
        client.chat_postMessage(
            channel=user_id,
            blocks=_confirmation_dm(prefs),
            text="You're set up for the competitor digest.",
            unfurl_links=False,
        )


# ─── Flask adapter ────────────────────────────────────────────────────────────

flask_app = Flask(__name__)
handler   = SlackRequestHandler(bolt_app)


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


@flask_app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)
