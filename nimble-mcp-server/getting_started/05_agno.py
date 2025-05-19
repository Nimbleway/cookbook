"""
Web search integration with Agno agent framework using Nimble MCP Server.
"""
import asyncio
import os
import sys

from agno.agent import Agent
from agno.tools.mcp import MCPTools, SSEClientParams

from dotenv import load_dotenv
load_dotenv()

MCP_URL = "https://mcp.nimbleway.com/sse"

async def main(query: str) -> None:
    api_key = os.environ.get("NIMBLE_API_KEY")
    if not api_key:
        raise ValueError("NIMBLE_API_KEY environment variable not set")
    
    server_params = SSEClientParams(
        url=MCP_URL,
        headers={"Authorization": f"Basic {api_key}"}
    )
    
    async with MCPTools(
        transport="sse",
        server_params=server_params,
        timeout_seconds=30
    ) as nimble_mcp_server:
        search_agent = Agent(
            tools=[nimble_mcp_server],
            instructions=[
                "You are a web search assistant that provides accurate information.",
                "Search the web to find current and relevant information.",
                "Provide clear, concise summaries of what you find."
            ],
            markdown=True,
        )
        
        print(f"Searching for information about: {query}")
        await search_agent.aprint_response(
            query, 
            stream=True,
            stream_intermediate_steps=True
        )

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "latest developments in space exploration"
    asyncio.run(main(query))
