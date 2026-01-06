"""Terminal UI utilities for the web agent CLI."""

import os
import time
from typing import Optional

import questionary
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.status import Status

console = Console()

style = Style.from_dict(
    {
        "prompt": "#00aaff bold",
        "placeholder": "#888888 italic",
        "bottom-toolbar": "#333333",
    }
)


def print_welcome():
    """Print welcome banner."""
    console.print()
    console.print()

    console.print("╔═══════════════════════════════════════════════════════════╗", style="bold bright_cyan", justify="center")
    console.print("║                                                           ║", style="bold bright_cyan", justify="center")
    console.print("║          🌐  N I M B L E   W E B   A G E N T  🤖          ║", style="bold bright_white", justify="center")
    console.print("║                                                           ║", style="bold bright_cyan", justify="center")
    console.print("║          AI-Powered Web Research & Data Extraction        ║", style="bright_magenta", justify="center")
    console.print("║                                                           ║", style="bold bright_cyan", justify="center")
    console.print("╚═══════════════════════════════════════════════════════════╝", style="bold bright_cyan", justify="center")

    console.print()
    console.print("Powered by LangChain • Nimble Web Intelligence • Claude Sonnet 4.5", style="dim italic", justify="center")
    console.print()


def clear_and_reset_screen():
    """Clear the console screen and reprint the welcome banner."""
    console.clear()
    print_welcome()


def print_company_form_header():
    """Print header for company research form."""
    console.print()
    console.rule("[bold magenta]Company Research Form[/bold magenta]")
    console.print()
    console.print("[dim]Please provide the company details below:[/dim]")
    console.print()


def print_pricing_form_header():
    """Print header for pricing analysis form."""
    console.print()
    console.rule("[bold green]Pricing Analysis Form[/bold green]")
    console.print()
    console.print("[dim]Please provide the product details below:[/dim]")
    console.print()


def get_bottom_toolbar():
    """Return bottom toolbar."""
    width = os.get_terminal_size().columns if hasattr(os, "get_terminal_size") else 80
    return [("class:bottom-toolbar", "─" * width)]


def print_response_header():
    """Print the response section header."""
    console.print()
    console.print("━" * os.get_terminal_size().columns, style="bright_cyan")
    console.print("✨ Agent Response", style="bold bright_cyan", justify="center")
    console.print("━" * os.get_terminal_size().columns, style="bright_cyan")
    console.print()


def print_agent_text(text: str):
    """Print agent text response."""
    console.print(f"[cyan]Assistant:[/cyan]\n{text}")


def print_tool_call(tool_name: str, tool_input: dict):
    """Print tool call information."""
    console.print(f"[yellow]🔧 Calling tool:[/yellow] {tool_name}")
    console.print(f"[dim]Parameters:[/dim] {tool_input}")
    console.print()


def print_tool_result(tool_name: str, content: str, elapsed_time: Optional[float] = None):
    """Print tool execution result."""
    elapsed_str = ""
    if elapsed_time is not None:
        elapsed_str = f" [dim]({elapsed_time:.2f}s)[/dim]"

    console.print(f"[green]Tool Result ({tool_name}):{elapsed_str}[/green]")
    if isinstance(content, str) and len(content) > 500:
        console.print(f"[dim]{content[:500]}...[/dim]")
    else:
        console.print(f"[dim]{content}[/dim]")
    console.print()


def print_footer(total_time: float):
    """Print completion footer with total time."""
    console.print()
    console.rule(style="dim")
    console.print(
        f"[dim italic]Total processing time: {total_time:.2f}s[/dim italic]",
        justify="right"
    )


def create_spinner(message: str) -> Status:
    """Create and return a status spinner."""
    return Status(
        f"[dim]{message}[/dim]",
        console=console,
        spinner="dots",
    )


def _extract_text_from_block(block) -> Optional[str]:
    """Extract text from a content block (dict or object)."""
    if isinstance(block, dict):
        return block.get("text", "") if block.get("type") == "text" else None

    if hasattr(block, "type") and block.type == "text":
        return getattr(block, "text", "")

    return None


def _extract_tool_call_from_block(block) -> Optional[dict]:
    """Extract tool call info from a content block (dict or object)."""
    if isinstance(block, dict) and block.get("type") == "tool_use":
        return block

    if hasattr(block, "type") and block.type == "tool_use":
        return {
            "name": getattr(block, "name", "unknown"),
            "input": getattr(block, "input", {}),
            "id": getattr(block, "id", ""),
        }

    return None


def _parse_content_blocks(content) -> tuple[list[str], list[dict]]:
    """Parse content into text parts and tool calls."""
    if not isinstance(content, list):
        return [], []

    text_parts = []
    tool_calls = []

    for block in content:
        text = _extract_text_from_block(block)
        if text:
            text_parts.append(text)
            continue

        tool_call = _extract_tool_call_from_block(block)
        if tool_call:
            tool_calls.append(tool_call)

    return text_parts, tool_calls


async def get_mode_selection() -> str:
    """Prompt user to select agent mode (returns 'general', 'company', or 'pricing')."""
    console.print()
    console.rule("[bold bright_cyan]Select Agent Mode[/bold bright_cyan]")
    console.print()

    choices = [
        questionary.Choice(
            title="General Question - Ask any question and get comprehensive answers",
            value="general"
        ),
        questionary.Choice(
            title="Company Research - Deep dive into company information",
            value="company"
        ),
        questionary.Choice(
            title="Pricing Analysis - Compare product prices across marketplaces",
            value="pricing"
        ),
    ]

    try:
        mode = await questionary.select(
            "",
            choices=choices,
            style=questionary.Style([
                ('question', 'fg:#00aaff bold'),
                ('pointer', 'fg:#00aaff bold'),
                ('highlighted', 'fg:#00aaff bold'),
                ('selected', 'fg:#00ff00'),
            ])
        ).ask_async()

        if mode is None:
            raise KeyboardInterrupt

        return mode

    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        raise


async def get_company_research_input(session: PromptSession) -> Optional[str]:
    """Prompt for company details and return formatted research query."""
    print_company_form_header()

    try:
        with patch_stdout():
            company_name = await session.prompt_async(
                "  Company Name → ",
                placeholder="e.g., Anthropic",
                bottom_toolbar=get_bottom_toolbar,
            )
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        raise

    if not company_name.strip():
        console.print("[yellow]Company name is required[/yellow]")
        return None

    try:
        with patch_stdout():
            company_domain = await session.prompt_async(
                "  Website/Domain → ",
                placeholder="e.g., anthropic.com",
                bottom_toolbar=get_bottom_toolbar,
            )
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        raise

    if not company_domain.strip():
        console.print("[yellow]Website/domain is required[/yellow]")
        return None

    query = f"Research the company '{company_name}' (website: {company_domain})"

    console.print()
    console.print(f"[dim]Researching:[/dim] [bold]{company_name}[/bold] [dim]({company_domain})[/dim]")
    console.print()

    return query


async def get_general_question_input(session: PromptSession) -> Optional[str]:
    """Prompt for general question and return query string."""
    try:
        with patch_stdout():
            query = await session.prompt_async(
                "  → ",
                placeholder="Enter your task...",
                bottom_toolbar=get_bottom_toolbar,
            )
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        raise

    if not query.strip():
        console.print("[yellow]No task provided[/yellow]")
        return None

    return query


async def get_pricing_analysis_input(session: PromptSession) -> Optional[str]:
    """Prompt for product details and return formatted pricing analysis query."""
    print_pricing_form_header()

    try:
        with patch_stdout():
            product_name = await session.prompt_async(
                "  Product Name → ",
                placeholder="e.g., iPhone 15 Pro Max 256GB",
                bottom_toolbar=get_bottom_toolbar,
            )
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        raise

    if not product_name.strip():
        console.print("[yellow]Product name is required[/yellow]")
        return None

    query = f"Analyze pricing for: '{product_name}'"

    console.print()
    console.print(f"[dim]Analyzing pricing for:[/dim] [bold]{product_name}[/bold]")
    console.print()

    return query


def display_agent_status(status: str, mode_name: Optional[str] = None) -> None:
    """Display agent initialization status ('initializing', 'ready', or 'error')."""
    if mode_name:
        console.print(f"\n[dim]Selected mode:[/dim] {mode_name}")
        console.print()

    if status == "initializing":
        console.print("[dim]Initializing agent...[/dim]")
    elif status == "ready":
        console.print("[green]✓ Agent ready![/green]")
        console.print()


class AgentResponseDisplay:
    """Manages the display of agent responses with spinners and formatting."""

    def __init__(self):
        self.status: Optional[Status] = None
        self.tool_start_times = {}
        self.task_start_time = time.time()

    def start_processing(self):
        """Show processing spinner."""
        self.status = create_spinner("Agent is processing...")
        self.status.start()

    def stop_spinner(self):
        """Stop any active spinner."""
        if self.status:
            self.status.stop()
            self.status = None

    def handle_message(self, message) -> None:
        """Handle any message type from the agent stream."""
        if not hasattr(message, "type"):
            return

        if message.type == "human":
            return

        if message.type == "ai":
            self._handle_ai_message(message)
            return

        if message.type == "tool":
            self._handle_tool_message(message)
            return

    def _handle_ai_message(self, message) -> None:
        """Handle AI message with text and/or tool calls."""
        self.stop_spinner()
        content = message.content

        if isinstance(content, str):
            print_agent_text(content)
            console.print()
            return

        text_parts, tool_calls = _parse_content_blocks(content)

        if text_parts:
            combined_text = "\n".join(text_parts)
            print_agent_text(combined_text)
            console.print()

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "unknown")
            tool_input = tool_call.get("input", {})
            tool_id = tool_call.get("id", "")

            self.tool_start_times[tool_id] = time.time()
            print_tool_call(tool_name, tool_input)

            self.status = create_spinner(f"Executing {tool_name}...")
            self.status.start()

    def _handle_tool_message(self, message) -> None:
        """Handle tool execution result."""
        self.stop_spinner()

        tool_name = getattr(message, "name", "unknown")
        tool_call_id = getattr(message, "tool_call_id", None)
        content = message.content

        elapsed_time = None
        if tool_call_id in self.tool_start_times:
            elapsed_time = time.time() - self.tool_start_times[tool_call_id]
            del self.tool_start_times[tool_call_id]

        print_tool_result(tool_name, content, elapsed_time)

        # Restart processing spinner for agent's next turn
        self.status = create_spinner("Agent is processing...")
        self.status.start()

    def finish(self):
        """Finish display and show total time."""
        self.stop_spinner()
        total_time = time.time() - self.task_start_time
        print_footer(total_time)
