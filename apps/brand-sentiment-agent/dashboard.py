"""Self-contained HTML dashboard: the "taking action on the data in a separate
interface" step. No external CDN or JS dependency. Pure HTML/CSS: grouped mini
bars are `<div>`s with CSS border-radius and a CSS-only hover tooltip.

Two series appear per theme (current window vs prior window), so a legend is
always shown per the dataviz skill's rule for >=2 series. The prior window uses
a de-emphasis gray and the current window the accent hue, the same convention the
skill's stat-tile spec uses for a trend line against its current point. Escalation
is a separate status signal (icon + label + a fixed status color), never implied
by the series hue, so a status color never impersonates a series.
"""

from __future__ import annotations

import html
import os
import webbrowser

from schema import SentimentResult, ThemeRow

_DIRECTION_ARROW = {"up": "&#9650;", "down": "&#9660;", "flat": "&#9679;", "new": "&#9733;"}


def _fmt_pct(row: ThemeRow) -> str:
    if row.change_pct is None:
        return "n/a"
    return f"{row.change_pct:+.0f}%"


def _delta_class(row: ThemeRow) -> str:
    if row.escalated:
        return "delta-critical"
    if row.direction == "down":
        return "delta-good"
    if row.direction == "up":
        return "delta-warning"
    return "delta-flat"


def _quotes_html(row: ThemeRow) -> str:
    if not row.representative_quotes:
        return ""
    items = "".join(
        f'<li>&ldquo;{html.escape(q["text"])}&rdquo; <span class="quote-meta">({html.escape(q["url"])}, {html.escape(q["date"])})</span></li>'
        for q in row.representative_quotes
    )
    return f'<ul class="quote-list">{items}</ul>'


def _theme_row(row: ThemeRow, max_negative: int) -> str:
    max_negative = max(max_negative, 1)
    prior_pct = max(2.0, round(row.prior_negative / max_negative * 100, 1)) if row.prior_negative else 0.0
    current_pct = max(2.0, round(row.current_negative / max_negative * 100, 1)) if row.current_negative else 0.0
    theme = html.escape(row.theme)
    badge = (
        '<span class="status-tag status-critical" title="Escalated">&#9888; <span class="status-label">escalated</span></span>'
        if row.escalated
        else ""
    )
    source_mix = ", ".join(f"{html.escape(k)}: {v}" for k, v in row.source_mix.items())
    return f"""
      <div class="theme-card {'escalated' if row.escalated else ''}">
        <div class="theme-head">
          <div class="theme-name">{theme} {badge}</div>
          <div class="theme-delta {_delta_class(row)}">{_DIRECTION_ARROW.get(row.direction, '')} {_fmt_pct(row)} <span class="delta-caption">neg. volume vs prior</span></div>
        </div>
        <div class="mini-bars" tabindex="0">
          <div class="mini-bar-row">
            <span class="mini-bar-label">prior</span>
            <div class="mini-bar-track"><div class="mini-bar-fill fill-prior" style="width:{prior_pct}%"><span class="mini-bar-value">{row.prior_negative}</span></div></div>
          </div>
          <div class="mini-bar-row">
            <span class="mini-bar-label">current</span>
            <div class="mini-bar-track"><div class="mini-bar-fill fill-current" style="width:{current_pct}%"><span class="mini-bar-value">{row.current_negative}</span></div></div>
          </div>
          <div class="theme-tooltip">
            <div>current window: {row.current_volume} items, {row.current_negative} negative</div>
            <div>prior window: {row.prior_volume} items, {row.prior_negative} negative</div>
            <div>source mix: {source_mix or '&ndash;'}</div>
            {_quotes_html(row)}
          </div>
        </div>
      </div>"""


def _table_rows(result: SentimentResult) -> str:
    rows = []
    for row in result.theme_table:
        rows.append(
            "<tr>"
            f"<td>{html.escape(row.theme)}</td>"
            f"<td class=\"num\">{row.current_volume}</td>"
            f"<td class=\"num\">{row.current_negative}</td>"
            f"<td class=\"num\">{row.prior_volume}</td>"
            f"<td class=\"num\">{row.prior_negative}</td>"
            f"<td class=\"num\">{_fmt_pct(row)}</td>"
            f"<td>{html.escape(row.direction)}</td>"
            f"<td>{'yes' if row.escalated else 'no'}</td>"
            "</tr>"
        )
    return "".join(rows)


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentiment triage &mdash; {brand}</title>
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
    --series-current: #2a78d6;
    --series-prior:   #c3c2b7;
    --status-critical: #d03b3b;
    --status-critical-text: #a52323;
    --delta-good:      #006300;
    --delta-warning:   #a86400;
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
      --series-current: #3987e5;
      --series-prior:   #52514e;
      --status-critical: #e66767;
      --status-critical-text: #ffb3b3;
      --delta-good:      #0ca30c;
      --delta-warning:   #eda100;
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
    --series-current: #3987e5;
    --series-prior:   #52514e;
    --status-critical: #e66767;
    --status-critical-text: #ffb3b3;
    --delta-good:      #0ca30c;
    --delta-warning:   #eda100;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; background: var(--page); }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--text-primary); padding: 32px 16px 64px; }}
  .viz-root {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .subtitle {{ color: var(--text-secondary); font-size: 14px; margin: 0 0 24px; }}
  .stat-tiles {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
  .stat-tile {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; flex: 1 1 160px; }}
  .stat-tile .label {{ color: var(--text-secondary); font-size: 12px; margin-bottom: 6px; }}
  .stat-tile .value {{ font-size: 26px; font-weight: 600; }}
  .card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 24px; margin-bottom: 20px; }}
  .card h2 {{ font-size: 15px; margin: 0 0 4px; }}
  .card .caption {{ color: var(--text-muted); font-size: 13px; margin: 0 0 16px; }}
  .legend {{ display: flex; gap: 18px; font-size: 12px; color: var(--text-secondary); margin-bottom: 20px; }}
  .legend-key {{ display: flex; align-items: center; gap: 6px; }}
  .legend-swatch {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
  .swatch-current {{ background: var(--series-current); }}
  .swatch-prior {{ background: var(--series-prior); }}
  .theme-card {{ border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; position: relative; }}
  .theme-card.escalated {{ border-color: var(--status-critical); }}
  .theme-card:last-child {{ margin-bottom: 0; }}
  .theme-head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; gap: 12px; flex-wrap: wrap; }}
  .theme-name {{ font-size: 14px; font-weight: 600; }}
  .theme-delta {{ font-size: 13px; font-weight: 600; white-space: nowrap; }}
  .delta-caption {{ font-size: 11px; font-weight: 400; color: var(--text-muted); }}
  .delta-critical {{ color: var(--status-critical-text); }}
  .delta-good {{ color: var(--delta-good); }}
  .delta-warning {{ color: var(--delta-warning); }}
  .delta-flat {{ color: var(--text-muted); }}
  .status-tag {{ font-size: 12px; color: var(--status-critical-text); font-weight: 600; }}
  .status-label {{
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.02em;
    border: 1px solid var(--status-critical); border-radius: 4px; padding: 1px 5px;
  }}
  .mini-bars {{ position: relative; }}
  .mini-bar-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
  .mini-bar-row:last-child {{ margin-bottom: 0; }}
  .mini-bar-label {{ width: 52px; flex: 0 0 52px; font-size: 11px; color: var(--text-muted); text-align: right; }}
  .mini-bar-track {{ flex: 1 1 auto; background: var(--grid); border-radius: 0 4px 4px 0; height: 18px; }}
  .mini-bar-fill {{ height: 18px; min-width: 26px; border-radius: 0 4px 4px 0; display: flex; align-items: center; justify-content: flex-end; padding-right: 6px; }}
  .fill-current {{ background: var(--series-current); }}
  .fill-prior {{ background: var(--series-prior); }}
  .mini-bar-value {{ color: #fff; font-size: 11px; font-weight: 600; }}
  .theme-tooltip {{
    position: absolute; left: 0; top: calc(100% + 6px); background: var(--text-primary); color: var(--page);
    padding: 10px 12px; border-radius: 6px; font-size: 12px; line-height: 1.6; width: 100%;
    opacity: 0; visibility: hidden; pointer-events: none; transition: opacity 0.12s ease; z-index: 2;
  }}
  .mini-bars:hover .theme-tooltip, .mini-bars:focus-within .theme-tooltip {{ opacity: 1; visibility: visible; }}
  .quote-list {{ margin: 6px 0 0; padding-left: 16px; }}
  .quote-meta {{ color: var(--text-muted); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--text-muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.02em; }}
  td.num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  th:nth-child(2), th:nth-child(3), th:nth-child(4), th:nth-child(5), th:nth-child(6) {{ text-align: right; }}
  .insufficient {{ color: var(--text-muted); font-size: 13px; }}
  .insufficient span {{ display: inline-block; margin-right: 10px; }}
</style>
</head>
<body>
  <div class="viz-root">
    <h1>Sentiment triage &mdash; {brand}</h1>
    <p class="subtitle">{window_days}-day current/prior windows &middot; as of {as_of_date}</p>

    <div class="stat-tiles">
      <div class="stat-tile"><div class="label">Escalated themes</div><div class="value">{escalated_count}</div></div>
      <div class="stat-tile"><div class="label">Themes tracked</div><div class="value">{theme_count}</div></div>
      <div class="stat-tile"><div class="label">Items after dedupe</div><div class="value">{deduped_count}</div></div>
      <div class="stat-tile"><div class="label">Below sample minimum</div><div class="value">{insufficient_count}</div></div>
    </div>

    <div class="card">
      <h2>Negative volume, current vs prior window</h2>
      <p class="caption">Hover a theme for the source mix and representative quotes. Escalated themes crossed the 25% rise threshold.</p>
      <div class="legend">
        <span class="legend-key"><span class="legend-swatch swatch-current"></span>current window</span>
        <span class="legend-key"><span class="legend-swatch swatch-prior"></span>prior window</span>
      </div>
      {theme_cards}
    </div>

    <div class="card">
      <h2>Full theme table</h2>
      <p class="caption">Every theme that cleared the minimum sample size.</p>
      <table>
        <thead>
          <tr><th>Theme</th><th>Current items</th><th>Current neg.</th><th>Prior items</th><th>Prior neg.</th><th>Change</th><th>Direction</th><th>Escalated</th></tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>

    {insufficient_section}
  </div>
</body>
</html>
"""


def render_dashboard(result: SentimentResult) -> str:
    max_negative = max(
        (max(r.current_negative, r.prior_negative) for r in result.theme_table),
        default=1,
    )
    ordered = result.triage_list + [r for r in result.theme_table if not r.escalated]
    theme_cards = "".join(_theme_row(r, max_negative) for r in ordered) or '<p class="insufficient">No theme cleared the minimum sample size this run.</p>'

    if result.insufficient_volume:
        items = "".join(f"<span>{html.escape(t)}</span>" for t in result.insufficient_volume)
        insufficient_section = f"""<div class="card">
      <h2>Insufficient volume</h2>
      <p class="caption">Dropped below the minimum sample size ({len(result.insufficient_volume)} theme(s)), not shown above.</p>
      <div class="insufficient">{items}</div>
    </div>"""
    else:
        insufficient_section = ""

    return _TEMPLATE.format(
        brand=html.escape(result.brand),
        window_days=result.window_days,
        as_of_date=html.escape(result.as_of_date),
        escalated_count=len(result.triage_list),
        theme_count=len(result.theme_table),
        deduped_count=result.total_items_after_dedupe,
        insufficient_count=len(result.insufficient_volume),
        theme_cards=theme_cards,
        table_rows=_table_rows(result),
        insufficient_section=insufficient_section,
    )


def write_dashboard(result: SentimentResult, out_dir: str, filename: str = "dashboard.html") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w") as f:
        f.write(render_dashboard(result))
    return path


def open_dashboard(path: str) -> None:
    webbrowser.open(f"file://{os.path.abspath(path)}")
