# AI Setup Instructions — LangChain Lead Gen

You are helping the user set up and run the LangChain Lead Gen app. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

Run each of the following checks. If any fail, install the missing dependency before continuing.

**Python 3.9+**
```bash
python3 --version
```
If missing or below 3.9: direct the user to https://python.org/downloads

**pip**
```bash
pip --version
```
If missing: direct the user to https://pip.pypa.io/en/stable/installation/

---

## Step 2: Clone the repo

Check whether the repo is already cloned locally:

```bash
ls cookbook-langchain-lead-gen
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd langchain-lead-gen
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook-langchain-lead-gen
cd cookbook-langchain-lead-gen
```

---

## Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

This installs LangChain, LangGraph, the Anthropic SDK, Nimble Python SDK, Streamlit, and Pandas.

---

## Step 4: Get API keys

Ask the user if they already have both keys, or need to get one or both.

**Nimble API key**
Get one at: https://nimbleway.com
Tell the user: used to search Google Maps for businesses and extract website content (email, hours, description).

**Anthropic API key**
Get one at: https://console.anthropic.com
Tell the user: used by Claude to run the enrichment agent (LangGraph ReAct loop), score leads 1–10, and answer chat questions about the results.

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

## Step 6: Launch the app

```bash
streamlit run app.py
```

The app opens at http://localhost:8501

---

## Step 7: Orient the user

Walk the user through the app:

1. **Search bar** — enter any Google Maps query, e.g. `"independent coffee shops in Nashville, TN"` or `"marketing agencies in Austin, TX"`. Click **Find Leads**.

2. **Live extraction** — the agent searches Google Maps, then visits every business website one by one. Cards appear in real time showing extraction progress (`3/16: Business Name`).

3. **Scoring** — once all sites are extracted, Claude scores every lead 1–10 based on data completeness, ratings, and engagement signals. Score badges appear on each card.

4. **Card details** — click **View details** on any card to see contact info (email, phone, website), opening hours, business description, score reason, attributes (offerings, amenities, atmosphere), and a Google Maps link.

5. **Chat** — after results load, use the chat box to ask questions about your leads: *"Which leads have outdoor seating?"*, *"Who scored highest?"*, *"Which businesses open before 7am?"*

6. **Results table & export** — scroll down for a sortable table of all leads. Click **Download CSV** to export the full enriched list.

---

## Notes

- Each search makes live API calls to Nimble and Anthropic — results vary by query and location.
- The agent extracts email, opening hours, and a short description from each business website. If a field isn't found on the site, it is set to null.
- The app uses `claude-sonnet-4-6` for enrichment, scoring, and chat.
