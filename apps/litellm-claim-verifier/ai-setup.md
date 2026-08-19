You are helping the user set up and run the Claim Verifier — a tool that takes a document,
checks every factual claim in it against live web sources, and returns an annotated report
with a verdict and citation per claim. Follow these steps in order. Check each prerequisite
before proceeding. Tell the user what you're doing at each step.

---

## Step 1 — Check prerequisites

**Python 3.10 to 3.14.** LiteLLM requires `>=3.10,<3.15`.

```bash
python3 --version
```

If this reports 3.9 or older — common on macOS, where the system `python3` is 3.9 — look
for a newer one before continuing. Run this exactly as written; a bare `ls` with a glob
fails on zsh when one path does not match:

```bash
for v in 3.14 3.13 3.12 3.11 3.10; do command -v python$v; done
```

Use the highest version it prints in Step 3, substituting it for `python3`. If it prints
nothing, tell the user to install Python 3.12 (`brew install python@3.12` on macOS) and
stop here.

**git.** `git --version`

---

## Step 2 — Clone the repo

If the user already has the monorepo, pull instead of cloning.

```bash
if [ -d cookbook ]; then
  cd cookbook && git pull
else
  git clone https://github.com/Nimbleway/cookbook && cd cookbook
fi
cd apps/litellm-claim-verifier
```

---

## Step 3 — Install dependencies

Use the Python binary confirmed in Step 1.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Takes 1–2 minutes; LiteLLM is a large install. Confirm it worked:

```bash
python -c "from importlib.metadata import version; print('litellm', version('litellm'))"
python -c "import litellm; from litellm.types.utils import SearchProviders; print('nimble registered:', 'nimble' in [p.value for p in SearchProviders])"
```

The second command must print `nimble registered: True`. If it prints `False`, the
installed LiteLLM predates the Nimble search provider — check that `pip install` used this
folder's `requirements.txt`.

---

## Step 4 — Get API keys

Two keys are needed. Tell the user what each is for:

- **`NIMBLE_API_KEY`** — from [nimbleway.com](https://nimbleway.com), under Settings → API
  keys. This is what fetches live web results, one search per claim, at $0.005 per search.
- **`ANTHROPIC_API_KEY`** — from
  [console.anthropic.com](https://console.anthropic.com). Two models are used: a cheap one
  to pull claims out of the document, and a strong one to judge them against the evidence.

---

## Step 5 — Configure environment

```bash
cp .env.example .env
```

Then edit `.env` so these two lines have real values:

```
NIMBLE_API_KEY=...
ANTHROPIC_API_KEY=...
```

Leave everything else commented out. The gateway settings at the bottom are optional and
covered in Step 7.

---

## Step 6 — Run it

```bash
python verify.py samples/sports_draft.md
```

Expected: about 30 seconds. The document is 333 words and yields roughly 15 claims. Claims
appear as a list and each flips to its verdict as it resolves — `supported`,
`contradicted`, or `unverifiable`.

A run on this sample costs about **$0.36**: 15 searches plus 15 judgment calls. Tell the
user this before running it.

It finishes by writing `report.html` and `report.md`. Open the HTML report:

```bash
open report.html    # macOS; use xdg-open on Linux
```

`samples/sports_draft.md` has four deliberate factual errors planted in it, so several
claims should come back `contradicted`. `samples/sports_draft.answers.md` lists what the
fixture was built to produce — use it to check the run behaved.

---

## Step 7 — Optional: route through a LiteLLM proxy

Only do this if the user wants the dashboard. It is not needed to use the app.

```bash
export LITELLM_MASTER_KEY=sk-choose-any-value
litellm --config config.yaml
```

The proxy comes up on `:4000` with a dashboard at `http://127.0.0.1:4000/ui` — log in with
username `admin` and the master key as the password. Then, in a second shell:

```bash
LITELLM_BASE_URL=http://127.0.0.1:4000 \
LITELLM_MASTER_KEY=sk-choose-any-value \
  python verify.py samples/sports_draft.md
```

Every call now shows on one ledger — the extractor, all 15 searches, all 15 adjudications.

Two things to tell the user if they want request-level detail in that dashboard:
- **Logs and Usage need Postgres.** Without `DATABASE_URL` set the proxy runs fine and the
  Search Tools page works, but the spend endpoints return errors.
- **Opening a log row to read its prompt and response** needs
  `store_prompts_in_spend_logs: true` under `general_settings` — it ships commented out in
  `config.yaml`, so uncomment it and restart the proxy.

---

## Step 8 — Orient the user

Point out, in the HTML report:

- **Verdicts with citations** — each claim names the URL that decided it
- **Corrections** — contradicted claims come with what the source actually says
- **Not checked** — opinions and predictions are set aside rather than guessed at
- **The cost table** — search spend and token spend separately, plus cost per claim.
  Judgment costs roughly 4× retrieval, so grounding generously is the cheap choice.

Things to try next:

1. Their own document — `python verify.py path/to/doc.md`
2. `python verify.py doc.md --no-cache` to re-check claims already cached
3. Point `claim-adjudicator` in `config.yaml` at a cheaper model and compare verdicts
   against `samples/sports_draft.answers.md`
4. Change `SEARCH_PROVIDER` in `retrieve.py` to swap the search backend

---

## Notes

- **Live web results vary.** The same claim can resolve differently across runs as sources
  change or rank differently. Verdicts are evidence-dependent, not deterministic.
- **`unverifiable` is a real outcome**, not a failure — it means the retrieved sources did
  not settle the claim. A verifier that always concludes is guessing.
- **Per-claim results are cached** in `data/cache/`, keyed on claim text. Re-running the
  same document is nearly free; `--no-cache` forces fresh searches.
- **Failed searches degrade to empty evidence** for that claim rather than sinking the run,
  and the claim comes back `unverifiable`.
- **Python 3.9 will fail** on the type annotations in the adapter. This is the most common
  setup problem.
