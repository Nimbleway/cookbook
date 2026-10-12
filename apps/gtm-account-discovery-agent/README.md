# GTM Account Discovery Agent

> **Cookbook Example**: one account-discovery use case, built two ways on Nimble:
> a Search API pipeline your code controls, and a Web Search Agent run with a
> headcount gate.

Starts from an ICP and returns the companies that match every criterion, each with the
evidence behind it, plus every rejected company and the criterion it failed. Ships
configured for US legal AI software companies that are scaling a US sales team, the
example in Nimble's developer guide on building GTM agents (Use Case 3).

The ICP, in `config.py`, treats every criterion as a hard constraint:

1. Headquartered in the United States.
2. Builds AI software for legal work, sold to law firms or in-house legal teams (not a law firm or legal services provider itself).
3. 50 to 500 employees today.
4. Most recent priced round is a Series A, B or C closed on or after 2025-04-01.
5. Hiring at least one quota-carrying sales role (AE, SDR/BDR or sales leadership) in the US.

## Two patterns, one task

| | Pattern A: Search API | Pattern B: Web Search Agent |
| --- | --- | --- |
| Who does the research | Your code: broaden, extract, narrow | Nimble's Web Search Agent (`use_case="dataset_building"`, `effort="high"`) |
| LLM in your loop | Yes: Claude extracts candidates and grades evidence; your code decides pass/fail | Only in the headcount gate, to read headcount figures from the agent's claim and one search |
| Where the ICP lives | `ICP_CRITERIA` in the judge prompts, decision rules in `agent.py` | Agent `goals`, `sources` and required evidence fields in `output_schema` |
| Rejections | Every candidate, with the stage and criterion it failed | `near_misses` with `failed_criterion` |
| Output | `artifacts/legal_ai_discovery__pattern_A.json` | `artifacts/legal_ai_discovery__pattern_B.json` (run, content, trust, gate results) |

Pattern A gives you a deterministic, re-runnable pipeline with an audit trail for every
decision. Pattern B reaches into careers pages and ATS boards in one call and grades
each field it returns, which tells your code what to re-check.

### Pattern A: broaden, extract, narrow

```
BROADEN   6 lite searches, start_date = start of the funding window, max_results=10;
          one is limited to legal-tech press (include_domains)
EXTRACT   Claude pulls candidate companies out of titles and snippets, and flags any
          result that states a non-US HQ or that the company is a law firm
DEDUPE    one entry per company, keyed on domain or a normalized name (in code)
NARROW    per candidate: one firmographic search -> judge HQ, product, size, and
          extract the latest round (series, close date); stage is decided in code
          only for survivors: one hiring search on ATS boards + the company domain
          -> judge the sales role
```

The judges grade each criterion `met`, `not_met` or `unclear` with the evidence and
URL. `firmographic_decision()` and `hiring_decision()` make the call in code: anything
not explicitly `met` fails, and `unclear` is recorded as `Unverified: ...`. Funding
stage is never graded by the model: it returns the latest round's series and close
date, and `stage_check()` compares the date with `ROUND_WINDOW_START` in code. Including
the domain in the firmographic query keeps a name like "DeepIP" from resolving to
generic patent pages.

### Pattern B: goals, required evidence, and a headcount gate

`get_or_create_agent()` reuses the agent named `AGENT_NAME` if it exists, otherwise it
creates it with `agents.create(...)`. The hard constraints are written as agent
`goals`, and the output schema requires `employee_count`, `latest_round`, `sales_role`
and `sales_role_url` on every row. A rule kept only in the prompt was not enough in
testing: the agent filled rows whose own evidence said a criterion was unconfirmed.

After the run, the headcount gate checks the size criterion for every row in code,
whether or not the agent cited its figure. It runs one Search API call per row
(`{company} {domain} employees headcount team size`, lite, 5 results), Claude lists the
headcount figures in the agent's own `employee_count` claim and in those results, and
`headcount_gate()` decides:

- **pass**: every dated figure from the last 12 months is within 50 to 500
- **fail**: no dated figure, or none within the band
- **review**: recent figures disagree about the band

`verified_companies` in the artifact lists the rows that passed. Each gate entry also
records the agent's claim and the confidence `runs.result` gave it.

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
```

## Configure

| Variable | Required | Description |
| --- | --- | --- |
| `NIMBLE_API_KEY` | yes | From online.nimbleway.com → Account Settings → API Keys |
| `ANTHROPIC_API_KEY` | yes | From console.anthropic.com. Pattern A extraction and judging; Pattern B headcount gate |
| `AS_OF_DATE` | no | Date the ICP is evaluated against (default: today). `2026-10-07` reproduces the committed example's input |

In `agent.py`:

- `MODEL`: Claude model for extraction, judging and the headcount gate (default `claude-sonnet-4-6`)

In `config.py`:

- `ICP_CRITERIA`, `MIN_EMPLOYEES`, `MAX_EMPLOYEES`, `ROUND_WINDOW_START`, `TARGET_COUNT`: the ICP
- `DISCOVERY`, `LEGAL_PRESS`, `ATS`, `FIRMOGRAPHIC_SEARCH`, `HIRING_SEARCH`: the Pattern A searches
- `AGENT_NAME`, `GOALS`, `SOURCES`, `OUTPUT_SCHEMA`, `EFFORT`: the Pattern B agent
- `HEADCOUNT_SEARCH`, `HEADCOUNT_MAX_AGE_DAYS`: the headcount gate

`EFFORT` defaults to `high`. `dataset_building` needs `high` or above, and an `x-high`
run of this task was cancelled server-side after about 10 minutes with no output, so
`high` is the tested setting.

A reused agent keeps the goals, sources and schema it was created with. After editing
those in `config.py`, change `AGENT_NAME` (or update the agent) so the run uses them.

`ATS` does not include Gem. Add `jobs.gem.com` if your targets post there: on the
committed run, Pattern A missed Supio's sales role because it was on a Gem board.

## Example

From the US legal AI runs on 2026-10-07:

- `examples/legal_ai_discovery__pattern_B.json`: the Web Search Agent result as returned
  by `runs.result` (run metadata, `output.content`, full `output.trust`). 7 minutes 32
  seconds; 5 companies and 6 near-misses from 22 sources, 21 graded primary. Every row
  names an open US sales role with its careers or ATS URL; all five `employee_count`
  claims came back `low`.
- `examples/legal_ai_discovery__trust_gate.md`: the headcount checks on those five rows
  (Sandstone 32 and Billables AI unverified fail; Supio, GC AI and Eve pass) and the
  final verified list: Eve, GC AI, Supio and Ivo.
- `examples/legal_ai_discovery__pattern_A.md`: a record of the Search API pipeline run:
  6 discovery searches, 29 candidates, 15 researched, 3 qualified (Eve, GC AI, Ivo) and
  26 rejections by criterion. The extraction and judging in that run were done by hand,
  so this file is a record, not output of `agent.py`.

The two patterns missed different companies. The agent near-missed Ivo because its
careers page rendered without roles; the pipeline had found Ivo's postings on Ashby and
Lever. The pipeline rejected Supio because Gem was not in its ATS list; the agent found
the posting.

These are illustrative output, committed to show the shape of a result and kept as
they came back from the run. Treat every claim in them as an example of the pipeline's
output, not as verified research. Re-run the agent for current findings before relying
on any of it.

## Project structure

```
gtm-account-discovery-agent/
├── agent.py          # Pattern A (Search API pipeline) and Pattern B (Web Search Agent + headcount gate)
├── config.py         # ICP, searches, Web Search Agent goals/sources/schema
├── schema.py         # Structured outputs for the LLM steps (Pydantic)
├── examples/         # Committed outputs from the 2026-10-07 runs
├── README.md
├── ai-setup.md       # Setup steps for an AI coding agent
├── requirements.txt
└── .env.example
```
