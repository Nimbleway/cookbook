"""
Web search integration with LangChain framework using Nimble MCP Server.
"""
import asyncio
import os
import sys

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from dotenv import load_dotenv
load_dotenv()

MCP_URL = "https://mcp.nimbleway.com/sse"

async def main(query: str) -> None:
    api_key = os.environ.get("NIMBLE_API_KEY")
    if not api_key:
        raise ValueError("NIMBLE_API_KEY environment variable not set")
    
    async with MultiServerMCPClient({
        "nimble": {
            "url": MCP_URL,
            "transport": "sse",
            "headers": {"Authorization": f"Basic {api_key}"}
        }
    }) as client:
        # Load all available MCP tools
        tools = client.get_tools()
        
        agent = create_react_agent("openai:gpt-4.1", tools)
        
        # Run the agent with the query
        print(f"Searching for information about: {query}")
        agent_response = await agent.ainvoke({
            "messages": f"Find information about {query} and provide a concise summary."
        })
        
        print(agent_response)

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "latest developments in renewable energy"
    asyncio.run(main(query))
