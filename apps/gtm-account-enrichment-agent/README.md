# GTM Account Enrichment Agent

> **Cookbook Example**: one account-enrichment use case, built two ways on Nimble:
> a Search API pipeline your code controls, and a Web Search Agent run.

Turns a CRM account (a company name and a domain) into a current company profile:
products, customers, headquarters, headcount, funding, leadership, hiring and recent
announcements, with a source behind every value. Sources often disagree on these
fields, so the profile keeps the conflicting values instead of hiding them. Ships
configured for `eve.legal`, the example in Nimble's developer guide on building GTM
agents (Use Case 1).

## Two patterns, one task

| | Pattern A: Search API | Pattern B: Web Search Agent |
| --- | --- | --- |
| Who does the research | Your code: five `nimble.search` passes (identity, funding, leadership, hiring, signals), each with its own sources and depth | Nimble's Web Search Agent (`use_case="enrichment"`, `effort="high"`) |
| LLM in your loop | Yes: Claude (`langchain-anthropic`) extracts the evidence into a fixed profile | No: run, poll and fetch in Python |
| Conflicting sources | Kept in `conflicts` with every value, URL and date; `resolve_conflicts()` applies your precedence rules | Resolved by the agent and recorded in `data_conflicts` |
| Citations | Result URLs in `field_sources` and `evidence` | Per-field `trust.claims` (JSON path, confidence, citations) |
| Output | `artifacts/eve_legal_enrichment__pattern_A.json` | `artifacts/eve_legal_enrichment__pattern_B.json` (run, content, trust) |

Pattern A fits when the enrichment rules belong to your system: which fields to fill,
which source wins, how fresh a posting must be. Pattern B fits when you want the
finished profile with the research and conflict resolution done for you.

### Pattern A: how the passes are scoped

| Pass | Scope | Depth |
| --- | --- | --- |
| identity | `include_domains=[DOMAIN]` (first-party pages only) | standard, 5 |
| funding | open web | standard, 6 |
| leadership | open web | standard, 5 |
| hiring | `include_domains=ATS` (Greenhouse, Ashby, Lever) | lite, 20 |
| signals | `time_range="year"` | lite, 8 |

With `search_depth="standard"` the result text can come back in `description` while
`content` is empty, so the code reads `r.content or r.description`.

The extraction step does not choose between disagreeing sources. It leaves the field
null and lists every value in `conflicts`. `resolve_conflicts()` then fills the field:
for `employee_count`, `customer_count` and `open_roles_summary` the most recent dated
value wins; for every other field the most trusted source tier wins (first-party, then
press, then other sites, then data aggregators). Both rules are in `config.py`.

### Pattern B: input_data and trust

The enrichment use case takes `input_data` shaped like the `output_schema`. The agent
researches only the null fields, returns your input values marked `pre_existing`, and
attaches a claim per JSON path with a confidence grade and citations. The input tells
the agent to resolve the company from its domain, prefer first-party pages, treat data
aggregators as secondary, and log disagreements in `data_conflicts`.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add NIMBLE_API_KEY and ANTHROPIC_API_KEY
python agent.py        # runs Pattern A, then Pattern B
```

To run one pattern only:

```bash
python agent.py --pattern A
python agent.py --pattern B
python agent.py --pattern B --effort medium
```

## Configure

| Variable | Required | Description |
| --- | --- | --- |
| `NIMBLE_API_KEY` | yes | From online.nimbleway.com → Account Settings → API Keys |
| `ANTHROPIC_API_KEY` | Pattern A | From console.anthropic.com |

In `agent.py`:

- `MODEL`: Claude model for the Pattern A extraction step (default `claude-sonnet-4-6`)

In `config.py`:

- `COMPANY_NAME`, `DOMAIN`, `PASSES`: the account and the Pattern A searches
- `ATS`: job boards the hiring pass is scoped to
- `SOURCE_TIERS`, `FRESHEST_WINS`: your precedence rules for conflicts
- `AGENT_NAME`, `EFFORT`, `AGENT_INPUT`, `INPUT_DATA`, `PROFILE_OUTPUT_SCHEMA`: the Pattern B run (`EFFORT`: `low` | `medium` | `high` | `x-high` | `max`, default `high`)

To enrich a different account, change `COMPANY_NAME`, `DOMAIN`, the query strings in
`PASSES` and the domain named in `AGENT_INPUT`. Pattern B reuses the agent named
`AGENT_NAME` on later runs.

If the hiring pass returns pages outside the ATS hosts, switch it to
`search_depth="standard"`, which applies `include_domains` strictly.

## Example

From the eve.legal runs on 2026-10-07:

- `examples/eve_legal_enrichment__pattern_B.json`: the Web Search Agent result as
  returned by `runs.result` (run metadata, `output.content`, full `output.trust`). The
  run took 2 minutes 49 seconds, cited nine sources (five first-party) and logged four
  conflicts (headquarters, headcount, customer count, founded year) with a resolution
  for each.
- `examples/eve_legal_enrichment__pattern_A.md`: a record of the Search API run on the
  same day: the queries, what each returned, and the three conflicts found
  (headquarters, headcount from 1-10 to 376, customer count). The extraction in that run
  was done by hand, so this file is a record, not output of `agent.py`.

These are illustrative output, committed to show the shape of a result and kept as
they came back from the run. Treat every claim in them as an example of the pipeline's
output, not as verified research. Re-run the agent for current findings before relying
on any of it.

## Project structure

```
gtm-account-enrichment-agent/
├── agent.py          # Pattern A (Search API + Claude extraction) and Pattern B (Web Search Agent)
├── config.py         # Account, search passes, precedence rules, Web Search Agent parameters
├── schema.py         # Pattern A profile schema (Pydantic)
├── examples/         # Committed outputs from the 2026-10-07 runs
├── README.md
├── ai-setup.md       # Setup steps for an AI coding agent
├── requirements.txt
└── .env.example
```
