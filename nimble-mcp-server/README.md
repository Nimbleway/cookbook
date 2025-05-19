# Nimble MCP Cookbook

This repository contains examples and guides for using Nimble MCP (Model Context Protocol) with various AI agent frameworks and applications.

## Available Tools

- **nimble_deep_web_search**: Perform web searches across multiple search engines (Google, Bing, Yandex) with configurable parameters
- **nimble_google_maps_search**: Search for places on Google Maps and retrieve structured location data
- **nimble_google_maps_reviews**: Collect reviews for a specific place from Google Maps
- **nimble_google_maps_place**: Retrieve detailed, dynamic information about a specific place from Google Maps, including core details, metadata, amenities, and more.

## Usage in Claude Desktop, Qodo Gen, Cursor...

The fastest way to use this MCP server is to connect to our official remote instance using Server-Sent Events (SSE) transport. This allows you to use the server without installing it locally.

### Remote Connection Setup (SSE)

1. **Get a Nimble API Key**:
   - Register for an account at [Nimble's signup page](https://app.nimbleway.com/signup)
   - Navigate to the "Pipelines" page and access the "Nimble API" pipeline
   - Obtain your API credentials (provided as a base64 token)

2. **Prerequisites**:
   - Ensure you have [Node.js and npm](https://nodejs.org/) installed on your system
   - The configuration below uses `npx` to run the MCP remote client without needing a local installation

3. **Add Configuration to your MCP-Compatible Client**:
   
   This configuration works with Claude Desktop, Cursor, Qodo, and any other client that supports Model Context Protocol (MCP).
   
   Add this configuration to your `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "nimble-mcp-server": {
         "command": "npx",
         "args": [
           "-y", "mcp-remote", "https://mcp.nimbleway.com/sse", 
           "--header", "Authorization:${NIMBLE_API_KEY}"],
         "env": {
           "NIMBLE_API_KEY": "Basic XXX"
         }
       }
     }
   }
   ```
   > **Note:** Replace `Basic XXX` with your actual Nimble API key.

4. **Start using the MCP tools with your AI agent!**

## Examples using Agents frameworks

Before running the examples, you'll need to set up the required environment variables:

```bash
# Required for all examples
export NIMBLE_API_KEY="your-nimble-api-key"

# For OpenAI-based examples (required for most examples)
export OPENAI_API_KEY="your-api-key"

# For Azure's OpenAI integrations (required for 03_autogen_azure.py)
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_ENDPOINT="your-endpoint"
```

You can also create a `.env` file in the project root directory with these variables.

## Getting Started

These examples demonstrate the basic usage of Nimble MCP with different AI frameworks:

| File | Description |
|------|-------------|
| `01_python.py` | Simple Python-based usage of Nimble MCP with no additional frameworks |
| `02_autogen.py` | Using Microsoft AutoGen framework with Nimble MCP and OpenAI |
| `03_autogen_azure.py` | Using Microsoft AutoGen with Azure OpenAI and Nimble MCP |
| `04_langchain.py` | Using LangChain framework with Nimble MCP |
| `05_agno.py` | Using Agno agent framework with Nimble MCP |
| `06_llamaindex.py` | Using LlamaIndex framework with Nimble MCP |

### Running Examples

You can run any example with a simple command:

```bash
# Basic usage (will use the default search query)
python cookbook/getting_started/01_python.py

# Provide a custom search query
python cookbook/getting_started/01_python.py "latest AI research in 2025"
```

## Framework Documentation

For more information on the frameworks used in these examples, refer to their official documentation:

- [AutoGen](https://microsoft.github.io/autogen/) - Framework for building AI agents
- [LangChain](https://python.langchain.com/) - Framework for developing applications powered by language models
- [LlamaIndex](https://www.llamaindex.ai/) - Data framework for LLM applications
- [Agno](https://github.com/agno-ai/agno) - Agent framework for building AI assistants


## Contributing

We welcome contributions to this cookbook! If you have an example or improvement to share, please submit a pull request.
