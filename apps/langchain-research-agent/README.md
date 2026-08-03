# langchain-research-agent — Nimble × LangChain

Give any LangChain agent live web data in three lines, using the official `langchain-nimble`
integration.

## The integration

```python
from langchain.agents import create_agent
from langchain_nimble import NimbleToolkit

toolkit = NimbleToolkit(
    nimble_api_key=KEY,
    include_search=True,              # fast web search
    include_web_search_agents=True,   # deep, cited research runs
)
agent = create_agent(model=model, tools=toolkit.get_tools(), system_prompt=POLICY)
```

That's it. `NimbleToolkit` is the single entry point — flip a flag and the corresponding Nimble tools
appear in your agent's toolset, with LangChain handling the tool-calling loop.

### What each flag gives your agent

| flag | tools the model can call | default |
|---|---|---|
| `include_search` | `nimble_search` — ranked real-time results | ✅ on |
| `include_extract` | `nimble_extract` — clean markdown from any URL | ✅ on |
| `include_web_search_agents` | `nimble_web_search_agent_run_start` / `_run_status` / `_run_result`, plus create and list | off |
| `include_extract_templates` | structured scraping for known page types | off |
| `include_crawl`, `include_map` | multi-page crawl, URL discovery | off |

Install: `pip install "langchain-nimble>=4.0.0"` — **requires Python 3.10+**.

`nimble_api_key` is a required field on the toolkit; it is not read from the environment implicitly.

## What this cookbook builds with it

A gap filler. Point it at a CSV with holes; it returns the file filled in, with the source URL,
confidence grade and which Nimble tool answered beside every value.

It demonstrates what an integration is actually for: **letting the model choose the right Nimble tool
for each job.**

| the model reaches for | when | cost |
|---|---|---|
| nothing | the cell already has a value | free |
| `nimble_search` | a fact confirmable in one lookup — a website, a head office | seconds |
| a Web Search Agent run | anything needing multi-source, cited research | minutes |

Cells that can't be confirmed are left blank rather than guessed.

## Setup

**Python 3.10 or newer** — macOS ships 3.9, which fails with a misleading
`No matching distribution found`.

```bash
python3.12 -m venv .venv          # substitute your 3.10+ interpreter
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # NIMBLE_API_KEY + ANTHROPIC_API_KEY
```

Nimble API key: https://online.nimbleway.com/account-settings/api-keys

## Usage

Run **Setup** above first — these commands use the venv's interpreter directly, so no `activate` is
needed, but `.venv` has to exist.

```bash
.venv/bin/python fill_gaps.py                    # cached demo, no keys needed
USE_LIVE=true .venv/bin/python fill_gaps.py      # live
USE_LIVE=true .venv/bin/python fill_gaps.py --input my.csv --key-column company
```

A live run prints the model's tool choices as they happen:

```
Ramp       headquarters     tier 2 search    22.7s  unverified
Vanta      employee_count   tier 3 agent    235.0s  high
```

Flags: `--governed employee_count,funding_stage,total_raised` forces those columns through a cited
research run; `--chunk 10` sets companies per run.

## Output

`data/filled.csv` — your columns unchanged, plus `<col>__source`, `<col>__confidence`,
`<col>__tier` for each.

```
company   website     headquarters        employee_count  funding_stage  total_raised
Deel      deel.com    San Francisco CA    5,001-10,000    Series E       nearly $1.3 billion
```

`employee_count` reads `tier=agent confidence=high source=linkedin.com/company/deel`, while
`website` reads `tier=file confidence=given` because you supplied it.

## Using the integration in your own agent

Three things worth knowing when you adapt this:

**Search and Web Search Agents are different products.** `nimble_search` returns results in seconds.
A Web Search Agent run takes minutes and returns a schema-conforming answer with per-claim citations
and confidence. Give your agent both and let it choose; don't treat them as interchangeable.

**A Web Search Agent's `output_schema` can be overridden per run.** That is how this app makes your
CSV header the agent's schema without creating a new agent per file. `output_schema` is required when
`use_case` is `enrichment`.

**The source allow-list applies to Web Search Agent runs, not to `nimble_search`** — the search tool
takes no domain filter. If provenance matters for a field, route it through a run. This app enforces
that in code via `--governed`, because a system prompt asking the model to avoid certain fields was
not reliably obeyed.

## Project structure

```
fill_gaps.py                 the whole app
data/sample_accounts.csv     6 companies, 23 blanks
data/sample_filled.json      cached result of a real run — powers the no-key demo
data/filled.csv              example output with provenance columns
data/runs/                   raw agent responses, saved before any transform
data/run_state.json          chunk -> run id, so an interrupted job resumes
```

## Reference

- `langchain-nimble` on GitHub: https://github.com/Nimbleway/langchain-nimble
- Nimble Web Search Agents: https://docs.nimbleway.com
