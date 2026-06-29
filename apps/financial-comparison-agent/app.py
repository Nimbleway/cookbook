"""Chainlit dashboard for the Comps Agent.

Trigger:  type a ticker (e.g. "CMG") in the chat.
Monitor:  the agent's tool calls render live as steps (LangchainCallbackHandler).
Display:  a comps table (cl.Dataframe), an EV/EBITDA chart (cl.Plotly), the verdict,
          and recent catalysts. Every run is persisted to Supabase and reloadable
          from the recent-runs buttons shown at the start of a chat.
"""
import asyncio
import json
import re
import time
from datetime import datetime

import chainlit as cl
import pandas as pd
import plotly.graph_objects as go
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import agent
import config
import storage
from schema import FIELD_LABELS

# Columns shown in the comps table, in order.
TABLE_FIELDS = [
    "market_cap_b", "pe", "forward_pe", "ps", "ev_ebitda", "peg",
    "rev_growth", "op_margin", "price_target", "analyst_recom",
]

AGENT = agent.build_agent()


def parse_ticker(text: str) -> str:
    """Pull a ticker out of free text ("analyze CMG", "$CMG", "CMG")."""
    tokens = re.findall(r"[A-Za-z.]{1,6}", text)
    for t in tokens:                       # prefer an explicit all-caps ticker
        if t.isupper() and 1 <= len(t) <= 5:
            return t
    return tokens[-1].upper() if tokens else text.strip().upper()


def comps_dataframe(comps) -> pd.DataFrame:
    rows = []
    for c in comps.companies:
        row = {"Ticker": f"{c.ticker} ★" if c.is_target else c.ticker,
               "Name": (c.name or "")[:24]}
        row.update({FIELD_LABELS[f]: getattr(c, f) for f in TABLE_FIELDS})
        rows.append(row)
    med = comps.peer_median()
    median_row = {"Ticker": "Peer median", "Name": ""}
    median_row.update({FIELD_LABELS[f]: med[f] for f in TABLE_FIELDS})
    rows.append(median_row)
    return pd.DataFrame(rows)


def ev_ebitda_chart(comps) -> go.Figure:
    companies = [c for c in comps.companies if c.ev_ebitda is not None]
    med = comps.peer_median()["ev_ebitda"]
    fig = go.Figure(go.Bar(
        x=[c.ticker for c in companies],
        y=[c.ev_ebitda for c in companies],
        marker_color=[config.NIMBLE_YELLOW if c.is_target else "#5a6072" for c in companies],
        text=[c.ev_ebitda for c in companies],
        textposition="outside",
    ))
    if med is not None:
        fig.add_hline(y=med, line_dash="dash", line_color="#e05c2a",
                      annotation_text=f"peer median {med}", annotation_position="top left")
    fig.update_layout(
        title="EV/EBITDA vs peers", height=340, showlegend=False,
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#e0e0e0"),
        margin=dict(t=48, b=24, l=24, r=24),
    )
    fig.update_xaxes(gridcolor="#2a2a3e")
    fig.update_yaxes(gridcolor="#2a2a3e")
    return fig


def catalysts_md(comps) -> str:
    if not comps.catalysts:
        return ""
    lines = ["\n**Recent catalysts**"]
    for c in comps.catalysts[:8]:
        date = f"`{c.date}` " if c.date else ""
        ticker = f"**{c.ticker}** " if c.ticker else ""
        lines.append(f"- {date}{ticker}{c.headline}")
    return "\n".join(lines)


async def render_comps(comps, actions=None) -> None:
    """Render a ComparableSet as the final answer (used by live runs and reloads)."""
    df = comps_dataframe(comps)
    content = (
        f"## {comps.target_ticker} — {comps.target_name or ''}\n\n"
        f"#### Verdict\n{comps.verdict}\n\n{catalysts_md(comps)}"
    )
    await cl.Message(
        content=content,
        elements=[
            cl.Dataframe(name="Comps table", data=df, display="inline"),
            cl.Plotly(name="EV/EBITDA vs peers", figure=ev_ebitda_chart(comps), display="inline"),
        ],
        actions=actions or [],
    ).send()


def _fmt_date(iso) -> str:
    try:
        return datetime.fromisoformat(str(iso)).strftime("%b %d")
    except Exception:
        return str(iso)[:10]


@cl.set_starters
async def starters():
    # Chainlit renders starters as one flat row with no section headers, so the
    # two groups are distinguished by icon + verb: yellow "Analyze…" cards run a
    # fresh analysis; muted "Reopen…" cards (a /reload command handled in
    # on_message) replay a saved run. Starters are the only element guaranteed
    # visible on the fresh-chat splash, so this is how past runs stay reachable.
    demo = [
        cl.Starter(label="Analyze Chipotle (CMG)", message="CMG", icon="/public/new.svg"),
        cl.Starter(label="Analyze Salesforce (CRM)", message="CRM", icon="/public/new.svg"),
        cl.Starter(label="Analyze Nike (NKE)", message="NKE", icon="/public/new.svg"),
        cl.Starter(label="Analyze Nvidia (NVDA)", message="NVDA", icon="/public/new.svg"),
    ]
    try:
        recent = await cl.make_async(storage.recent_runs)(4)
    except Exception:
        recent = []
    history = [
        cl.Starter(
            label=f"Reopen {r['target_ticker']} · {_fmt_date(r['created_at'])}",
            message=f"/reload {r['id']}",
            icon="/public/history.svg",
        )
        for r in recent
    ]
    return demo + history


@cl.on_chat_start
async def start():
    await cl.Message(
        content=(
            "## Financial Comparison Agent\n"
            "Live **comparable-company analysis** powered by Nimble + Claude.\n\n"
            "**How to use:** type a single US stock **ticker symbol** — e.g. `CMG`, "
            "`CRM`, `NKE` — or click a starter below. I'll discover the company's public "
            "peers, pull current valuation multiples for each, surface recent catalysts, "
            "and give a relative-valuation verdict.\n\n"
            "Past analyses appear as **↻ starter cards** on the new-chat screen — "
            "click one to reopen it."
        )
    ).send()


@cl.action_callback("reload")
async def reload(action: cl.Action):
    cl.user_session.set("convo", None)  # reloaded runs are view-only; next msg starts fresh
    cl.user_session.set("comps", None)
    comps = await cl.make_async(storage.get_run)(action.payload["run_id"])
    await render_comps(comps, actions=_new_analysis_action())


def _text_of(m) -> str:
    """Natural-language text from an AIMessage (handles str or content-block list)."""
    c = m.content
    if isinstance(c, list):
        c = " ".join(
            b.get("text", "") for b in c
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return c.strip() if isinstance(c, str) else ""


def _tool_result_line(m) -> str:
    """A detailed one-liner summarizing a tool's result."""
    content = m.content if isinstance(m.content, str) else str(m.content)
    try:
        d = json.loads(content)
    except Exception:
        d = None
    if m.name == "find_peers":
        ans = " ".join(((d or {}).get("answer") or "").split())
        # Repress the line entirely when find_peers has no usable answer — the agent
        # still gets the raw results to curate from; we just don't show a dud line.
        if not ans:
            return ""
        return f"   ↳ 🔍 peer ideas: {ans[:160]}{'…' if len(ans) > 160 else ''}"
    if m.name == "get_financials" and d:
        return (f"   ↳ 📊 {d.get('ticker')} — P/E {d.get('pe')} · Fwd {d.get('forward_pe')} · "
                f"P/S {d.get('ps')} · EV/EBITDA {d.get('ev_ebitda')} · "
                f"rev {d.get('rev_growth')}% · op margin {d.get('op_margin')}%")
    if m.name == "get_catalysts" and d:
        items = d.get("items", [])
        latest = items[0].get("title") if items else ""
        head = f" — latest: “{latest[:80]}”" if latest else ""
        return f"   ↳ 📰 {len(items)} catalysts{head}"
    return f"   ↳ ✓ {m.name}"


def _progress_lines(m) -> list:
    """Feed lines for one streamed message: the agent's reasoning, the tool calls it
    makes (with args), and a detailed summary of each tool result."""
    out = []
    if isinstance(m, AIMessage):
        text = _text_of(m)
        if text:
            out.append(f"💭 {text}")
        for tc in (m.tool_calls or []):
            args = ", ".join(f"{k}={v}" for k, v in (tc.get("args") or {}).items())
            out.append(f"⚙️ calling **{tc['name']}**({args})")
    elif isinstance(m, ToolMessage):
        out.append(_tool_result_line(m))
    return [ln for ln in out if ln]


def _new_analysis_action():
    return [cl.Action(name="new_analysis", payload={}, label="🔄 New analysis")]


def _last_ai_text(convo) -> str:
    """The agent's most recent natural-language answer (skipping tool-call turns)."""
    for m in reversed(convo):
        if isinstance(m, AIMessage) and not m.tool_calls:
            content = m.content
            if isinstance(content, list):  # anthropic content blocks
                content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            if content and str(content).strip():
                return str(content)
    return ""


class _Progress:
    """A single self-updating progress message with a heartbeat. A detailed feed of the
    agent's reasoning, tool calls, and results builds up, while a ticking "working (Ns)"
    line below it proves the agent is alive even during silent LLM/tool gaps."""

    def __init__(self):
        self.lines = []
        self.msg = None
        self._stop = asyncio.Event()
        self._task = None
        self._t0 = 0.0

    async def start(self, header):
        self.lines = [header, ""]
        self.msg = cl.Message(content="\n".join(self.lines))
        await self.msg.send()
        self._t0 = time.time()
        self._task = asyncio.create_task(self._beat())

    async def _beat(self):
        dots = 0
        while not self._stop.is_set():
            dots = dots % 3 + 1
            elapsed = int(time.time() - self._t0)
            self.msg.content = "\n".join(
                self.lines + ["", f"⏳ working{'.' * dots} ({elapsed}s)"])
            try:
                await self.msg.update()
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=1.2)
            except asyncio.TimeoutError:
                pass

    def add(self, line):
        if line:
            self.lines.append(line)

    async def finish(self):
        self._stop.set()
        if self._task:
            await self._task
        if self.msg:
            self.msg.content = "\n".join(self.lines)
            await self.msg.update()


async def _stream_agent(convo, prog):
    """Run the agent over `convo`, appending detailed feed lines (reasoning, tool calls
    with args, and result summaries) to `prog`. Returns the extended `convo`."""
    async for chunk in AGENT.astream(
        {"messages": convo}, config={"recursion_limit": 60}, stream_mode="updates",
    ):
        for _node, update in chunk.items():
            for m in (update or {}).get("messages", []):
                convo.append(m)
                for line in _progress_lines(m):
                    prog.add(line)
    return convo


@cl.on_message
async def on_message(message: cl.Message):
    # Reopen a saved run (fired by a "↻" recent-run starter). View-only: clears
    # any active conversation so the next ticker starts fresh.
    text = (message.content or "").strip()
    if text.startswith("/reload "):
        run_id = text.split(" ", 1)[1].strip()
        cl.user_session.set("convo", None)
        cl.user_session.set("comps", None)
        try:
            comps = await cl.make_async(storage.get_run)(run_id)
        except Exception as exc:
            await cl.Message(content=f"⚠️ Couldn't reopen that run: {exc}").send()
            return
        await render_comps(comps, actions=_new_analysis_action())
        return

    convo = cl.user_session.get("convo")
    prog = _Progress()

    # No active analysis -> treat the message as a new ticker.
    if not convo:
        ticker = parse_ticker(message.content)
        convo = [HumanMessage(content=f"Build a comparable-company analysis for {ticker}.")]
        await prog.start(f"**Researching {ticker}** — live progress")
        try:
            convo = await _stream_agent(convo, prog)
            prog.add("")
            prog.add("🧮 building comps table & writing the verdict…")
            plan = await cl.make_async(agent.extract_plan)(convo)
            comps = await cl.make_async(agent.assemble_comps)(plan)
            await cl.make_async(storage.persist)(comps, config.MODEL)
        except Exception as exc:
            await prog.finish()
            await cl.Message(content=f"⚠️ Analysis failed for **{ticker}**: {exc}").send()
            return
        await prog.finish()
        cl.user_session.set("convo", convo)
        cl.user_session.set("comps", comps)
        await render_comps(comps, actions=_new_analysis_action())
        return

    # Active analysis -> follow-up question. The agent keeps its Nimble tools, so it can
    # gather more data on demand (e.g. "add SHAK", "latest news on CAVA", "compare to MCD").
    convo.append(HumanMessage(content=message.content))
    await prog.start("**Looking into that…**")
    try:
        convo = await _stream_agent(convo, prog)
    except Exception as exc:
        await prog.finish()
        await cl.Message(content=f"⚠️ {exc}").send()
        return
    await prog.finish()
    cl.user_session.set("convo", convo)
    answer = _last_ai_text(convo) or "I couldn't find an answer to that."
    await cl.Message(content=answer, actions=_new_analysis_action()).send()


@cl.action_callback("new_analysis")
async def new_analysis(action: cl.Action):
    cl.user_session.set("convo", None)
    cl.user_session.set("comps", None)
    await cl.Message(
        content="🔄 **New analysis** — enter a ticker (e.g. `CMG`, `CRM`, `NKE`)."
    ).send()
