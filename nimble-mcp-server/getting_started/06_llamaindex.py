"""
Web search integration with LlamaIndex framework using Nimble MCP Server.
"""
import asyncio
import os
import sys

from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
from llama_index.llms.openai import OpenAI
from llama_index.core.agent.workflow import FunctionAgent

from dotenv import load_dotenv
load_dotenv()

MCP_URL = "https://mcp.nimbleway.com/sse"

async def main(query: str) -> None:
    api_key = os.environ.get("NIMBLE_API_KEY")
    if not api_key:
        raise ValueError("NIMBLE_API_KEY environment variable not set")
    
    mcp_client = BasicMCPClient(
        command_or_url=MCP_URL,
        timeout=30, 
        env={
            "NIMBLE_API_KEY": api_key,
            "MCP_HEADERS": f"Authorization=Basic {api_key}"
        }
    )
    
    print("Loading MCP tools...")
    tools = await McpToolSpec(client=mcp_client).to_tool_list_async()
    
    agent = FunctionAgent(
        tools=tools,
        llm=OpenAI(model="gpt-4.1"),
        verbose=True
    )
    
    print(f"Searching for information about: {query}")
    print("This may take a few moments...")
    
    response = await agent.run(query)
    print("\nResults:")
    print(response)

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "recent advancements in AI research"
    asyncio.run(main(query))
