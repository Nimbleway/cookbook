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
                            search_depth="standard"  → scan for candidate documents
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

The `output_schema` repeats `required` on the nested `developments` item object and
restates every field description from `schema.py`. Both matter: without the nested
`required`, the API legitimately returns developments carrying only
`title`/`summary`/`why_it_matters` — no date, materiality, confidence or `source_urls` —
and without the descriptions, `sources` comes back as prose ("SEC EDGAR 10-Q for the
period ended July 26, 2026") instead of URLs. Any field still missing is backfilled from
`output.trust.claims[].citations`, which carry the real primary-document URLs, and the
CLI prints an `incomplete output` block listing whatever is still thin.

## The Nimble client

Both patterns use Nimble's official **`nimble-python`** SDK directly. For the Search API
that is deliberate: as of `langchain-nimble` 4.0.0 its `NimbleSearchTool` does not expose
`full_content`, which this agent needs to read primary documents.

### Why every search runs at `search_depth="standard"`

`search_depth="lite"` **silently ignores `include_domains`**. Measured over 10 scoped
queries, lite returned 21/45 off-domain results (47%) where standard returned 0/50 —
`include_domains=["sec.gov"]` on lite comes back with YouTube videos and vendor marketing
pages. Since the source allow-list is what makes these agents cite primary sources, lite
is never sent to the API: `nimble_search` accepts `search_depth="lite"` as a *scan* hint,
issues the request at standard depth, and trims the result to `title`/`url`/`description`
locally (61-80% smaller than an untrimmed standard result, so a scan stays cheap).
Standard was not slower in testing — 0.75s vs 1.33s median.

Note this also affects `langchain-nimble` itself, whose `NimbleSearchTool` defaults to
`search_depth="lite"`: calling it with `include_domains=["sec.gov"]` returns off-domain
results. The problem is lite mode in the Search API, not the wrapper's ranking.

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
