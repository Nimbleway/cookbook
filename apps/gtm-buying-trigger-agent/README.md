# GTM Buying Trigger Agent

> **Cookbook Example**: one buying-trigger monitoring use case, built two ways on
> Nimble: a Search API pipeline your code controls, and a Web Search Agent run.

Watches a list of accounts for recent company events that change their go-to-market
priorities, budget or team (funding rounds, executive hires, new offices or markets,
launches, partnerships, acquisitions, large customer wins) and returns, per account,
each event with its date, type, strength, reason and source, plus an outreach angle a
rep can open with. Ships configured for five B2B software accounts (Cato Networks,
Mark43, Veylo, BlueVoyant, commercetools) and a 30-day window, the example in Nimble's
developer guide on building GTM agents (Use Case 2).

## Two patterns, one task

| | Pattern A: Search API | Pattern B: Web Search Agent |
| --- | --- | --- |
| Who does the research | Your code: per account, three news searches, one per trigger family | Nimble's Web Search Agent (`use_case="research"`, `effort="high"`) |
| LLM in your loop | Yes: Claude (`langchain-anthropic`) turns each account's results into triggers | No: run, poll and fetch in Python |
| Recency | `start_date` = window start on every search; the prompt dates each event | Window stated in the run input; the agent dates each event |
| Output shape | `window_start`, `window_end`, `accounts[]` (one entry per account, `triggers[]` nested inside), `excluded_events[]` | Same, plus the per-claim `trust` block |
| Output | `artifacts/buying_triggers__pattern_A.json` | `artifacts/buying_triggers__pattern_B.json` (run, content, trust) |

Pattern A fits when your system decides which queries to run and how to classify and
rank an event. Pattern B fits when you want a finished per-account trigger brief, with
the research, dating and citation done by Nimble.

### Pattern A: searches

For each account in `WATCHLIST`:

```
{name} {descriptor} funding round acquisition
{name} {descriptor} appoints executive hire chief
{name} {descriptor} launches expansion partnership
```

Every search uses `focus="news"`, `search_depth="lite"`, `max_results=8` and
`start_date` set to the window start: 15 searches for five accounts. The code keeps each
result's title, URL, text (`r.content or r.description`), publish date
(`additional_data.publish_date` or `publish_date_raw`) and source. Claude then turns
that account's results into triggers, dated by the event rather than by the article,
with one trigger per event however many outlets covered it.

### Pattern B: the agent

`get_or_create_agent()` reuses the agent named `AGENT_NAME` if it exists. Otherwise it
calls `agents.create(...)` with `GOALS`, `SOURCES` and `OUTPUT_SCHEMA`. If the API does
not accept the `goals` parameter, it creates the agent with the goals in the skill text
(`"General research\n\nGoals:\n- ..."`), the form the API stores them in. The run input
is built by `config.run_prompt()` from the watchlist, window and `SELLER_CONTEXT`.

The goals ask the agent to date events by when they happened, resolve each account by
its domain, return one entry per account with its triggers nested inside, cite the
company's own newsroom when one exists, return one trigger per event, write the
outreach angle only from that account's triggers, and return `trigger_count` 0 rather
than pad an account with weak events.

### post_process() (both patterns)

`post_process()` guarantees the report shape the next step (a CRM write, a Slack alert)
can rely on:

1. One entry per watchlist account, in watchlist order; entries for other accounts are dropped.
2. Every trigger's `event_date` inside the window; anything else goes to `excluded_events`.
3. One trigger per event within an account: the same headline, or the same type and date
   with the same source or mostly the same names, counts once.
4. `trigger_count` matches the triggers, and `strongest_trigger` names one of them
   (strength first, then the most recent event, when it is not already set).
5. `outreach_angle` is dropped when an event it may cite was moved out of the window.

Pattern B saves the checked report as `output.content` and the agent's original as
`output.raw_content`. `remap_trust_claims()` re-points each trust claim's path at the same
item in the checked report (`output.trust`) and drops claims about removed or recomputed
values; the original trust block stays in `output.raw_trust`.

On the committed Pattern B example it changes nothing: 10 triggers in, 10 out.

## What each pattern returns

From the runs on 2026-10-12 (same watchlist, window 2026-09-12 to 2026-10-12):

- **Pattern A** returned 120 article-level results from 15 searches in seconds. Every
  trigger in the agent's output appears in those results, often several times: the
  Cato Networks CRO appointment came back from five outlets. The results also carry
  market roundups, job listings, index pages and new coverage of older events, which
  the extraction step and `post_process()` sort out. Your code owns how each event is
  classified and ranked.
- **Pattern B** returned one entry per account in 4 minutes 31 seconds: 10 triggers,
  each dated by the event, typed, graded and cited to the company's own newsroom (20
  primary sources, all official), 25 excluded events with their dates and reasons, and
  an outreach angle per account.

| Account | Triggers (agent) | Strongest trigger |
| --- | --- | --- |
| Cato Networks | 1 | New CRO, Chad Gardner (2026-10-07) |
| Mark43 | 3 | New CMO, Alison Durant (2026-10-01); also the ForceMetrics acquisition and the San Diego County Sheriff go-live |
| Veylo | 3 | Funding round and new Executive Chairman (2026-10-01); also a new CMO and CGO, and the rebrand from BlueGenAI |
| BlueVoyant | 2 | New CRO, John Hultman (2026-10-07); also a Microsoft Defender XDR ISOC deployment service |
| commercetools | 1 | New CMO, Katy Hiller (2026-10-06) |

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add NIMBLE_API_KEY and ANTHROPIC_API_KEY
python agent.py        # runs Pattern A, then Pattern B
```

To run one pattern only, or only `post_process()` on a saved Pattern B result:

```bash
python agent.py --pattern A
python agent.py --pattern B
python agent.py --post-process examples/buying_triggers__pattern_B.json
```

## Configure

| Variable | Required | Description |
| --- | --- | --- |
| `NIMBLE_API_KEY` | yes | From online.nimbleway.com → Account Settings → API Keys |
| `ANTHROPIC_API_KEY` | Pattern A | From console.anthropic.com |
| `AS_OF_DATE` | no | Window end date (default: today). `2026-10-12` reproduces the committed example's window (2026-09-12 to 2026-10-12) and run input |

In `agent.py`:

- `MODEL`: Claude model for the Pattern A extraction step (default `claude-sonnet-4-6`)

In `config.py`:

- `WATCHLIST`: accounts, each with `name`, `domain`, `descriptor` and an optional `prompt_note`
- `WINDOW_DAYS`: monitoring window length (default 30)
- `SELLER_CONTEXT`, `TRIGGER_DEFINITION`, `TRIGGER_TYPES`, `STRENGTHS`: what counts as a trigger
- `QUERY_TEMPLATES`, `SEARCH_PARAMS`: the Pattern A searches
- `AGENT_NAME`, `GOALS`, `SOURCES`, `OUTPUT_SCHEMA`, `EFFORT`: the Pattern B agent

A reused agent keeps the goals, sources and schema it was created with. After editing
those in `config.py`, change `AGENT_NAME` (or update the agent) so the run uses them.

## Notes

- The 2026-10-12 agent was configured through the Nimble MCP server, which stores goals
  inside the skill text. `agent.py` sends `goals=GOALS` to `agents.create` first and
  falls back to the skill text on a 400 or 422.
- The run was started with the agent id (`runs.create`); the agent's default effort is
  `high`.
- The 2026-10-12 Search API results were classified by hand for the record in
  `examples/`; there is no Pattern A model output from that day.

## Example

From the runs on 2026-10-12:

- `examples/buying_triggers__pattern_B.json`: the Web Search Agent result as returned by
  `runs.result` (run metadata including the exact input, `output.content`, full
  `output.trust`).
- `examples/buying_triggers__pattern_A.md`: a record of the Search API run: queries,
  parameters and the events each account's results contained.

These are illustrative output, committed to show the shape of a result and kept as
they came back from the run. Treat every claim in them as an example of the pipeline's
output, not as verified research. Re-run the agent for current findings before relying
on any of it.

## Project structure

```
gtm-buying-trigger-agent/
├── agent.py          # Pattern A (Search API + Claude), Pattern B (Web Search Agent), post_process()
├── config.py         # Watchlist, window, trigger definition, searches, Web Search Agent definition
├── schema.py         # Pattern A extraction schema (Pydantic)
├── examples/         # Committed outputs from the 2026-10-12 runs
├── README.md
├── ai-setup.md       # Setup steps for an AI coding agent
├── requirements.txt
└── .env.example
```
