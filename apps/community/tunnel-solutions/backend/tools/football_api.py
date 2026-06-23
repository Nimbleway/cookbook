import os
import httpx
from dotenv import load_dotenv

load_dotenv()

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": FOOTBALL_API_KEY}
WORLD_CUP_ID = 1

async def get_match_info(query: str) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/fixtures",
                headers=HEADERS,
                params={"league": WORLD_CUP_ID, "next": 10},
                timeout=10
            )
            data = response.json()
            fixtures = data.get("response", [])
            return {"upcoming_matches": fixtures[:5]} if fixtures else {}
    except Exception as e:
        return {"error": str(e)}

async def get_live_match(query: str) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/fixtures",
                headers=HEADERS,
                params={"league": WORLD_CUP_ID, "live": "all"},
                timeout=10
            )
            data = response.json()
            return {"live_matches": data.get("response", [])}
    except Exception as e:
        return {"error": str(e)}

async def get_player_stats(player_name: str) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/players",
                headers=HEADERS,
                params={"search": player_name, "league": WORLD_CUP_ID},
                timeout=10
            )
            data = response.json()
            players = data.get("response", [])
            return {"player": players[0]} if players else {}
    except Exception as e:
        return {"error": str(e)}