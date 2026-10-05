# pricing-comparison-agent

A **LangChain agent** that compares competitor pricing for a specific buyer profile,
using **Nimble** for web data. Give it a list of vendors and a buyer profile (hosts, GB
ingested, seats, events), and it extracts each vendor's published pricing, normalizes the
different billing units onto one basis, and computes a modeled annual cost, or routes the
vendor to a "quote required" list when the page does not publish enough to price it.

| File | Pattern | Who runs the research loop |
| --- | --- | --- |
| `agent.py` / `run.py` | **A** - LangChain + Nimble Search API | the LangChain agent |
| `agent_api_v2.py` | **B** - Nimble Web Search Agent (Agent API) | Nimble |

Both patterns produce the same `VendorPricing` shape, so the cost model and artifact
writer downstream are identical either way. Only the retrieval step changes.

## Why the arithmetic is not the LLM's job

An LLM asked to just "compute the annual cost" will happily produce a plausible number
even when a vendor's page does not state an overage rate. `pricing_model.py` does the
arithmetic in plain Python instead, dispatching on an explicit `tier_type` field
(`flat_all_inclusive`, `base_plus_overage`, `pure_per_unit`, `unpublished`) that the
extraction step must set per tier. `unpublished` always routes to `quote_required`; it is
never treated as an implicit all-inclusive flat fee just because some fields came back
null. This is the difference between "the model didn't find an overage rate" and "the
model guessed there wasn't one."

## Run

```bash
uv sync
cp .env.example .env       # NIMBLE_API_KEY + an LLM_MODEL and its key

uv run python run.py "Datadog,New Relic,Grafana Labs" --hosts 200 --gb-ingested 2000
uv run python agent_api_v2.py "Datadog,New Relic,Grafana Labs" --hosts 200 --gb-ingested 2000
```

Writes three artifacts to `./output` (or `--out-dir`): `comparison_table.md`,
`cost_ranking.md`, `quote_required.md`, plus a timestamped JSON snapshot. Pass
`--diff-against <snapshot.json>` (or just re-run; it auto-picks the previous snapshot in
the same output directory) to see what changed since a prior run, this is the "run it on
a schedule" path, not required for a single demo run.

Also writes `dashboard.html` to the same directory and opens it in the default
browser (skip with `--no-dashboard`): a ranked cost bar per vendor with the tier and
assumptions on hover, the quote-required list, and the full extracted pricing table.

Buyer profile flags: `--hosts`, `--gb-ingested`, `--seats`, `--events`, mapping to the
`billing_unit` values a vendor's tiers can be extracted against. Supply at least one.

`LLM_MODEL` is provider-agnostic via `init_chat_model`: `openai:gpt-5.1` (default),
`anthropic:claude-sonnet-5`, `google_genai:gemini-2.5-pro`, ... Install the matching
provider package (`langchain-openai` is bundled).

## Files

- `schema.py` - `PriceTier` (with the `tier_type` discriminator), `VendorPricing`,
  `CostEstimate`, `QuoteRequired`, `PricingComparisonResult`.
- `pricing_model.py` - the deterministic cost model. No LLM calls.
- `config.py` - the extraction agent's role and system-prompt builder.
- `agent.py` - the Pattern A LangChain agent and its `nimble_search` tool. Full-content
  results are sliced to the query-relevant windows of the page, not head-truncated.
- `agent_api_v2.py` - the Pattern B driver (`nimble.agents.run` -> poll -> result).
- `run.py` - Pattern A CLI and the shared artifact writer.
- `dashboard.py` - writes the self-contained `dashboard.html` artifact both entrypoints
  open after a run.

## Example

`examples/` holds real runs comparing Datadog, New Relic, and Grafana Labs for a
200-host, 2 TB/month ingest buyer, one via Pattern A (`pattern_a_result.json`,
`comparison_table.md`, ...) and one via Pattern B (`pattern_b/`). Both find Datadog's
real per-host Pro tier ($15/host, $36,000/yr for this buyer) and New Relic's free/usage
tier ($0.40/GB over 100GB included, $9,120/yr), with Grafana Labs correctly routed to
quote-required since its usage-based tiers are not fully published.

One correctness note worth knowing if you extend this: Datadog also has a free
Infrastructure tier capped at 5 hosts. An earlier version of the cost model treated a
capped free tier as unconditionally free and returned $0/yr for a 200-host buyer, since
`flat_all_inclusive` only checked whether a base fee existed, not whether the buyer's
quantity exceeded the tier's cap. `PriceTier.included_quantity` now doubles as that cap
for `flat_all_inclusive` tiers, and the cost model treats a tier as inapplicable, not
free, once the buyer's quantity exceeds it.
