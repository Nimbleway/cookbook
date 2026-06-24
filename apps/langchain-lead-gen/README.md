# langchain-lead-gen — AI Lead Generation Agent

A Streamlit app that turns a Google Maps search query into a scored, enriched lead list — powered by [Nimble](https://nimbleway.com) and LangChain.

![Lead Scout](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20LangChain-edc602)

## What it does

1. **Search** — queries Google Maps via Nimble's Web Search Agent and returns businesses matching your query
2. **Enrich** — visits each business website and extracts email, opening hours, and a short description
3. **Score** — ranks every lead 1–10 on outreach potential (data completeness, ratings, engagement signals)
4. **Chat** — lets you ask natural language questions about your lead list
5. **Export** — downloads the full enriched list as a CSV

## Stack

- [Nimble](https://nimbleway.com) — Google Maps agent + website extraction
- [LangGraph](https://langchain-ai.github.io/langgraph/) — ReAct agent orchestration
- [LangChain Anthropic](https://python.langchain.com/docs/integrations/chat/anthropic/) — Claude for enrichment, scoring, and chat
- [Streamlit](https://streamlit.io) — UI

## Setup

**1. Clone and install dependencies**

```bash
git clone https://github.com/Nimbleway/cookbook-langchain-lead-gen
cd cookbook-langchain-lead-gen
pip install -r requirements.txt
```

**2. Add your API keys**

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```
NIMBLE_API_KEY=your_nimble_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

Get a Nimble API key at [nimbleway.com](https://nimbleway.com).

**3. Run**

```bash
streamlit run app.py
```

## Usage

Enter any Google Maps search query — e.g. `"independent coffee shops in Nashville, TN"` — and click **Find Leads**.

The agent will search, enrich each business website, score every lead, and surface a ranked list you can explore and export.

## Project structure

```
lead-scout/
├── agent.py          # Nimble tools, LangGraph agent, scoring chain, chat function
├── app.py            # Streamlit UI + streaming logic
├── requirements.txt
├── .env.example
└── .streamlit/
    └── config.toml   # Dark theme, Nimble yellow
```
