# litellm-claim-verifier — Claim Verifier

Hand it a document. Get back every factual claim it contains, with a verdict, the
source that decides it, and what the check cost. Powered by
[Nimble](https://nimbleway.com) search through [LiteLLM](https://github.com/BerriAI/litellm).

![Built with Nimble + LiteLLM](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20LiteLLM-edc602)

Nimble is a first-class search provider in LiteLLM (`nimble/search`), so one SDK routes
a cheap model for claim extraction, live web search for evidence, and a strong model for
judgment — three vendors behind one interface and one cost ledger.

## What it does

1. **Extract** — a cheap model reads the document and pulls out every checkable factual
   claim, setting opinions and predictions aside
2. **Retrieve** — each claim gets its own Nimble search, run concurrently; full-page
   markdown is cut to a claim-relevant window before any model reads it
3. **Adjudicate** — a strong model rules on each claim against the retrieved sources:
   supported, contradicted, or unverifiable, with the deciding URL and a correction
4. **Report** — the document annotated claim by claim, plus search spend and token spend
   accounted separately

## Stack

- [Nimble Search](https://nimbleway.com) — live web results with structured content
- [LiteLLM](https://github.com/BerriAI/litellm) — one interface for the models and the
  search provider; optionally a proxy with a dashboard
- `claude-haiku-4-5` — claim extraction (mechanical, high volume)
- `claude-opus-5` — adjudication (judgment, needs to reason about partial evidence)
- Python 3.10–3.14

## Setup

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/litellm-claim-verifier

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # add NIMBLE_API_KEY and ANTHROPIC_API_KEY
python verify.py samples/sports_draft.md
```

Get a Nimble API key at [nimbleway.com](https://nimbleway.com); an Anthropic key at
[console.anthropic.com](https://console.anthropic.com).

Python 3.10 is the floor — LiteLLM requires `>=3.10,<3.15`, and the stock `python3` on
macOS is older than that.

## Usage

```bash
python verify.py samples/sports_draft.md    # verify a document
python verify.py doc.md --no-cache          # ignore cached per-claim results
python verify.py doc.md --record            # save this run for replay
USE_LIVE=false python verify.py             # replay the recorded run, zero API calls
```

Writes `report.html` (annotated document, verdicts, cost table) and `report.md`.

`--record` saves a run to `data/sample_run.json`; `USE_LIVE=false` then replays it with
no API calls at all, which makes it the safe way to demo or record. `REPLAY_DELAY` sets
the pacing in seconds per claim, and `REPLAY_DELAY=0` disables the animation.

## Gateway mode

The app needs no proxy — unset, it calls Anthropic and Nimble directly. Set
`LITELLM_BASE_URL` and every call routes through a LiteLLM proxy instead, so all three
vendors appear on one dashboard with one credential.

```bash
litellm --config config.yaml               # proxy on :4000, dashboard at /ui

LITELLM_BASE_URL=http://127.0.0.1:4000 \
LITELLM_MASTER_KEY=sk-your-master-key \
  python verify.py samples/sports_draft.md
```

Models resolve as `litellm_proxy/claim-extractor` and `litellm_proxy/claim-adjudicator`;
search goes to `POST /v1/search/nimble-search`. Both names are defined in `config.yaml`,
so which model does which job stays the proxy's decision. Per-call search cost is read
from the proxy's `x-litellm-response-cost` header, so the terminal total and the
dashboard total agree.

`./demo.sh` prints the architecture; `./demo.sh run` runs a verification through the
gateway.

## What a run costs

Measured on `samples/sports_draft.md` — 333 words, 15 claims, 28 seconds:

| Component | Calls | Spend |
|---|---:|---:|
| Nimble search | 15 | $0.0750 |
| Extraction (Haiku) | 1 | $0.0074 |
| Adjudication (Opus) | 15 | $0.2733 |
| **Total** | | **$0.3557** |

About $0.024 per verified claim. Token spend runs roughly 4× search spend — retrieval is
the cheap input and judgment is what costs, which makes grounding generously the
economical choice rather than the expensive one.

## Design notes

**Truncation is load-bearing.** LiteLLM maps `snippet = content or description`, and
Nimble returns full page markdown — one Wikipedia result measured 262,834 characters,
roughly 65k tokens. `retrieve.py` cuts each result to a 1,500-char window chosen by
rarity-weighted keyword scoring, after stripping nav menus and tables. Without it, token
cost would run about 50× the search cost.

**`unverifiable` is a real verdict.** A verifier that always reaches a conclusion is
guessing, and a guess wearing a citation is worse than an abstention.

**The cheap/strong split is the point.** Extraction is mechanical and runs once per
document; adjudication needs to weigh partial evidence and runs once per claim. Routing
them to different models is a change to one string, which is only true because both go
through the same interface.

**Swapping providers.** `retrieve.py` is the only module that names a provider, and
`search_provider` is a string — pointing the app at a different search backend is a
one-line change that nothing downstream notices.

## Project structure

| File | Purpose |
|---|---|
| `verify.py` | CLI and orchestration, per-claim caching, cost totals |
| `extract.py` | claim extraction |
| `retrieve.py` | Nimble search, markdown cleaning, window selection |
| `adjudicate.py` | verdicts |
| `report.py` | annotated HTML + Markdown reports |
| `progress.py` | live per-claim progress board |
| `gateway.py` | optional routing through a LiteLLM proxy |
| `schemas.py` | pydantic contracts between stages |
| `config.yaml` | LiteLLM proxy config for gateway deployments |
| `demo.sh` | architecture printout and a one-command run |
| `samples/` | test fixtures with deliberate errors seeded, plus an answer key |

## Going further

- **Different document type** — contracts, research summaries, press releases. Extraction
  prompts live in `extract.py`; nothing else needs to know.
- **Different search provider** — change `SEARCH_PROVIDER` in `retrieve.py`.
- **Cheaper judgment** — point `claim-adjudicator` at a smaller model in `config.yaml` and
  compare verdict quality against the answer key in `samples/`.
- **Run it in CI** — the Markdown report and a non-zero exit on contradictions turn this
  into a documentation check.
