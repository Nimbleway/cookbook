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

The `nimble_search` tool: `search_depth="standard"` to find the right pages,
`full_content=True` (≤4 results) to read the pages it cites — full-content results are
**sliced to the query-relevant windows** of the page, not truncated to the first N
characters.

## Output shape

Both patterns return the same shape, so a Pattern B result parses with
`schema.DiligenceProfile`: `scorecard` stays nested, and `confidence_by_dimension` is a
list of `{dimension, grade}` rather than a mapping (the Agent API rejects open objects in
an `output_schema`, so a `Dict[str, str]` cannot be expressed there). `agent_api_v2.py`
also repeats `required` on every nested object and restates the field descriptions —
without them the API returns an empty `confidence_by_dimension`, leadership entries with
no `background`, and `sources` as bare hostnames. The CLI prints an `incomplete output`
block for anything still missing.

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
that is deliberate: as of `langchain-nimble` 4.0.0 its `NimbleSearchTool` does not expose
`full_content`, which this agent needs to read primary documents.

### Why every search runs at `search_depth="standard"`

`search_depth="lite"` **does not honour `include_domains`** — `include_domains=["sec.gov"]`
comes back with YouTube videos and vendor marketing pages. The source allow-list is what
makes these agents cite primary sources, so lite is never sent to the API: `nimble_search`
accepts `search_depth="lite"` as a *scan* hint, issues the request at standard depth, and
trims the result to `title`/`url`/`description` locally, which keeps a scan cheap.
Standard was not slower in testing.

## Setup & run

```bash
uv sync                    # or: pip install -r requirements.txt
cp .env.example .env       # NIMBLE_API_KEY + an LLM_MODEL and its key
```

`LLM_MODEL` is provider-agnostic via `init_chat_model` — `openai:gpt-5.1` (default),
`anthropic:claude-sonnet-5`, `google_genai:gemini-2.5-pro`, … Install the matching
provider package (`langchain-openai` is bundled).

Temperature is only sent when `LLM_TEMPERATURE` is set. `gpt-5.x`, the o-series and
`claude-sonnet-5` all reject the parameter, so pinning it by model name goes stale
with every release.

Env overrides: `LLM_MODEL`, `LLM_TEMPERATURE` (unset — see above),
`NIMBLE_CONTENT_CHAR_CAP` (`8000`), `AGENT_RECURSION_LIMIT` (`48`).

## Example

`examples/ramp_profile.json` — a real Pattern A run for `"Ramp"`, driven by
`anthropic:claude-sonnet-5`: business model, product inventory, leadership, a terse
funding summary, partnerships, competitors, and a scorecard with a confidence grade for
each of the seven dimensions. All 23 sources are full URLs.

This is illustrative model output, committed to show the shape of a result and kept as
it came back from the run. Treat every claim and grade in it as an example of the
pipeline's output, not as verified research — re-run the agent for current findings
before relying on any of it.
