# llamaindex-tariff-desk — Nimble × LlamaIndex

![Built with Nimble + LlamaIndex](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20LlamaIndex-edc602)

A knowledge base that researches what it doesn't know, dates everything it holds, and refuses
to answer from a fact that has aged out. Built on the official
[`llama-index-tools-nimble`](https://pypi.org/project/llama-index-tools-nimble/) integration.

## The integration

```python
from llama_index.tools.nimble import NimbleAgentToolSpec

# Raise timeout: the default is 300s, shorter than a typical run.
tool = NimbleAgentToolSpec(agent_id="wsa_...", effort="high", timeout=1800)

doc = tool.run(
    "Which duty overlays are in force for this tariff line?",
    output_schema=SCHEMA,          # structured answer instead of prose
    sources={"prioritize": "official register notices"},
)

doc.text                      # the answer, plus a Sources: list
doc.metadata["confidence"]    # high | medium | low | pre_existing
doc.metadata["claims"]        # per-claim citations, keyed by JSON path
doc.metadata["run_id"]        # durable handle on the run
```

The package ships two tool specs. `NimbleToolSpec` wraps Search — one query, ranked results in
seconds. `NimbleAgentToolSpec` runs a **Nimble Web Search Agent** — it plans, reads and
cross-checks many sources, then returns one synthesized answer with per-claim citations.

Both return LlamaIndex `Document` objects, which is why this integration fits RAG unusually well:
research output *is* the framework's native currency, so it drops straight into an index.

### Four things worth knowing before you build on it

**Raise `timeout`.** It defaults to 300 seconds while the default effort takes 5–15 minutes, so an
out-of-the-box configuration fails on runs that are working perfectly. This app uses 1800.

**`run()` blocks for the whole run.** There is no start-now/collect-later split and no event stream
through the tool, so research belongs on a background thread with its state on disk. A run that
outlives its deadline is *not* lost: `NimbleAgentTimeoutError` carries the `run_id`, the run keeps
going server-side, and `recover_runs.py` collects it later.

**`output_schema` is what buys per-cell provenance.** With a schema, `claims` are keyed by JSON path
(`$.additional_duties[0].rate`) so every value has its own citation. Without one they are keyed by
prose callout and cannot be attached to a field.

**`sources.allow` is a hard whitelist.** A domain left out is a domain the agent cannot read, and it
fails silently — the gap shows up in `unverified`, not as an error. This app uses that deliberately:
the base-rate agent may only read the official schedule.

## What this cookbook builds with it

A tariff desk. Ask what the duty is on a product from a country; get an answer assembled from
cited, dated facts. If the corpus doesn't cover it, agents research it and the result joins the
index, so the next question about it is free.

Retrieval-augmented generation exists because a model's knowledge is frozen at training time. But a
vector store built once has the same disease: it relocates the staleness from the model's weights
into your index, where nobody notices. Ask a static index for a duty rate that changed in April and
it answers with March's figure, confidently, forever.

So the corpus here is **researched rather than uploaded, dated rather than timeless, and refreshed
rather than fixed** — and the retrieval path withholds anything past its shelf life instead of
serving it as current.

> **A demonstration, not a compliance reference.** The shipped corpus is a snapshot of what the
> agents found on the dates shown. Every figure carries its source and its research date; none have
> been reviewed by a customs professional. Point it at your own products before drawing conclusions.

## What it does

1. **Look up the tariff code** — describe a product in plain words; an agent returns candidate
   subheadings quoted from the official schedule, each cited. It never picks one, because
   classification is a human decision and a wrong code yields a confidently wrong duty.
2. **Research the facts** — two agents run per product-and-origin: one reads the base schedule rate,
   one establishes which duty overlays are in force.
3. **Index with provenance** — each run becomes a `Document` whose node metadata carries confidence,
   per-claim citations, source URLs and the research date.
4. **Answer, or decline** — a freshness guard withholds expired facts rather than answering from
   them, and the reply states the research date and source beside every figure.
5. **Refresh what moved** — re-research only what is past its shelf life, and log what changed.

## Three agents, because the jobs differ

| Agent | Reads | Effort | Shelf life |
|---|---|---|---|
| `tariff-schedule-rate` | official schedule (USITC), CBP | `medium` | 90 days |
| `tariff-policy-overlay` | Federal Register, USTR, White House, CBP | `high` | 7 days |
| `hts-code-candidates` | official schedule + CBP rulings | `medium` | cached per query |

The split is not tidiness. A single run asked for both the rate *and* the overlays let the schedule
lookup fail quietly into `unverified`; narrowing each task fixed it. And since base rates hold for
years while overlays move constantly, separate shelf lives mean a refresh only re-researches the
volatile half.

Base rates are keyed **origin-free** — the rate belongs to the tariff code, not the route — so
adding a new sourcing country for a code already covered costs one run, not two.

The overlay agent runs at `high` because `medium` was measurably unreliable here: it listed expired
instruments as active and, on one lane, never found the order that had terminated a duty. `high`
found it. That is the kind of thing only measurement tells you.

## Stack

- [Nimble Web Search Agents](https://nimbleway.com) — every fact in the corpus
- [`llama-index-tools-nimble`](https://pypi.org/project/llama-index-tools-nimble/) — the integration
- [LlamaIndex](https://www.llamaindex.ai/) — ingestion, index, retrieval, response synthesis
- [Anthropic Claude](https://www.anthropic.com) — question parsing and answer writing
- OpenAI `text-embedding-3-small` — embeddings only
- [Streamlit](https://streamlit.io) — UI

## Setup

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/llamaindex-tariff-desk

python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env                     # add the three API keys
./.venv/bin/python setup_agents.py       # provisions the three agents, writes their ids
./.venv/bin/python build_index.py        # indexes the shipped corpus (~10 seconds)
./.venv/bin/streamlit run app.py
```

Get a Nimble API key at [nimbleway.com](https://nimbleway.com). That sequence runs against the
cached corpus and makes no billable calls. Set `USE_LIVE=true` to research live.

## Usage

Ask `What's the duty on HTS 8507.60.00 from China?` and the answer separates the base schedule rate
from each duty overlay, with the instrument, effective date, source link and research date on each.

Don't know the code? Open the lookup and type `canvas sneakers with rubber soles`. Candidates come
back quoted from the schedule; pick one and it fills the question.

Ask `What's out of date?` and it answers from index metadata — no agent run, no cost.

The shipped corpus contains one deliberately expired fact, so the freshness guard has something to
catch: ask about `6109.10.00 from India` and watch it decline to answer from a stale overlay.

## Project structure

```
app.py                  Streamlit UI: question box, code lookup, coverage sidebar
setup_agents.py         provision the three agents once, verify with a GET
prewarm.py              research a starting corpus (concurrency-capped)
build_index.py          build or update the index; re-embeds only what changed
refresh.py              re-research what is past its shelf life, log what moved
recover_runs.py         collect runs that outlived their deadline
prefetch_lookups.py     cache code lookups so the lookup box works offline
desk/
  agents_config.py      the three agent configs — schemas, prompts, goals, sources
  research.py           run an agent, save raw, stay resumable
  classify.py           plain-language product -> candidate tariff codes
  ingest.py             run records -> Documents -> persisted index
  freshness.py          shelf-life guard and the node postprocessor
  router.py             lane retrieval, plus corpus questions answered from metadata
  normalize.py          question -> canonical route key
  delta.py              what changed between two runs of the same fact
  models.py             LLM and embedding configuration
tests/test_offline.py   31 tests, no API keys and no billable calls required
data/samples/           the shipped corpus, replayed when USE_LIVE=false
data/hts_samples/       cached code lookups for offline use
```

## Output

Every answer carries, per figure:

| Field | Description |
|---|---|
| the value | rate or duty, as the source states it |
| `researched_at` | when an agent established it |
| `confidence` | the run's own grade: `high`, `medium`, `low`, `pre_existing` |
| source URL | the document it was read from |
| `unverified` | what the agent could not confirm — shown as prominently as the answer |
| `confirmed_absent` | overlays checked and ruled out, kept distinct from "couldn't check" |

That last pair matters more than it looks. **`confidence` grades what was claimed, not what was
covered** — a run returns `high` while leaving facts unverified. Showing gaps beside answers is the
difference between a demo and a trap.

## Going further

- **Swap the domain.** Nothing here is tariff-specific except the three agent configs in
  `desk/agents_config.py`. The pattern — research into `Document`s, index with provenance, guard on
  shelf life, refresh the volatile half — fits any corpus whose facts expire at different rates.
- **Tune the shelf lives.** `TTL_DAYS` in `desk/agents_config.py`. Shorter means fresher and more
  expensive; the point is that the number is explicit rather than implied.
- **Schedule the refresh.** `refresh.py` is idempotent and concurrency-capped, so cron works.
- **Add a fact class.** A third `kind` with its own agent, schema and shelf life is about thirty
  lines, and the sidebar picks it up automatically.

## Requirements

Python 3.10+ (required by `llama-index-tools-nimble`). Three keys: Nimble, Anthropic, OpenAI. A full
corpus build is two agent runs per product-and-origin, a few minutes each — the shipped corpus means
you don't need to pay for one to see the app work.
