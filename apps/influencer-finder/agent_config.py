"""Canonical production agent config — the exact config validated in the design smoke.

One dataset_building agent: discovers influencers matching a niche + platform + follower
band + geography. Single runs yield ~5-10 quality matches; the app accumulates a dataset
by running several queries and upserting into Supabase (dedup on platform+handle).
"""

INFLUENCER_FINDER = {
    "display_name": "Influencer Finder",
    "description": "Discovers a dataset of influencers matching a niche, platform, follower band, and geography.",
    "icon": "📣",
    "use_case": "dataset_building",
    "effort": "high",
    "domain_expertise": """# Influencer Discovery — Domain Expertise

You are an influencer-marketing analyst building an outreach-ready dataset of creators matching a
brief. The brief specifies a niche, one or more platforms, a follower band, and a geography.

## Discovery
- Treat the niche, platform(s), follower band, and geography as HARD filters. Do not include
  creators outside the follower band or wrong niche to inflate the list.
- Search the named platforms (Instagram, TikTok, YouTube, X, LinkedIn) and creator directories.
  Do not stop at the most famous names; surface credible mid-tier and micro creators too.

## Per-row rules
- handle and platform; profile_url must be the creator's real profile page (never a search page).
- follower_count and engagement_rate copied as strings from what is shown (e.g. "48.2K", "3.1%");
  null when not visible, never invented.
- contact: only a publicly listed business email; null otherwise. Never guess an email.
- One row per distinct creator; merge duplicates across platforms into the row for the requested
  platform. Include observed_at (ISO 8601).

## Anti-hallucination
- Never invent a handle, follower count, or email. Omit rather than guess.""",
    "goals": [
        "Returns at least 20 distinct creators matching the criteria (keep expanding beyond the obvious names to reach the count)",
        "Returns distinct creators matching the niche, platform, follower band, and geography in the prompt (hard filters)",
        "Every row has a real profile_url on the requested platform (never a search page)",
        "follower_count and engagement_rate are strings copied from the page; null when not shown, never invented",
        "Includes a mix of mid-tier and micro creators, not only the most famous",
        "contact is a public business email only, else null; never guessed",
        "One row per distinct creator, deduplicated; each has observed_at (ISO 8601)",
    ],
    "sources": {
        "allow": [
            {"title": "Instagram", "domains": ["instagram.com"], "order": 0},
            {"title": "TikTok", "domains": ["tiktok.com"], "order": 1},
            {"title": "YouTube", "domains": ["youtube.com"], "order": 2},
            {"title": "X / Twitter", "domains": ["x.com", "twitter.com"], "order": 3},
            {"title": "LinkedIn", "domains": ["linkedin.com"], "order": 4},
            {"title": "Social Blade", "domains": ["socialblade.com"], "order": 5},
            {"title": "Creator Directories", "domains": [], "order": 6},
        ],
        "block": [],
        "avoid": "follower-count guessing services and pages that do not show the creator's own profile",
        "prioritize": "the creator's own profile page on the requested platform",
    },
    "output_schema": {
        "type": "array",
        "description": "One row per distinct influencer matching the brief.",
        "items": {"type": "object",
            "required": ["handle", "platform", "profile_url", "observed_at"],
            "properties": {
                "handle": {"type": "string"},
                "platform": {"type": "string"},
                "profile_url": {"type": "string"},
                "follower_count": {"type": ["string", "null"], "description": "Verbatim, e.g. '48.2K'"},
                "engagement_rate": {"type": ["string", "null"], "description": "Verbatim, e.g. '3.1%'"},
                "niche": {"type": ["string", "null"]},
                "location": {"type": ["string", "null"]},
                "contact": {"type": ["string", "null"], "description": "Public business email only, else null"},
                "bio_summary": {"type": ["string", "null"]},
                "observed_at": {"type": "string"},
            }, "additionalProperties": True},
    },
    "suggested_questions": [
        "Sustainable fashion micro-influencers on Instagram, 10k-100k followers, US",
        "Home-cooking creators on TikTok with 50k-500k followers in the UK",
        "B2B SaaS thought leaders on LinkedIn with 20k+ followers",
    ],
}


def run_input(query: str) -> str:
    """Wrap a query with an explicit recall nudge."""
    return f"Find at least 20 distinct creators: {query}"
