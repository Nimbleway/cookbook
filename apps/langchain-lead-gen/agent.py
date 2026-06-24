import os
import json
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from nimble_python import Nimble

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
NIMBLE_BASE_URL = "https://sdk.nimbleway.com"

_nimble_client = Nimble(api_key=NIMBLE_API_KEY)
_full_records: list = []


def get_full_records() -> list:
    """Returns the raw Google Maps records from the last search_google_maps call."""
    return _full_records


@tool
def nimble_extract(url: str) -> str:
    """Extract the full text content of a webpage as markdown. Use this to read a business website and find contact info and descriptions."""
    result = _nimble_client.extract(url=url, formats=["markdown"], render=True)
    content = (result.data.markdown or "").strip()
    # Truncate to avoid overwhelming the context window
    return content[:8000] if content else "No content extracted."


@tool
def search_google_maps(query: str) -> str:
    """Search Google Maps for businesses matching the query.
    Returns a JSON list of businesses with title, address, phone_number, rating, and website_url."""
    response = requests.post(
        f"{NIMBLE_BASE_URL}/v1/agents/run",
        headers={
            "Authorization": f"Bearer {NIMBLE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"agent": "google_maps_search", "params": {"query": query}},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    records = body.get("data", {}).get("parsing", {}).get("entities", {}).get("SearchResult", [])

    global _full_records
    _full_records = records

    def available_items(lst):
        return [i.get("display_name") for i in (lst or []) if i.get("is_available")]

    results = []
    for r in records:
        place_info = r.get("place_information") or {}
        results.append({
            "title": r.get("title"),
            "address": r.get("address"),
            "street_address": r.get("street_address"),
            "city": r.get("city"),
            "zip_code": r.get("zip_code"),
            "phone_number": r.get("phone_number"),
            "rating": r.get("rating"),
            "number_of_reviews": r.get("number_of_reviews"),
            "business_status": r.get("business_status"),
            "business_category": r.get("business_category", []),
            "website_url": place_info.get("website_url"),
            "place_url": r.get("place_url"),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "price_level": r.get("price_level"),
            "accessibility": available_items(r.get("accessibility")),
            "amenities": available_items(r.get("amenities")),
            "atmosphere": available_items(r.get("atmosphere")),
            "crowd": available_items(r.get("crowd")),
            "dining_options": available_items(r.get("dining_options")),
            "highlights": available_items(r.get("highlights")),
            "offerings": available_items(r.get("offerings")),
            "payments": available_items(r.get("payments")),
            "planning": available_items(r.get("planning")),
            "popular_for": available_items(r.get("popular_for")),
            "services": available_items(r.get("services")),
        })

    return json.dumps(results)


SEARCH_SYSTEM_PROMPT = """You are a lead generation agent that finds and enriches business leads from Google Maps.

When given a search query:
1. Call search_google_maps with the query
2. From the results, filter out any business without a website_url
3. For EVERY business that has a website_url, call nimble_extract with their website_url
4. From the extracted content, identify: any contact email address, opening hours, and write a 1-2 sentence description of the business

Return a JSON array as your final answer. Each element must have these exact keys:
title, address, phone_number, rating, website_url, email, opening_hours, description

If a value is not found, set it to null.
End your response with the JSON array only — no text after the closing bracket."""


ENRICH_SYSTEM_PROMPT = """You are a lead enrichment agent.

You will be given a list of businesses that already have name, address, phone, rating, and website URL.
For each business, call nimble_extract with their website_url to retrieve contact information and a description.
Extract any email address, opening hours, and write a 1-2 sentence description of the business.

Return a JSON array as your final answer. Each element must have these exact keys:
title, address, phone_number, rating, website_url, email, opening_hours, description

If a value is not found, set it to null.
End your response with the JSON array only — no text after the closing bracket."""


def get_search_agent():
    model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=8192)
    tools = [search_google_maps, nimble_extract]
    return create_react_agent(model, tools, prompt=SEARCH_SYSTEM_PROMPT)


def get_enrich_agent():
    model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=8192)
    tools = [nimble_extract]
    return create_react_agent(model, tools, prompt=ENRICH_SYSTEM_PROMPT)


def parse_leads(text: str) -> list:
    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"[parse_leads] failed: {e}\ncontent preview: {str(text)[:300]}")
    return []


def score_leads(leads: list) -> list:
    """Score enriched leads on outreach potential. Returns [{title, score, reason}]."""
    from langchain_core.prompts import ChatPromptTemplate

    model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=2048)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a sales intelligence analyst scoring business leads on outreach potential.

Score each lead 1–10 based on:
- Data completeness (has email, phone, website)
- Business health (rating, number of reviews, operational status)
- Engagement signals (rich website, active presence, clear value proposition)
- Overall appeal as a sales prospect

Return a JSON array only — no other text. Each element:
{{"title": "...", "score": 8, "reason": "One concise sentence."}}"""),
        ("human", "Score these leads:\n\n{leads}"),
    ])
    chain = prompt | model
    result = chain.invoke({"leads": json.dumps(leads, indent=2)})
    content = result.content if hasattr(result, "content") else str(result)
    return parse_leads(content)


def chat_with_leads(message: str, leads_context: str, history: list) -> str:
    """Answer a question about the lead list. History is [{role, content}]."""
    model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=1024)
    messages = [
        ("system",
         f"You are a helpful sales assistant. You have a list of enriched and scored business leads.\n\n"
         f"Leads data:\n{leads_context}\n\n"
         "Answer questions about these leads concisely. Reference specific business names when relevant."),
    ]
    for h in history:
        messages.append((h["role"], h["content"]))
    messages.append(("human", message))
    result = model.invoke(messages)
    return result.content if hasattr(result, "content") else str(result)
