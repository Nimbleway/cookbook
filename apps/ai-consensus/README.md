# AI Consensus Dashboard

Ask the same question to ChatGPT, Perplexity, and Gemini simultaneously. Use Claude to judge whether they agree.

Built with [Nimble Web Search Agents](https://nimbleway.com) — one API that talks to all three AI interfaces without managing separate keys or browser sessions.

---

## What it does

- **Browse tab** — 100 pre-loaded questions across Tech, Finance, Health, E-commerce, and Society. Each question shows the verdict from all three models and a consensus label (Strong / Moderate / Split). Filter by category, consensus type, or free-text search.
- **Live tab** — Type any question and get real-time answers from all three AIs in parallel (~60s), then Claude reads all three responses and judges consensus.

**Results from the pre-loaded dataset (100 questions):**

| Consensus | Count |
|---|---|
| Strong | 44 |
| Moderate | 48 |
| Split | 8 |

---

## Setup

### Prerequisites

- Python 3.9+
- A [Nimble API key](https://nimbleway.com) — used to fetch live responses from ChatGPT, Perplexity, and Gemini
- An [Anthropic API key](https://console.anthropic.com) — used by Claude Haiku to judge consensus

### Install

```bash
git clone https://github.com/your-org/ai-consensus
cd ai-consensus
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

```
NIMBLE_API_KEY=your_nimble_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### Run

```bash
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`. The Browse tab works immediately with the pre-loaded data — no API calls needed.

---

## Re-fetching your own data (optional)

The repo includes pre-analyzed results for all 100 questions. If you want to run fresh fetches:

**Step 1 — Fetch responses from all three AIs (~30 min, uses your Nimble key):**

```bash
python3 fetch.py
```

This makes 300 parallel calls (100 questions × 3 models) and saves raw responses to `data/responses/`. Re-runnable — skips questions already cached.

**Step 2 — Analyze with Claude Haiku (~2 min, ~$0.16 in Anthropic credits):**

```bash
python3 analyze.py
```

Reads all raw responses, sends each question through a single Claude Haiku pass, and writes structured verdicts + consensus labels to `data/analysis/`.

---

## Project structure

```
ai-consensus/
├── app.py              — Streamlit dashboard (Browse + Live tabs)
├── analyze.py          — Claude Haiku consensus analysis
├── fetch.py            — Nimble fetch script (300 parallel calls)
├── questions.json      — 100 questions with structured prompts
├── requirements.txt
├── .env.example
└── data/
    └── analysis/       — 100 pre-analyzed question files
```

---

## How consensus is judged

Each question is sent to all three models with a structured prompt that enforces a short verdict and single-sentence reason. Claude Haiku then reads all three raw responses together and returns:

- A normalized verdict for each model (5 words max)
- A consensus label: `strong` (all 3 agree), `moderate` (2 agree, 1 differs), `split` (clear disagreement)
- A one-sentence summary of what they agree or disagree on

This approach handles Gemini's tendency to ignore format instructions — Haiku extracts the conclusion from a full essay just as accurately as from a structured response.

---

## Stack

| Layer | Tool |
|---|---|
| AI fetching | Nimble Web Search Agents (`chatgpt`, `perplexity`, `gemini`) |
| Fetch orchestration | `nimble-python` SDK + `ThreadPoolExecutor` |
| Consensus analysis | Claude Haiku (`claude-haiku-4-5-20251001`) |
| Dashboard | Streamlit |
| Language | Python |
