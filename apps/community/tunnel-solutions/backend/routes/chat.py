from fastapi import APIRouter
from pydantic import BaseModel
from agents.tunnel_agent import TunnelAgent

router = APIRouter()
agent = TunnelAgent()

class ChatRequest(BaseModel):
    message: str
    mode: str = "auto"

class ChatResponse(BaseModel):
    response: str
    mode_detected: str
    sources: list[str] = []

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await agent.run(request.message, request.mode)
    return ChatResponse(
        response=result["response"],
        mode_detected=result["mode"],
        sources=result.get("sources", [])
    )
