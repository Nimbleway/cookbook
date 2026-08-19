"""
Reporting — the document, annotated claim by claim.

Two outputs from one run: `report.html` for reading and screenshots, `report.md`
for terminals and CI. The HTML anchors each verdict to the sentence it came from,
because a verdict list detached from the prose is much harder to act on than an
annotated document.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from jinja2 import Environment

from schemas import Run

# Autoescape on: rationales, corrections and titles are model- and web-sourced, so a
# stray `<` must not be able to break the page. The annotated document is escaped by
# hand in `_annotate` (it has to be, to inject spans) and is marked `|safe` there.
_ENV = Environment(autoescape=True)

_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def _safe_id(claim_id: str) -> str:
    """
    Claim ids reach HTML as element ids and fragment hrefs. They originate in a model
    response, so they are sanitised rather than trusted: escaping alone would not stop a
    crafted id from breaking out of an attribute.
    """
    cleaned = _SAFE_ID.sub("", claim_id or "")
    return cleaned or "claim"


def _safe_url(url: str | None) -> str | None:
    """
    Only http(s) citations become links. Escaping does not neutralise a `javascript:` URL,
    and these URLs come from search results, which is to say from the open web.
    """
    if not url:
        return None
    return url if re.match(r"^https?://", url.strip(), re.IGNORECASE) else None

STATUS_LABEL = {
    "supported": "Supported",
    "contradicted": "Contradicted",
    "unverifiable": "Unverifiable",
}


def _annotate(document: str, run: Run) -> str:
    """
    Escape the document, then wrap each claim's source sentence in a marked span.

    The quote comes back from a model, so exact matching cannot be assumed: the
    fallback retries with flexible whitespace before giving up. A claim that can't be
    anchored still appears in the table below — it just isn't highlighted inline.
    """
    escaped = html.escape(document)

    # Every span is located against the UNTOUCHED escaped document, and insertion happens
    # afterwards in one pass. Replacing as we go would let a later quote match text inside
    # an already-inserted span, nesting two annotations over one occurrence.
    spans: list[tuple[int, int, int, object]] = []
    for i, result in enumerate(run.results, 1):
        quote = html.escape(result.claim.quote.strip())
        if not quote:
            continue

        start = escaped.find(quote)
        if start >= 0:
            end = start + len(quote)
        else:
            # Whitespace-flexible retry — model-copied quotes often normalise line breaks.
            match = re.compile(r"\s+".join(re.escape(w) for w in quote.split())).search(escaped)
            if not match:
                continue
            start, end = match.span()

        # Two claims over the same sentence: annotate the first, leave the second to the
        # table below. Overlapping markup would corrupt both.
        if any(start < prev_end and prev_start < end for prev_start, prev_end, _, _ in spans):
            continue
        spans.append((start, end, i, result))

    out: list[str] = []
    cursor = 0
    for start, end, i, result in sorted(spans):
        anchor = _safe_id(result.claim.id)
        out.append(escaped[cursor:start])
        out.append(
            f'<span class="claim {result.verdict.status}" id="anchor-{anchor}">'
            f'<a class="pin" href="#{anchor}">{i}</a>{escaped[start:end]}</span>'
        )
        cursor = end
    out.append(escaped[cursor:])
    escaped = "".join(out)

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", escaped) if p.strip()]
    return "\n".join(f"<p>{p}</p>" for p in paragraphs)


TEMPLATE = _ENV.from_string(
    """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claim Verification — {{ doc_name }}</title>
<style>
  :root{
    --bg:#faf9f7; --card:#fff; --ink:#1a1a1a; --muted:#6b6b6b; --line:#e5e3df;
    --brand:#edc602; --ok:#0f7b4a; --ok-bg:#e6f4ec; --bad:#c02626; --bad-bg:#fbeaea;
    --unk:#8a6d00; --unk-bg:#fdf6dd;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Helvetica,Arial,sans-serif}
  .wrap{max-width:1080px;margin:0 auto;padding:40px 24px 72px}
  header{border-bottom:4px solid var(--brand);padding-bottom:20px;margin-bottom:28px}
  h1{margin:0 0 6px;font-size:26px;letter-spacing:-.02em}
  .sub{color:var(--muted);font-size:14px}
  .sub code{background:#efede8;padding:1px 6px;border-radius:4px;font-size:12.5px}
  .tiles{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0 32px}
  .tile{flex:1 1 150px;background:var(--card);border:1px solid var(--line);
    border-radius:10px;padding:14px 16px}
  .tile .n{font-size:26px;font-weight:650;letter-spacing:-.02em}
  .tile .l{font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-top:2px}
  .tile.ok .n{color:var(--ok)} .tile.bad .n{color:var(--bad)} .tile.unk .n{color:var(--unk)}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:26px 30px;margin-bottom:28px}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);
    margin:0 0 16px;font-weight:600}
  .doc p{margin:0 0 14px}
  .claim{border-radius:3px;padding:1px 0;box-decoration-break:clone}
  .claim.supported{background:var(--ok-bg);box-shadow:inset 0 -2px 0 var(--ok)}
  .claim.contradicted{background:var(--bad-bg);box-shadow:inset 0 -2px 0 var(--bad)}
  .claim.unverifiable{background:var(--unk-bg);box-shadow:inset 0 -2px 0 var(--unk)}
  .pin{display:inline-block;min-width:16px;height:16px;line-height:16px;text-align:center;
    font-size:10.5px;font-weight:700;border-radius:4px;margin-right:5px;vertical-align:1px;
    background:#1a1a1a;color:#fff;text-decoration:none}
  .verdict{border-top:1px solid var(--line);padding:18px 0}
  .verdict:first-of-type{border-top:none;padding-top:0}
  .vhead{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}
  .badge{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
    padding:3px 9px;border-radius:20px}
  .badge.supported{background:var(--ok-bg);color:var(--ok)}
  .badge.contradicted{background:var(--bad-bg);color:var(--bad)}
  .badge.unverifiable{background:var(--unk-bg);color:var(--unk)}
  .num{font-size:10.5px;font-weight:700;background:#1a1a1a;color:#fff;border-radius:4px;
    min-width:17px;height:17px;line-height:17px;text-align:center;display:inline-block}
  .kind{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .ctext{font-weight:550;margin:0 0 6px}
  .rationale{color:#3d3d3d;font-size:14.5px;margin:0 0 8px}
  .correction{background:var(--bad-bg);border-left:3px solid var(--bad);padding:9px 12px;
    border-radius:0 6px 6px 0;font-size:14.5px;margin:0 0 8px}
  .meta{font-size:12.5px;color:var(--muted);display:flex;gap:14px;flex-wrap:wrap}
  .meta a{color:#1a5fb4;text-decoration:none;overflow-wrap:anywhere}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line)}
  th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600}
  td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
  tfoot td{font-weight:650;border-bottom:none}
  .skipped li{color:var(--muted);font-size:14px;margin-bottom:7px}
  .skipped .why{color:#3d3d3d;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
  footer{color:var(--muted);font-size:12.5px;text-align:center;margin-top:8px}
  .tablewrap{overflow-x:auto}
</style></head><body><div class="wrap">

<header>
  <h1>Claim verification — {{ doc_name }}</h1>
  <div class="sub">
    {{ n_claims }} claims checked against live web sources via
    <code>litellm.search(search_provider="nimble")</code>
    · adjudicated by <code>{{ adjudicator }}</code>
    {% if not run.live %} · <strong>cached replay, no API calls</strong>{% endif %}
  </div>
</header>

<div class="tiles">
  <div class="tile ok"><div class="n">{{ counts.supported }}</div><div class="l">Supported</div></div>
  <div class="tile bad"><div class="n">{{ counts.contradicted }}</div><div class="l">Contradicted</div></div>
  <div class="tile unk"><div class="n">{{ counts.unverifiable }}</div><div class="l">Unverifiable</div></div>
  <div class="tile"><div class="n">${{ '%.4f'|format(run.cost.search_spend) }}</div><div class="l">Search spend</div></div>
  <div class="tile"><div class="n">${{ '%.4f'|format(run.cost.token_spend) }}</div><div class="l">Token spend</div></div>
</div>

<div class="panel">
  <h2>The document, annotated</h2>
  <div class="doc">{{ annotated|safe }}</div>
</div>

<div class="panel">
  <h2>Verdicts</h2>
  {% for r in run.results %}
  <div class="verdict" id="{{ safe_id(r.claim.id) }}">
    <div class="vhead">
      <span class="num">{{ loop.index }}</span>
      <span class="badge {{ r.verdict.status }}">{{ labels[r.verdict.status] }}</span>
      <span class="kind">{{ r.claim.kind }}{% if r.claim.time_sensitive %} · time-sensitive{% endif %}</span>
    </div>
    <p class="ctext">{{ r.claim.text }}</p>
    <p class="rationale">{{ r.verdict.rationale }}</p>
    {% if r.verdict.correction %}<div class="correction"><strong>Correction:</strong> {{ r.verdict.correction }}</div>{% endif %}
    <div class="meta">
      <span>confidence: {{ r.verdict.confidence }}</span>
      <span>focus: {{ r.search_focus }}</span>
      <span>sources: {{ r.evidence|length }}</span>
      {% if r.verdict.deciding_url %}<span>decided by
        {% set href = safe_url(r.verdict.deciding_url) %}
        {% if href %}<a href="{{ href }}" rel="noopener noreferrer">{{ r.verdict.deciding_url }}</a>
        {% else %}{{ r.verdict.deciding_url }}{% endif %}
      </span>{% endif %}
      <span><a href="#anchor-{{ safe_id(r.claim.id) }}">back to text ↑</a></span>
    </div>
  </div>
  {% endfor %}
</div>

<div class="panel">
  <h2>Cost</h2>
  <div class="tablewrap"><table>
    <thead><tr><th>Component</th><th>Calls</th><th class="r">Spend</th></tr></thead>
    <tbody>
      <tr><td>Nimble search <span class="kind">$0.005 / query</span></td>
          <td>{{ run.cost.search_queries }}</td>
          <td class="r">${{ '%.4f'|format(run.cost.search_spend) }}</td></tr>
      <tr><td>Claim extraction <span class="kind">{{ extractor }}</span></td>
          <td>1</td><td class="r">${{ '%.4f'|format(run.cost.extract_spend) }}</td></tr>
      <tr><td>Adjudication <span class="kind">{{ adjudicator }}</span></td>
          <td>{{ n_adjudicated }}</td><td class="r">${{ '%.4f'|format(run.cost.adjudicate_spend) }}</td></tr>
    </tbody>
    <tfoot>
      <tr><td>Total</td><td></td><td class="r">${{ '%.4f'|format(run.cost.total) }}</td></tr>
      <tr><td>Per claim</td><td></td><td class="r">${{ '%.4f'|format(run.cost.per_claim(n_claims)) }}</td></tr>
    </tfoot>
  </table></div>
</div>

{% if run.skipped %}
<div class="panel">
  <h2>Not checked ({{ run.skipped|length }})</h2>
  <ul class="skipped">
    {% for s in run.skipped %}<li>“{{ s.quote }}” <span class="why">{{ s.reason }}</span></li>{% endfor %}
  </ul>
</div>
{% endif %}

<footer>Search spend and token spend both reported by LiteLLM via
<code>response_cost</code> — one SDK, one unit.</footer>
</div></body></html>"""
)


def _counts(run: Run) -> dict[str, int]:
    out = {"supported": 0, "contradicted": 0, "unverifiable": 0}
    for r in run.results:
        out[r.verdict.status] = out.get(r.verdict.status, 0) + 1
    return out


def write_html(run: Run, path: Path, extractor: str, adjudicator: str) -> Path:
    html_out = TEMPLATE.render(
        run=run,
        doc_name=Path(run.document_path).name,
        safe_url=_safe_url,
        safe_id=_safe_id,
        annotated=_annotate(run.document_text, run),
        counts=_counts(run),
        labels=STATUS_LABEL,
        n_claims=len(run.results),
        n_adjudicated=sum(1 for r in run.results if r.evidence),
        extractor=extractor,
        adjudicator=adjudicator,
    )
    path.write_text(html_out)
    return path


def write_markdown(run: Run, path: Path) -> Path:
    counts = _counts(run)
    lines = [
        f"# Claim verification — {Path(run.document_path).name}",
        "",
        f"{len(run.results)} claims checked against live web sources via Nimble, through LiteLLM."
        + ("" if run.live else " (cached replay — no API calls)"),
        "",
        f"- Supported: **{counts['supported']}**",
        f"- Contradicted: **{counts['contradicted']}**",
        f"- Unverifiable: **{counts['unverifiable']}**",
        "",
        "## Verdicts",
        "",
    ]
    for i, r in enumerate(run.results, 1):
        lines += [
            f"### {i}. {STATUS_LABEL[r.verdict.status]} — {r.claim.text}",
            "",
            f"> {r.claim.quote.strip()}",
            "",
            f"{r.verdict.rationale}",
            "",
        ]
        if r.verdict.correction:
            lines += [f"**Correction:** {r.verdict.correction}", ""]
        meta = f"`{r.claim.kind}` · confidence {r.verdict.confidence} · focus `{r.search_focus}` · {len(r.evidence)} sources"
        if r.verdict.deciding_url:
            meta += f" · decided by <{r.verdict.deciding_url}>"
        lines += [meta, ""]

    c = run.cost
    lines += [
        "## Cost",
        "",
        "| Component | Calls | Spend |",
        "|---|---:|---:|",
        f"| Nimble search | {c.search_queries} | ${c.search_spend:.4f} |",
        f"| Claim extraction | 1 | ${c.extract_spend:.4f} |",
        f"| Adjudication | {sum(1 for r in run.results if r.evidence)} | ${c.adjudicate_spend:.4f} |",
        f"| **Total** | | **${c.total:.4f}** |",
        f"| Per claim | | ${c.per_claim(len(run.results)):.4f} |",
        "",
    ]
    if run.skipped:
        lines += [f"## Not checked ({len(run.skipped)})", ""]
        lines += [f"- “{s.quote}” — {s.reason}" for s in run.skipped]
        lines += [""]

    path.write_text("\n".join(lines))
    return path
