import os
import httpx
from dotenv import load_dotenv

load_dotenv()

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
NIMBLE_URL = "https://api.webit.live/api/v1/realtime/web"

async def scrape_match_news(query: str) -> dict:
    if not NIMBLE_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                NIMBLE_URL,
                headers={
                    "Authorization": f"Basic {NIMBLE_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": f"https://www.google.com/search?q=2026+World+Cup+{query.replace(' ', '+')}",
                    "render": False,
                    "parse": True
                },
                timeout=15
            )
            data = response.json()
            return {"web_results": data.get("parsing", {})}
    except Exception as e:
        return {"error": str(e)}