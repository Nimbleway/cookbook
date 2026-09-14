# investment-screening-agent

A small **LangChain agent** for **deal sourcing / market mapping**: give it a short
investment thesis, get back a ranked shortlist of companies that fit, each with evidence,
plus the near-misses and why they were cut. It uses **Nimble** for web data and ships both
ways of using it:

| File | Pattern | Who runs the research loop |
| --- | --- | --- |
| `agent.py` / `run.py` | **A** — LangChain + Nimble Search API | the LangChain agent |
| `agent_api_v2.py` | **B** — Nimble Web Search Agent (Agent API) | Nimble |

## Pattern A — the LangChain agent drives

```
BROADEN   5+ discovery searches (funding round, product sub-category, customer segment,
          geography, directories) at search_depth="standard" → raw candidate set
NARROW    1–2 searches per candidate with full_content=True → HQ, product, customer,
          funding, investors
QUALIFY   test each candidate against the inclusion criteria pulled from the thesis
DEDUPE    one entry per company (legal suffixes and sub-product rows normalized away)
RANK      survivors by strength of evidence; everything cut goes to `excluded` with a reason
```

`screen()` runs a deterministic cleanup on the model's output: it drops placeholder rows,
personal-LinkedIn-only evidence, and sub-product rows that name another candidate as their
parent; collapses `Sixfold` / `Sixfold, Inc.`; and **moves every dropped candidate into
`excluded` with a reason** rather than deleting it silently. It also rebuilds
`ranked_shortlist` and `sources` from the survivors.

```bash
uv run python run.py "US private companies building AI software for insurance carriers"
uv run python run.py "Seed-stage LLM tools for commercial underwriting" --count 15 --json out.json
```

## Pattern B — Nimble's Web Search Agent does the research

`agent_api_v2.py` hands Nimble one dataset-building objective and follows the documented
`run → poll → result` lifecycle via the official `nimble-python` SDK, passing a flat
`output_schema` mirroring `ScreeningResult`.

```bash
uv run python agent_api_v2.py "US private companies building AI software for insurance carriers"
```

## Files

- `config.py` — `SKILL`, `GOALS`, `SOURCE_TIERS`, system-prompt builder.
- `schema.py` — `ScreeningResult`, `Candidate`, `Excluded`.
The `_clean` markers are anchored to parenthetical annotations and editorial phrases
rather than matched as bare substrings, so a real company is not mistaken for a note —
`Pointer Telocation Ltd` is a NASDAQ-listed firm, and `Acme (duplicate of Foo)` is not.
Pattern B runs the same hygiene pass over its rows.

`--effort` starts at `high`. This agent runs as `use_case="dataset_building"`, which the
API rejects below `medium` with a 422, and `medium` itself returned 0 candidates for 12
requested and 1 for 25 — so neither tier is offered on the CLI.

The Pattern A step budget scales with `--count` (`4 × count + 40`, floor 80). A fixed
budget overran on larger screens, and a `GraphRecursionError` loses the whole run rather
than returning a partial shortlist; the overrun is now reported with the limit that was
hit and how to raise it.

- `agent.py` — the LangChain agent, the `nimble_search` tool, and the `_clean` pass.
- `agent_api_v2.py` — the Pattern B driver.
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
`anthropic:claude-sonnet-5`, … Install the matching provider package.

Env overrides: `LLM_MODEL`, `SCREENING_TARGET_COUNT` (`25`), `AGENT_RECURSION_LIMIT`
(`80`), `NIMBLE_CONTENT_CHAR_CAP` (`6000`).

## Example

`examples/insurance_ai_screen.json` — a real Pattern A run for the insurance-carrier-AI
thesis: 17 confirmed companies (Gradient AI, Convr, Reserv, FurtherAI, ZestyAI, …) each
with HQ / product / funding / investors / evidence, plus 28 excluded companies with the
reason each was cut. Pattern A tends to return a tighter, more conservative list than the
Pattern B run (which targets the full 25) — the deterministic `_clean` pass errs toward
dropping anything it can't cleanly verify.

This is illustrative model output, committed to show the shape of a result and kept as it came back from the run. Treat every claim and grade in it as an example of the pipeline's output, not as verified research — re-run the agent for current findings before relying on any of it.
