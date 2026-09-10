# company-due-diligence-agent

A small **LangChain agent** that runs **preliminary investment due diligence** on a
company, using **Nimble** for web data. It ships both ways of using Nimble for the same
task:

| File | Pattern | Who runs the research loop |
| --- | --- | --- |
| `agent.py` / `run.py` | **A** — LangChain + Nimble Search API | the LangChain agent |
| `agent_api_v2.py` | **B** — Nimble Web Search Agent (Agent API) | Nimble |

## Pattern A — the LangChain agent drives

Give it a company name. The agent runs one focused pass per diligence dimension —
business model, products, leadership, funding, partnerships, competitors, regulatory —
scoping each search to the sources that fit it, reads the pages it will cite, cross-checks
funding figures, and returns a structured `DiligenceProfile` with a strengths / risks /
insufficient-evidence scorecard and a confidence grade per dimension.

```bash
uv run python run.py "Ramp"
uv run python run.py "Brex" --json profile.json
```

The `nimble_search` tool: `search_depth="lite"` to find the right pages,
`full_content=True` (≤4 results) to read the pages it cites — full-content results are
**sliced to the query-relevant windows** of the page, not truncated to the first N
characters.

## Pattern B — Nimble's Web Search Agent does the research

`agent_api_v2.py` hands Nimble one research objective and follows the documented
`run → poll → result` lifecycle via the official `nimble-python` SDK. It passes a flat
`output_schema` mirroring `DiligenceProfile` — including `as_of_date`,
`funding.last_round_valuation`, and a `confidence_by_dimension` list — so Nimble returns
structured data with per-claim citations.

```bash
uv run python agent_api_v2.py "Ramp"
uv run python agent_api_v2.py "Brex" --effort x-high --json result.json
```

## Files

- `config.py` — `SKILL`, `GOALS`, `SOURCE_TIERS`, `DIMENSIONS`, system-prompt builder.
- `schema.py` — `DiligenceProfile`, `Scorecard`, `Person`, `Funding`.
- `agent.py` — the Pattern A LangChain agent and its `nimble_search` tool.
- `agent_api_v2.py` — the Pattern B `run → poll → result` driver.
- `run.py` — Pattern A CLI.

## The Nimble client

Both patterns use Nimble's official **`nimble-python`** SDK directly. For the Search API
that is deliberate: as of `langchain-nimble` 4.0.0 its search wrapper does not expose
`full_content` and its domain-scoped ranking is weak for the primary-source retrieval
this agent depends on.

## Setup & run

```bash
uv sync
cp .env.example .env       # NIMBLE_API_KEY + an LLM_MODEL and its key
```

`LLM_MODEL` is provider-agnostic via `init_chat_model` — `openai:gpt-5.1` (default),
`anthropic:claude-sonnet-5`, `google_genai:gemini-2.5-pro`, … Install the matching
provider package (`langchain-openai` is bundled).

Env overrides: `LLM_MODEL`, `NIMBLE_CONTENT_CHAR_CAP` (`8000`), `AGENT_RECURSION_LIMIT` (`48`).

## Example

`examples/ramp_profile.json` — a real Pattern A run for `"Ramp"`: business model, product
inventory, leadership, a terse funding summary (`"$750M growth round"`, `"$44B
post-money"`), partnerships, competitors, and a scorecard with a confidence grade for
each of the seven dimensions.
