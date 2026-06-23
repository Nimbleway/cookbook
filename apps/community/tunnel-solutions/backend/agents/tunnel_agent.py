import os
from groq import Groq
from tools.football_api import get_match_info, get_live_match
from tools.nimble_tool import scrape_match_news
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are tunnel.solutions — an elite AI match intelligence agent for the 2026 FIFA World Cup.

Your name comes from the tunnel every player walks through before kickoff: a moment of focus, preparation, and clarity.
You bring that same energy to fans, fantasy players, and analysts.

You have three modes:
1. PRE-MATCH: Team form, predicted lineups, key battles, injury news, fantasy captain picks
2. LIVE: Real-time momentum, key events, tactical shifts
3. POST-MATCH: Goal breakdowns, player ratings, fantasy points

Always be sharp, confident, and insightful.
Start every pre-match briefing with: 🚇 TUNNEL REPORT —"""

class TunnelAgent:

    async def run(self, message: str, mode: str = "auto") -> dict:
        detected_mode = mode if mode != "auto" else self._detect_mode(message)
        context = await self._gather_context(message, detected_mode)
        response = await self._call_llm(message, context, detected_mode)
        return {
            "response": response,
            "mode": detected_mode,
            "sources": context.get("sources", [])
        }

    def _detect_mode(self, message: str) -> str:
        message_lower = message.lower()
        live_keywords = ["live", "happening", "right now", "current score"]
        post_keywords = ["result", "final score", "what happened", "breakdown"]

        if any(k in message_lower for k in live_keywords):
            return "live"
        elif any(k in message_lower for k in post_keywords):
            return "post_match"
        else:
            return "pre_match"

    async def _gather_context(self, message: str, mode: str) -> dict:
        context = {"data": {}, "sources": []}

        try:
            news = await scrape_match_news(message)
            if news:
                context["data"]["news"] = news
                context["sources"].append("Nimble Web Intelligence")
        except Exception:
            pass

        try:
            if mode == "live":
                match_data = await get_live_match(message)
            else:
                match_data = await get_match_info(message)

            if match_data:
                context["data"]["match"] = match_data
                context["sources"].append("Football API")
        except Exception:
            pass

        return context

    async def _call_llm(self, message: str, context: dict, mode: str) -> str:
        if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_key_here":
            return "Groq API key is missing. Please add GROQ_API_KEY in backend/.env."

        context_str = f"\n\nLIVE DATA:\n{context['data']}" if context["data"] else ""
        prompt = f"{message}{context_str}"

        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1024
            )

            return completion.choices[0].message.content

        except Exception as e:
            return f"Groq API Error: {str(e)}"