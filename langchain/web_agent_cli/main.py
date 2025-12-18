import asyncio
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_nimble import NimbleExtractTool, NimbleSearchTool
from prompt_toolkit import PromptSession
from prompt_toolkit.shortcuts import set_title

from prompts import get_system_prompt
from terminal_ui import (
    AgentResponseDisplay,
    clear_and_reset_screen,
    console,
    display_agent_status,
    get_company_research_input,
    get_general_question_input,
    get_mode_selection,
    print_response_header,
    print_welcome,
    style,
)

load_dotenv()


async def create_web_agent(mode: str = "general") -> Any:
    """Create a LangChain agent with Nimble tools."""
    missing_keys = []
    if not os.environ.get("NIMBLE_API_KEY"):
        missing_keys.append("NIMBLE_API_KEY")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing_keys.append("ANTHROPIC_API_KEY")

    if missing_keys:
        console.print(f"[red]Error: Missing required environment variables: {', '.join(missing_keys)}[/red]")
        raise ValueError(f"Missing required API keys: {', '.join(missing_keys)}")

    search_tool = NimbleSearchTool()
    extract_tool = NimbleExtractTool()
    today = datetime.now().strftime("%B %d, %Y")
    system_prompt = get_system_prompt(mode, today)

    agent = create_agent(
        model="claude-sonnet-4-5",
        tools=[search_tool, extract_tool],
        system_prompt=system_prompt,
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

    session = PromptSession(style=style)

    try:
        mode = await get_mode_selection(session)
    except (EOFError, KeyboardInterrupt):
        return

    clear_and_reset_screen()

    mode_name = "[magenta]Company Research Agent[/magenta]" if mode == "company" else "[cyan]General Question[/cyan]"
    display_agent_status("initializing", mode_name)

    try:
        agent = await create_web_agent(mode)
        display_agent_status("ready")
    except Exception as e:
        console.print(f"[red]Failed to initialize agent: {e}[/red]")
        return

    console.rule(style="bright_black")

    try:
        if mode == "company":
            query = await get_company_research_input(session)
        else:
            query = await get_general_question_input(session)
    except (EOFError, KeyboardInterrupt):
        return

    if not query:
        return

    try:
        await stream_agent_response(agent, query)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    console.print()


if __name__ == "__main__":
    asyncio.run(main())
