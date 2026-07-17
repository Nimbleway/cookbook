"""Linear GraphQL client: file verified gaps as issues."""
import os

import requests

API = "https://api.linear.app/graphql"


def _gql(query, variables=None):
    r = requests.post(API, json={"query": query, "variables": variables or {}},
                      headers={"Authorization": os.environ["LINEAR_API_KEY"],
                               "Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if "errors" in d:
        raise RuntimeError(d["errors"][0].get("message"))
    return d["data"]


def team_id():
    key = os.environ["LINEAR_TEAM_KEY"]
    teams = _gql("{ teams { nodes { id key } } }")["teams"]["nodes"]
    for t in teams:
        if t["key"] == key:
            return t["id"]
    raise RuntimeError(f"Linear team key {key} not found (have: {[t['key'] for t in teams]})")


def file_gap_ticket(gap_statement, verdict, evidence_summary, demand_evidence,
                    closest_matches, citation_urls):
    """Create one Linear issue for a verified gap. Returns (identifier, url)."""
    closest = "\n".join(
        f"- {m.get('product_name')} ({m.get('price_usd') or '?'}, rating {m.get('rating') or '?'}) - "
        f"{m.get('why_close_but_not_matching') or ''} {m.get('product_url')}"
        for m in (closest_matches or [])[:5])
    cites = "\n".join(f"- {u}" for u in (citation_urls or [])[:6])
    body = f"""## Assortment gap ({verdict})

**{gap_statement}**

### Customer demand evidence
{demand_evidence or '(from catalog whitespace analysis)'}

### Live-shelf verification
{evidence_summary}

### Closest existing products
{closest or '(none found)'}

### Sources
{cites or '(see app)'}

_Filed automatically by Assortment Gap Finder (Nimble Web Search Agents)._"""
    data = _gql("""
        mutation($input: IssueCreateInput!) {
          issueCreate(input: $input) { success issue { identifier url } }
        }""", {"input": {"teamId": team_id(),
                         "title": f"[Gap] {gap_statement[:120]}",
                         "description": body}})
    issue = data["issueCreate"]["issue"]
    return issue["identifier"], issue["url"]


if __name__ == "__main__":
    import config  # noqa: F401
    print("team id:", team_id())
