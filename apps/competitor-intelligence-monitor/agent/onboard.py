#!/usr/bin/env python3
"""
Competitor Monitor — Interactive Onboarding Wizard

Run with:  python onboard.py
"""

import json
import os
import sys
from pathlib import Path

# ─── ANSI colour helpers ──────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
DIM    = "\033[2m"


def green(s):  return f"{GREEN}{s}{RESET}"
def yellow(s): return f"{YELLOW}{s}{RESET}"
def cyan(s):   return f"{CYAN}{s}{RESET}"
def red(s):    return f"{RED}{s}{RESET}"
def bold(s):   return f"{BOLD}{s}{RESET}"
def dim(s):    return f"{DIM}{s}{RESET}"


def section_header(title):
    print(f"\n{CYAN}{'─' * 60}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{'─' * 60}{RESET}\n")


def prompt(label, hint="", required=True, default=""):
    hint_str = f" {dim('(' + hint + ')')}" if hint else ""
    default_str = f" {dim('[' + default + ']')}" if default else ""
    while True:
        val = input(f"{YELLOW}{label}{RESET}{hint_str}{default_str}: ").strip()
        if not val and default:
            return default
        if val:
            return val
        if not required:
            return ""
        print(red("  This field is required. Please enter a value."))


def prompt_optional(label, hint=""):
    hint_str = f" {dim('(' + hint + ')')}" if hint else ""
    val = input(f"{YELLOW}{label}{RESET}{hint_str} {dim('[press Enter to skip]')}: ").strip()
    return val


def prompt_yes_no(label, default_yes=True):
    default_hint = "Y/n" if default_yes else "y/N"
    val = input(f"{YELLOW}{label}{RESET} {dim('[' + default_hint + ']')}: ").strip().lower()
    if not val:
        return default_yes
    return val in ("y", "yes")


# ─── Colour palette for competitors ──────────────────────────────────────────

COLOR_PALETTE = [
    "#3498db", "#e67e22", "#9b59b6", "#e74c3c",
    "#1abc9c", "#f39c12", "#2ecc71", "#e91e63",
    "#00bcd4", "#ff5722",
]


def pick_color(index):
    return COLOR_PALETTE[index % len(COLOR_PALETTE)]


# ─── Banner ───────────────────────────────────────────────────────────────────

def print_banner():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════╗
║          COMPETITOR MONITOR — SETUP WIZARD               ║
╚══════════════════════════════════════════════════════════╝{RESET}

Welcome! This wizard sets up your competitor intelligence monitor.

It will:
  • Configure your company and the competitors you want to track
  • Collect the API keys required to run the monitor
  • Set up optional Slack and GitHub integrations
  • Write a {green('config.json')} and {green('.env')} file ready to use

Takes about {bold('2–3 minutes')} to complete.
""")


# ─── Step 1: Your company ─────────────────────────────────────────────────────

def step_your_company():
    section_header("Step 1 of 5 — Your Company")

    print(dim("  The monitor will track what people say about your company,\n"
              "  and position your company against the competitors you add next.\n"))

    name = prompt("Company name", hint="e.g. Acme Corp")
    aliases_raw = prompt(
        "Common aliases / spellings",
        hint="comma-separated, e.g. Acme, acme.com, Acme API",
    )
    aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]
    description = prompt(
        "One-sentence description",
        hint="e.g. a cloud infrastructure company",
    )
    industry = prompt(
        "Industry",
        hint="e.g. cloud infrastructure, web scraping APIs, fintech",
    )

    print(f"\n  {green('✓')} Company: {bold(name)}  |  Aliases: {', '.join(aliases)}")

    return {
        "name": name,
        "aliases": aliases,
        "description": description,
        "industry": industry,
    }


# ─── Step 2: Competitors ──────────────────────────────────────────────────────

def step_competitors():
    section_header("Step 2 of 5 — Competitors")

    print(dim("  Add the competitors you want to monitor, one at a time.\n"
              "  You can add as many as you like. Type 'done' when finished.\n"))

    competitors = []
    index = 0

    while True:
        comp_num = len(competitors) + 1
        print(f"\n{YELLOW}  Competitor #{comp_num}{RESET}  {dim('(or type done to finish)')}")

        name_raw = input(f"{YELLOW}  Name{RESET}: ").strip()
        if name_raw.lower() in ("done", "d", ""):
            if not competitors:
                print(red("  You need at least one competitor. Let's add one."))
                continue
            break

        aliases_raw = prompt(
            "  Aliases / domains",
            hint="comma-separated, e.g. CompetitorX, competitorx.com",
        )
        aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]

        github_repo = prompt_optional(
            "  GitHub repo",
            hint="owner/repo, e.g. openai/openai-python — leave blank if unknown",
        )

        pypi_package = prompt_optional(
            "  PyPI package name",
            hint="e.g. openai — leave blank if not on PyPI",
        )

        color = pick_color(index)
        print(f"  {green('✓')} Assigned color: {bold(color)}")

        competitors.append({
            "name": name_raw,
            "aliases": aliases,
            "github_repo": github_repo if github_repo else None,
            "pypi_package": pypi_package if pypi_package else None,
            "color": color,
        })
        index += 1
        print(f"  {green('✓')} Added {bold(name_raw)}")

    print(f"\n  {green('✓')} {len(competitors)} competitor(s) configured: "
          f"{', '.join(c['name'] for c in competitors)}")
    return competitors


# ─── Step 3: API keys (required) ─────────────────────────────────────────────

def step_api_keys():
    section_header("Step 3 of 5 — API Keys (Required)")

    print(f"  These two keys are {bold('required')} to run the monitor:\n")

    print(f"  {cyan('NIMBLE_API_KEY')} — used for web search to find competitor mentions")
    print(dim("    Get yours at: https://nimbleway.com  (sign up → API Keys)\n"))
    nimble_key = prompt("  NIMBLE_API_KEY")

    print(f"\n  {cyan('ANTHROPIC_API_KEY')} — used by Claude to synthesize and summarize findings")
    print(dim("    Get yours at: https://console.anthropic.com  (API Keys section)\n"))
    anthropic_key = prompt("  ANTHROPIC_API_KEY")

    return {
        "NIMBLE_API_KEY": nimble_key,
        "ANTHROPIC_API_KEY": anthropic_key,
    }


# ─── Step 4: Slack integration (optional) ────────────────────────────────────

def step_slack():
    section_header("Step 4 of 5 — Slack Integration (Optional)")

    print(dim("  If configured, the monitor posts a daily digest to a Slack channel\n"
              "  and supports personalized DMs via the /competitor-digest slash command.\n"))

    want_slack = prompt_yes_no("  Set up Slack integration?", default_yes=False)
    if not want_slack:
        print(f"  {dim('Skipping Slack — you can add it later by editing .env')}")
        return {"SLACK_BOT_TOKEN": "", "SLACK_CHANNEL_ID": "", "SLACK_SIGNING_SECRET": ""}

    print(f"\n  You'll need a Slack app with {bold('chat:write')} and {bold('commands')} scopes.")
    print(dim("  Create one at: https://api.slack.com/apps\n"))

    slack_token = prompt(
        "  SLACK_BOT_TOKEN",
        hint="starts with xoxb-",
    )

    print(dim("\n  To get the channel ID: right-click the channel in Slack → Copy Channel ID"))
    channel_id = prompt("  SLACK_CHANNEL_ID", hint="e.g. C01234ABCDE")

    print(dim("\n  Find this at: Slack App → Basic Information → App Credentials"))
    signing_secret = prompt("  SLACK_SIGNING_SECRET")

    return {
        "SLACK_BOT_TOKEN": slack_token,
        "SLACK_CHANNEL_ID": channel_id,
        "SLACK_SIGNING_SECRET": signing_secret,
    }


# ─── Step 5: GitHub API key (optional) ───────────────────────────────────────

def step_github():
    section_header("Step 5 of 5 — GitHub API Key (Optional)")

    print(dim("  Used for GitHub search and tracking competitor release notes.\n"
              "  Without it, GitHub sources are skipped (other sources still work).\n"))
    print(dim("  Create a token at: https://github.com/settings/tokens"))
    print(dim("  A classic token with no extra scopes is sufficient for public repos.\n"))

    gh_key = prompt_optional("  GH_API_KEY", hint="ghp_... or leave blank to skip")
    if gh_key:
        print(f"  {green('✓')} GitHub key configured")
    else:
        print(f"  {dim('Skipping GitHub — you can add it later by editing .env')}")

    return {"GH_API_KEY": gh_key}


# ─── Write files ──────────────────────────────────────────────────────────────

def write_config(company, competitors, base_dir):
    config = {
        "your_company": company,
        "competitors": competitors,
    }
    path = base_dir / "config.json"
    path.write_text(json.dumps(config, indent=2))
    return path


def write_env(env_vars, base_dir):
    path = base_dir / ".env"
    lines = []
    for key, value in env_vars.items():
        # Quote values that contain spaces or special chars
        if " " in value or "=" in value or not value:
            lines.append(f'{key}="{value}"')
        else:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n")
    return path


# ─── Summary ─────────────────────────────────────────────────────────────────

def print_summary(company, competitors, env_vars, config_path, env_path):
    print(f"\n{GREEN}{BOLD}╔══════════════════════════════════════════════════════════╗")
    print(f"║                  SETUP COMPLETE!                         ║")
    print(f"╚══════════════════════════════════════════════════════════╝{RESET}\n")

    print(f"  {green('✓')} Company configured: {bold(company['name'])}")
    print(f"  {green('✓')} Competitors: {', '.join(c['name'] for c in competitors)}")
    print(f"  {green('✓')} Files written:")
    print(f"      {bold(str(config_path))}")
    print(f"      {bold(str(env_path))}\n")

    # What's configured vs skipped
    configured = []
    skipped = []

    if env_vars.get("NIMBLE_API_KEY"):
        configured.append("Nimble API (web search)")
    if env_vars.get("ANTHROPIC_API_KEY"):
        configured.append("Anthropic API (AI synthesis)")
    if env_vars.get("SLACK_BOT_TOKEN"):
        configured.append("Slack (daily digest + DMs)")
    else:
        skipped.append("Slack")
    if env_vars.get("GH_API_KEY"):
        configured.append("GitHub (release tracking)")
    else:
        skipped.append("GitHub")

    if configured:
        print(f"  {green('Configured:')}  {', '.join(configured)}")
    if skipped:
        print(f"  {dim('Skipped:')}     {', '.join(skipped)}")

    print(f"\n{CYAN}{BOLD}  Next steps:{RESET}\n")
    print(f"  1. {bold('Run the agent')} (daily data collection + AI synthesis):")
    print(f"     {green('python agent.py')}\n")
    print(f"  2. {bold('Set up automated daily runs')} via GitHub Actions:")
    print(f"     {dim('Add your .env values as repository secrets,')}")
    print(f"     {dim('then push to main — the workflow runs at 8 AM UTC by default.')}\n")
    if skipped:
        print(f"  3. {bold('Add skipped integrations')} by editing {green('.env')} and re-running.\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    base_dir = Path(__file__).parent

    print_banner()

    # Check for existing .env
    env_path = base_dir / ".env"
    if env_path.exists():
        print(f"  {yellow('Warning:')} A {bold('.env')} file already exists at:\n"
              f"  {env_path}\n")
        overwrite = prompt_yes_no("  Overwrite it?", default_yes=False)
        if not overwrite:
            print(f"\n  {dim('Keeping existing .env — only config.json will be written.')}")
            skip_env = True
        else:
            skip_env = False
    else:
        skip_env = False

    try:
        company = step_your_company()
        competitors = step_competitors()
        api_keys = step_api_keys()
        slack = step_slack()
        github = step_github()
    except KeyboardInterrupt:
        print(f"\n\n  {red('Setup cancelled.')} Run {green('python onboard.py')} to start again.\n")
        sys.exit(0)

    env_vars = {**api_keys, **slack, **github}

    # Write config.json always
    config_path = write_config(company, competitors, base_dir)
    print(f"\n  {green('✓')} Written: {config_path}")

    # Write .env unless user chose to keep existing
    if not skip_env:
        written_env = write_env(env_vars, base_dir)
        print(f"  {green('✓')} Written: {written_env}")
    else:
        written_env = env_path
        print(f"  {dim('Skipped .env — existing file kept.')}")

    print_summary(company, competitors, env_vars, config_path, written_env)


if __name__ == "__main__":
    main()
