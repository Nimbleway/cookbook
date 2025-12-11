# Nimble Web Agent

> **Cookbook Example**: This is a ready-to-use example demonstrating how to build a web research agent using [LangChain](https://github.com/langchain-ai/langchain) and [langchain-nimble](https://github.com/nimbleway/langchain-nimble).

A single-task CLI agent that performs intelligent web research and data extraction. Enter one query, get comprehensive results powered by Nimble's web intelligence tools and Claude Sonnet 4.5.

## What This Example Demonstrates

- **LangChain Agent Framework**: Building autonomous agents with tool integration
- **Nimble Tools Integration**: Using `NimbleSearchTool` and `NimbleExtractTool` for web intelligence
- **Real-time Web Search**: Search for current information using Nimble's search API
- **Content Extraction**: Extract and analyze content from specific URLs
- **Rich Terminal UI**: Progress indicators, spinners, and formatted output

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

Run the agent with a single task:
```bash
uv run main.py
```

Enter your research query when prompted:
```
→ What are the latest AI trends?
```

The agent will autonomously:
1. Search the web for relevant information
2. Extract detailed content from top sources
3. Synthesize findings into a comprehensive answer

## Example

![Web Agent CLI Example](docs/example.png)