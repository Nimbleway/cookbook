"""
Basic example of using Nimble MCP Server for web search using FastMCP Client library.
"""
import asyncio
import os
import sys

from fastmcp import Client
from fastmcp.client.transports import SSETransport

MCP_URL = "https://mcp.nimbleway.com/sse"

async def search_web(query: str) -> None:
    api_key = os.environ.get("NIMBLE_API_KEY")
    if not api_key:
        raise ValueError("NIMBLE_API_KEY environment variable not set")
    
    transport = SSETransport(
        MCP_URL, 
        headers={"Authorization": f"Basic {api_key}"}
    )
    client = Client(transport)

    print(f"Searching for '{query}' - This may take a few moments...")
    
    async with client:
        results = await client.call_tool(
            "nimble_deep_web_search", 
            {"query": query}
        )
        
        for result in results:
            if hasattr(result, "text"):
                print(result.text)

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "recent advances in artificial intelligence"
    asyncio.run(search_web(query))
