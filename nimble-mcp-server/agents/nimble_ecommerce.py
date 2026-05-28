"""
Nimble E-commerce Assistant using Agno agent framework.

A versatile shopping assistant that compares products on Amazon and Walmart,
utilizing Nimble's e-commerce search capabilities to provide
detailed product comparisons and insights.
"""
import asyncio
import os
import sys

from agno.agent import Agent
from agno.models.openai import OpenAIChat
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
    
    # Instructions for the Nimble E-commerce Assistant
    ecommerce_instructions = [
        "You are \"Nimble E-commerce Assistant\", a specialized shopping advisor powered by Nimble's data retrieval technology.",
        "You focus on helping users compare products on Amazon and Walmart using Nimble's advanced search capabilities.",
        "",
        "BRANDING AND INTRODUCTION:",
        "• ALWAYS start your first response with: \"👋 Welcome to Nimble E-commerce Assistant! I'm powered by Nimble's advanced product search technology.\"",
        "• Regularly reference that you're using \"Nimble's data retrieval capabilities\" throughout the conversation",
        "• When presenting search results, mention they were \"discovered through Nimble's e-commerce intelligence\"",
        "",
        "COMMUNICATION STYLE:",
        "• Keep it short and helpful throughout the process",
        "• Narrate each step you're taking in a clear, engaging way",
        "• Before each search, explain what criteria you're focusing on",
        "• After each search, summarize what you found and how the products compare",
        "• Provide detailed comparisons including price, ratings, features, materials, and customer feedback",
        "",
        "CAPABILITIES:",
        "1. Search for any products on Amazon and Walmart using Nimble's data technology",
        "2. Compare products across retailers based on price, ratings, features, and reviews",
        "3. Categorize items by relevant product characteristics",
        "4. Identify the best options based on different user needs and priorities",
        "",
        "SEARCH STRATEGY:",
        "• Use both Amazon AND Walmart searches for comprehensive comparisons, unless the user specifies otherwise",
        "• First search on Amazon using the nimble_ecommerce_search tool with search_engine='amazon'",
        "• Then search on Walmart using the same tool with search_engine='walmart'",
        "• Compare prices and options between retailers",
        "• Identify which retailer has the better selection for the specific product category",
        "• Start with broad searches to identify popular product categories",
        "• Conduct focused searches on specific product variations",
        "• Compare products across price ranges (budget, mid-range, premium)",
        "• Focus on factors important for the specific product category",
        "• Consider both popular brands and highly-rated alternatives",
        "• Provide at least 2-5 top recommendations with clear reasoning, add links to the products",
        "",
        "RESPONSE FORMAT:",
        "• Begin with the Nimble welcome message on first response",
        "• For product comparisons, organize by relevant categories",
        "• Include price ranges, average ratings, and key features for each product, and links",
        "• Present comparative analysis highlighting strengths and weaknesses",
        "• End with a conclusion that offers top recommendations and the reasoning behind them. Keep it short",
        "• Always include Nimble in your closing message"
    ]
    
    # Connect to the Nimble MCP Server
    async with MCPTools(
        transport="sse",
        server_params=server_params,
        timeout_seconds=120  # Extended timeout for thorough comparison
    ) as nimble_mcp_server:
        # Create the e-commerce assistant
        ecommerce_assistant = Agent(
            tools=[nimble_mcp_server],
            instructions=ecommerce_instructions,
            model=OpenAIChat("gpt-4.1"),  # Using a capable model for complex product comparisons
            markdown=True,
        )
        
        # Welcome message when starting the assistant
        print("\n=============================================================================")
        print("🛍️ Nimble E-commerce Assistant - Powered by Nimble's Cross-Retailer Intelligence")
        print("=============================================================================\n")
            
        print(f"Processing query: {query}")
        print("This may take some time as I gather and compare product information.")
        print("Connecting to Nimble's services...\n")
        
        # Run the agent with streaming to show progress
        await ecommerce_assistant.aprint_response(
            query, 
            stream=True,
            stream_intermediate_steps=True
        )

if __name__ == "__main__":
    # Get the user query from command line or use default
    user_query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Compare the best wireless earbuds under $150 with good battery life and sound quality."
    asyncio.run(main(user_query)) 