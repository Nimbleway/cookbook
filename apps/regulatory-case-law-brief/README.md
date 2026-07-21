# regulatory-case-law-brief — Regulatory & Case-Law Brief

Generate a cited compliance brief for any activity and jurisdiction: the applicable regulations, key case law, recent changes, and a plain-language summary, with every claim linked to a **primary source**. A single [Nimble](https://nimbleway.com) Web Search Agent researches official statute, court, and agency sites.

![Built with Nimble](https://img.shields.io/badge/Built%20with-Nimble-edc602)

## What it does

1. **Ask** — you give a topic: an activity + jurisdiction, e.g. "launching a consumer fintech lending product in Texas"
2. **Research** — a `research` agent searches official sources and returns a structured brief: applicable regulations, key case law/enforcement actions, recent changes, and a summary, each cited to a primary source
3. **Render** — the app writes a Markdown brief per topic and a structured `briefs.json`, remapping every citation to its real public URL
4. **Read** — a Streamlit viewer shows the brief: a readable summary, then tabbed Regulations / Case law / Recent changes / Sources with expandable items and source links

## Stack

- [Nimble Web Search Agents](https://nimbleway.com) — one `research` agent; sources use category-group steering toward primary/official sources (statutes, court opinions, agency pages), with field-level citations
- [Streamlit](https://streamlit.io) — the brief viewer
- Python 3.10+ — resumable per-topic runs, citation remapping

## Setup

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/regulatory-case-law-brief
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add NIMBLE_API_KEY (nimbleway.com)
```

The repo ships 3 pre-built briefs in `data/` + `briefs/`, so the viewer runs immediately:

```bash
streamlit run app.py
```

To generate briefs live:

```bash
python setup_agent.py    # creates the agent (once; id in agents.json)
python run_brief.py      # runs each topic in data/topics.txt, ~10-20 min each, resumable
# or one topic:
python run_brief.py --topic "Data privacy obligations for a UK fintech"
```

## Usage

Topics live one-per-line in `data/topics.txt` (activity + jurisdiction). `run_brief.py` runs each, caches the raw result to `data/raw/<slug>.json`, and renders `briefs/<slug>.md` + a structured `data/briefs.json`. Rerunning skips topics already cached; `--render-only` rebuilds the briefs from cache with no API calls.

## Project structure

```
├── config.py         # env, paths, effort
├── agent_config.py   # the research agent config (primary-source steering)
├── setup_agent.py    # creates the agent
├── run_brief.py      # run topics (resumable) + render briefs (citation remap)
├── app.py            # Streamlit brief viewer
├── data/topics.txt   # the topics to brief
├── data/raw/*.json   # cached agent results (the demo cache)
├── data/briefs.json  # structured briefs the viewer reads
└── briefs/*.md       # rendered Markdown briefs
```

## Output

Per topic, a structured brief (in `data/briefs.json` and as `briefs/<slug>.md`):

| field | contents |
|---|---|
| `summary` | plain-language compliance overview (research, not legal advice) |
| `regulations` | applicable statutes/regulations: name, jurisdiction, requirement, primary-source URL |
| `cases` | key case law / enforcement actions: case name, court, date, holding, source URL |
| `changes` | recent or pending changes with dates and source URLs |
| `sources` | the primary sources cited, as public URLs |

## Going further

- **Any topic** — edit `data/topics.txt`; the agent is jurisdiction-agnostic (US federal + state, EU, UK all worked in testing)
- **Deeper research** — set `RCB_EFFORT=max` for judgment-heavy topics (slower, more thorough)
- **Export** — `briefs/*.md` are portable Markdown; drop them into a wiki or PDF pipeline

## Notes

- **Research, not legal advice** — every brief says so; it is a research aid, not a substitute for counsel
- **Citations are real public URLs.** The agent's structured output returns internal cache paths in `citation_url`; the real public URLs live in the trust object (`trust.sources`, `trust.claims[].citations[].url`). `run_brief.py` remaps each field to its real URL at render time
- **Honest gaps** — the agent distinguishes "not found after search" from "confirmed none" (e.g. when no court opinion on a niche topic exists)
- **Run time** — research runs average ~10–20 min per topic; `run_brief.py` runs them concurrently and is resumable
