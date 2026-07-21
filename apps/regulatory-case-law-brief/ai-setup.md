# AI Setup — Regulatory & Case-Law Brief

You are helping the user set up and run Regulatory & Case-Law Brief: a Nimble Web Search Agents app that turns an activity + jurisdiction into a cited compliance brief (applicable regulations + key case law + recent changes), every claim linked to a primary source. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1 — Check prerequisites

```bash
python3 --version    # need 3.10+
git --version
```

Only one credential is needed: a **Nimble API key** (nimbleway.com). No database or other accounts.

---

## Step 2 — Clone the repo

```bash
if [ -d cookbook ]; then cd cookbook && git pull; else git clone https://github.com/Nimbleway/cookbook && cd cookbook; fi
cd apps/regulatory-case-law-brief
```

---

## Step 3 — Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Under a minute (just requests, python-dotenv, streamlit).

---

## Step 4 — Fast path vs live

Tell the user they have two options:
- **Just read the briefs** — the repo ships 3 pre-built briefs. Skip to Step 7 and launch the viewer now; no key needed.
- **Generate briefs live** — continue with Step 5.

---

## Step 5 — Configure the key

```bash
cp .env.example .env
```

Set `NIMBLE_API_KEY` (from the Nimble dashboard at nimbleway.com). Show the user the file and confirm.

---

## Step 6 — Create the agent and run topics

```bash
python setup_agent.py    # ~10s; creates the research agent, id saved to agents.json (idempotent)
```

Edit `data/topics.txt` (one topic per line: activity + jurisdiction), then:

```bash
python run_brief.py      # runs each uncached topic, renders briefs
```

Research runs average **~10-20 min per topic**, run concurrently, resumable (rerun skips cached topics). Tell the user they can test one fast with `python run_brief.py --topic "..."`. When it finishes it reports how many briefs rendered.

---

## Step 7 — Launch the viewer

```bash
streamlit run app.py
```

Walk the user through it:
1. Pick a topic from the dropdown
2. Read the summary (broken into readable sections)
3. Open the **Regulations** / **Case law** / **Recent changes** / **Sources** tabs — each regulation and case expands to its full text and a primary-source link

---

## Notes

- **Research, not legal advice** — every brief carries the disclaimer; it is a research aid, not counsel
- **Citations are real public URLs** — the app remaps the agent's internal cache references to public source URLs at render time
- **Any jurisdiction** — US federal + state, EU, and UK all work; just change the topic
- **Depth** — set `RCB_EFFORT=max` in `.env` for a deeper (slower) pass on complex topics
- **"Not found" vs "none"** — the agent distinguishes a gap in its search from a confirmed absence; that wording is intentional
