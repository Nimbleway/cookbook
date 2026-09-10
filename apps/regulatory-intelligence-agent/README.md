# regulatory-intelligence-agent

A small **LangChain agent** that monitors **regulatory and filing intelligence** for a
company, sector, or topic, using **Nimble** for web data.

Give it a subject. It runs several targeted searches — SEC filings, enforcement actions,
investigations, policy/rule changes — reads the primary documents, and returns a
structured brief of the material developments with citations, a materiality grade, and a
confidence grade.

The repo ships both ways of using Nimble for the same task:

| File | Pattern | Who runs the research loop |
| --- | --- | --- |
| `agent.py` / `run.py` | **A** — LangChain + Nimble Search API | the LangChain agent |
| `agent_api_v2.py` | **B** — Nimble Web Search Agent (Agent API) | Nimble |

## Pattern A — the LangChain agent drives

```
run.py ─> agent.py: create_agent(model, tools=[nimble_search], response_format=RegulatoryBrief)
                       │
                       └─ nimble_search  →  Nimble Search API
                            search_depth="lite"      → scan for candidate documents
                            full_content=True (≤4)   → pull + slice the primary docs to cite
                            include_domains=[...]     → scope each pass (sec.gov, federalregister.gov, …)
```

- `config.py` — the agent's role (`SKILL`), objectives (`GOALS`), and `SOURCE_TIERS`
  (with a `<company>.com` placeholder the agent substitutes per subject).
- `schema.py` — the `RegulatoryBrief` / `Development` structured-output models.
- `agent.py` — builds the agent and the `nimble_search` tool. `full_content` results are
  **sliced to the query-relevant windows** of the document, not truncated to the first N
  characters, so a deep read of a 150–400 KB 10-K keeps Item 1A / export-control / legal
  sections rather than the cover page.
- `run.py` — CLI entrypoint.

## Pattern B — Nimble's Web Search Agent does the research

`agent_api_v2.py` hands Nimble one research objective and follows the documented
`run → poll → result` lifecycle via the official `nimble-python` SDK:

```bash
uv run python agent_api_v2.py "NVIDIA"
uv run python agent_api_v2.py "semiconductor export controls" --effort x-high --json out.json
```

It passes the `RegulatoryBrief` shape as `output_schema`, so Nimble returns structured
data with per-claim citations and confidence.

## The Nimble client

Both patterns use Nimble's official **`nimble-python`** SDK directly. For the Search API
that is a deliberate choice: as of `langchain-nimble` 4.0.0 its search wrapper does not
expose `full_content` and its domain-scoped ranking is unreliable for primary-document
retrieval (`include_domains=["sec.gov"]` returns `sec.gov/ombuds` rather than the filing).

## Setup

```bash
uv sync                       # or: pip install -e .
cp .env.example .env          # NIMBLE_API_KEY + an LLM_MODEL and its key
```

`LLM_MODEL` is provider-agnostic via LangChain's `init_chat_model` —
`openai:gpt-5.1` (default), `anthropic:claude-sonnet-5`, `google_genai:gemini-2.5-pro`,
etc. Install the matching provider package (`langchain-openai` is bundled).

## Run

```bash
uv run python run.py "NVIDIA"
uv run python run.py "Microsoft" --model anthropic:claude-sonnet-5 --json brief.json
```

Env overrides: `LLM_MODEL`, `NIMBLE_CONTENT_CHAR_CAP` (default `8000`),
`AGENT_RECURSION_LIMIT` (default `40`).

## Example

`examples/nvidia_brief.json` — a real Pattern A run for `"NVIDIA"`: material developments
spanning recent 10-K / 10-Q / 8-K disclosures, BIS export-control rules, and ongoing
securities litigation, each citing the primary document on `sec.gov` or
`federalregister.gov`.
