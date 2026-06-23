# AI Setup Instructions — AI Consensus Dashboard

You are helping the user set up and run the AI Consensus Dashboard. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

Run each of the following checks. If any fail, install the missing dependency before continuing.

**Python 3.9+**
```bash
python3 --version
```
If missing or below 3.9: direct the user to https://python.org/downloads

**Nimble CLI**
```bash
nimble --version
```
If missing: `npm install -g @nimbleway/nimble`

**nimble-python**
```bash
python3 -c "import nimble_python; print('ok')"
```
If missing: `pip install nimble-python`

**git**
```bash
git --version
```
If missing: direct the user to https://git-scm.com

---

## Step 2: Clone the repo

Check whether the repo is already cloned locally:

```bash
ls cookbook-ai-consensus
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd cookbook-ai-consensus
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook-ai-consensus
cd cookbook-ai-consensus
```

---

## Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 4: Get API keys

Ask the user if they already have both keys, or need to get one or both.

**Nimble API key**
Get one at: https://nimbleway.com
Tell the user: used to fetch live responses from ChatGPT, Perplexity, and Gemini.

**Anthropic API key**
Get one at: https://console.anthropic.com
Tell the user: used by Claude Haiku to judge consensus across the three AI responses.

Note: neither key is needed to browse the pre-loaded dataset. If the user chooses Path A in Step 6, skip this step.

---

## Step 5: Configure environment

```bash
cp .env.example .env
```

Open `.env` and add the user's keys:
```
NIMBLE_API_KEY=their_nimble_key_here
ANTHROPIC_API_KEY=their_anthropic_key_here
```

---

## Step 6: Choose a path

Ask the user:

> "The app includes pre-loaded answers and consensus analysis for 100 questions across Tech, Finance, Health, E-commerce, and Society — you can explore the full dashboard right now with no API calls. Or I can fetch fresh responses from all three AIs and re-run the analysis, which takes about 30 minutes.
>
> Which would you prefer?
> A) Explore the pre-loaded dataset now
> B) Fetch fresh responses and run the full analysis"

**If they choose A** — skip Steps 7 and 8, go directly to Step 9 (Launch the dashboard).

**If they choose B** — continue with Step 7.

---

## Step 7: Fetch live responses

```bash
python3 fetch.py
```

This makes 300 parallel calls (100 questions × 3 models) and saves raw responses to `data/responses/`. Takes approximately 30 minutes. Re-runnable — skips questions already cached.

---

## Step 8: Run consensus analysis

```bash
python3 analyze.py
```

Sends each question through Claude Haiku, which reads all three raw responses and returns a normalized verdict, consensus label, and one-sentence summary. Takes approximately 2 minutes and costs roughly $0.16 in Anthropic credits.

---

## Step 9: Launch the dashboard

```bash
streamlit run app.py
```

The dashboard opens at http://localhost:8501

---

## Step 10: Orient the user

Walk the user through the two dashboard tabs:

1. **Browse** — the pre-loaded (or freshly analyzed) dataset. Show them how to filter by category (Tech, Finance, Health, E-commerce, Society), consensus type (Strong, Moderate, Split), or free-text search. Each question shows the verdict from all three models and a consensus label.

2. **Live** — type any question and get real-time answers from ChatGPT, Perplexity, and Gemini in parallel (~60 seconds), then Claude reads all three and judges consensus. This tab requires both API keys to be set in `.env`.

---

## Notes

- Strong consensus = all 3 models agree. Moderate = 2 agree, 1 differs. Split = clear disagreement.
- The Live tab works independently of the dataset — the user can ask any question at any time without re-running fetch or analyze.
- Re-running `fetch.py` skips already-cached questions, so it's safe to run incrementally.
