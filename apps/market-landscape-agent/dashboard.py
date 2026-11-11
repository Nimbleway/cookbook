"""Self-contained HTML dashboard: the "taking action on the data in a separate
interface" step. No external CDN or JS dependency.

The story here is a bottom-up estimate sitting orders of magnitude below several
published top-down figures, so a linear bar chart would make the bottom-up range
invisible next to an $11.91B estimate. This uses a **log-scale range chart**
instead: one horizontal axis in dollars, the bottom-up low-high estimate drawn as
a floating range bar, and each published estimate plotted as a status-colored dot
at its parsed dollar value. Dot color is state (flagged / consistent / unparseable),
never per-source identity, since which specific research firm a dot belongs to is
a tooltip/table fact, not something a reader needs to color-match at a glance.
"""

from __future__ import annotations

import html
import math
import os
import webbrowser

from schema import LandscapeResult, ReconciliationFlag


def _fmt_compact_dollar(v: float) -> str:
    v = abs(v)
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:,.0f}"


def _log_domain(values: list[float]) -> tuple[float, float]:
    positive = [v for v in values if v and v > 0]
    if not positive:
        return 1.0, 10.0
    lo = 10 ** math.floor(math.log10(min(positive)))
    hi = 10 ** math.ceil(math.log10(max(positive)))
    if lo == hi:
        hi = lo * 10
    return lo, hi


def _x_pct(value: float, domain_min: float, domain_max: float) -> float:
    value = max(value, domain_min)
    span = math.log10(domain_max) - math.log10(domain_min)
    return (math.log10(value) - math.log10(domain_min)) / span * 100 if span else 0.0


def _status_class(flag: ReconciliationFlag) -> str:
    if flag.parsed_published_value is None or flag.ratio_vs_midpoint is None:
        return "dot-unparsed"
    return "dot-flagged" if flag.flagged else "dot-good"


def _axis_ticks(domain_min: float, domain_max: float) -> str:
    ticks = []
    decades = round(math.log10(domain_max) - math.log10(domain_min))
    for i in range(decades + 1):
        v = domain_min * (10 ** i)
        pct = _x_pct(v, domain_min, domain_max)
        ticks.append(
            f'<div class="axis-tick" style="left:{pct}%">'
            f'<span class="axis-line"></span><span class="axis-label">{_fmt_compact_dollar(v)}</span></div>'
        )
    return "".join(ticks)


def _range_and_dots(result: LandscapeResult, domain_min: float, domain_max: float) -> str:
    b = result.bottom_up
    left_pct = 0.0 if b.low <= 0 else _x_pct(b.low, domain_min, domain_max)
    right_pct = _x_pct(max(b.high, domain_min), domain_min, domain_max)
    right_pct = max(right_pct, left_pct + 1.5)
    low_label = "$0" if b.low <= 0 else _fmt_compact_dollar(b.low)

    range_html = f"""
      <div class="range-bar" style="left:{left_pct}%; width:{right_pct - left_pct}%">
        <span class="range-tooltip">Bottom-up estimate: {low_label} &ndash; {_fmt_compact_dollar(b.high)} (confidence: {html.escape(b.confidence)})</span>
      </div>
      <div class="range-label" style="left:{left_pct}%">{low_label}</div>
      <div class="range-label" style="left:{right_pct}%">{_fmt_compact_dollar(b.high)}</div>"""

    positions: list[float] = []
    dots = []
    for flag in result.reconciliation:
        v = flag.parsed_published_value
        x = _x_pct(v, domain_min, domain_max) if v is not None and v > 0 else 2.0
        row = 0
        for placed in positions:
            if abs(x - placed) < 6:
                row += 1
        positions.append(x)
        top = 34 + row * 24
        ratio_txt = f"{flag.ratio_vs_midpoint:.1f}x the bottom-up midpoint" if flag.ratio_vs_midpoint is not None else "could not compute a ratio"
        dots.append(
            f'<div class="dot {_status_class(flag)}" style="left:{x}%; top:{top}px" tabindex="0">'
            f'<span class="dot-tooltip"><strong>{html.escape(flag.published_source)}</strong><br>'
            f'&ldquo;{html.escape(flag.published_figure)}&rdquo;<br>{ratio_txt}</span></div>'
        )
    return range_html + "".join(dots)


def _reconciliation_rows(result: LandscapeResult) -> str:
    rows = []
    for flag in result.reconciliation:
        ratio = f"{flag.ratio_vs_midpoint:.1f}x" if flag.ratio_vs_midpoint is not None else "n/a"
        rows.append(
            "<tr>"
            f"<td>{html.escape(flag.published_source)}</td>"
            f"<td>{html.escape(flag.published_figure)}</td>"
            f"<td class=\"num\">{ratio}</td>"
            f"<td>{'flagged' if flag.flagged else 'consistent'}</td>"
            "</tr>"
        )
    return "".join(rows)


def _vendor_rows(vendors, with_reason: bool) -> str:
    rows = []
    for v in vendors:
        link = f'<a href="{html.escape(v.evidence_urls[0])}">source</a>' if v.evidence_urls else "&ndash;"
        if with_reason:
            rows.append(
                "<tr>"
                f"<td>{html.escape(v.company_name)}</td>"
                f"<td>{html.escape(v.exclusion_reason or '')}</td>"
                "</tr>"
            )
        else:
            rows.append(
                "<tr>"
                f"<td>{html.escape(v.company_name)}</td>"
                f"<td>{html.escape(v.headquarters or '-')}</td>"
                f"<td>{html.escape(v.product_focus)}</td>"
                f"<td>{html.escape(v.funding_total or '-')}</td>"
                f"<td>{html.escape(v.disclosed_arr or '-')}</td>"
                f"<td>{link}</td>"
                "</tr>"
            )
    return "".join(rows)


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market landscape &mdash; {category}</title>
<style>
  :root {{
    color-scheme: light;
    --surface-1:      #fcfcfb;
    --page:           #f9f9f7;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:     #898781;
    --grid:           #e1e0d9;
    --border:         rgba(11,11,11,0.10);
    --series-1:       #2a78d6;
    --status-good:    #0ca30c;
    --status-critical: #d03b3b;
    --status-critical-text: #a52323;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) {{
      color-scheme: dark;
      --surface-1:      #1a1a19;
      --page:           #0d0d0d;
      --text-primary:   #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted:     #898781;
      --grid:           #2c2c2a;
      --border:         rgba(255,255,255,0.10);
      --series-1:       #3987e5;
      --status-good:    #0ca30c;
      --status-critical: #e66767;
      --status-critical-text: #ffb3b3;
    }}
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --surface-1:      #1a1a19;
    --page:           #0d0d0d;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --grid:           #2c2c2a;
    --border:         rgba(255,255,255,0.10);
    --series-1:       #3987e5;
    --status-good:    #0ca30c;
    --status-critical: #e66767;
    --status-critical-text: #ffb3b3;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; background: var(--page); }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--text-primary); padding: 32px 16px 64px; }}
  .viz-root {{ max-width: 940px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .subtitle {{ color: var(--text-secondary); font-size: 14px; margin: 0 0 8px; }}
  .criteria {{ color: var(--text-muted); font-size: 12px; margin: 0 0 24px; }}
  .stat-tiles {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
  .stat-tile {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; flex: 1 1 160px; }}
  .stat-tile .label {{ color: var(--text-secondary); font-size: 12px; margin-bottom: 6px; }}
  .stat-tile .value {{ font-size: 22px; font-weight: 600; }}
  .card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 24px; margin-bottom: 20px; }}
  .card h2 {{ font-size: 15px; margin: 0 0 4px; }}
  .card .caption {{ color: var(--text-muted); font-size: 13px; margin: 0 0 16px; }}
  .legend {{ display: flex; gap: 16px; font-size: 12px; color: var(--text-secondary); margin-bottom: 24px; flex-wrap: wrap; }}
  .legend-key {{ display: flex; align-items: center; gap: 6px; }}
  .legend-swatch {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
  .legend-pill {{ width: 20px; height: 10px; border-radius: 5px; display: inline-block; background: var(--series-1); }}
  .swatch-good {{ background: var(--status-good); }}
  .swatch-flagged {{ background: var(--status-critical); }}
  .swatch-unparsed {{ background: var(--text-muted); }}
  .chart-area {{ position: relative; height: 140px; margin: 0 8px 36px; }}
  .range-bar {{
    position: absolute; top: 8px; height: 24px; background: var(--series-1);
    border-radius: 12px; transform: translateX(0);
  }}
  .range-tooltip {{
    position: absolute; left: 50%; top: -8px; transform: translate(-50%, -100%);
    background: var(--text-primary); color: var(--page); padding: 6px 10px; border-radius: 6px;
    font-size: 12px; white-space: nowrap; opacity: 0; visibility: hidden; transition: opacity 0.12s ease; pointer-events: none;
  }}
  .range-bar:hover .range-tooltip {{ opacity: 1; visibility: visible; }}
  .range-label {{ position: absolute; top: 36px; font-size: 11px; color: var(--text-secondary); transform: translateX(-50%); font-variant-numeric: tabular-nums; }}
  .dot {{
    position: absolute; width: 12px; height: 12px; border-radius: 50%; transform: translate(-50%, -50%);
    border: 2px solid var(--surface-1); cursor: default;
  }}
  .dot-good {{ background: var(--status-good); }}
  .dot-flagged {{ background: var(--status-critical); }}
  .dot-unparsed {{ background: var(--text-muted); }}
  .dot-tooltip {{
    position: absolute; left: 50%; bottom: 18px; transform: translateX(-50%);
    background: var(--text-primary); color: var(--page); padding: 8px 10px; border-radius: 6px;
    font-size: 12px; line-height: 1.5; width: 240px; opacity: 0; visibility: hidden;
    transition: opacity 0.12s ease; pointer-events: none; z-index: 3;
  }}
  .dot:hover .dot-tooltip, .dot:focus .dot-tooltip {{ opacity: 1; visibility: visible; }}
  .axis {{ position: relative; height: 28px; border-top: 1px solid var(--grid); margin-top: 4px; }}
  .axis-tick {{ position: absolute; top: 0; transform: translateX(-50%); text-align: center; }}
  .axis-tick .axis-line {{ display: block; width: 1px; height: 6px; background: var(--grid); margin: 0 auto; }}
  .axis-tick .axis-label {{ display: block; font-size: 11px; color: var(--text-muted); margin-top: 4px; white-space: nowrap; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--text-muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.02em; }}
  td.num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  a {{ color: var(--series-1); text-decoration: none; font-size: 12px; }}
  a:hover {{ text-decoration: underline; }}
  .assumptions {{ font-size: 13px; color: var(--text-secondary); margin: 0; padding-left: 18px; }}
</style>
</head>
<body>
  <div class="viz-root">
    <h1>Market landscape &mdash; {category}</h1>
    <p class="subtitle">As of {as_of_date} &middot; confidence: {confidence}</p>
    <p class="criteria">Inclusion criteria: {criteria}</p>

    <div class="stat-tiles">
      <div class="stat-tile"><div class="label">Bottom-up estimate</div><div class="value">{range_label}</div></div>
      <div class="stat-tile"><div class="label">Included vendors</div><div class="value">{included_count}</div></div>
      <div class="stat-tile"><div class="label">Excluded candidates</div><div class="value">{excluded_count}</div></div>
      <div class="stat-tile"><div class="label">Published estimates flagged</div><div class="value">{flagged_count} / {published_count}</div></div>
    </div>

    <div class="card">
      <h2>Bottom-up estimate vs published figures (log scale)</h2>
      <p class="caption">Hover the range or a dot for the source and its ratio to the bottom-up midpoint.</p>
      <div class="legend">
        <span class="legend-key"><span class="legend-pill"></span>bottom-up range</span>
        <span class="legend-key"><span class="legend-swatch swatch-good"></span>published, consistent</span>
        <span class="legend-key"><span class="legend-swatch swatch-flagged"></span>published, flagged</span>
        <span class="legend-key"><span class="legend-swatch swatch-unparsed"></span>unparseable figure</span>
      </div>
      <div class="chart-area">
        {range_and_dots}
      </div>
      <div class="axis">{axis_ticks}</div>
      <p class="caption" style="margin-top:20px; margin-bottom:8px;">How the bottom-up range was built:</p>
      <ul class="assumptions">{assumptions}</ul>
    </div>

    <div class="card">
      <h2>Reconciliation detail</h2>
      <table>
        <thead><tr><th>Source</th><th>Published figure</th><th>Ratio vs midpoint</th><th>Status</th></tr></thead>
        <tbody>{reconciliation_rows}</tbody>
      </table>
    </div>

    <div class="card">
      <h2>Included vendors ({included_count})</h2>
      <table>
        <thead><tr><th>Company</th><th>HQ</th><th>Product focus</th><th>Funding</th><th>ARR</th><th>Evidence</th></tr></thead>
        <tbody>{included_rows}</tbody>
      </table>
    </div>

    <div class="card">
      <h2>Excluded candidates ({excluded_count})</h2>
      <table>
        <thead><tr><th>Company</th><th>Reason</th></tr></thead>
        <tbody>{excluded_rows}</tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""


def render_dashboard(result: LandscapeResult) -> str:
    b = result.bottom_up
    published_values = [f.parsed_published_value for f in result.reconciliation if f.parsed_published_value]
    domain_min, domain_max = _log_domain([b.high] + published_values + ([b.low] if b.low > 0 else []))

    flagged_count = sum(1 for f in result.reconciliation if f.flagged)
    assumptions = "".join(f"<li>{html.escape(a)}</li>" for a in b.assumptions)

    return _TEMPLATE.format(
        category=html.escape(result.category),
        as_of_date=html.escape(result.as_of_date),
        confidence=html.escape(b.confidence),
        criteria=html.escape("; ".join(result.inclusion_criteria)),
        range_label=f"{_fmt_compact_dollar(b.low)}&ndash;{_fmt_compact_dollar(b.high)}",
        included_count=len(result.included),
        excluded_count=len(result.excluded),
        flagged_count=flagged_count,
        published_count=len(result.reconciliation),
        range_and_dots=_range_and_dots(result, domain_min, domain_max),
        axis_ticks=_axis_ticks(domain_min, domain_max),
        assumptions=assumptions,
        reconciliation_rows=_reconciliation_rows(result),
        included_rows=_vendor_rows(result.included, with_reason=False),
        excluded_rows=_vendor_rows(result.excluded, with_reason=True),
    )


def write_dashboard(result: LandscapeResult, out_dir: str, filename: str = "dashboard.html") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w") as f:
        f.write(render_dashboard(result))
    return path


def open_dashboard(path: str) -> None:
    webbrowser.open(f"file://{os.path.abspath(path)}")
