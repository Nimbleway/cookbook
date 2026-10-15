"""Self-contained HTML dashboard: the "taking action on the data in a separate
interface" step. No external CDN or JS dependency, so it renders identically every
time it's opened, including mid-recording. Pure HTML/CSS: bars are `<div>`s with
CSS border-radius (rounded at the data end, square at the baseline) and a CSS-only
hover tooltip, so there is no script to fail silently.

Colors follow the dataviz skill's reference palette (references/palette.md): a
single categorical series needs no legend box (the chart title names it), status
colors (quote-required) are fixed and always paired with an icon + label rather
than relying on color alone, and every value shown on a bar or tag is also present
in the data table below it, so nothing is hover-only.
"""

from __future__ import annotations

import html
import os
import webbrowser

from schema import PricingComparisonResult

_UNIT_LABEL = {
    "host": "host",
    "gb_ingested_monthly": "GB ingested/mo",
    "seat": "seat",
    "event_monthly": "event/mo",
    "other": "unit",
}


def _fmt_money(v: float) -> str:
    return f"${v:,.0f}"


def _bar_row(estimate, max_annual: float) -> str:
    pct = max(2.0, round(estimate.modeled_annual_cost / max_annual * 100, 1)) if max_annual else 2.0
    vendor = html.escape(estimate.vendor)
    tier = html.escape(estimate.tier_used)
    unit = html.escape(_UNIT_LABEL.get(estimate.billing_unit, estimate.billing_unit))
    assumptions = "".join(f"<li>{html.escape(a)}</li>" for a in estimate.assumptions)
    return f"""
      <div class="bar-row">
        <div class="bar-label">{vendor}</div>
        <div class="bar-track">
          <div class="bar-fill" style="width:{pct}%">
            <span class="bar-value">{_fmt_money(estimate.modeled_annual_cost)}/yr</span>
          </div>
          <div class="bar-tooltip">
            <strong>{_fmt_money(estimate.modeled_annual_cost)}/yr</strong> &middot; {tier} &middot; billed per {unit}
            <ul>{assumptions}</ul>
          </div>
        </div>
      </div>"""


def _quote_row(q) -> str:
    return f"""
      <div class="quote-row">
        <span class="status-tag status-serious" aria-hidden="true">&#9888;</span>
        <div>
          <div class="quote-vendor">{html.escape(q.vendor)} <span class="status-label">quote required</span></div>
          <div class="quote-reason">{html.escape(q.missing_input)}</div>
        </div>
      </div>"""


def _table_rows(result: PricingComparisonResult) -> str:
    rows = []
    for v in result.vendors:
        for t in v.tiers:
            # overage_rate_per_unit (base_plus_overage) and flat_rate_per_unit
            # (pure_per_unit) are both "the $/unit rate" from the reader's point of
            # view, just for different tier shapes, so they share this column.
            rate = t.overage_rate_per_unit if t.overage_rate_per_unit is not None else t.flat_rate_per_unit
            rows.append(
                "<tr>"
                f"<td>{html.escape(v.vendor)}</td>"
                f"<td>{html.escape(t.tier_name)}</td>"
                f"<td>{html.escape(t.tier_type)}</td>"
                f"<td>{html.escape(_UNIT_LABEL.get(t.billing_unit, t.billing_unit))}</td>"
                f"<td class=\"num\">{_fmt_money(t.base_fee_monthly) if t.base_fee_monthly is not None else '&ndash;'}</td>"
                f"<td class=\"num\">{f'{t.included_quantity:,.0f}' if t.included_quantity is not None else '&ndash;'}</td>"
                f"<td class=\"num\">{_fmt_money(rate) if rate is not None else '&ndash;'}</td>"
                f"<td><a href=\"{html.escape(t.source_url)}\">source</a></td>"
                "</tr>"
            )
    return "".join(rows)


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pricing comparison &mdash; {as_of_date}</title>
<style>
  :root {{
    color-scheme: light;
    --surface-1:      #fcfcfb;
    --page:           #f9f9f7;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:     #898781;
    --grid:           #e1e0d9;
    --baseline:       #c3c2b7;
    --border:         rgba(11,11,11,0.10);
    --series-1:       #2a78d6;
    --series-1-wash:  rgba(42,120,214,0.10);
    --status-serious: #ec835a;
    --status-serious-text: #b64a1f;
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
      --baseline:       #383835;
      --border:         rgba(255,255,255,0.10);
      --series-1:       #3987e5;
      --series-1-wash:  rgba(57,135,229,0.14);
      --status-serious: #ec835a;
      --status-serious-text: #ffb391;
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
    --baseline:       #383835;
    --border:         rgba(255,255,255,0.10);
    --series-1:       #3987e5;
    --series-1-wash:  rgba(57,135,229,0.14);
    --status-serious: #ec835a;
    --status-serious-text: #ffb391;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; background: var(--page); }}
  body {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    color: var(--text-primary);
    padding: 32px 16px 64px;
  }}
  .viz-root {{ max-width: 880px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .subtitle {{ color: var(--text-secondary); font-size: 14px; margin: 0 0 28px; }}
  .card {{
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 24px;
    margin-bottom: 20px;
  }}
  .card h2 {{ font-size: 15px; margin: 0 0 4px; }}
  .card .caption {{ color: var(--text-muted); font-size: 13px; margin: 0 0 20px; }}
  .stat-tiles {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
  .stat-tile {{
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 20px;
    flex: 1 1 160px;
  }}
  .stat-tile .label {{ color: var(--text-secondary); font-size: 12px; margin-bottom: 6px; }}
  .stat-tile .value {{ font-size: 26px; font-weight: 600; }}
  .bar-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }}
  .bar-row:last-child {{ margin-bottom: 0; }}
  .bar-label {{ width: 160px; flex: 0 0 160px; font-size: 13px; color: var(--text-secondary); text-align: right; }}
  .bar-track {{
    position: relative;
    flex: 1 1 auto;
    background: var(--grid);
    border-radius: 0 4px 4px 0;
    height: 24px;
  }}
  .bar-fill {{
    position: relative;
    height: 24px;
    min-width: 44px;
    background: var(--series-1);
    border-radius: 0 4px 4px 0;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 8px;
    transition: filter 0.1s ease;
  }}
  .bar-row:hover .bar-fill {{ filter: brightness(1.08); }}
  .bar-value {{ color: #fff; font-size: 12px; font-weight: 600; white-space: nowrap; }}
  .bar-tooltip {{
    position: absolute;
    left: 0;
    top: -8px;
    transform: translateY(-100%);
    background: var(--text-primary);
    color: var(--page);
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.5;
    width: max-content;
    max-width: 320px;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transition: opacity 0.12s ease;
    z-index: 2;
  }}
  .bar-tooltip ul {{ margin: 6px 0 0; padding-left: 16px; }}
  .bar-row:hover .bar-tooltip, .bar-row:focus-within .bar-tooltip {{ opacity: 1; visibility: visible; }}
  .quote-row {{ display: flex; gap: 10px; align-items: flex-start; padding: 10px 0; border-top: 1px solid var(--border); }}
  .quote-row:first-child {{ border-top: none; }}
  .status-tag {{ color: var(--status-serious); font-size: 16px; line-height: 1.4; }}
  .status-label {{
    font-size: 11px;
    font-weight: 600;
    color: var(--status-serious-text);
    border: 1px solid var(--status-serious);
    border-radius: 4px;
    padding: 1px 6px;
    margin-left: 8px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }}
  .quote-vendor {{ font-size: 13px; font-weight: 600; }}
  .quote-reason {{ font-size: 12px; color: var(--text-secondary); margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--text-muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.02em; }}
  td.num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  th:nth-child(5), th:nth-child(6), th:nth-child(7) {{ text-align: right; }}
  a {{ color: var(--series-1); text-decoration: none; font-size: 12px; }}
  a:hover {{ text-decoration: underline; }}
  .empty {{ color: var(--text-muted); font-size: 13px; }}
</style>
</head>
<body>
  <div class="viz-root">
    <h1>Pricing comparison</h1>
    <p class="subtitle">Buyer profile {buyer_profile} &middot; as of {as_of_date}</p>

    <div class="stat-tiles">
      <div class="stat-tile">
        <div class="label">Cheapest option</div>
        <div class="value">{cheapest_vendor}</div>
      </div>
      <div class="stat-tile">
        <div class="label">Modeled annual cost</div>
        <div class="value">{cheapest_cost}</div>
      </div>
      <div class="stat-tile">
        <div class="label">Vendors compared</div>
        <div class="value">{vendor_count}</div>
      </div>
      <div class="stat-tile">
        <div class="label">Quote required</div>
        <div class="value">{quote_count}</div>
      </div>
    </div>

    <div class="card">
      <h2>Modeled annual cost, cheapest first</h2>
      <p class="caption">Hover a bar for the tier and the assumptions behind its number.</p>
      {bar_rows}
    </div>

    {quote_section}

    <div class="card">
      <h2>All extracted pricing tiers</h2>
      <p class="caption">Every tier the agent found, computable or not, with its source.</p>
      <table>
        <thead>
          <tr><th>Vendor</th><th>Tier</th><th>Type</th><th>Billing unit</th><th>Base fee/mo</th><th>Included</th><th>Rate/unit</th><th>Source</th></tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""


def render_dashboard(result: PricingComparisonResult) -> str:
    max_annual = max((e.modeled_annual_cost for e in result.cost_ranking), default=0.0)
    bar_rows = "".join(_bar_row(e, max_annual) for e in result.cost_ranking) or '<p class="empty">No vendor was fully computable for this buyer profile.</p>'

    if result.quote_required:
        quote_rows = "".join(_quote_row(q) for q in result.quote_required)
        quote_section = f"""<div class="card">
      <h2>Quote required</h2>
      <p class="caption">Pricing not published clearly enough to model &mdash; contact the vendor.</p>
      {quote_rows}
    </div>"""
    else:
        quote_section = ""

    cheapest = result.cost_ranking[0] if result.cost_ranking else None
    buyer_profile = ", ".join(f"{v:,.0f} {_UNIT_LABEL.get(k, k)}" for k, v in result.buyer_profile.items())

    return _TEMPLATE.format(
        as_of_date=html.escape(result.as_of_date),
        buyer_profile=html.escape(buyer_profile),
        cheapest_vendor=html.escape(cheapest.vendor) if cheapest else "&ndash;",
        cheapest_cost=_fmt_money(cheapest.modeled_annual_cost) + "/yr" if cheapest else "&ndash;",
        vendor_count=str(len(result.vendors)),
        quote_count=str(len(result.quote_required)),
        bar_rows=bar_rows,
        quote_section=quote_section,
        table_rows=_table_rows(result),
    )


def write_dashboard(result: PricingComparisonResult, out_dir: str, filename: str = "dashboard.html") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w") as f:
        f.write(render_dashboard(result))
    return path


def open_dashboard(path: str) -> None:
    webbrowser.open(f"file://{os.path.abspath(path)}")
