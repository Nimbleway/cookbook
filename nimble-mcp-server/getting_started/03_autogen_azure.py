"""
Web search integration with Microsoft AutoGen framework using Azure OpenAI model and Nimble MCP Server.
"""
import asyncio
import os
import sys

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from autogen_ext.tools.mcp import SseServerParams, mcp_server_tools

from dotenv import load_dotenv
load_dotenv()

MCP_URL = "https://mcp.nimbleway.com/sse"

async def main(query: str) -> None:
    api_key = os.environ.get("NIMBLE_API_KEY")
    if not api_key:
        raise ValueError("NIMBLE_API_KEY environment variable not set")
    
    nimble_server_params = SseServerParams(
        url=MCP_URL,
        headers={"Authorization": f"Basic {api_key}"},
        timeout=30,
    )
    
    tools = await mcp_server_tools(nimble_server_params)
    
    model_client = AzureOpenAIChatCompletionClient(
        model="gpt-4o", 
        api_version="2024-06-01"
    )
    
    agent = AssistantAgent(
        name="azure_web_search_assistant",
        model_client=model_client,
        tools=tools,
        reflect_on_tool_use=True
    )
    
    await Console(
        agent.run_stream(
            task=f"Search the web for information about: {query}", 
            cancellation_token=CancellationToken()
        )
    )

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "recent breakthroughs in machine learning"
    asyncio.run(main(query))
