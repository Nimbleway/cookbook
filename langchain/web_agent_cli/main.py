import asyncio
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_nimble import NimbleExtractTool, NimbleSearchTool
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import set_title

from terminal_ui import (
    AgentResponseDisplay,
    console,
    get_bottom_toolbar,
    print_response_header,
    print_welcome,
    style,
)

load_dotenv()


async def create_web_agent() -> Any:
    """Create a LangChain agent with Nimble tools."""
    import os

    if not os.environ.get("NIMBLE_API_KEY"):
        console.print("[red]Error: NIMBLE_API_KEY environment variable is required[/red]")
        raise ValueError("NIMBLE_API_KEY is required")

    # Initialize Nimble tools
    search_tool = NimbleSearchTool()
    extract_tool = NimbleExtractTool()

    # Get current date for time-aware responses
    today = datetime.now().strftime("%B %d, %Y")

    # Create agent with tools and system prompt
    agent = create_agent(
        model="claude-sonnet-4-5",
        tools=[search_tool, extract_tool],
        system_prompt=(
            f"You are a helpful assistant with access to real-time web "
            f"information. Today's date is {today}. "
            f"You can search the web and extract content from "
            f"specific URLs. Use the search tool to find relevant information, "
            f"then use the extract tool to get detailed content from specific "
            f"pages when needed. Always cite your sources and provide "
            f"comprehensive, accurate answers."
        ),
    )

    return agent


async def stream_agent_response(agent: Any, query: str) -> None:
    """Stream agent response and display with formatting."""
    print_response_header()

    display = AgentResponseDisplay()
    display.start_processing()

    last_processed_index = 0

    async for step in agent.astream(
        {"messages": [{"role": "user", "content": query}]},
        stream_mode="values",
    ):
        messages = step["messages"]

        for message in messages[last_processed_index:]:
            display.handle_message(message)

        last_processed_index = len(messages)

    display.finish()


async def main():
    """Main entry point."""
    set_title("Nimble Web Agent")

    print_welcome()

    console.print("[dim]Initializing agent...[/dim]")
    try:
        agent = await create_web_agent()
        console.print("[green]✓ Agent ready![/green]")
        console.print()
    except Exception as e:
        console.print(f"[red]Failed to initialize agent: {e}[/red]")
        return

    session = PromptSession(style=style)

    console.rule(style="bright_black")

    try:
        with patch_stdout():
            query = await session.prompt_async(
                "  → ",
                placeholder="Enter your task...",
                bottom_toolbar=get_bottom_toolbar,
            )
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    if not query.strip():
        console.print("[yellow]No task provided[/yellow]")
        return

    try:
        await stream_agent_response(agent, query)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    console.print()


if __name__ == "__main__":
    asyncio.run(main())
