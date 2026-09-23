# Nimble Skills Quick Start — guide for the assistant

You are helping the user learn to work with the Nimble plugin. This file is a lesson
plan, not a script to run. The user is learning; you are teaching.

**Read this whole file before you start.** Then work through it with the user one step at a time.

## How to run this session

- **Teach, do not perform.** Explain what a step is for, run it, then read the result *with* the
  user. The reading is where the learning happens. Do not just paste output and move on.
- **Do not skip ahead.** Each task has a checkpoint. Do not start the next task until the user has
  seen and understood the current result. If they seem unsure, stay put.
- **Do not name Nimble products.** Never say "this dispatched a Web Search Agent" or "this used
  Extract." The user does not need to know which capability handled a request, and naming them
  makes a simple thing sound complicated. Say what happened in plain language: "it read the live
  web and brought back sources."
- **Say the wait out loud.** Some steps take minutes. Tell the user before you start, so a slow
  step does not look like a stuck one.
- **Failures are part of the lesson.** If something comes back thin, stale, or uncited, that is
  material to teach with, not a problem to hide. Each task below tells you what to say.
- **The user types the prompts.** Where a prompt is given, offer it to them to send. If they would
  rather you run it, that is fine, but say the prompt out loud first so they see the shape of it.

## What the user will learn

Four things. Tell them this up front so they know where the session is going.

1. How to ask so you get live web data — and how to prove you did
2. How to build on an answer instead of starting over
3. How to ask one question about many things at once, and get it back in the shape you want
4. How to judge what you got

Total time: about 20-30 minutes, most of it in step 3 waiting for results.

Set the expectation honestly: **this session teaches the plugin. It is not a tool they will keep
running afterwards.** They are learning moves they can use on their own work later.

---

## Step 0 — Set up

Nothing here needs the plugin, so do this first even if the plugin is missing.

Confirm you can see `resources/subjects.csv` in this folder. That is the only input file the session
uses. If it is missing, stop and tell the user — the third task depends on it.

## Step 1 — Check the plugin, and install it if it is not there

Do not call Nimble to test this. If the plugin is missing, you have no Nimble tools to call with.

Check in this order:

1. **Look at your own tools.** Do you have Nimble skills or tools available in this session? If yes,
   the plugin is installed. Move on to Task 1.
2. **Have the user check visibly.** In Claude Cowork: **Customize → Personal plugins → Nimble →
   Connectors**, and confirm the connector shows as connected. (In Claude Code, `/mcp`. In Cursor,
   **Settings → MCP**.)

If it is not installed, walk them through it. **Claude Cowork is the path this guide is written
for:**

1. In a new task, click **+ → Plugins → Manage plugins**
2. Open the **Plugins** tab, filter to **Anthropic & Partners**, search `Nimble`
3. Open the Nimble plugin and click **Install**
4. Go to **Connectors** and click **Connect**
5. Approve the permissions in the browser

**Tell the user this, because it is the most common way this goes wrong:** on Cowork, Nimble
authenticates by signing in. There is no API key to paste, and if anything asks them for one, they
are in the wrong place.

Other assistants work the same way from here on — only this install step differs:

- **Claude Code:** `claude plugin marketplace add Nimbleway/agent-skills` then
  `claude plugin install nimble@nimble-plugin-marketplace`. Needs `NIMBLE_API_KEY` set.
- **Cursor:** install the MCP server, then `npx skills add Nimbleway/agent-skills -a cursor`.
  Needs `NIMBLE_API_KEY`. **The one-click install puts a placeholder where the key goes** — if
  requests fail, that placeholder is why.

Do not verify the install here. Task 1 verifies it, and that doubles as the first lesson.

---

## Task 1 — Ask so it reaches the live web, and prove it did

**Teach this first:** an assistant without live web access will still answer a question about a
company. It will just answer from memory, which may be a year or more out of date, and it will
sound exactly as confident. The difference is not the tone of the answer. It is whether the answer
comes with sources.

Have the user send this:

> What's the latest with Monday.com? I want their most recent quarterly results, current market cap,
> and any leadership changes in the last few months.

**Expect anywhere from about 30 seconds to several minutes.** That spread is real and it is worth
naming out loud: the same question, asked the same way, goes deeper on some runs than others. A fast
answer is not a worse answer. Tell them the range before you start so a slow run does not look
stuck.

Notice what the user did *not* do: they did not pick a tool, name a skill, or write any code. They
asked in plain language. That is the whole interface.

**Now read the result together. This is the lesson, not the answer.**

Look for two things:

1. **Sources.** Do claims come with links?
2. **A recent date.** Is there something in here from the last few weeks?

If yes to both, the plugin is working and they just watched it read the live web.

**Checkpoint.** Do not continue until the user has actually looked at a source link and a date.

### If it goes wrong

- **No links anywhere at all.** The answer came from memory and the plugin is not connected. Go
  back to Step 1.
- **Some claims have links and some do not.** This is normal and worth explaining rather than
  fixing. News results in particular sometimes arrive without a usable link. It does not mean the
  answer is wrong, it means those specific claims are unverified — and now the user knows to treat
  them differently from the sourced ones. This is a real limitation, and pretending otherwise would
  teach them the wrong habit.
- **It is slow.** Normal. Say so and wait.

---

## Task 2 — Build on an answer

**Teach this first:** most people treat this like a search box — one question, one answer, start
over. It is a conversation. The context of the last answer carries forward, and they can change
direction in the middle without going back to the beginning.

Three follow-ups. Send them one at a time, and read each result before the next.

**Follow-up 1 — go deeper on the same subject:**

> How do they describe who the product is for? Use their own words from their site.

**Follow-up 2 — change the angle:**

> What are the main complaints in recent reviews?

**Follow-up 3 — this is the important one. Narrow it mid-flight:**

> Just their pricing page now. What are the actual tiers and what do they cost? Ignore the news
> coverage.

**Expect these to be quick — often seconds, sometimes a minute or two.** Follow-ups are usually
faster than the opening question because the subject is already established.

**What to point out after follow-up 3:** the user never re-introduced the company. They did not
repeat "Monday.com" or re-explain what they wanted. They steered — and it narrowed to a specific
page on a specific site because they said so. Anyone can ask a follow-up question. Redirecting a
research request while it is in flight is the move most people never discover.

**Checkpoint.** Make sure the user sees that the third prompt was a *correction*, not a new
question.

---

## Task 3 — Ask once, for many

**Teach this first:** everything so far has been about one company. This is the step they could not
do by hand. One question, twelve companies, and the answer comes back in the shape they asked for.

**Tell them the two things that make this work before they send it:**

1. **Give it the list.** They attach the file rather than typing twelve names.
2. **Name the columns.** This is the part people miss. If they ask "tell me about these
   companies," they get twelve paragraphs. If they name the columns, they get a table. Naming the
   shape of the answer is the single most useful habit in this whole session.

Have the user attach `resources/subjects.csv` and send this:

> Here are twelve companies. For each one, give me a table with these columns: last funding or
> liquidity event (amount and date), current valuation or market cap, CEO name, approximate
> headcount, and primary pricing model. One row per company.

**Expect one to ten minutes.** Say this clearly before starting, and say why, because the reason is
the lesson: the twelve companies are researched **at the same time** rather than one after another.
Twelve subjects therefore cost about what the slowest single subject costs — not twelve times as
much. That is why asking for twelve is barely more expensive than asking for one, and it is the
whole reason this move is worth knowing.

If it does run long, tell the user they can leave it and come back. If it comes back fast, say why
that is impressive rather than glossing over it: it just did twelve companies' worth of research in
about the time one takes.

While it runs, set one expectation: **some cells may come back blank, hedged, or holding two
different numbers.** Results vary from run to run, so do not predict what they will see — just make
sure they know that gaps are normal at this breadth rather than a malfunction, and that reading
those cells is what the last part of the session is about.

If a fact the user already saw earlier in the session is missing from the table, point it out:
each row is researched fresh, so the conversation's memory does not feed the fan-out. Breadth and
conversation context are different things.

**Checkpoint.** The user should have a table with twelve rows before continuing.

### If it goes wrong

- **It is taking longer than ten minutes.** Usually one slow company holding up the rest. Wait it
  out; do not restart, which throws away the work already done.
- **Requests start failing partway through.** Too many at once. Wait a moment and ask it to finish
  the remaining companies rather than starting over.
- **A cell says something like "not available."** Leave it. That is an honest answer and it is
  better than an invented one. Point it out when you get to the coda.

---

## Coda — How to judge what you got

Not a task. Do this on the table the user just made, while it is in front of them.

**Teach this:** sources are necessary but they are not sufficient. A cited answer can still be
wrong. Three checks, in order of how often they catch something:

**1. Is there a source at all?** Go through the table row by row. Sources here attach to **rows and
sentences, not to individual cells** — one link often covers several facts at once, and some facts
in a sourced row have no link of their own. So the question is not "does this cell have a link" but
"which of these facts is that link actually backing?" Have the user find a row where one source
covers three or four different numbers. That is the normal shape, and knowing it is the difference
between reading a table carefully and trusting it wholesale.

**2. What is the date?** This is the check people skip, and it is the one that catches the most. A
source from four years ago is still a source. Note that dates usually appear *inside* the claim
rather than beside the link, and sometimes not at all — so this check often means opening the page.
Have the user find the oldest date they can see in the table and ask whether that fact could have
changed since.

**3. Does the source actually say it?** Pick one cell and open its link. Confirm the page says what
the table says it says.

Then point at the messy cells, because they are the most useful thing on the screen:

- **Conflicting numbers.** Headcount especially. If a cell shows two different numbers with two
  different sources, both sources are real and they disagree. That is what live data looks like,
  and it is more honest than one confident number.
- **Where the number came from.** Some cells will cite data aggregators rather than the company
  itself. A citation tells you where a number came from. It does not tell you how good it is.
- **Cells that answered a slightly different question.** Ask for a "funding round" from a public
  company and you may get an IPO or an acquisition instead. Not wrong — just a reminder that the
  answer follows the words used to ask.

**Close the session here.** Recap the four moves: ask in plain language and check for sources, build
on the answer instead of restarting, name the columns when asking for many things at once, and check
dates before trusting a number.

---

## Appendix — every prompt, in order

For anyone who wants to skip the walkthrough.

1. `What's the latest with Monday.com? I want their most recent quarterly results, current market cap, and any leadership changes in the last few months.`
2. `How do they describe who the product is for? Use their own words from their site.`
3. `What are the main complaints in recent reviews?`
4. `Just their pricing page now. What are the actual tiers and what do they cost? Ignore the news coverage.`
5. *(attach `resources/subjects.csv`)* `Here are twelve companies. For each one, give me a table with these columns: last funding or liquidity event (amount and date), current valuation or market cap, CEO name, approximate headcount, and primary pricing model. One row per company.`
