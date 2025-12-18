# Nimble Web Agent

> **Cookbook Example**: This is a ready-to-use example demonstrating how to build a web research agent using [LangChain](https://github.com/langchain-ai/langchain) and [langchain-nimble](https://github.com/nimbleway/langchain-nimble).

An intelligent CLI agent with two specialized modes for web research and data extraction. Choose between general questions or deep company research, powered by Nimble's web intelligence tools and Claude Sonnet 4.5.

## What This Example Demonstrates

- **Multi-Mode Agent Architecture**: Switch between general questions and specialized company research
- **LangChain Agent Framework**: Building autonomous agents with tool integration
- **Nimble Tools Integration**: Using `NimbleSearchTool` and `NimbleExtractTool` for web intelligence
- **Real-time Web Search**: Search for current information using Nimble's search API
- **Content Extraction**: Extract and analyze content from specific URLs
- **Structured Research Output**: Specialized prompts for comprehensive company intelligence
- **Rich Terminal UI**: Mode selection, progress indicators, spinners, and formatted output

## Installation

1. Clone the repository:
```bash
cd langchain/web_agent_cli
```

2. Install dependencies:
```bash
uv sync
```

3. Get your API keys:

   **Nimble API Key:**
   - Register for an account at [Nimble's signup page](https://app.nimbleway.com/signup)
   - Navigate to your "Account settings" page and open the "API KEYS" tab
   - Click on "+ Add Key" to generate a new token and copy it

   **Anthropic API Key:**
   - Sign up at [Anthropic Console](https://console.anthropic.com)
   - Navigate to API Keys section
   - Create a new API key

4. Set up environment variables:
```bash
cp .env.example .env
```

   Edit `.env` and add your API keys:
   ```
   NIMBLE_API_KEY=your_nimble_api_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ```

## Usage

Run the agent:
```bash
uv run main.py
```

You'll be prompted to select an agent mode:
```
1. General Question (default) - Ask any question
2. Company Research Agent - Deep dive into company information
```

### Mode 1: General Question

Enter any research query:
```
→ What are the latest AI trends in 2025?
```

The agent will autonomously:
1. Search the web for relevant information
2. Extract detailed content from top sources
3. Synthesize findings into a comprehensive answer

### Mode 2: Company Research Agent

Provide company details:
```
Company Name → Anthropic
Website/Domain → anthropic.com
```

The agent will research and structure information about:
- **Company Overview & Mission**: What they do, founding details
- **Key People & Leadership**: C-suite executives, founders, board members
- **Competitors & Market Position**: Main competitors, competitive advantages
- **Recent News & Developments**: Funding, product launches, partnerships

All facts are cited with sources for easy verification.

## Example

![Web Agent CLI Example](docs/example.png)