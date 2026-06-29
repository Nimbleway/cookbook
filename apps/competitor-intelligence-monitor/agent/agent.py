import os
import re
import json
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
import operator

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import anthropic
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from typing_extensions import TypedDict

load_dotenv(Path(__file__).parent / ".env", override=True)

# ─── Load config ──────────────────────────────────────────────────────────────

CONFIG_FILE = Path(__file__).parent / "config.json"
with open(CONFIG_FILE) as _f:
    _CONFIG = json.load(_f)

YOUR_COMPANY      = _CONFIG["your_company"]["name"]
YOUR_COMPANY_ALIASES  = _CONFIG["your_company"]["aliases"]
YOUR_COMPANY_DESC = _CONFIG["your_company"].get("description", "")

COMPETITOR_ALIASES = {}
GITHUB_REPOS       = {}
PYPI_PACKAGES      = {}

for _c in _CONFIG["competitors"]:
    _n = _c["name"]
    COMPETITOR_ALIASES[_n] = _c["aliases"]
    GITHUB_REPOS[_n]       = _c.get("github_repo")
    PYPI_PACKAGES[_n]      = _c.get("pypi_package")

COMPETITOR_ALIASES[YOUR_COMPANY] = YOUR_COMPANY_ALIASES

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
GITHUB_TOKEN = os.getenv("GH_API_KEY")
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL_ID")

slack_client = WebClient(token=SLACK_TOKEN)
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

NOW = datetime.now(timezone.utc)
WEEK_AGO = (NOW - timedelta(days=7)).strftime("%Y-%m-%d")
WEEK_AGO_TS = int((NOW - timedelta(days=7)).timestamp())
SEARCH_START = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")   # yesterday only — no overlap with prior run
SEARCH_START_TS = int((NOW - timedelta(days=1)).timestamp())
WEEK_START = (NOW - timedelta(days=NOW.weekday())).strftime("%Y-%m-%d")  # Monday of current week
IS_MONDAY = NOW.weekday() == 0
IS_MWF    = NOW.weekday() in (0, 2, 4)

SEEN_URLS_FILE = Path(__file__).parent / "seen_urls.json"
SEEN_CONTEXT_FILE = Path(__file__).parent / "seen_context.json"

# ─── Graph state ─────────────────────────────────────────────────────────────

class AgentState(TypedDict, total=False):
    # Accumulated by operator.add across parallel collect_competitor nodes
    raw_results: Annotated[list, operator.add]
    fresh_results: list
    synthesis: dict
    seen_urls: dict        # {url: date_str} — rolling 30-day URL history
    seen_context: dict     # {date_str: [topic_str, ...]} — rolling 7-day story history
    # Set per-competitor via Send
    current_competitor: str
    current_aliases: list


# ─── Persistence helpers ─────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception as e:
        print(f"[State] Failed to load {path.name}: {e} — starting fresh")
        return {}


def _prune_by_date(data: dict, days: int, by_value: bool = False) -> dict:
    """Prune dict entries older than `days`. Use by_value=True when keys are URLs and values are dates."""
    cutoff = (NOW - timedelta(days=days)).strftime("%Y-%m-%d")
    if by_value:
        return {k: v for k, v in data.items() if isinstance(v, str) and v >= cutoff}
    return {k: v for k, v in data.items() if k >= cutoff}


# ─── Nimble Search API ───────────────────────────────────────────────────────

NIMBLE_SEARCH_URL = "https://sdk.nimbleway.com/v1/search"
TODAY = NOW.strftime("%Y-%m-%d")


def nimble_search(query: str, focus: str = "general", max_results: int = 8,
                  date_filter: bool = True) -> list:
    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "lite",
        "focus": focus,
    }
    if date_filter:
        payload["start_date"] = SEARCH_START
        payload["end_date"] = TODAY
    try:
        resp = requests.post(
            NIMBLE_SEARCH_URL,
            headers={"Authorization": f"Bearer {NIMBLE_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as e:
        print(f"  [Search error] {query[:60]}: {e}")
        return []


def _parse_date(raw: str) -> str:
    """Normalise any ISO-ish date string to YYYY-MM-DD, or return empty string."""
    if not raw:
        return ""
    return str(raw)[:10]


def _to_results(items: list, competitor: str, platform: str) -> list:
    out = []
    for r in items:
        if not r.get("url"):
            continue
        date = _parse_date(
            r.get("date") or r.get("published_date") or
            r.get("publishedDate") or r.get("published_at") or ""
        )
        out.append({
            "competitor": competitor, "platform": platform,
            "url": r.get("url", ""), "title": r.get("title", "")[:150],
            "snippet": r.get("description", "")[:250],
            "event_date": date,
        })
    return out


# ─── Per-source collectors (called in parallel within each competitor) ───────

def _reddit(c, aliases):
    """All Reddit mentions — any subreddit, any thread."""
    out = []
    for a in aliases:
        out += _to_results(
            nimble_search(f'"{a}" site:reddit.com', focus="social"), c, "Reddit")
    return out


def _twitter(c, aliases):
    """All Twitter/X mentions — not just their own account."""
    out = []
    for a in aliases:
        out += _to_results(
            nimble_search(f'"{a}" (site:twitter.com OR site:x.com)', focus="social"), c, "Twitter/X")
    return out


def _linkedin(c, aliases):
    out = []
    for a in aliases[:1]:
        out += _to_results(
            nimble_search(f'"{a}" site:linkedin.com', focus="social"), c, "LinkedIn")
    return out


def _instagram(c, aliases):
    out = []
    for a in aliases[:1]:
        out += _to_results(
            nimble_search(f'"{a}" site:instagram.com', focus="social"), c, "Instagram")
    return out


def _youtube(c, aliases):
    if not IS_MWF:
        return []
    out = []
    for a in aliases[:1]:
        out += _to_results(
            nimble_search(f'"{a}" site:youtube.com', focus="general"), c, "YouTube")
    return out


def _producthunt(c, aliases):
    if not IS_MONDAY:
        return []
    out = []
    for a in aliases[:1]:
        out += _to_results(
            nimble_search(f'"{a}" site:producthunt.com', focus="general", date_filter=False), c, "Product Hunt")
    return out


def _blogs(c, aliases):
    """Official blog + general blog/announcement coverage."""
    out = []
    for a in aliases[:1]:
        out += _to_results(
            nimble_search(f'"{a}" (blog OR announcement OR launch OR "new feature" OR release)',
                          focus="general"), c, "Blog")
    return out


def _news(c, aliases):
    out = []
    for a in aliases[:1]:
        out += _to_results(nimble_search(f'"{a}"', focus="news"), c, "News")
    return out


def _medium_devto(c, aliases):
    """Medium, Dev.to, Substack, and other developer writing."""
    out = []
    for a in aliases[:1]:
        out += _to_results(
            nimble_search(f'"{a}" (site:medium.com OR site:dev.to OR site:substack.com)',
                          focus="coding"), c, "Dev Writing")
    return out


def _coding(c, aliases):
    """GitHub discussions, Stack Overflow, coding forums."""
    out = []
    for a in aliases[:1]:
        out += _to_results(nimble_search(f'"{a}"', focus="coding"), c, "Dev")
    return out


def _hackernews(c, aliases):
    out = []
    for a in aliases:
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": a, "tags": "(story,comment)",
                        "numericFilters": f"created_at_i>{SEARCH_START_TS}", "hitsPerPage": 8},
                timeout=15,
            )
            resp.raise_for_status()
            for h in resp.json().get("hits", []):
                title = h.get("title") or (h.get("comment_text") or "")[:150]
                ts = h.get("created_at_i")
                hn_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""
                out.append({"competitor": c, "platform": "Hacker News",
                            "url": f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
                            "title": title,
                            "snippet": f"Points: {h.get('points', 0)}, Comments: {h.get('num_comments', 0)}",
                            "event_date": hn_date})
        except Exception as e:
            print(f"  [HN error] {a}: {e}")
    return out


def _github(c, aliases):
    if not GITHUB_TOKEN:
        return []
    out = []
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    for a in aliases[:1]:
        try:
            r = requests.get("https://api.github.com/search/repositories",
                             params={"q": f'"{a}" pushed:>{SEARCH_START}', "sort": "updated", "per_page": 5},
                             headers=headers, timeout=15)
            if r.ok:
                for item in r.json().get("items", []):
                    out.append({"competitor": c, "platform": "GitHub", "url": item["html_url"],
                                "title": item["full_name"], "snippet": (item.get("description") or "")[:200],
                                "event_date": _parse_date(item.get("pushed_at", ""))})
            r = requests.get("https://api.github.com/search/issues",
                             params={"q": f'"{a}" created:>{SEARCH_START}', "sort": "created", "per_page": 5},
                             headers=headers, timeout=15)
            if r.ok:
                for item in r.json().get("items", []):
                    out.append({"competitor": c, "platform": "GitHub", "url": item["html_url"],
                                "title": item["title"], "snippet": (item.get("body") or "")[:200],
                                "event_date": _parse_date(item.get("created_at", ""))})
        except Exception as e:
            print(f"  [GitHub error] {a}: {e}")
    return out


def _github_releases(c, aliases):
    """Official repo release notes — high-signal product launch indicator."""
    if not GITHUB_TOKEN:
        return []
    out = []
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    for a in aliases[:1]:
        try:
            r = requests.get("https://api.github.com/search/repositories",
                             params={"q": f'"{a}" in:name,description', "sort": "stars", "per_page": 3},
                             headers=headers, timeout=15)
            if not r.ok:
                continue
            for repo in r.json().get("items", []):
                full_name = repo["full_name"]
                rel = requests.get(f"https://api.github.com/repos/{full_name}/releases",
                                   params={"per_page": 3}, headers=headers, timeout=15)
                if not rel.ok:
                    continue
                for release in rel.json():
                    published = release.get("published_at", "")[:10]
                    if published >= SEARCH_START:
                        body = (release.get("body") or "")[:300]
                        out.append({"competitor": c, "platform": "GitHub Releases",
                                    "url": release["html_url"],
                                    "title": f"{full_name} — {release.get('name') or release.get('tag_name', '')}",
                                    "snippet": body, "event_date": published})
        except Exception as e:
            print(f"  [GitHub releases error] {a}: {e}")
    return out


def _g2_capterra(c, aliases):
    """G2 and Capterra reviews — direct customer sentiment signal."""
    if not IS_MONDAY:
        return []
    out = []
    for a in aliases[:1]:
        out += _to_results(
            nimble_search(f'"{a}" (site:g2.com OR site:capterra.com OR site:trustpilot.com)',
                          focus="general", date_filter=False), c, "Reviews")
    return out


def _positioning(c, aliases):
    """Competitor messaging changes and direct comparisons."""
    out = []
    for a in aliases[:1]:
        # Direct comparisons to your company — no date filter, these persist on the web
        out += _to_results(
            nimble_search(
                f'"{a}" ("vs {YOUR_COMPANY}" OR "vs {YOUR_COMPANY_ALIASES[0] if YOUR_COMPANY_ALIASES else YOUR_COMPANY}" OR "{YOUR_COMPANY} alternative" OR "compared to {YOUR_COMPANY}")',
                focus="general", date_filter=False), c, "Positioning")
        # Pitch/messaging changes this week
        out += _to_results(
            nimble_search(
                f'"{a}" (rebrand OR "new positioning" OR "value proposition" OR "use case" OR "how it works")',
                focus="general"), c, "Positioning")
    return out


SOURCE_FNS = [
    _reddit, _twitter, _linkedin,
    _youtube, _producthunt, _blogs, _news,
    _medium_devto, _coding, _hackernews, _github,
    _github_releases, _g2_capterra, _positioning,
]


# ─── LangGraph nodes ─────────────────────────────────────────────────────────

def load_state(state: AgentState) -> dict:
    urls_raw = _load_json(SEEN_URLS_FILE)
    ctx_raw = _load_json(SEEN_CONTEXT_FILE)
    seen_urls = _prune_by_date(urls_raw.get("entries", urls_raw), 30, by_value=True)
    seen_context = _prune_by_date(ctx_raw, 30)
    print(f"State loaded: {len(seen_urls)} known URLs, {len(seen_context)} days of context")
    return {"seen_urls": seen_urls, "seen_context": seen_context}


def route_collectors(state: AgentState):
    """Fan out to one collect_competitor node per competitor, running in parallel."""
    return [
        Send("collect_competitor", {"current_competitor": comp, "current_aliases": aliases})
        for comp, aliases in COMPETITOR_ALIASES.items()
    ]


def collect_competitor(state: AgentState) -> dict:
    """Collect all sources for one competitor. Sources run in parallel via ThreadPoolExecutor."""
    competitor = state["current_competitor"]
    aliases = state["current_aliases"]
    print(f"  Collecting: {competitor}...")
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fn, competitor, aliases) for fn in SOURCE_FNS]
        for future in futures:
            try:
                results += future.result()
            except Exception as e:
                print(f"  [Collect error] {competitor}: {e}")
    print(f"  {competitor}: {len(results)} raw results")
    return {"raw_results": results}


def deduplicate(state: AgentState) -> dict:
    """Remove exact URL duplicates (within-run and against history).

    Only filters URLs seen more than 2 days ago. URLs within the search window
    pass through to Claude, which uses seen_context topic slugs to avoid
    re-reporting already-covered stories. This prevents the search window
    overlapping with the dedup window and producing zero fresh results.
    """
    seen_urls = state.get("seen_urls", {})
    raw = state.get("raw_results", [])

    # URLs seen before the search window are stale — filter them out.
    # URLs seen in the last 2 days pass through to Claude's semantic dedup.
    cutoff = (NOW - timedelta(days=2)).strftime("%Y-%m-%d")
    old_seen = {url for url, d in seen_urls.items() if d < cutoff}

    seen_in_run: set = set()
    unique = []
    for r in raw:
        url = r.get("url", "")
        if url and url not in seen_in_run:
            seen_in_run.add(url)
            unique.append(r)

    fresh = [r for r in unique if r.get("url", "") not in old_seen]
    print(f"Dedup: {len(raw)} raw → {len(unique)} unique → {len(fresh)} passed to synthesis")
    return {"fresh_results": fresh}


def synthesize(state: AgentState) -> dict:
    """
    Claude synthesizes findings. Receives full 7-day story history so it can
    skip re-reporting stories already covered, even if they appear at new URLs.
    """
    fresh = state.get("fresh_results", [])
    seen_context = state.get("seen_context", {})

    if not fresh:
        return {"synthesis": {"overview": "No new competitor activity found this past week.",
                               "findings": [], "topics": []}}

    # Select up to 50 items per competitor with platform diversity (round-robin across sources).
    from collections import defaultdict
    per_comp: dict = defaultdict(list)
    for r in fresh:
        per_comp[r.get("competitor", "Unknown")].append(r)
    capped = []
    for comp_items in per_comp.values():
        by_platform: dict = defaultdict(list)
        for item in comp_items:
            by_platform[item.get("platform", "Unknown")].append(item)
        selected = []
        iterators = {p: iter(items) for p, items in by_platform.items()}
        while len(selected) < 40 and iterators:
            exhausted = []
            for platform, it in iterators.items():
                if len(selected) >= 40:
                    break
                try:
                    selected.append(next(it))
                except StopIteration:
                    exhausted.append(platform)
            for p in exhausted:
                del iterators[p]
        capped.extend(selected)
    fresh = capped
    print(f"Synthesis input: {len(fresh)} items (40/competitor, platform-diverse)")

    history_lines = []
    overview_lines = []
    for date in sorted(seen_context.keys(), reverse=True)[:7]:
        day = seen_context[date]
        topics = day["topics"] if isinstance(day, dict) else day
        overview = day.get("overview", "") if isinstance(day, dict) else ""
        for topic in topics:
            history_lines.append(f"  [{date}] {topic}")
        if overview:
            overview_lines.append(f"  [{date}] {overview}")
    history_str = "\n".join(history_lines) if history_lines else "  (none yet)"
    prior_overviews_str = "\n".join(overview_lines[:7]) if overview_lines else "  (none yet)"

    _tracked_competitors = [c for c in COMPETITOR_ALIASES if c != YOUR_COMPANY]
    _tracked_str = ", ".join(_tracked_competitors)
    prompt = f"""You are a competitive intelligence analyst at {YOUR_COMPANY}, {YOUR_COMPANY_DESC}. \
Today is {NOW.strftime('%Y-%m-%d')}. Your audience is {YOUR_COMPANY}'s sales team, marketing team, and executive leadership. \
You are analyzing the past 2 days ({SEARCH_START} to {TODAY}) for competitors: {_tracked_str} — and for {YOUR_COMPANY} itself.

RECENT DAILY OVERVIEWS (your executive summaries from previous runs — today's overview MUST say something meaningfully different, not a variation of these):
{prior_overviews_str}

STORIES ALREADY REPORTED (do not re-report unless meaningfully updated):
{history_str}

A story counts as "meaningfully updated" ONLY if a concrete NEW development has occurred:
- A new product or feature has actually shipped as a direct result
- A pricing change, repositioning, or new target market has been announced
- A follow-on funding round, acquisition, or named customer win has closed
- The story has materially escalated (e.g. a breach grew in scope, a lawsuit was filed)

These do NOT count as meaningfully updated — skip them:
- More tweets, LinkedIn posts, or articles discussing the same news
- Industry commentary or analysis of an event already reported
- The same story picked up by additional media outlets or influencer accounts
- Community reaction without a new concrete development attached
- An amplification account (e.g. SwissCognitive, AI newsletters) sharing old news

When in doubt, skip it. It is better to under-report than to repeat the same story.

INSTRUCTIONS:
1. Skip noise, duplicate stories, and anything not from the past 2 days.
2. For each finding, write a summary in 2 parts separated by a period: (a) 1 sentence on what happened — factual, under 120 characters; (b) 1-2 sentences explaining why this is good or bad for {YOUR_COMPANY} specifically — what competitive advantage or threat does it create, what does it mean for {YOUR_COMPANY}'s market position. Keep part (b) under 220 characters. Be direct and specific, no padding.
3. Sentiment reflects how the news reflects on the company being reported on (not Nimble's perspective):
   - "positive": good news for that company — funding, launches, growth, praise, partnerships
   - "negative": bad news for that company — outages, bad press, losing users, criticism
   - "neutral": no strong signal either way
4. Assign a category to each finding: Funding | Product Launch | Reliability | Customer Feedback | Hiring | Pricing | Partnership | Community
4b. Set "event_date" to the date from the raw item's "event_date" field (YYYY-MM-DD). If the raw item has no date, use the closest date you can infer from context, otherwise leave it empty.
4c. Set "source_type" to "Self-Promoted" if the content was published by the company itself (their own blog, official social account, their GitHub repo, their Product Hunt post, press release, etc.) or "Organic" if it was written or posted by a third party (news article, community discussion, user review, someone else mentioning them).
5. Output up to 6 findings per competitor — ONLY for the tracked competitors: {_tracked_str}. Do NOT include findings for any other company, even if they appear in the raw data. Prioritise the most significant, but include anything with real competitive relevance. Do not pad with noise. The sheet is a master database; Slack will display only the top 3 automatically.
6. Output up to 5 findings for {YOUR_COMPANY} in "nimble_findings" — include all meaningful mentions.
7. Pick the single most strategically important finding today as "signal_of_week". Rules: (a) must be from a TRACKED competitor only — {', '.join(c for c in COMPETITOR_ALIASES if c != YOUR_COMPANY)}. Never assign an unknown or untracked company here, even if their news seems significant. (b) must be a high-impact event: funding round, major product launch, pricing change, acquisition, or a direct competitive move against {YOUR_COMPANY}. (c) Do NOT pick minor integrations, format support, small feature updates, or incremental improvements. (d) "vs {YOUR_COMPANY}" comparison posts from any company belong in positioning_alerts, not here. If nothing clears the bar, set it to null.
8. For "activity", count the total number of meaningful signals per competitor and assign an overall sentiment for the week.
9. Write a sharp 2-sentence executive overview — what does this week mean for {YOUR_COMPANY}'s competitive position?
10. Produce "topics" strings for deduplication of future runs. Format each as "{{Competitor}}:{{Category}}:{{3-5 word slug}}" — e.g. "Exa:Funding:250M-series-C" or "Tavily:Partnership:nebius-acquisition". Use the same slug if the same event would be described multiple ways, so future runs can match it reliably.
11. Populate "positioning_alerts" with any evidence of: (a) ANY company — tracked or untracked — directly comparing themselves to {YOUR_COMPANY} or publishing "vs {YOUR_COMPANY}" content; (b) a tracked competitor changing their core pitch, tagline, or value proposition; (c) any new "vs {YOUR_COMPANY}" comparison content anywhere on the web. Use the actual company name as "competitor", not a tracked competitor you guessed. These are HIGH PRIORITY — flag them even if subtle. Leave the list empty if nothing found.

Return ONLY valid JSON:
{{
  "signal_of_week": {{
    "competitor": "Firecrawl",
    "title": "One-line headline",
    "summary": "One sentence on what happened and why it matters to Nimble.",
    "url": "https://...",
    "sentiment": "positive|negative|neutral"
  }},
  "overview": "Two sharp sentences from Nimble's competitive perspective.",
  "activity": [
    {{"competitor": "{_tracked_competitors[0] if _tracked_competitors else 'Competitor'}", "signal_count": 5, "sentiment": "positive"}},
    {{"competitor": "{_tracked_competitors[1] if len(_tracked_competitors) > 1 else 'Competitor2'}", "signal_count": 3, "sentiment": "neutral"}}
  ],
  "findings": [
    {{
      "competitor": "Exa",
      "platform": "Reddit",
      "url": "https://...",
      "title": "Short title",
      "summary": "What happened. Why it matters to Nimble.",
      "sentiment": "positive|negative|neutral",
      "category": "Funding|Product Launch|Reliability|Customer Feedback|Hiring|Pricing|Partnership|Community",
      "event_date": "YYYY-MM-DD",
      "source_type": "Organic|Self-Promoted"
    }}
  ],
  "nimble_findings": [
    {{
      "platform": "Reddit",
      "url": "https://...",
      "title": "Short title",
      "summary": "What people are saying and why it matters.",
      "sentiment": "positive|negative|neutral",
      "category": "Community|Customer Feedback|Product Launch|Pricing|Partnership",
      "event_date": "YYYY-MM-DD",
      "source_type": "Organic|Self-Promoted"
    }}
  ],
  "positioning_alerts": [
    {{
      "competitor": "Firecrawl",
      "type": "nimble_comparison|pitch_change",
      "title": "Short headline",
      "summary": "What changed and why it matters to Nimble's positioning.",
      "url": "https://...",
      "sentiment": "positive|negative|neutral",
      "event_date": "YYYY-MM-DD",
      "source_type": "Organic|Self-Promoted"
    }}
  ],
  "topics": ["Firecrawl raised $12M Series A", "Exa launched reranking endpoint"]
}}

Raw data ({len(fresh)} items):
{json.dumps(fresh)}"""

    resp = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "max_tokens":
        print("WARNING: Claude output was truncated (stop_reason=max_tokens). Falling back.")
        result = {"signal_of_week": None, "overview": "Synthesis truncated — output too long.",
                  "activity": [], "findings": [], "nimble_findings": [], "positioning_alerts": [], "topics": [],
                  "synthesis_ok": False}
    else:
        text = resp.content[0].text.strip()
        # Extract the outermost JSON object — handles preamble/postamble and markdown fences
        m = re.search(r'\{.*\}', text, re.DOTALL)
        text = m.group() if m else text
        try:
            result = json.loads(text)
            result["synthesis_ok"] = True
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}\nRaw output (first 500 chars): {text[:500]}")
            result = {"signal_of_week": None, "overview": "Synthesis failed — JSON parse error.",
                      "activity": [], "findings": [], "nimble_findings": [], "positioning_alerts": [], "topics": [],
                      "synthesis_ok": False}
    n_findings = len(result.get("findings", [])) + len(result.get("nimble_findings", []))
    print(f"Synthesis: {n_findings} findings, {len(result.get('topics', []))} topics")
    return {"synthesis": result}


S = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}

SUMMARY_CAP = 380


def _cap_summary(text: str) -> str:
    """Trim to SUMMARY_CAP chars at a sentence boundary, then word boundary."""
    if len(text) <= SUMMARY_CAP:
        return text
    for punct in (". ", "! ", "? "):
        idx = text.rfind(punct, 0, SUMMARY_CAP)
        if idx > SUMMARY_CAP // 2:
            return text[:idx + 1]
    idx = text.rfind(" ", 0, SUMMARY_CAP)
    return (text[:idx] + "…") if idx > 0 else text[:SUMMARY_CAP] + "…"


def _finding_block(item: dict, show_competitor: bool = False) -> dict:
    sent = S.get(item.get("sentiment", "neutral"), "⚪")
    title = (item.get("title") or "No title")[:80]
    summary = _cap_summary(item.get("summary") or "")
    url = item.get("url", "")
    platform = item.get("platform", "Web")
    category = item.get("category", "")
    source_type = item.get("source_type", "")
    meta_parts = [p for p in [category, platform, source_type] if p]
    meta = " · ".join(meta_parts)
    prefix = f"*{item.get('competitor', 'Unknown')}*  " if show_competitor else ""
    parts = summary.split(". ", 1)
    if len(parts) == 2:
        summary_text = f"_{parts[0]}._\n↳ _{parts[1]}_"
    else:
        summary_text = f"_{summary}_"
    linked_title = f"<{url}|{title}>" if url else title
    return {"type": "section", "text": {"type": "mrkdwn",
            "text": f"{sent}  {prefix}*{linked_title}*\n{summary_text}\n`{meta}`"}}


def post_slack(state: AgentState) -> dict:
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        s = state.get("synthesis", {})
        print("\n── Synthesis Results ──────────────────────────────────────")
        print(s.get("overview", "No overview generated."))
        for f in s.get("findings", []):
            print(f"\n[{f.get('competitor')}] {f.get('title')}\n  {f.get('summary')}\n  {f.get('url')}")
        if s.get("nimble_findings"):
            print(f"\n── {YOUR_COMPANY} mentions ──")
            for f in s.get("nimble_findings", []):
                print(f"  {f.get('title')}\n  {f.get('url')}")
        print("────────────────────────────────────────────────────────────\n")
        print("Tip: add Slack credentials to .env to receive these as a formatted digest.")
        return {}

    s = state.get("synthesis", {})
    overview = s.get("overview", "")
    findings = s.get("findings", [])
    nimble_findings = s.get("nimble_findings", [])
    signal = s.get("signal_of_week")
    activity = s.get("activity", [])
    positioning_alerts = s.get("positioning_alerts", [])

    print(f"[Slack] {len(findings)} competitor findings, {len(nimble_findings)} {YOUR_COMPANY} findings. Channel={SLACK_CHANNEL!r}")

    if not findings and not nimble_findings:
        try:
            slack_client.chat_postMessage(channel=SLACK_CHANNEL,
                                          text=f"Competitor Monitor — {TODAY}\n\nNo significant activity found.")
            print("[Slack] Posted no-activity notice.")
        except Exception as e:
            print(f"[Slack] Error posting no-activity notice: {e}")
        return {}

    blocks = []

    # ── Header ────────────────────────────────────────────────────────────────
    blocks.append({"type": "header",
                   "text": {"type": "plain_text",
                            "text": f"Daily Competitor Intelligence  |  {TODAY}"}})

    # ── Executive summary ─────────────────────────────────────────────────────
    if overview:
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn", "text": overview}})
        blocks.append({"type": "divider"})

# ── Signal of the Day ────────────────────────────────────────────────────
    if signal and signal.get("title") and signal.get("url"):
        sent = S.get(signal.get("sentiment", "neutral"), "⚪")
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": f"*SIGNAL OF THE DAY*\n{sent}  *<{signal.get('url')}|{signal.get('title')}>*\n{signal.get('summary', '')}"}})
        blocks.append({"type": "divider"})

    # ── Positioning Alerts ────────────────────────────────────────────────────
    if positioning_alerts:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*POSITIONING ALERTS*"}})
        for alert in positioning_alerts:
            sent = S.get(alert.get("sentiment", "neutral"), "⚪")
            title = (alert.get("title") or "")[:80]
            summary = _cap_summary(alert.get("summary") or "")
            url = alert.get("url", "")
            comp = alert.get("competitor", "")
            alert_type = alert.get("type", "")
            tag = f"{YOUR_COMPANY} Comparison" if alert_type == "nimble_comparison" else "Pitch Change"
            linked = f"<{url}|{title}>" if url else title
            blocks.append({"type": "section", "text": {"type": "mrkdwn",
                "text": f"{sent}  *{comp}*  —  *{linked}*\n_{summary}_\n`{tag} · Positioning`"}})
        blocks.append({"type": "divider"})

    # ── Findings by competitor (max 3 each) ───────────────────────────────────
    by_competitor: dict = {}
    for f in findings:
        by_competitor.setdefault(f.get("competitor", "Unknown"), []).append(f)

    for comp, items in by_competitor.items():
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn", "text": f"*{comp.upper()}*"}})
        for item in items[:3]:
            blocks.append(_finding_block(item))
        blocks.append({"type": "divider"})

    # ── Your company section ──────────────────────────────────────────────────
    if nimble_findings:
        blocks.append({"type": "header",
                       "text": {"type": "plain_text", "text": f"{YOUR_COMPANY}  |  What People Are Saying"}})
        for item in nimble_findings[:4]:
            blocks.append(_finding_block(item))
        blocks.append({"type": "divider"})

    # Slack hard limit is 50 blocks
    if len(blocks) > 49:
        blocks = blocks[:49]

    print(f"[Slack] Posting {len(blocks)} blocks…")
    try:
        slack_client.chat_postMessage(
            channel=SLACK_CHANNEL, blocks=blocks,
            text=f"Daily competitor intelligence — {TODAY}",
            unfurl_links=False, unfurl_media=False)
        print(f"[Slack] Posted — {len(findings)} competitor findings, {len(nimble_findings)} {YOUR_COMPANY} findings")
    except SlackApiError as e:
        print(f"[Slack] API error: {e.response['error']} — {e.response}")
    except Exception as e:
        print(f"[Slack] Unexpected error: {type(e).__name__}: {e}")
    return {}


# ─── Personalized DMs ─────────────────────────────────────────────────────────

def _build_dm_blocks(name: str, team: str, overview: str, signal,
                     findings: list, nimble_findings: list,
                     positioning_alerts: list, brief: bool,
                     date_range: str = "") -> list:
    blocks = []
    team_label = f"  ·  {team}" if team else ""
    period = date_range if date_range else TODAY

    blocks.append({"type": "header", "text": {"type": "plain_text",
                   "text": f"Competitor Digest{team_label}  |  {period}"}})

    if name:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": f"Hi {name} 👋"}})

    IMPACT_RANK = {"High": 0, "Medium": 1, "Low": 2}

    if brief:
        if overview:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": overview}})
            blocks.append({"type": "divider"})

        if signal and signal.get("title") and signal.get("url"):
            sent = S.get(signal.get("sentiment", "neutral"), "⚪")
            blocks.append({"type": "section", "text": {"type": "mrkdwn",
                "text": f"*SIGNAL OF THE DAY*\n{sent}  *<{signal['url']}|{signal['title']}>*\n{signal.get('summary', '')}"}})
            blocks.append({"type": "divider"})

        by_comp: dict = {}
        for f in findings:
            by_comp.setdefault(f.get("competitor", "Unknown"), []).append(f)

        if by_comp:
            blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
                "text": "_Brief mode — showing top 2 findings per competitor by impact. Run `/competitor-digest` to switch to detailed._"}]})

        for comp, items in by_comp.items():
            sorted_items = sorted(items, key=lambda x: IMPACT_RANK.get(x.get("impact", ""), 3))
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{comp.upper()}*"}})
            for item in sorted_items[:2]:
                blocks.append(_finding_block(item))
        if by_comp:
            blocks.append({"type": "divider"})

        if nimble_findings:
            blocks.append({"type": "section",
                           "text": {"type": "mrkdwn", "text": f"*{YOUR_COMPANY.upper()}*"}})
            sorted_nimble = sorted(nimble_findings, key=lambda x: IMPACT_RANK.get(x.get("impact", ""), 3))
            for nf in sorted_nimble[:2]:
                blocks.append(_finding_block(nf))
            blocks.append({"type": "divider"})

    else:
        if overview:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": overview}})
            blocks.append({"type": "divider"})

        if signal and signal.get("title") and signal.get("url"):
            sent = S.get(signal.get("sentiment", "neutral"), "⚪")
            blocks.append({"type": "section", "text": {"type": "mrkdwn",
                "text": f"*SIGNAL OF THE DAY*\n{sent}  *<{signal['url']}|{signal['title']}>*\n{signal.get('summary', '')}"}})
            blocks.append({"type": "divider"})

        if positioning_alerts:
            lines = ["*POSITIONING ALERTS*"]
            for alert in positioning_alerts:
                sent = S.get(alert.get("sentiment", "neutral"), "⚪")
                title = (alert.get("title") or "")[:80]
                summary = _cap_summary(alert.get("summary") or "")
                url = alert.get("url", "")
                comp = alert.get("competitor", "")
                tag = f"{YOUR_COMPANY} Comparison" if alert.get("type") == "nimble_comparison" else "Pitch Change"
                linked = f"<{url}|{title}>" if url else title
                lines.append(f"\n{sent}  *{comp}*  —  *{linked}*\n_{summary}_\n`{tag} · Positioning`")
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})
            blocks.append({"type": "divider"})

        by_competitor: dict = {}
        for f in findings:
            by_competitor.setdefault(f.get("competitor", "Unknown"), []).append(f)
        for comp, items in by_competitor.items():
            sorted_items = sorted(items, key=lambda x: IMPACT_RANK.get(x.get("impact", ""), 3))
            blocks.append({"type": "section",
                           "text": {"type": "mrkdwn", "text": f"*{comp.upper()}*"}})
            for item in sorted_items[:3]:
                blocks.append(_finding_block(item))
            blocks.append({"type": "divider"})

        if nimble_findings:
            sorted_nimble_det = sorted(nimble_findings, key=lambda x: IMPACT_RANK.get(x.get("impact", ""), 3))
            blocks.append({"type": "header",
                           "text": {"type": "plain_text", "text": f"{YOUR_COMPANY}  |  What People Are Saying"}})
            for item in sorted_nimble_det[:3]:
                blocks.append(_finding_block(item))
            blocks.append({"type": "divider"})

    blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
        "text": "Run `/competitor-digest` to update your preferences"}]})

    if len(blocks) > 49:
        blocks = blocks[:49]

    return blocks


def _prev_delivery_date(selected_days: list, reference_date: datetime) -> str:
    """Return the most recent day before reference_date that appears in selected_days.

    This gives the correct accumulation window for first-time deliveries:
    - Friday only        → previous Friday  (7 days back)
    - Mon+Wed+Fri on Mon → previous Friday  (3 days back)
    - Mon+Wed+Fri on Wed → previous Monday  (2 days back)
    - every day          → yesterday        (1 day back)
    """
    days = selected_days if selected_days else [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ]
    d = reference_date - timedelta(days=1)
    for _ in range(14):
        if d.strftime("%A").lower() in days:
            return d.strftime("%Y-%m-%d")
        d -= timedelta(days=1)
    # Fallback: should never be reached with valid days list
    return (reference_date - timedelta(days=7)).strftime("%Y-%m-%d")


def send_personalized_dms(state: AgentState) -> dict:
    if not SLACK_TOKEN:
        return {}
    try:
        from user_prefs import load_all_prefs, save_prefs
    except ImportError:
        print("[DMs] user_prefs not available — skipping")
        return {}

    all_prefs = load_all_prefs()
    if not all_prefs:
        print("[DMs] No registered users — skipping")
        return {}

    synthesis   = state.get("synthesis", {})
    todays_fnd  = synthesis.get("findings", [])
    todays_nim  = synthesis.get("nimble_findings", [])
    todays_pos  = synthesis.get("positioning_alerts", [])
    signal      = synthesis.get("signal_of_week")
    overview    = synthesis.get("overview", "")
    today_name  = NOW.strftime("%A").lower()

    sent = 0
    TRACKED = set(COMPETITOR_ALIASES.keys()) - {YOUR_COMPANY}

    for user_id, prefs in all_prefs.items():
        selected_days = prefs.get("days", [])
        if selected_days and today_name not in selected_days:
            continue

        name           = prefs.get("name", "")
        team           = prefs.get("team", "")
        selected_cats  = set(prefs.get("categories", []))
        include_nimble = prefs.get("include_nimble", True)
        brief          = prefs.get("format", "detailed") == "brief"

        # Use today's synthesis directly
        combined_fnd = todays_fnd
        combined_nim = todays_nim
        combined_pos = todays_pos
        date_range   = TODAY

        # ── Filter to user's preferences ─────────────────────────────────────
        filtered = [f for f in combined_fnd
                    if f.get("competitor") in TRACKED
                    and (not selected_cats or f.get("category") in selected_cats)]
        filtered_nim = combined_nim if include_nimble else []
        filtered_pos = (combined_pos
                        if not selected_cats or "Positioning" in selected_cats
                        else [])

        if not filtered and not filtered_nim and not filtered_pos:
            print(f"[DMs] No relevant findings for {user_id} ({team}) — sending no-activity notice")
            no_activity_blocks = [
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"*Competitor Digest — {date_range}*\n\nNo significant competitor activity found in your categories for this period."}},
            ]
            try:
                slack_client.chat_postMessage(
                    channel=user_id, blocks=no_activity_blocks,
                    text=f"Competitor Digest — {date_range}: No significant activity found.",
                    unfurl_links=False, unfurl_media=False,
                )
            except Exception as e:
                print(f"[DMs] No-activity notice error for {user_id}: {e}")
            continue

        blocks = _build_dm_blocks(
            name=name, team=team, overview=overview, signal=signal,
            findings=filtered, nimble_findings=filtered_nim,
            positioning_alerts=filtered_pos, brief=brief,
            date_range=date_range,
        )

        delivery_ok = False

        # ── Slack DM ─────────────────────────────────────────────────────────
        try:
            slack_client.chat_postMessage(
                channel=user_id, blocks=blocks,
                text=f"Your competitor digest — {date_range}",
                unfurl_links=False, unfurl_media=False,
            )
            delivery_ok = True
            print(f"[DMs] Slack → {user_id} ({team}, {date_range}, {len(filtered)} findings)")
        except SlackApiError as e:
            print(f"[DMs] Slack error for {user_id}: {e.response['error']}")
        except Exception as e:
            print(f"[DMs] Slack error for {user_id}: {type(e).__name__}: {e}")

        if delivery_ok:
            sent += 1
            prefs["last_sent"] = TODAY
            save_prefs(user_id, prefs)

    print(f"[DMs] Sent {sent}/{len(all_prefs)} personalized digests")
    return {}


def save_state(state: AgentState) -> dict:
    fresh = state.get("fresh_results", [])
    seen_urls = dict(state.get("seen_urls", {}))
    seen_context = dict(state.get("seen_context", {}))
    synthesis = state.get("synthesis", {})
    synthesis_ok = synthesis.get("synthesis_ok", True)

    if synthesis_ok:
        for r in fresh:
            url = r.get("url", "")
            if url:
                seen_urls[url] = TODAY
        for r in synthesis.get("nimble_findings", []):
            url = r.get("url", "")
            if url:
                seen_urls[url] = TODAY
    else:
        print("State: synthesis failed — skipping URL dedup update so items can be retried tomorrow")

    SEEN_URLS_FILE.write_text(json.dumps({"entries": seen_urls}, indent=2))

    new_topics = synthesis.get("topics", [])
    new_overview = synthesis.get("overview", "")
    if synthesis_ok and (new_topics or new_overview):
        seen_context[TODAY] = {"topics": new_topics, "overview": new_overview}
    SEEN_CONTEXT_FILE.write_text(json.dumps(seen_context, indent=2))

    print(f"State saved: {len(seen_urls)} URLs, {len(seen_context)} days of context")
    return {}


# ─── Weekly summary (Mondays only) ───────────────────────────────────────────

def post_weekly_summary(state: AgentState) -> dict:
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        return {}
    if NOW.weekday() != 0:  # 0 = Monday
        return {}

    seen_context = state.get("seen_context", {})
    all_topics = []
    for date in sorted(seen_context.keys()):
        day = seen_context[date]
        topics = day["topics"] if isinstance(day, dict) else day
        for topic in topics:
            all_topics.append(f"[{date}] {topic}")

    if not all_topics:
        print("No weekly topics to summarise.")
        return {}

    prompt = f"""You are a competitive intelligence analyst at {YOUR_COMPANY}.
Write a very short weekly summary of competitor activity for the week of {WEEK_START}.

Topics reported this week (from daily digests):
{chr(10).join(all_topics)}

Return ONLY valid JSON:
{{
  "summary": "2-3 sentences covering the most important themes of the week.",
  "links": [
    {{"title": "Brief title", "url": "https://...", "competitor": "Firecrawl"}}
  ]
}}
Include at most 2 links — only if a story was truly significant. Leave links as an empty list if nothing stands out."""

    try:
        resp = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        text = m.group() if m else text
        result = json.loads(text)
    except Exception as e:
        print(f"  [Weekly summary error] {e}")
        return {}

    blocks = [
        {"type": "header", "text": {"type": "plain_text",
                                    "text": f"Weekly Summary  |  Week of {WEEK_START}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": result.get("summary", "")}},
    ]

    links = result.get("links", [])
    if links:
        blocks.append({"type": "divider"})
        link_lines = [f"*{l.get('competitor', '')}*  —  <{l.get('url', '')}|{l.get('title', '')}>"
                      for l in links[:2]]
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(link_lines)}})

    try:
        slack_client.chat_postMessage(
            channel=SLACK_CHANNEL, blocks=blocks,
            text=f"Weekly summary — week of {WEEK_START}",
            unfurl_links=False, unfurl_media=False)
        print(f"Posted weekly summary to Slack")
    except SlackApiError as e:
        print(f"[Slack] Weekly summary API error: {e.response['error']}")
    except Exception as e:
        print(f"[Slack] Weekly summary unexpected error: {type(e).__name__}: {e}")
    return {}


# ─── Build and run graph ──────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_state", load_state)
    g.add_node("collect_competitor", collect_competitor)
    g.add_node("deduplicate", deduplicate)
    g.add_node("synthesize", synthesize)
    g.add_node("post_slack", post_slack)
    g.add_node("send_personalized_dms", send_personalized_dms)
    g.add_node("save_state", save_state)
    g.add_node("post_weekly_summary", post_weekly_summary)

    g.add_edge(START, "load_state")
    g.add_conditional_edges("load_state", route_collectors, ["collect_competitor"])
    g.add_edge("collect_competitor", "deduplicate")
    g.add_edge("deduplicate", "synthesize")
    g.add_edge("synthesize", "post_slack")
    g.add_edge("post_slack", "send_personalized_dms")
    g.add_edge("send_personalized_dms", "save_state")
    g.add_edge("save_state", "post_weekly_summary")
    g.add_edge("post_weekly_summary", END)
    return g.compile()


def main():
    print(f"Starting daily competitor monitor for {YOUR_COMPANY} — {TODAY}...")
    graph = build_graph()
    graph.invoke({
        "raw_results": [],
        "fresh_results": [],
        "synthesis": {},
        "seen_urls": {},
        "seen_context": {},
        "current_competitor": "",
        "current_aliases": [],
    })
    print("Done.")


if __name__ == "__main__":
    main()
