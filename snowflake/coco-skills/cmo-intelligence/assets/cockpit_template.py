"""CMO digital-shelf cockpit — premium SPA, hosted Streamlit-in-Snowflake, brand-agnostic.
A single-page app (sticky pill-nav, AI Insights, share-of-shelf, content health, voice-of-customer,
AI-answer share, trends) over one per-app schema's view set. Marketing focus.

This is a TEMPLATE: __DB__ / __SCHEMA__ / __BRAND__ / __CATEGORY__ are substituted at provision time."""
import json, re
import streamlit as st
import streamlit.components.v1 as components
from snowflake.snowpark.context import get_active_session

BRAND = "__BRAND__"
SCHEMA = "__SCHEMA__"
CATEGORY = "__CATEGORY__"
DB = "__DB__"
S = DB + "." + SCHEMA          # every object lands in one per-app schema
A = S                          # analytics views live alongside raw tables
L = S                          # alert views too
AGENT_NAME = ((BRAND or CATEGORY).upper().replace(" ", "_")) + "_SHELF_ANALYST"  # matches agent.sql

st.set_page_config(page_title=BRAND + " digital shelf", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>#MainMenu,header,footer{visibility:hidden;height:0;}.block-container{padding:0 !important;max-width:100% !important;}"
            "[data-testid='stAppViewBlockContainer']{padding:0 !important;}"
            "[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none !important;}</style>", unsafe_allow_html=True)
session = get_active_session()
SNAP = "(SELECT MAX(snapshot_date) FROM " + S + ".RAW_PDP)"

# Shell-first: paint a branded loading note immediately so the first (cold) load
# isn't a blank screen with a cryptic "Running rows(...)". Cleared right before
# the cockpit renders. The real fix for load time is fewer queries (below) — and,
# longer-term, a Task-precomputed snapshot the cockpit just SELECTs.
_loading = st.empty()
_loading.info("Loading the " + (BRAND or CATEGORY or "digital shelf") + " cockpit — assembling live shelf data…")


@st.cache_data(ttl=300)
def rows(sql):
    try:
        return [list(r) for r in session.sql(sql).collect()]
    except Exception:
        return []


def one(sql, n=1):
    """First row of a query, or [None]*n if it errors / returns nothing."""
    r = rows(sql)
    return r[0] if r else [None] * n


def num(v):
    try:
        f = float(v); return int(f) if f == int(f) else round(f, 1)
    except (TypeError, ValueError):
        return v


def q(s):
    return str(s).replace("'", "''")


# ── Dynamic competitive set: focal first, then top brand tiers by share ──
# Category-overview mode (no focal brand configured) leads with the market-
# leading tier so every surface still has a subject.
_brank = rows("SELECT brand_tier, SUM(products_in_serp) FROM " + A + ".V_SHARE_OF_SHELF WHERE snapshot_date=" + SNAP + " GROUP BY 1 ORDER BY 2 DESC")
_GENERIC = {"other / marketplace", "private label", "other named brand", "unknown", "generic", "n/a", "other"}
_order = [r[0] for r in _brank if r[0]]
OVERVIEW = not (BRAND and BRAND.strip())
_lead = next((b for b in _order if b.lower() not in _GENERIC), (_order[0] if _order else None))
FOCAL = _lead if OVERVIEW else BRAND
COMP = [b for b in _order if b != FOCAL and b.lower() not in _GENERIC][:7]
BRANDS = ([FOCAL] + COMP) if FOCAL else _order[:8]


def ff(alias=""):
    """Focal-row filter: is_focal in brand mode; brand_tier match in overview mode."""
    p = (alias + ".") if alias else ""
    if OVERVIEW:
        return (p + "brand_tier='" + q(FOCAL) + "'") if FOCAL else "FALSE"
    return p + "is_focal"
BRANDS_IN = "(" + ",".join("'" + q(b) + "'" for b in BRANDS) + ")" if BRANDS else "('')"
_PAL = ["#e32123", "#EA580C", "#D97706", "#0EA5E9", "#8b5cf6", "#2563eb", "#ec4899", "#84cc16", "#0d9488", "#94A3B8"]
BCMAP = {}
_ci = 0
for _b in BRANDS:
    if _b == FOCAL:
        BCMAP[_b] = "#234291"
    else:
        BCMAP[_b] = _PAL[_ci % len(_PAL)]; _ci += 1
BCMAP.setdefault("Other / Marketplace", "#E2E8F0")
BCMAP.setdefault("Private label", "#CBD5E1")

# Global signals reused across retailer slices (defensive: views may be empty on a fresh perimeter)
ai_focal = one("SELECT ROUND(AVG(share_of_answer_pct),0) FROM " + A + ".V_AI_SHARE_OF_ANSWER WHERE brand='" + q(FOCAL) + "'")[0]
_dl = one("SELECT d_share, d_sponsored, d_oos FROM " + A + ".V_TREND_KPI ORDER BY snapshot_date DESC LIMIT 1", 3)
d_share, d_sponsored, d_oos = num(_dl[0]), num(_dl[1]), num(_dl[2])
data = {}


# ── Build EVERY retailer slice from a handful of GROUP BY passes, not ~9 queries
# per slice. The cold-load was dominated by a per-retailer bundle() loop that
# re-ran the heavy resolution views once per slice; here each metric is fetched
# once (GROUP BY retailer, with ROLLUP giving the "All" row), then pivoted in
# Python into data["slices"][<retailer|All>]. ──
_kpi_share = rows("SELECT retailer,"
    " ROUND(AVG(CASE WHEN brand_tier='" + q(FOCAL) + "' THEN share_of_shelf_pct END),0),"
    " SUM(IFF(brand_tier='" + q(FOCAL) + "',products_in_serp,0)),"
    " ROUND(AVG(CASE WHEN brand_tier='" + q(FOCAL) + "' THEN sponsored_share_pct END),1)"
    " FROM " + A + ".V_SHARE_OF_SHELF WHERE snapshot_date=" + SNAP + " GROUP BY ROLLUP(retailer)")
_kpi_unit = rows("SELECT retailer, ROUND(AVG(unit_price_amount),2) FROM " + A + ".V_BRAND_CLASSIFIED WHERE " + ff() + " AND unit_price_amount IS NOT NULL AND snapshot_date=" + SNAP + " GROUP BY ROLLUP(retailer)")
_kpi_content = rows("SELECT retailer, ROUND(AVG(content_score),0) FROM " + A + ".V_CONTENT_HEALTH WHERE " + ff() + " AND snapshot_date=" + SNAP + " GROUP BY ROLLUP(retailer)")
if not OVERVIEW:
    # brand mode: V_ALERT_OOS is the single source of truth (incl. severity)
    _kpi_oos = rows("SELECT retailer, COUNT(*) FROM " + L + ".V_ALERT_OOS WHERE snapshot_date=" + SNAP + " GROUP BY ROLLUP(retailer)")
    _oos_rows = rows("SELECT product_name, product_image, product_url, retailer, position, best_price, severity"
                     " FROM " + L + ".V_ALERT_OOS WHERE snapshot_date=" + SNAP + " ORDER BY position LIMIT 120")
else:
    # overview mode: same severity buckets over the leading tier
    _ow = " AND " + ff() + " AND product_out_of_stock AND snapshot_date=" + SNAP
    _kpi_oos = rows("SELECT retailer, COUNT(*) FROM " + A + ".V_BRAND_CLASSIFIED WHERE 1=1" + _ow + " GROUP BY ROLLUP(retailer)")
    _oos_rows = rows("SELECT product_name, product_image, product_url, retailer, position, best_price,"
                     " CASE WHEN position<=5 THEN 'CRITICAL' WHEN position<=24 THEN 'HIGH' WHEN position<=48 THEN 'MODERATE' ELSE 'LOW' END"
                     " FROM " + A + ".V_BRAND_CLASSIFIED WHERE 1=1" + _ow + " ORDER BY position LIMIT 120")
_sos = rows("SELECT retailer, brand_tier, SUM(products_in_serp) FROM " + A + ".V_SHARE_OF_SHELF WHERE snapshot_date=" + SNAP + " GROUP BY 1,2")
_price = rows("SELECT retailer, ROUND(AVG(IFF(" + ff() + ",unit_price_amount,NULL)),2), ROUND(AVG(IFF(NOT (" + ff() + "),unit_price_amount,NULL)),2) FROM " + A + ".V_BRAND_CLASSIFIED WHERE unit_price_amount IS NOT NULL AND snapshot_date=" + SNAP + " GROUP BY retailer")
_grades = rows("SELECT retailer, content_grade, COUNT(*) FROM " + A + ".V_CONTENT_HEALTH WHERE " + ff() + " AND snapshot_date=" + SNAP + " GROUP BY 1,2")
_weak = rows("SELECT product_name, product_image, product_url, retailer, content_grade, content_score, number_of_reviews FROM " + A + ".V_CONTENT_HEALTH WHERE " + ff() + " AND snapshot_date=" + SNAP + " ORDER BY content_score ASC LIMIT 120")


def _byret(rws):  # index ROLLUP results; the retailer-NULL row is the "All" aggregate
    return {(r[0] if r[0] is not None else "All"): r for r in rws}


_si, _ui, _ci2, _oi = _byret(_kpi_share), _byret(_kpi_unit), _byret(_kpi_content), _byret(_kpi_oos)


def _sos_list(ret):  # share-of-shelf % by brand tier within the slice
    agg = {}
    for r in _sos:
        if ret is None or r[0] == ret:
            agg[r[1]] = agg.get(r[1], 0) + (r[2] or 0)
    tot = sum(agg.values()) or 1
    return sorted([[b, num(round(v * 100.0 / tot, 1))] for b, v in agg.items() if b], key=lambda x: -(x[1] or 0))


def _grades_map(ret):
    m = {}
    for r in _grades:
        if (ret is None or r[0] == ret) and r[0]:
            m.setdefault(r[0], {})[r[1]] = int(r[2])
    return m


def _prods(rws, ret, kind):
    out = []
    for r in rws:
        if ret is not None and r[3] != ret:
            continue
        if kind == "oos":
            out.append({"name": r[0], "img": r[1], "url": r[2], "retailer": r[3], "position": int(r[4]) if r[4] is not None else None, "price": num(r[5]), "sev": r[6]})
        else:
            out.append({"name": r[0], "img": r[1], "url": r[2], "retailer": r[3], "grade": r[4], "score": int(r[5]) if r[5] is not None else 0, "reviews": int(r[6]) if r[6] is not None else 0})
        if len(out) >= 9:
            break
    return out


def slice_for(ret):
    """Assemble one slice (ret=None → All) from the pre-fetched grouped results."""
    key = "All" if ret is None else ret
    ks = _si.get(key, [None, None, None, None]); us = _ui.get(key, [None, None])
    cs = _ci2.get(key, [None, None]); oo = _oi.get(key, [None, 0])
    b = {"kpi": {"share": num(ks[1]), "skus": int(ks[2] or 0), "sponsored": num(ks[3]), "unit_price": num(us[1]),
                 "oos": int(oo[1] or 0), "ai": num(ai_focal) if ai_focal is not None else 0, "content": num(cs[1]),
                 "d_share": (d_share if ret is None else None), "d_sponsored": (d_sponsored if ret is None else None), "d_oos": (d_oos if ret is None else None)}}
    b["share"] = _sos_list(ret)
    b["pricing"] = [[r[0], num(r[1]), num(r[2])] for r in _price if (ret is None or r[0] == ret)]
    b["content_grades"] = _grades_map(ret)
    b["oos_products"] = _prods(_oos_rows, ret, "oos")
    b["weak_products"] = _prods(_weak, ret, "weak")
    return b


# Retailers are config-driven (CFG_QUERIES / retailer_map), so derive the axis from data.
_rets = sorted({r[0] for r in _sos if r[0]})
data["retailers"] = ["All"] + _rets
data["slices"] = {"All": slice_for(None)}
for _r in _rets:
    data["slices"][_r] = slice_for(_r)
_b0 = data["slices"]["All"]
data["kpi"] = _b0["kpi"]; data["share"] = _b0["share"]; data["pricing"] = _b0["pricing"]
data["content_grades"] = _b0["content_grades"]; data["oos_products"] = _b0["oos_products"]; data["weak_products"] = _b0["weak_products"]

data["by_retailer"] = {}
for ret, brand, pct in rows("SELECT retailer, brand_tier, share_of_shelf_pct FROM " + A + ".V_SHARE_OF_SHELF WHERE snapshot_date=" + SNAP + " AND brand_tier IN " + BRANDS_IN + " ORDER BY retailer, share_of_shelf_pct DESC"):
    data["by_retailer"].setdefault(ret, []).append([brand, num(pct)])
data["ai_share"] = [[r[0], num(r[1])] for r in rows("SELECT brand, ROUND(AVG(share_of_answer_pct),1) FROM " + A + ".V_AI_SHARE_OF_ANSWER GROUP BY 1 ORDER BY 2 DESC")]
data["voc_pos"] = [[r[0], num(r[1])] for r in rows("SELECT theme, pct_within_sentiment FROM " + A + ".V_SENTIMENT_SUMMARY WHERE sentiment='positive' ORDER BY mentions DESC LIMIT 6")]
data["voc_fix"] = [[r[0], num(r[1])] for r in rows("SELECT theme, pct_within_sentiment FROM " + A + ".V_SENTIMENT_SUMMARY WHERE sentiment='negative' ORDER BY mentions DESC LIMIT 6")]
data["top_sources"] = [[r[0], num(r[1])] for r in rows("SELECT domain, share_pct FROM " + A + ".V_AI_TOP_SOURCES ORDER BY citations DESC LIMIT 8")]
data["nba"] = [{"sev": r[0], "area": r[1], "head": r[2], "metric": r[3], "act": r[4]} for r in rows("SELECT severity, area, headline, metric, recommended_action FROM " + A + ".V_NEXT_BEST_ACTIONS ORDER BY priority")]

# ── Per-brand review analysis (what people say about each brand) ──
_VJOIN = "(SELECT DISTINCT retailer,product_id,brand_tier FROM " + A + ".V_BRAND_CLASSIFIED WHERE snapshot_date=" + SNAP + ") bc"
_themes = rows("SELECT bc.brand_tier, v.sentiment, v.theme, SUM(v.mention_count)"
               " FROM " + S + ".RAW_VOC v JOIN " + _VJOIN + " ON bc.retailer=v.retailer AND bc.product_id=v.product_id"
               " WHERE v.sentiment IN ('positive','negative') AND v.theme IS NOT NULL AND bc.brand_tier IN " + BRANDS_IN + " GROUP BY 1,2,3")
_tot = rows("SELECT bc.brand_tier, SUM(v.mention_count), ROUND(AVG(v.recommend_pct),0), ROUND(AVG(v.star_pct_5),0),"
            " SUM(IFF(v.sentiment='positive',v.mention_count,0)), SUM(IFF(v.sentiment='negative',v.mention_count,0)), SUM(IFF(v.sentiment='neutral',v.mention_count,0))"
            " FROM " + S + ".RAW_VOC v JOIN " + _VJOIN + " ON bc.retailer=v.retailer AND bc.product_id=v.product_id"
            " WHERE bc.brand_tier IN " + BRANDS_IN + " GROUP BY 1")
_summ = rows("SELECT brand_tier, ai_summary FROM ("
             " SELECT bc.brand_tier, v.ai_summary, ROW_NUMBER() OVER(PARTITION BY bc.brand_tier ORDER BY v.mention_count DESC NULLS LAST) rn"
             " FROM " + S + ".RAW_VOC v JOIN " + _VJOIN + " ON bc.retailer=v.retailer AND bc.product_id=v.product_id"
             " WHERE v.ai_summary IS NOT NULL AND bc.brand_tier IN " + BRANDS_IN + ") WHERE rn=1")
_stot, _agg = {}, {}
for bt, sent, th, m in _themes:
    _stot[(bt, sent)] = _stot.get((bt, sent), 0) + (m or 0)
    _agg.setdefault((bt, sent), []).append((th, m or 0))
_br = {}
for bt in BRANDS:
    pos = sorted(_agg.get((bt, 'positive'), []), key=lambda x: -x[1])[:5]
    neg = sorted(_agg.get((bt, 'negative'), []), key=lambda x: -x[1])[:5]
    pt = _stot.get((bt, 'positive'), 0) or 1
    nt = _stot.get((bt, 'negative'), 0) or 1
    _br[bt] = {"pos": [[t, round(m * 100.0 / pt, 1)] for t, m in pos], "neg": [[t, round(m * 100.0 / nt, 1)] for t, m in neg]}
for bt, tot, rec, star, p, n, nu in _tot:
    if bt in _br:
        s = (p or 0) + (n or 0) + (nu or 0) or 1
        _br[bt].update({"mentions": int(tot or 0), "rec": num(rec), "star": num(star),
                        "split": [round((p or 0) * 100.0 / s), round((n or 0) * 100.0 / s), round((nu or 0) * 100.0 / s)]})
for bt, summ in _summ:
    if bt in _br:
        _br[bt]["summary"] = (summ or "")[:300]
data["brand_order"] = [bt for bt in BRANDS if _br.get(bt, {}).get("mentions")]
data["brand_reviews"] = {bt: _br[bt] for bt in data["brand_order"]}

# Trends over snapshots (a fresh perimeter has one day; the daily task accumulates more)
tr = rows("SELECT snapshot_date, brand_tier, share_of_shelf_pct FROM " + A + ".V_TREND_SOS_DAILY WHERE brand_tier IN " + BRANDS_IN + " ORDER BY snapshot_date")
dates = sorted(set(str(r[0]) for r in tr))
series = {}
for dt, bt, pct in tr:
    series.setdefault(bt, {})[str(dt)] = num(pct)
data["trend_dates"] = dates
data["trend_share"] = {bt: [series[bt].get(dt) for dt in dates] for bt in series}
data["trend_focal"] = data["trend_share"].get(FOCAL, [])
data["trend_comp"] = COMP[:3]
sp = rows("SELECT snapshot_date, sponsored_pct, oos FROM " + A + ".V_TREND_KPI ORDER BY snapshot_date")
data["trend_sponsored"] = [num(r[1]) for r in sp]
data["trend_oos"] = [int(r[2]) if r[2] is not None else 0 for r in sp]


# Exec briefing + pre-answered assistant prompts (Cortex, cached)
def cortex(prompt):
    try:
        return session.sql("SELECT AI_COMPLETE('__CORTEX_MODEL__', ?)", params=[prompt]).collect()[0][0].strip()
    except Exception:
        return "(Cortex unavailable)"


CTX = (BRAND + ": share of shelf " + str(data['kpi']['share']) + "% (chg " + str(d_share) + " vs prev day), share of AI answer " + str(data['kpi']['ai']) + "%, "
       "sponsored " + str(data['kpi']['sponsored']) + "%, " + str(data['kpi']['oos']) + " out-of-stock, content " + str(data['kpi']['content']) + "/100. "
       "Share by brand: " + "; ".join(str(b) + " " + str(p) + "%" for b, p in data["share"][:8]) + ". "
       "Top complaints: " + ", ".join(str(t) for t, _ in data["voc_fix"][:3]) + ". "
       "Next best actions: " + " | ".join(str(a['head']) + ": " + str(a['metric']) for a in data["nba"]))


# NOTE: the cold-load exec briefing (4 sequential Cortex COMPLETE calls) was REMOVED for
# performance — its output (briefing/qa) was never rendered by the HTML, so it only blocked
# first paint by 30-80s. CTX above is still built (cheap string) for the live-chat fallback.

# ── Snapshot label + raw shelf rows + totals (for D&T / Raw Data tabs) ──
data["snap_date"] = one("SELECT TO_CHAR(MAX(snapshot_date),'Mon DD, YYYY') FROM " + S + ".RAW_PDP")[0] or ""
data["total_skus"] = int(one("SELECT COUNT(*) FROM " + A + ".V_BRAND_CLASSIFIED WHERE snapshot_date=" + SNAP)[0] or 0)
data["raw_rows"] = [{"name": r[0], "brand": r[1], "retailer": r[2], "pos": int(r[3]) if r[3] is not None else None,
                     "price": num(r[4]), "oos": bool(r[5]), "kk": bool(r[6])}
                    for r in rows("SELECT product_name, brand_tier, retailer, position, best_price, product_out_of_stock, is_focal FROM " + A + ".V_BRAND_CLASSIFIED WHERE snapshot_date=" + SNAP + " AND product_name IS NOT NULL ORDER BY is_focal DESC, position LIMIT 40")]

# ── AI Insights (4 cards) + week-in-three scorecard, derived from live data ──
_ins = []
if data["kpi"]["oos"]:
    _ins.append({"tag": "alert", "tab": "Retailer",
                 "headline": str(data["kpi"]["oos"]) + " " + BRAND + " SKUs out of stock on the shelf",
                 "detail": "Out-of-stock listings in top search slots send a ready-to-buy shopper straight to a competitor. Fix availability first."})
_kk = [x for x in (data["trend_focal"] or []) if x is not None]
if len(_kk) >= 2:
    _chg = round(_kk[-1] - _kk[0], 1)
    _ins.append({"tag": "trend", "tab": "Analytics",
                 "headline": "Share of shelf " + ("up" if _chg >= 0 else "down") + " " + str(abs(_chg)) + "pp — now " + str(_kk[-1]) + "%",
                 "detail": "Moved from " + str(_kk[0]) + "% to " + str(_kk[-1]) + "% over the window while sponsored share rose across the set — competitors are buying visibility."})
if data["voc_fix"]:
    _t, _p = data["voc_fix"][0]
    _ins.append({"tag": "risk", "tab": "Brand",
                 "headline": '"' + str(_t) + '" is the #1 complaint — ' + str(_p) + "% of negative mentions",
                 "detail": "A fixable issue quietly eroding ratings and repeat purchase — worth addressing this quarter."})
_src = data["top_sources"][0][0] if data["top_sources"] else "retailer & review sites"
_ins.append({"tag": "opportunity", "tab": "Brand",
             "headline": BRAND + " in only " + str(data["kpi"]["ai"]) + "% of AI answers — upside in answer engines",
             "detail": "ChatGPT and Perplexity lean on " + str(_src) + " and social to recommend " + CATEGORY + " — earn presence there to shape what the AI says."})
data["insights"] = _ins[:4]

# Week in three cards: win / risk / invest
_best_ret, _best_share = None, -1
for _ret, _lst in data["by_retailer"].items():
    for _b, _pct in _lst:
        if _b == FOCAL and (_pct or 0) > _best_share:
            _best_ret, _best_share = _ret, _pct
_sc = []
if _best_ret:
    _sc.append({"kind": "win", "label": "Defend", "metric": str(_best_share) + "%",
                "headline": BRAND + " leads on " + str(_best_ret) + " — " + str(_best_share) + "% share of shelf",
                "detail": "Your strongest retailer. Hold price and content position; this is the base to protect."})
if data["nba"]:
    _n = data["nba"][0]
    _sc.append({"kind": "risk", "label": "Act now", "metric": _n["metric"],
                "headline": _n["head"], "detail": _n["act"]})
_sc.append({"kind": "invest", "label": "Invest", "metric": str(data["kpi"]["ai"]) + "%",
            "headline": "Win the AI shelf and weak listings",
            "detail": "Lift content on the lowest-scoring SKUs and earn citations on " + str(_src) + " to grow share of AI answer."})
data["scorecard"] = _sc[:3]

# Expose dynamic brand metadata for the front-end
data["focal"] = FOCAL
data["category"] = CATEGORY
data["brands"] = BRANDS
data["bcmap"] = BCMAP
data["matrix_brands"] = BRANDS[:6]
data["overview"] = OVERVIEW
# Answer engines actually present (empty until the GEO backfill runs)
data["engines"] = [r[0] for r in rows("SELECT DISTINCT engine FROM " + S + ".GEO_ANSWERS WHERE engine IS NOT NULL ORDER BY engine")]

HTML = r"""<meta charset="utf-8"><style>
/* No web-font @import: the Streamlit-in-Snowflake iframe has no egress, so we
   rely on the system-ui font stack below (nothing leaves the account). */
:root{
--navy:#234291;--navy7:#1B3372;--navy50:#EEF1F9;--red:#e32123;
--ink:#0F172A;--mut:#64748B;--sub:#94A3B8;--line:#E5E7EB;--surf:#fff;--alt:#F8FAFC;
--rose-bd:#FECDD3;--amber-bd:#FDE68A;--sky-bd:#BAE6FD;--emer-bd:#A7F3D0;
--fs:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;--fm:'Inter',ui-monospace,monospace;
--sh:0 1px 2px rgba(15,23,42,.05),0 1px 1px rgba(15,23,42,.03);--sh2:0 6px 18px rgba(15,23,42,.08),0 2px 6px rgba(15,23,42,.04);}
*{box-sizing:border-box;}
body{margin:0;background:var(--alt);color:var(--ink);font-family:var(--fs);-webkit-font-smoothing:antialiased;font-feature-settings:"cv11","ss01";}
.hdr{position:sticky;top:0;z-index:30;background:rgba(248,250,252,.86);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);}
.hdr .in{max-width:1480px;margin:0 auto;padding:16px 24px 14px;display:flex;flex-direction:column;gap:14px;}
.brow{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap;}
.bleft{display:flex;align-items:center;gap:12px;min-width:0;}
.bleft .logo{height:15px;width:auto;color:var(--ink);}
.bleft .dv{height:30px;width:1px;background:var(--line);}
.bleft .ttl{font-size:14px;font-weight:600;color:var(--ink);line-height:1.15;}
.bleft .sb{font-size:11px;color:var(--mut);margin-top:1px;}
.nav{display:inline-flex;align-items:center;gap:2px;padding:4px;background:var(--alt);border:1px solid var(--line);border-radius:16px;flex-wrap:wrap;}
.nav .t{position:relative;display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:12px;font-size:13px;font-weight:500;color:var(--mut);border:none;background:none;cursor:pointer;white-space:nowrap;transition:color .15s,background .15s;}
.nav .t svg{width:16px;height:16px;}
.nav .t:hover{color:var(--ink);}
.nav .t.on{color:#fff;background:var(--navy);box-shadow:0 2px 6px rgba(35,66,145,.28);}
.fbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;}
.fsel{position:relative;display:flex;flex-direction:column;justify-content:center;background:var(--surf);border:1px solid var(--line);border-radius:10px;padding:6px 30px 6px 12px;min-width:138px;min-height:46px;}
.fsel .fl{font-size:10px;text-transform:uppercase;letter-spacing:.04em;color:var(--sub);}
.fsel .fv{font-size:13.5px;color:var(--ink);font-weight:500;margin-top:2px;}
.fsel .chev{position:absolute;right:9px;top:50%;transform:translateY(-50%);color:var(--sub);width:16px;height:16px;pointer-events:none;}
.fsel.sel{cursor:pointer;}.fsel.sel:hover{border-color:var(--sub);}.fsel.sel select{appearance:none;-webkit-appearance:none;border:none;background:none;font-family:var(--fs);font-size:13.5px;font-weight:500;color:var(--ink);cursor:pointer;outline:none;padding:0;margin-top:2px;width:100%;}
.fsel.mute{opacity:.6;}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;}
@media(max-width:1100px){.kpis{grid-template-columns:repeat(3,1fr);}}@media(max-width:680px){.kpis{grid-template-columns:repeat(2,1fr);}}
.kc{background:var(--surf);border:1px solid var(--line);border-radius:14px;padding:14px 15px;box-shadow:var(--sh);transition:box-shadow .2s,transform .2s;}
.kc:hover{box-shadow:var(--sh2);transform:translateY(-1px);}
.kc .kt{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:18px;}
.kc .kl{font-size:10px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--mut);}
.kc .kv{font-size:30px;font-weight:800;color:var(--ink);line-height:1.05;letter-spacing:-.6px;margin-top:8px;font-variant-numeric:tabular-nums;}
.kc.al .kv{color:var(--red);}
.kc .ks{font-size:11px;color:var(--sub);margin-top:5px;line-height:1.35;}
.grade{display:inline-flex;align-items:center;justify-content:center;height:24px;min-width:28px;padding:0 6px;border-radius:7px;font-size:12px;font-weight:800;}
.kd{display:inline-flex;align-items:center;gap:3px;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;margin-top:8px;font-variant-numeric:tabular-nums;}
.kd.up{background:#ECFDF5;color:#059669;}.kd.down{background:#FEF2F2;color:#e32123;}.kd.flat{background:var(--alt);color:var(--sub);}
.main{max-width:1480px;margin:0 auto;padding:26px 24px 96px;}
.stack{display:flex;flex-direction:column;gap:30px;}
.view{display:none;}.view.on{display:block;animation:fade .3s cubic-bezier(.22,1,.36,1);}@keyframes fade{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:none;}}
.sec .sh{margin-bottom:14px;}.sec .stt{font-size:18px;font-weight:700;color:var(--ink);letter-spacing:-.3px;}.sec .sss{font-size:13px;color:var(--mut);margin-top:3px;line-height:1.45;max-width:90ch;}
.card{background:var(--surf);border:1px solid var(--line);border-radius:14px;box-shadow:var(--sh);}.card.p{padding:20px;}
.card h3{font-size:16px;font-weight:700;margin:0 0 3px;color:var(--ink);letter-spacing:-.2px;}.card .why{font-size:12.5px;color:var(--mut);margin:0 0 16px;line-height:1.5;}
.grid2{display:grid;grid-template-columns:1.05fr .95fr;gap:18px;}@media(max-width:900px){.grid2{grid-template-columns:1fr;}}
/* AI insights */
.tom{border:1px solid #FCE9B6;border-radius:14px;overflow:hidden;background:linear-gradient(135deg,rgba(255,251,235,.85),#fff 46%,rgba(240,249,255,.5));box-shadow:var(--sh);}
.tom .th{display:flex;align-items:center;gap:12px;padding:15px 20px;border-bottom:1px solid rgba(229,231,235,.7);}
.tom .ic{height:34px;width:34px;border-radius:50%;background:#fff;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;flex-shrink:0;color:var(--navy);}
.tom .ic svg{width:18px;height:18px;}
.tom .tt{flex:1;min-width:0;}.tom .tt .a{display:flex;align-items:center;gap:6px;font-size:16px;font-weight:600;color:var(--ink);}.tom .tt .a svg{width:15px;height:15px;color:#f59e0b;}.tom .tt .b{font-size:11px;color:var(--mut);margin-top:1px;}
.regen{display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:10px;font-size:12px;font-weight:500;background:#fff;border:1px solid var(--line);color:var(--ink);cursor:pointer;transition:all .15s;}
.regen:hover{border-color:#f59e0b;color:#b45309;}.regen svg{width:14px;height:14px;}
.tom .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:18px 20px;}@media(max-width:760px){.tom .grid{grid-template-columns:1fr;}}
.icard{display:block;text-align:left;background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px;cursor:pointer;box-shadow:var(--sh);transition:box-shadow .18s,transform .18s;width:100%;}
.icard:hover{box-shadow:var(--sh2);transform:translateY(-1px);}
.icard.alert{box-shadow:0 0 0 1px var(--rose-bd),var(--sh);}.icard.risk{box-shadow:0 0 0 1px var(--amber-bd),var(--sh);}.icard.trend{box-shadow:0 0 0 1px var(--sky-bd),var(--sh);}.icard.opportunity{box-shadow:0 0 0 1px var(--emer-bd),var(--sh);}
.icard .ir{display:flex;align-items:center;gap:6px;margin-bottom:9px;}
.ipill{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:999px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;}.ipill svg{width:12px;height:12px;}
.ipill.alert{background:#FFE4E6;color:#9F1239;}.ipill.risk{background:#FEF3C7;color:#92400E;}.ipill.trend{background:#E0F2FE;color:#075985;}.ipill.opportunity{background:#D1FAE5;color:#065F46;}
.iopen{margin-left:auto;display:inline-flex;align-items:center;gap:3px;font-size:10px;font-weight:600;color:var(--mut);text-transform:capitalize;}.iopen svg{width:12px;height:12px;}
.icard .ih{font-size:14px;font-weight:600;color:var(--ink);line-height:1.35;}.icard .id{font-size:12px;color:var(--mut);margin-top:5px;line-height:1.5;}
/* scorecard trio */
.trio{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}@media(max-width:820px){.trio{grid-template-columns:1fr;}}
.scard{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:var(--sh);border-top:3px solid var(--navy);}
.scard.win{border-top-color:#059669;}.scard.risk{border-top-color:var(--red);}.scard.invest{border-top-color:var(--navy);}
.scard .sl{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--mut);display:flex;justify-content:space-between;align-items:center;gap:8px;}
.scard .sm{font-size:13px;font-weight:800;font-variant-numeric:tabular-nums;}
.scard.win .sm{color:#059669;}.scard.risk .sm{color:var(--red);}.scard.invest .sm{color:var(--navy);}
.scard .shd{font-size:15px;font-weight:700;color:var(--ink);margin-top:10px;line-height:1.35;}.scard .sd{font-size:12.5px;color:var(--mut);margin-top:6px;line-height:1.5;}
/* matrix */
.mtx{width:100%;border-collapse:separate;border-spacing:0;font-size:13px;}
.mtx th{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);padding:6px 10px 10px;text-align:center;}.mtx th.bl{text-align:left;}
.mtx td{padding:2px;text-align:center;}.mtx td.bn{text-align:left;padding:6px 10px;font-weight:600;color:var(--ink);white-space:nowrap;}.mtx td.bn.kk{color:var(--navy);}
.mcell{display:block;border-radius:8px;padding:11px 6px;font-weight:700;font-variant-numeric:tabular-nums;}
/* per-brand reviews */
.brsel{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:16px;}
.brchip{font-size:12.5px;font-weight:600;border:1px solid var(--line);background:#fff;color:var(--mut);border-radius:999px;padding:6px 13px;cursor:pointer;transition:all .15s;}
.brchip:hover{border-color:var(--navy);color:var(--navy);}.brchip.on{background:var(--navy);border-color:var(--navy);color:#fff;}
.revhead{display:flex;align-items:center;gap:8px;border-left:3px solid var(--navy);padding-left:10px;margin-bottom:14px;}.revhead b{font-size:16px;color:var(--ink);}.revhead .brdot{width:10px;height:10px;border-radius:50%;}.revsub{font-size:11px;color:var(--sub);text-transform:uppercase;letter-spacing:.06em;}
.brstat{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px;}.brstat .bx{background:var(--alt);border:1px solid var(--line);border-radius:11px;padding:13px 15px;}.brstat .bn{font-size:24px;font-weight:800;color:var(--ink);letter-spacing:-.5px;font-variant-numeric:tabular-nums;}.brstat .bxl{font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);margin-top:4px;}
.splitbar{display:flex;height:12px;border-radius:6px;overflow:hidden;margin-bottom:8px;}.splitbar>div{height:100%;}
.splitleg{display:flex;gap:16px;font-size:11.5px;color:var(--mut);margin-bottom:18px;}.splitleg span{display:inline-flex;align-items:center;gap:5px;}.splitleg i{width:10px;height:10px;border-radius:3px;}
.revgrid{display:grid;grid-template-columns:1fr 1fr;gap:22px;}@media(max-width:760px){.revgrid{grid-template-columns:1fr;}}
.revcol .revh,.revsumm .revh{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin-bottom:11px;}
.revsumm{margin-top:18px;border-top:1px solid var(--line);padding-top:16px;}.revsumm p{margin:0;font-size:14px;line-height:1.6;color:var(--ink);font-style:italic;}
/* bars */
.bars{display:flex;flex-direction:column;gap:10px;}.br{display:grid;grid-template-columns:140px 1fr 48px;align-items:center;gap:12px;}.br .l{font-size:13px;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--mut);}.br.kk .l{font-weight:700;color:var(--ink);}
.br .t{height:22px;background:var(--alt);border-radius:7px;overflow:hidden;}.br .f{height:100%;border-radius:7px;background:#9DB0D8;transition:width .7s cubic-bezier(.22,1,.36,1);}.br .f.kk{background:var(--navy);}.br .v{font-family:var(--fm);font-size:12.5px;text-align:right;font-weight:600;font-variant-numeric:tabular-nums;}
/* donut */
.donut-wrap{display:flex;gap:24px;align-items:center;flex-wrap:wrap;}.donut{position:relative;width:188px;height:188px;flex-shrink:0;}.donut .ctr{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;}.donut .ctr .b{font-size:28px;font-weight:800;color:var(--ink);letter-spacing:-.5px;}.donut .ctr .s{font-size:10px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin-top:3px;}
.leg{flex:1;min-width:200px;display:flex;flex-direction:column;gap:7px;}.leg .lr{display:flex;align-items:center;gap:9px;font-size:13px;}.leg .lr .sw{width:10px;height:10px;border-radius:50%;}.leg .lr .nm{flex:1;color:var(--mut);}.leg .lr.kk .nm{font-weight:700;color:var(--ink);}.leg .lr .vv{font-family:var(--fm);font-weight:600;}
/* pricing */
.grp{display:flex;gap:24px;align-items:flex-end;justify-content:space-around;height:220px;padding-top:14px;}.grp .c{display:flex;flex-direction:column;align-items:center;gap:10px;flex:1;}.grp .pr{display:flex;gap:10px;align-items:flex-end;height:160px;}
.grp .b{width:34px;border-radius:7px 7px 0 0;display:flex;align-items:flex-start;justify-content:center;}.grp .b span{font-family:var(--fm);font-size:10.5px;font-weight:600;margin-top:-18px;color:var(--ink);}.grp .b.kk{background:var(--navy);}.grp .b.cp{background:#CBD5E1;}.grp .rl{font-size:13px;text-transform:capitalize;font-weight:600;}
.legend{display:flex;gap:18px;font-size:12px;color:var(--mut);margin-top:14px;justify-content:center;flex-wrap:wrap;}.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;}
/* product cards */
.pgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}@media(max-width:820px){.pgrid{grid-template-columns:1fr 1fr;}}@media(max-width:520px){.pgrid{grid-template-columns:1fr;}}
.pc{display:block;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh);transition:transform .15s,box-shadow .15s;}.pc:hover{transform:translateY(-3px);box-shadow:var(--sh2);}
a.pc{text-decoration:none;color:inherit;cursor:pointer;}a.pc.lk:hover{border-color:var(--navy);}a.pc .popen{margin-top:10px;font-family:var(--fm);font-size:10.5px;font-weight:700;color:var(--navy);opacity:0;transition:opacity .15s;}a.pc:hover .popen{opacity:1;}
.pc .iw{height:138px;background:linear-gradient(135deg,#FBFCFE,#EEF1F9);display:flex;align-items:center;justify-content:center;padding:10px;}.pc .iw img{max-width:100%;max-height:100%;object-fit:contain;mix-blend-mode:multiply;}
.pc .ph{height:138px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#EEF1F9,#DCE3F5);color:var(--navy);font-weight:800;font-size:26px;}
.pc .pb{padding:13px 15px;}.pc .pn{font-size:12.5px;font-weight:600;color:var(--ink);line-height:1.35;height:34px;overflow:hidden;}.pc .pm{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;}
.pchip{font-family:var(--fm);font-size:10.5px;font-weight:600;border-radius:6px;padding:3px 8px;background:var(--alt);color:var(--mut);}.pchip.crit{background:#FEF2F2;color:#b42318;}.pchip.high{background:#FFF7ED;color:#9a3412;}.pchip.ret{text-transform:capitalize;}
/* content stack */
.cstack{display:flex;flex-direction:column;gap:11px;}.cstack .row{display:grid;grid-template-columns:84px 1fr 38px;align-items:center;gap:12px;}.cstack .row .l{font-size:13px;text-transform:capitalize;text-align:right;color:var(--mut);}.cstack .seg{height:24px;border-radius:7px;overflow:hidden;display:flex;}.cstack .seg>div{height:100%;}.cstack .v{font-family:var(--fm);font-size:12px;font-weight:600;}
.gleg{display:flex;gap:14px;font-size:12px;color:var(--mut);margin-top:14px;justify-content:center;}.gleg i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;}
.tnote{font-size:13px;color:var(--ink);background:var(--navy50);border:1px solid #D6DEF2;border-radius:12px;padding:12px 15px;margin-top:16px;line-height:1.55;}
.legd{display:flex;gap:16px;font-size:12px;color:var(--mut);margin-top:12px;justify-content:center;flex-wrap:wrap;}.legd span{display:inline-flex;align-items:center;gap:6px;}.legd i{width:18px;height:3px;border-radius:2px;}
.daxis{display:flex;justify-content:space-between;font-family:var(--fm);font-size:10.5px;color:var(--sub);margin-top:6px;}
/* D&T */
.dgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;}@media(max-width:900px){.dgrid{grid-template-columns:1fr 1fr;}}
.dc{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:var(--sh);}.dc .di{height:32px;width:32px;border-radius:9px;background:var(--navy50);color:var(--navy);display:flex;align-items:center;justify-content:center;}.dc .di svg{width:17px;height:17px;}.dc .dl{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin-top:12px;}.dc .dv{font-size:13.5px;color:var(--ink);margin-top:5px;line-height:1.45;}
.flow{display:flex;gap:10px;flex-wrap:wrap;align-items:stretch;}
.fstep{flex:1;min-width:150px;background:var(--alt);border:1px solid var(--line);border-radius:12px;padding:13px 15px;}.fstep .fn{font-family:var(--fm);font-size:10px;color:var(--navy);font-weight:700;}.fstep .ft{font-size:13px;font-weight:600;color:var(--ink);margin-top:5px;}.fstep .fd{font-size:11.5px;color:var(--mut);margin-top:4px;line-height:1.4;}
.obj{display:flex;flex-wrap:wrap;gap:10px;}.objc{font-family:var(--fm);font-size:12px;background:var(--alt);border:1px solid var(--line);border-radius:9px;padding:9px 12px;color:var(--ink);}.objc b{color:var(--navy);font-weight:700;}
/* raw table */
.rtbl{width:100%;border-collapse:separate;border-spacing:0;font-size:13px;}.rtbl th{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);padding:9px 12px;text-align:left;border-bottom:2px solid var(--line);background:#FBFCFE;}.rtbl td{padding:9px 12px;border-bottom:1px solid #F1F5F9;color:var(--ink);}.rtbl td.pn{max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}.rtbl td.cap{text-transform:capitalize;}.rtbl tr.kkr td{background:var(--navy50);}.rtbl tr.kkr td:first-child{font-weight:600;}
.ob{font-size:11px;font-weight:700;color:#b42318;background:#FEF2F2;border-radius:6px;padding:2px 8px;}.ib{font-size:11px;font-weight:600;color:#059669;background:#ECFDF5;border-radius:6px;padding:2px 8px;}
/* buzzbee */
.bzbtn{position:fixed;bottom:22px;right:22px;z-index:40;display:flex;align-items:center;gap:11px;padding:9px 17px 9px 9px;border:none;cursor:pointer;border-radius:999px;background:linear-gradient(135deg,#FFE066,#FFC542 55%,#FF9E1C);box-shadow:0 8px 22px rgba(217,119,6,.28),0 0 0 1px rgba(180,83,9,.18);transition:box-shadow .2s,transform .2s;}
.bzbtn:hover{box-shadow:0 12px 30px rgba(217,119,6,.34);transform:translateY(-1px);}
.bzbtn .bzi{height:34px;width:34px;border-radius:50%;background:rgba(255,255,255,.92);box-shadow:0 1px 3px rgba(0,0,0,.12);display:flex;align-items:center;justify-content:center;color:#B45309;}.bzbtn .bzi svg{width:18px;height:18px;}
.bzbtn .bzl{font-size:14px;font-weight:700;color:#7C3A03;letter-spacing:-.2px;}
.bzwrap{display:none;position:fixed;inset:0;z-index:50;}.bzwrap.on{display:block;}
.bzov{position:absolute;inset:0;background:rgba(15,23,42,.22);}
.bzpanel{position:absolute;top:0;right:0;height:100%;width:min(420px,94vw);background:#fff;box-shadow:-12px 0 40px rgba(15,23,42,.18);display:flex;flex-direction:column;animation:slidein .28s cubic-bezier(.22,1,.36,1);}
@keyframes slidein{from{transform:translateX(100%);}to{transform:none;}}
.bzh{display:flex;align-items:center;gap:11px;padding:18px 20px;border-bottom:1px solid var(--line);}
.bzh .bzi{height:34px;width:34px;border-radius:50%;background:linear-gradient(135deg,#FFE066,#FF9E1C);display:flex;align-items:center;justify-content:center;color:#7C3A03;}.bzh .bzi svg{width:17px;height:17px;}
.bzh .a{font-size:15px;font-weight:700;color:var(--ink);}.bzh .b{font-size:11px;color:var(--mut);margin-top:1px;}.bzx{margin-left:auto;background:none;border:none;cursor:pointer;color:var(--sub);padding:6px;border-radius:8px;}.bzx:hover{background:var(--alt);color:var(--ink);}.bzx svg{width:18px;height:18px;}
.bzbody{flex:1;overflow-y:auto;padding:18px 20px;display:flex;flex-direction:column;gap:12px;}
.bzintro{font-size:13px;color:var(--mut);line-height:1.55;}
.bzq{display:block;width:100%;text-align:left;background:var(--alt);border:1px solid var(--line);border-radius:11px;padding:11px 13px;font-size:13px;color:var(--ink);cursor:pointer;font-family:var(--fs);transition:all .15s;}.bzq:hover{border-color:var(--navy);background:var(--navy50);}
.bzmsg{background:var(--navy50);border:1px solid #D6DEF2;border-radius:12px 12px 12px 4px;padding:12px 14px;font-size:13px;line-height:1.55;color:var(--ink);}
.bzu{align-self:flex-end;background:var(--navy);color:#fff;border-radius:12px 12px 4px 12px;padding:9px 13px;font-size:13px;max-width:85%;}
.bzhint{font-size:11.5px;color:var(--sub);text-align:center;padding-top:6px;border-top:1px solid var(--line);margin-top:4px;}
</style>
<svg width="0" height="0" style="position:absolute"><defs>
<symbol id="i-brief" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="7" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></symbol>
<symbol id="i-cart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/></symbol>
<symbol id="i-tag" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r="1.2" fill="currentColor"/></symbol>
<symbol id="i-doc" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></symbol>
<symbol id="i-bar" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></symbol>
<symbol id="i-wrench" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></symbol>
<symbol id="i-db" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></symbol>
<symbol id="i-spark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.94 14.06 8.5 9.94 4.38 8.5 8.5 7.06 9.94 2.94l1.44 4.12 4.12 1.44-4.12 1.44z" transform="translate(0.5 1.5) scale(0.95)"/><path d="M18 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/></symbol>
<symbol id="i-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></symbol>
<symbol id="i-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></symbol>
<symbol id="i-alert" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.59 16.73A2 2 0 0 1 2 15.31V8.69a2 2 0 0 1 .59-1.42l4.68-4.68A2 2 0 0 1 8.69 2h6.62a2 2 0 0 1 1.42.59l4.68 4.68A2 2 0 0 1 22 8.69v6.62a2 2 0 0 1-.59 1.42l-4.68 4.68a2 2 0 0 1-1.42.59H8.69a2 2 0 0 1-1.42-.59z"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></symbol>
<symbol id="i-up" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></symbol>
<symbol id="i-bulb" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></symbol>
<symbol id="i-store" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m2 7 1.5-3h17L22 7"/><path d="M4 7v13a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V7"/><path d="M4 7h16"/><path d="M9 21v-6h6v6"/></symbol>
<symbol id="i-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></symbol>
<symbol id="i-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></symbol>
<symbol id="i-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></symbol>
</defs></svg>
<header class="hdr"><div class="in">
  <div class="brow">
    <div class="bleft">
      <svg class="logo" viewBox="0 0 91.264 13.181"><path d="M 12.214 9.877 L 10.984 10.176 L 10.984 0 L 15.378 0 L 15.378 13.181 L 9.701 13.181 L 3.163 3.023 L 4.394 2.724 L 4.394 13.181 L 0 13.181 L 0 0 L 5.852 0 L 12.214 9.877 Z M 18.016 0 L 22.55 0 L 22.55 13.181 L 18.016 13.181 L 18.016 0 Z M 45.484 0 L 45.484 13.181 L 41.178 13.181 L 41.178 1.705 L 42.004 1.81 L 37.576 13.181 L 33.094 13.181 L 28.665 1.863 L 29.491 1.74 L 29.491 13.181 L 25.185 13.181 L 25.185 0 L 32.198 0 L 36.134 10.738 L 34.57 10.738 L 38.472 0 L 45.484 0 Z M 57.688 6.784 L 58.039 5.975 C 59.035 6.011 59.867 6.169 60.535 6.45 C 61.203 6.731 61.701 7.124 62.029 7.627 C 62.369 8.12 62.539 8.711 62.539 9.402 C 62.539 10.117 62.375 10.762 62.046 11.336 C 61.73 11.91 61.244 12.361 60.588 12.689 C 59.932 13.017 59.111 13.181 58.127 13.181 L 47.776 13.181 L 48.778 6.415 L 47.776 0 L 57.758 0 C 58.977 0 59.932 0.287 60.623 0.861 C 61.314 1.424 61.66 2.209 61.66 3.216 C 61.66 3.79 61.531 4.329 61.273 4.833 C 61.015 5.337 60.594 5.765 60.008 6.116 C 59.434 6.456 58.66 6.678 57.688 6.784 Z M 52.205 12.197 L 50.482 10.176 L 56.686 10.176 C 57.073 10.176 57.377 10.076 57.6 9.877 C 57.823 9.666 57.934 9.385 57.934 9.033 C 57.934 8.717 57.823 8.448 57.6 8.225 C 57.389 8.002 57.073 7.891 56.651 7.891 L 51.449 7.891 L 51.449 4.938 L 55.983 4.938 C 56.288 4.938 56.54 4.845 56.739 4.657 C 56.95 4.47 57.055 4.23 57.055 3.937 C 57.055 3.667 56.962 3.445 56.774 3.269 C 56.587 3.093 56.323 3.005 55.983 3.005 L 50.5 3.005 L 52.205 0.984 L 53.101 6.415 L 52.205 12.197 Z M 69.133 0 L 69.133 11.178 L 67.094 9.139 L 76.901 9.139 L 76.901 13.181 L 64.599 13.181 L 64.599 0 L 69.133 0 Z M 90.614 5.026 L 90.614 8.155 L 80.684 8.155 L 80.684 5.026 L 90.614 5.026 Z M 83.795 6.591 L 82.986 11.494 L 81.264 9.596 L 91.264 9.596 L 91.264 13.181 L 78.505 13.181 L 79.471 6.591 L 78.505 0 L 91.176 0 L 91.176 3.585 L 81.264 3.585 L 82.986 1.687 L 83.795 6.591 Z" fill="currentColor"/></svg>
      <div class="dv"></div>
      <div><div class="ttl">Digital Shelf Intelligence</div><div class="sb" id="subhead"></div></div>
    </div>
    <nav class="nav" id="nav"></nav>
  </div>
  <div class="fbar" id="fbar"></div>
  <div class="kpis" id="kpis"></div>
</div></header>
<main class="main"><div id="views"></div></main>
<script>
var DATA=__DATA__;var FOCAL=DATA.focal;var CATEGORY=DATA.category;var RET="All";function S(){return DATA.slices[RET]||DATA.slices.All;}var K=S().kpi;var CUR="Leadership";
function cap(s){return s?s.charAt(0).toUpperCase()+s.slice(1):s;}
var RETS=(DATA.retailers||[]).filter(function(r){return r!=="All";});
var RETLBL=RETS.map(cap).join(" · ")||"tracked retailers";
var ENGLBL=(DATA.engines&&DATA.engines.length)?DATA.engines.map(cap).join(" · "):"answer engines";
var SUBJ=FOCAL||cap(CATEGORY||"category");
var BC=DATA.bcmap;
function isKK(n){return n===FOCAL;}
function ico(id){return '<svg><use href="#'+id+'"/></svg>';}
function fmtN(n){return (n==null?0:n).toLocaleString();}
function sec(t,s,body){return '<div class="sec"><div class="sh"><div class="stt">'+t+'</div><div class="sss">'+s+'</div></div>'+body+'</div>';}

/* ---------- KPI strip ---------- */
function gradeBadge(s){var g,bg,fg;if(s>=85){g="A";bg="#D1FAE5";fg="#065F46";}else if(s>=70){g="B";bg="#D1FAE5";fg="#047857";}else if(s>=55){g="C";bg="#FEF9C3";fg="#854D0E";}else if(s>=40){g="D";bg="#FFEDD5";fg="#9A3412";}else{g="F";bg="#FFE4E6";fg="#9F1239";}return '<span class="grade" style="background:'+bg+';color:'+fg+'">'+g+'</span>';}
function kdelta(v,unit,inv){if(v==null)return '<div class="kd flat">&nbsp;</div>';if(Math.abs(v)<0.05)return '<div class="kd flat">no change vs prev</div>';var up=inv?v<0:v>0;return '<div class="kd '+(up?"up":"down")+'">'+(v>0?"▲ +":"▼ ")+v+(unit||"")+' vs prev day</div>';}
function renderKPIs(){
  var cards=[
    {l:"Share of Shelf",v:K.share+"%",s:"Listing share · primary brand tier",d:kdelta(K.d_share,"pp",false)},
    {l:"Share of AI Answer",v:K.ai+"%",s:"Across category prompts",d:'<div class="kd flat">'+ENGLBL+'</div>'},
    {l:SUBJ+" SKUs visible",v:fmtN(K.skus),s:"Across "+RETLBL,d:'<div class="kd flat">&nbsp;</div>'},
    {l:"Active Alerts",v:fmtN(K.oos),s:"Out-of-stock listings on shelf",d:kdelta(K.d_oos,"",true),al:true},
    {l:"Content Score",v:K.content,s:"0–100 · listing completeness",badge:gradeBadge(K.content),d:'<div class="kd flat">open Content tab</div>'}
  ];
  document.getElementById("kpis").innerHTML=cards.map(function(c){return '<div class="kc'+(c.al?" al":"")+'"><div class="kt"><span class="kl">'+c.l+'</span>'+(c.badge||"")+'</div><div class="kv">'+c.v+'</div><div class="ks">'+c.s+'</div>'+c.d+'</div>';}).join("");
}
/* ---------- filter bar (As of + live Retailer) ---------- */
function rlabel(r){return r==="All"?"All retailers":r.charAt(0).toUpperCase()+r.slice(1);}
function renderFilters(){
  var asof='<div class="fsel"><span class="fl">As of</span><span class="fv">'+DATA.snap_date+'</span></div>';
  var ret='<label class="fsel sel"><span class="fl">Retailer</span><select id="retsel">'+DATA.retailers.map(function(r){return '<option value="'+r+'"'+(r===RET?' selected':'')+'>'+rlabel(r)+'</option>';}).join("")+'</select><svg class="chev"><use href="#i-chev"/></svg></label>';
  var kw='<div class="fsel mute"><span class="fl">Keyword</span><span class="fv">All</span><svg class="chev"><use href="#i-chev"/></svg></div>';
  var sel='<div class="fsel mute"><span class="fl">Sellers</span><span class="fv">1P + 3P</span><svg class="chev"><use href="#i-chev"/></svg></div>';
  document.getElementById("fbar").innerHTML=asof+ret+kw+sel;
  var rs=document.getElementById("retsel");rs.onchange=function(){RET=rs.value;K=S().kpi;renderKPIs();paint(CUR);};
}
/* ---------- shared chart helpers ---------- */
function hbar(rows,u){u=(u===undefined?"%":u);var max=Math.max.apply(null,rows.map(function(r){return r[1];}))||1;return '<div class="bars">'+rows.map(function(r){var kk=isKK(r[0]);return '<div class="br'+(kk?" kk":"")+'"><div class="l">'+r[0]+'</div><div class="t"><div class="f'+(kk?" kk":"")+'" style="width:'+(r[1]/max*100).toFixed(1)+'%"></div></div><div class="v">'+r[1]+u+'</div></div>';}).join("")+'</div>';}
function donut(rows){var tot=rows.reduce(function(s,r){return s+r[1];},0)||1,R=78,C=2*Math.PI*R,off=0,s="";rows.forEach(function(r){var len=r[1]/tot*C,col=BC[r[0]]||"#ccc";s+='<circle cx="94" cy="94" r="'+R+'" fill="none" stroke="'+col+'" stroke-width="22" stroke-dasharray="'+len+' '+(C-len)+'" stroke-dashoffset="'+(-off)+'" transform="rotate(-90 94 94)"/>';off+=len;});return '<svg viewBox="0 0 188 188" width="188" height="188">'+s+'</svg>';}
function pcards(items){var gc={CRITICAL:"crit",HIGH:"high",F:"crit",D:"high"};return '<div class="pgrid">'+items.map(function(p){var img=p.img?'<div class="iw"><img src="'+p.img+'" onerror="this.parentNode.innerHTML=\'<div class=ph>KK</div>\'"></div>':'<div class="ph">KK</div>';var ch=p.sev?'<span class="pchip '+(gc[p.sev]||"")+'">'+p.sev+'</span><span class="pchip ret">'+p.retailer+'</span><span class="pchip">pos #'+p.position+'</span><span class="pchip">$'+p.price+'</span>':'<span class="pchip '+(gc[p.grade]||"")+'">grade '+p.grade+'</span><span class="pchip ret">'+p.retailer+'</span><span class="pchip">score '+p.score+'</span><span class="pchip">'+p.reviews+' reviews</span>';var open=p.url?'<div class="popen">View on '+p.retailer+' &#8599;</div>':'';var tag=p.url?'a':'div';var href=p.url?' href="'+p.url+'" target="_blank" rel="noopener"':'';return '<'+tag+' class="pc'+(p.url?" lk":"")+'"'+href+'>'+img+'<div class="pb"><div class="pn">'+p.name+'</div><div class="pm">'+ch+'</div>'+open+'</div></'+tag+'>';}).join("")+'</div>';}
function sparkline(){
  var d=DATA.trend_dates,kk=(DATA.trend_focal||[]),comp=(DATA.trend_comp||[]);
  var W=1080,H=190,pl=10,pr=10,pt=16,pb=10,n=d.length;
  var all=[];kk.forEach(function(v){if(v!=null)all.push(v);});comp.forEach(function(c){(DATA.trend_share[c]||[]).forEach(function(v){if(v!=null)all.push(v);});});
  var mn=Math.min.apply(null,all),mx=Math.max.apply(null,all);mn=Math.floor(mn-3);mx=Math.ceil(mx+3);if(mn<0)mn=0;if(mx===mn)mx=mn+1;
  function X(i){return pl+i*((W-pl-pr)/Math.max(1,n-1));}function Y(v){return pt+(1-(v-mn)/(mx-mn))*(H-pt-pb);}
  var pts=kk.map(function(v,i){return v==null?null:[X(i),Y(v)];}).filter(Boolean);
  var line=pts.map(function(p,i){return (i?'L':'M')+p[0]+' '+p[1];}).join(' ');
  var area=pts.length?('M'+pts[0][0]+' '+(H-pb)+' '+pts.map(function(p){return 'L'+p[0]+' '+p[1];}).join(' ')+' L'+pts[pts.length-1][0]+' '+(H-pb)+' Z'):'';
  var svg='<svg viewBox="0 0 '+W+' '+H+'" width="100%" style="display:block"><defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#234291" stop-opacity=".20"/><stop offset="1" stop-color="#234291" stop-opacity="0"/></linearGradient></defs>';
  [0,.5,1].forEach(function(g){var y=pt+g*(H-pt-pb);svg+='<line x1="'+pl+'" y1="'+y+'" x2="'+(W-pr)+'" y2="'+y+'" stroke="#F1F5F9"/>';});
  var cc=DATA.bcmap;
  comp.forEach(function(c){var s=DATA.trend_share[c];if(!s)return;var lp=s.map(function(v,i){return v==null?null:[X(i),Y(v)];}).filter(Boolean).map(function(p,i){return (i?'L':'M')+p[0]+' '+p[1];}).join(' ');svg+='<path d="'+lp+'" fill="none" stroke="'+cc[c]+'" stroke-width="1.5" stroke-opacity=".5" stroke-linejoin="round"/>';});
  svg+='<path d="'+area+'" fill="url(#ag)"/><path d="'+line+'" fill="none" stroke="#234291" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>';
  pts.forEach(function(p){svg+='<circle cx="'+p[0]+'" cy="'+p[1]+'" r="3.2" fill="#234291"/>';});
  svg+='</svg>';
  var ax='<div class="daxis">'+d.map(function(x){return '<span>'+x.slice(5)+'</span>';}).join("")+'</div>';
  var leg='<div class="legd">'+[FOCAL].concat(comp).map(function(b){return '<span><i style="background:'+(DATA.bcmap[b]||"#94A3B8")+'"></i>'+b+'</span>';}).join("")+'</div>';
  return svg+ax+leg;
}
function matrix(){
  var rets=RETS,brands=DATA.matrix_brands;
  var m={};rets.forEach(function(r){(DATA.by_retailer[r]||[]).forEach(function(p){m[r+"|"+p[0]]=p[1];});});
  var h='<table class="mtx"><thead><tr><th class="bl">Brand</th>'+rets.map(function(r){return '<th>'+r+'</th>';}).join("")+'</tr></thead><tbody>';
  brands.forEach(function(b){var kk=isKK(b);h+='<tr><td class="bn'+(kk?" kk":"")+'">'+b+'</td>'+rets.map(function(r){var v=m[r+"|"+b];if(v==null)return '<td><span class="mcell" style="background:#FBFCFE;color:#CBD5E1">—</span></td>';var t=Math.min(v/40,1);var bg=kk?'rgba(35,66,145,'+(0.10+t*0.55).toFixed(2)+')':'rgba(100,116,139,'+(0.06+t*0.30).toFixed(2)+')';var col=(kk&&t>0.5)?'#fff':'#0F172A';return '<td><span class="mcell" style="background:'+bg+';color:'+col+'">'+v+'%</span></td>';}).join("")+'</tr>';});
  return '<div class="card p">'+h+'</tbody></table></div>';
}
/* ---------- views ---------- */
var VIEWS={
 Leadership:function(){
   var cards=DATA.insights.map(function(b){var open=b.tab?'<span class="iopen">Open '+b.tab+ico("i-arrow")+'</span>':'';var ig={alert:"i-alert",risk:"i-alert",trend:"i-up",opportunity:"i-bulb"}[b.tag]||"i-up";return '<button class="icard '+b.tag+'" data-tab="'+(b.tab||"")+'"><div class="ir"><span class="ipill '+b.tag+'">'+ico(ig)+b.tag+'</span>'+open+'</div><div class="ih">'+b.headline+'</div><div class="id">'+b.detail+'</div></button>';}).join("");
   var tom='<div class="tom"><div class="th"><div class="ic">'+ico("i-spark")+'</div><div class="tt"><div class="a">AI Insights'+ico("i-spark")+'</div><div class="b">'+DATA.insights.length+' AI-powered insights the leadership team should act on</div></div><button class="regen" id="regen">'+ico("i-refresh")+'Refresh view</button></div><div class="grid">'+cards+'</div></div>';
   var traj=sec("Portfolio trajectory","Focal-brand share of shelf across all retailers, daily — momentum, not just today\'s snapshot.",'<div class="card p">'+sparkline()+'</div>');
   var trio=sec("The week in three cards","Auto-generated from the live alert and shelf data.",'<div class="trio">'+DATA.scorecard.map(function(c){return '<div class="scard '+c.kind+'"><div class="sl"><span>'+c.label+'</span><span class="sm">'+c.metric+'</span></div><div class="shd">'+c.headline+'</div><div class="sd">'+c.detail+'</div></div>';}).join("")+'</div>');
   var mx=sec("Brand × retailer health snapshot","Where to defend, where to invest. Cell shade scales with share of shelf; __BRAND__ row in navy.",matrix());
   return '<div class="stack">'+tom+traj+trio+mx+'</div>';
 },
 Retailer:function(){
   var max=Math.max.apply(null,S().pricing.map(function(p){return Math.max(p[1]||0,p[2]||0);}))||1;
   var price='<div class="card p"><h3>Unit price — __BRAND__ vs the competitive set</h3><p class="why">A persistent premium invites switching and private-label trade-down. Price per unit normalizes across pack sizes.</p><div class="grp">'+S().pricing.map(function(p){return '<div class="c"><div class="pr"><div class="b kk" style="height:'+((p[1]||0)/max*100).toFixed(0)+'%"><span>'+(p[1]!=null?"$"+p[1]:"-")+'</span></div><div class="b cp" style="height:'+((p[2]||0)/max*100).toFixed(0)+'%"><span>'+(p[2]!=null?"$"+p[2]:"-")+'</span></div></div><div class="rl">'+p[0]+'</div></div>';}).join("")+'</div><div class="legend"><span><i style="background:#234291"></i>__BRAND__</span><span><i style="background:#CBD5E1"></i>Competitor avg</span></div></div>';
   var oos='<div class="card p"><h3>'+K.oos+' __BRAND__ SKUs out of stock</h3><p class="why">An out-of-stock SKU in a top search slot is pure lost sell-through — the shopper is there, ready to buy, and converts to a competitor. Click a tile to open the live retailer page.</p>'+pcards(S().oos_products)+'</div>';
   return sec("Retailer execution","Pricing competitiveness and on-shelf availability across "+RETLBL+".","<div class='stack'>"+price+oos+"</div>");
 },
 Brand:function(){
   var sh=S().share;
   var dc='<div class="card p"><h3>Share of shelf</h3><p class="why">Visibility is the top of the funnel — if you\'re not on the shelf, you\'re not in the basket.</p><div class="donut-wrap"><div class="donut">'+donut(sh.filter(function(r){return r[1]>1;}))+'<div class="ctr"><div class="b">'+K.share+'%</div><div class="s">'+FOCAL+'</div></div></div><div class="leg">'+sh.slice(0,8).map(function(r){return '<div class="lr '+(isKK(r[0])?"kk":"")+'"><span class="sw" style="background:'+(BC[r[0]]||"#ccc")+'"></span><span class="nm">'+r[0]+'</span><span class="vv" style="color:'+(BC[r[0]]||"#64748B")+'">'+r[1]+'%</span></div>';}).join("")+'</div></div></div>';
   var bars='<div class="card p"><h3>The competitive set, ranked</h3><p class="why">__BRAND__ versus every brand tier on the shelf today.</p>'+hbar(sh.filter(function(r){return r[1]>0.5;}).slice(0,9))+'</div>';
   var aiC='<div class="card p"><h3>Share of AI answer — by brand</h3><p class="why">How often each brand is named when shoppers ask ChatGPT, Perplexity and Gemini what __CATEGORY__ to buy. __BRAND__ wins the shelf but is under-cited here.</p>'+hbar(DATA.ai_share)+'</div>';
   var src='';
   if(DATA.top_sources&&DATA.top_sources.length){var sm=DATA.top_sources[0][1]||1;src='<div class="card p"><h3>Top sources behind the AI answers</h3><p class="why">The domains the answer engines cite when recommending __CATEGORY__ — where to earn presence to shape what the AI says.</p><div class="bars">'+DATA.top_sources.map(function(r){return '<div class="br"><div class="l" style="text-transform:none;text-align:right">'+r[0]+'</div><div class="t"><div class="f" style="width:'+(r[1]/sm*100).toFixed(0)+'%;background:#234291"></div></div><div class="v">'+r[1]+'%</div></div>';}).join("")+'</div></div>';}
   var rev='<div class="card p"><h3>What people say — by brand</h3><p class="why">Review sentiment and themes per brand, from retailer reviews. Pick a brand to see what shoppers praise and flag.</p><div class="brsel" id="brsel">'+DATA.brand_order.map(function(b,i){return '<button class="brchip'+(i===0?" on":"")+'" data-b="'+b.replace(/"/g,"&quot;")+'">'+b+'</button>';}).join("")+'</div><div id="brbody"></div></div>';
   var top=sec("Brand & category","__BRAND__\'s position in the __CATEGORY__ set across the selected retailer scope.","<div class='grid2'>"+dc+bars+"</div>");
   var aigrid=sec("AI visibility & sources","Answer-engine presence across the category and the domains shaping it.","<div class='stack'>"+aiC+src+"</div>");
   var revsec=sec("Voice of the customer","Per-brand review analysis — understand what people are actually saying about each brand.",rev);
   return '<div class="stack">'+top+aigrid+revsec+'</div>';
 },
 Content:function(){
   var grades=["A","B","C","D","F"],gc={A:"#22c55e",B:"#86efac",C:"#E2E8F0",D:"#fbbf24",F:"#ef4444"};
   var stack='<div class="cstack">'+RETS.map(function(r){var c=S().content_grades[r]||{},tot=grades.reduce(function(s,g){return s+(c[g]||0);},0)||1;return '<div class="row"><div class="l">'+r+'</div><div class="seg">'+grades.map(function(g){return c[g]?'<div title="'+g+': '+c[g]+'" style="width:'+(c[g]/tot*100).toFixed(1)+'%;background:'+gc[g]+'"></div>':"";}).join("")+'</div><div class="v">'+tot+'</div></div>';}).join("")+'</div><div class="gleg">'+grades.map(function(g){return '<span><i style="background:'+gc[g]+'"></i>'+g+'</span>';}).join("")+'</div>';
   var c1='<div class="card p"><h3>Listing content health</h3><p class="why">Weak listings lose the click you already won — thin titles, few images and no reviews quietly cap conversion.</p>'+stack+'</div>';
   var c2='<div class="card p"><h3>Weakest __BRAND__ listings to fix first</h3><p class="why">The lowest content scores, with the product so the team can act. Click a tile to open the retailer page.</p>'+pcards(S().weak_products)+'</div>';
   return sec("Content & search optimization","Where listing quality is capping conversion on __BRAND__\'s own SKUs.","<div class='stack'>"+c1+c2+"</div>");
 },
 Analytics:function(){
   var sh=(DATA.trend_focal&&DATA.trend_focal.length?DATA.trend_focal:[]);
   var note;
   if(sh.length<2){
     // day-1: a single snapshot has no time series yet — don't render 0%/undefined deltas
     note='<div class="tnote"><b>Reading the trend:</b> First snapshot captured — day-over-day trends appear once the daily refresh has run on a second day.</div>';
   }else{
     var first=sh[0],last=sh[sh.length-1],chg=(last-first).toFixed(1);
     var sp=DATA.trend_sponsored||[],sp0=sp.length?sp[0]:'—',sp1=sp.length?sp[sp.length-1]:'—';
     note='<div class="tnote"><b>Reading the trend:</b> __BRAND__ share of shelf moved from '+first+'% to '+last+'% over the window ('+(chg>=0?"+":"")+chg+' pts), while sponsored share went from '+sp0+'% to '+sp1+'% — competitors are buying visibility. Out-of-stock alerts by day: '+(DATA.trend_oos||[]).join(" → ")+'.</div>';
   }
   var trend='<div class="card p"><h3>Share of shelf over time</h3><p class="why">Day-over-day movement vs the competitive set — momentum, not just today\'s snapshot.</p>'+sparkline()+note+'</div>';
   var loved='<div class="card p"><h3>What customers love — __BRAND__</h3><p class="why">Share of positive review mentions by theme. Per-brand detail lives on the Brand tab.</p>'+hbar(DATA.voc_pos,"%")+'</div>';
   var fm=(DATA.voc_fix[0]&&DATA.voc_fix[0][1])||1;
   var fix='<div class="card p"><h3>What to fix — __BRAND__</h3><p class="why">Share of negative review mentions by theme — the top flagged theme to address.</p><div class="bars">'+DATA.voc_fix.map(function(r){return '<div class="br"><div class="l">'+r[0]+'</div><div class="t"><div class="f" style="width:'+(r[1]/fm*100).toFixed(0)+'%;background:#ef4444"></div></div><div class="v">'+r[1]+'%</div></div>';}).join("")+'</div></div>';
   return sec("Analytics & trends","How the shelf is moving over time — share momentum, sponsored pressure and availability by day.","<div class='stack'>"+trend+"<div class='grid2'>"+loved+fix+"</div></div>");
 },
 "D&T":function(){
   var d=DATA.trend_dates;
   var cells=[["i-store","Data sources",RETLBL+" SERP + PDP, plus "+ENGLBL+" answer engines"],
              ["i-refresh","Refresh cadence","Daily, on a Snowflake Task — captured async so the cockpit opens instantly"],
              ["i-bar","Snapshots loaded",d.length+" days ("+(d[0]||"")+" → "+(d[d.length-1]||"")+")"],
              ["i-db","SKUs this snapshot",fmtN(DATA.total_skus)+" classified shelf rows across "+RETS.length+" retailers"]];
   var grid='<div class="dgrid">'+cells.map(function(c){return '<div class="dc"><div class="di">'+ico(c[0])+'</div><div class="dl">'+c[1]+'</div><div class="dv">'+c[2]+'</div></div>';}).join("")+'</div>';
   var steps=[["1","Seed","Nimble Web Search Agents extract SERP + PDP into RAW tables, in-tenant"],["2","Resolve","Cortex classifies every SKU to a brand tier (__BRAND__ vs the set)"],["3","Model","Feature views → a governed semantic model for Cortex Analyst"],["4","Serve","A Cortex agent + this cockpit, both reading the same tables"]];
   var flow='<div class="card p"><h3>How it is built — entirely in Snowflake</h3><p class="why">No data leaves the tenant. One provisioning step builds the whole app from a single category (and optional brand).</p><div class="flow">'+steps.map(function(s){return '<div class="fstep"><div class="fn">STEP '+s[0]+'</div><div class="ft">'+s[1]+'</div><div class="fd">'+s[2]+'</div></div>';}).join("")+'</div></div>';
   var objs='<div class="card p"><h3>Governed objects</h3><p class="why">Everything is a first-class Snowflake object — versioned, permissioned, auditable.</p><div class="obj"><span class="objc">semantic view <b>SHELF_SV</b></span><span class="objc">agent <b>__AGENT_NAME__</b></span><span class="objc">cockpit <b>__SCHEMA___COCKPIT</b></span><span class="objc">daily task <b>DAILY_SHELF_TASK</b></span><span class="objc">on-demand <b>REFRESH_SHELF()</b></span></div></div>';
   return sec("Data & technology","The pipeline behind the cockpit — sources, freshness and the in-Snowflake build.","<div class='stack'>"+grid+flow+objs+"</div>");
 },
 "Raw Data":function(){
   var h='<table class="rtbl"><thead><tr><th>Product</th><th>Brand tier</th><th>Retailer</th><th>Pos</th><th>Price</th><th>Status</th></tr></thead><tbody>'+DATA.raw_rows.map(function(p){return '<tr class="'+(p.kk?"kkr":"")+'"><td class="pn" title="'+p.name+'">'+p.name+'</td><td>'+p.brand+'</td><td class="cap">'+p.retailer+'</td><td>'+(p.pos==null?"—":p.pos)+'</td><td>'+(p.price==null?"—":"$"+p.price)+'</td><td>'+(p.oos?'<span class="ob">Out of stock</span>':'<span class="ib">In stock</span>')+'</td></tr>';}).join("")+'</tbody></table>';
   return sec("Raw shelf data","Live classified SERP rows for the latest snapshot — the source rows behind every metric ("+fmtN(DATA.total_skus)+" total this snapshot, top 40 shown).","<div class='card p' style='overflow-x:auto'>"+h+"</div>");
 }
};
/* ---------- nav + routing ---------- */
var NAV=[["Leadership","i-brief"],["Retailer","i-cart"],["Brand","i-tag"],["Content","i-doc"],["Analytics","i-bar"],["D&T","i-wrench"],["Raw Data","i-db"]];
var navEl=document.getElementById("nav"),viewsEl=document.getElementById("views");
NAV.forEach(function(o,i){var b=document.createElement("button");b.className="t"+(i===0?" on":"");b.innerHTML=ico(o[1])+o[0];b.onclick=function(){go(o[0],b);};navEl.appendChild(b);});
function bindInsights(){document.querySelectorAll(".icard").forEach(function(c){c.onclick=function(){var t=c.getAttribute("data-tab");if(!t)return;var btn=Array.prototype.slice.call(navEl.children).filter(function(x){return x.textContent.trim()===t;})[0];if(btn)go(t,btn);};});var r=document.getElementById("regen");if(r)r.onclick=function(){paint("Leadership");};}
function renderBrandReviews(bt){
  var b=document.getElementById("brbody");if(!b)return;var r=DATA.brand_reviews[bt];if(!r){b.innerHTML="";return;}
  var sp=r.split||[0,0,0],col=BC[bt]||"#234291";
  var stat='<div class="brstat"><div class="bx"><div class="bn">'+(r.rec!=null?r.rec+"%":"—")+'</div><div class="bxl">would recommend</div></div><div class="bx"><div class="bn">'+(r.star!=null?r.star+"%":"—")+'</div><div class="bxl">5-star reviews</div></div><div class="bx"><div class="bn">'+(r.mentions||0).toLocaleString()+'</div><div class="bxl">review mentions</div></div></div>';
  var splitbar='<div class="splitbar"><div style="width:'+sp[0]+'%;background:#22c55e"></div><div style="width:'+sp[2]+'%;background:#CBD5E1"></div><div style="width:'+sp[1]+'%;background:#ef4444"></div></div><div class="splitleg"><span><i style="background:#22c55e"></i>positive '+sp[0]+'%</span><span><i style="background:#CBD5E1"></i>neutral '+sp[2]+'%</span><span><i style="background:#ef4444"></i>negative '+sp[1]+'%</span></div>';
  var loved=(r.pos&&r.pos.length)?'<div class="revcol"><div class="revh">What they love</div>'+hbar(r.pos,"%")+'</div>':'';
  var fm=(r.neg&&r.neg[0]&&r.neg[0][1])||1;
  var flag=(r.neg&&r.neg.length)?'<div class="revcol"><div class="revh">What they flag</div><div class="bars">'+r.neg.map(function(x){return '<div class="br"><div class="l">'+x[0]+'</div><div class="t"><div class="f" style="width:'+(x[1]/fm*100).toFixed(0)+'%;background:#ef4444"></div></div><div class="v">'+x[1]+'%</div></div>';}).join("")+'</div></div>':'';
  var summ=r.summary?'<div class="revsumm"><div class="revh">In their words</div><p>“'+r.summary+'”</p></div>':'';
  b.innerHTML='<div class="revhead" style="border-color:'+col+'"><span class="brdot" style="background:'+col+'"></span><b>'+bt+'</b><span class="revsub">what shoppers say</span></div>'+stat+splitbar+'<div class="revgrid">'+loved+flag+'</div>'+summ;
}
function bindBrand(){var chips=document.querySelectorAll("#brsel .brchip");chips.forEach(function(c){c.onclick=function(){chips.forEach(function(x){x.classList.remove("on");});c.classList.add("on");renderBrandReviews(c.getAttribute("data-b"));};});if(DATA.brand_order&&DATA.brand_order.length)renderBrandReviews(DATA.brand_order[0]);}
function paint(name){CUR=name;viewsEl.innerHTML='<div class="view on">'+VIEWS[name]()+'</div>';if(name==="Leadership")bindInsights();if(name==="Brand")bindBrand();window.scrollTo(0,0);}
function go(name,btn){Array.prototype.forEach.call(navEl.children,function(n){n.classList.remove("on");});btn.classList.add("on");paint(name);}
var _sh=document.getElementById("subhead");if(_sh)_sh.textContent=SUBJ+" · "+RETLBL;
renderKPIs();renderFilters();
paint("Leadership");
</script>"""
# Internal-scroll iframe so the header pins and the floating Nimble Web Search
# button stays in view (a tall non-scrolling iframe pushes fixed elements off-screen).
_loading.empty()  # data assembled — drop the loading note and paint the cockpit
components.html(HTML.replace("__DATA__", json.dumps(data)).replace("__AGENT_NAME__", AGENT_NAME), height=820, scrolling=True)

# ===== Nimble Web Search — LIVE Cortex assistant =====
# Runs as a native Streamlit element so it has a live Snowflake session for Cortex
# (the embedded SPA iframe above is sandboxed). Primary engine: Cortex Analyst
# text-to-SQL over the __BRAND__ semantic view, with Cortex Complete grounded in
# today's metrics as an alternative.
SV_FQN = DB + "." + SCHEMA + ".SHELF_SV"


def _ground(q):
    return cortex("You are __BRAND__'s digital-shelf analyst for the CMO. Answer in 3-5 sentences, concrete and "
                  "specific with numbers, using ONLY the live context below. If the answer isn't in the context, "
                  "say what you'd pull next. No jargon, no emoji.\n\nLIVE CONTEXT: " + CTX + "\n\nQUESTION: " + q)


_FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|CALL|CREATE|ALTER|DROP|GRANT|REVOKE|TRUNCATE|COPY)\b", re.I)


def _safe_select(sql):
    """Only run Analyst-generated SQL if it's a single read-only SELECT scoped to the
    semantic view — never execute generated SQL blindly. Returns the SQL or None."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s or ";" in s:                                    # empty or multi-statement
        return None
    if not re.match(r"^(SELECT|WITH)\b", s, re.I):           # read-only entry points only
        return None
    if _FORBIDDEN.search(s):                                 # no DDL/DML
        return None
    if "SHELF_SV" not in s.upper():                          # scoped to the app's semantic view
        return None
    return s


def ask_live(q):
    """Cortex Analyst (text-to-SQL over the semantic view); falls back to Cortex Complete."""
    try:
        import _snowflake
        body = {"messages": [{"role": "user", "content": [{"type": "text", "text": q}]}], "semantic_view": SV_FQN}
        resp = _snowflake.send_snow_api_request("POST", "/api/v2/cortex/analyst/message", {}, {}, body, None, 60000)
        content = resp.get("content") if isinstance(resp, dict) else None
        if isinstance(content, str):
            content = json.loads(content)
        msg = content.get("message", content) if isinstance(content, dict) else {}
        parts = msg.get("content", []) if isinstance(msg, dict) else []
        text, sql = "", None
        for p in parts:
            if not isinstance(p, dict):
                continue
            if p.get("type") == "text":
                text += p.get("text", "")
            elif p.get("type") == "sql":
                sql = p.get("statement")
        safe = _safe_select(sql)
        if safe:
            df = session.sql(safe).to_pandas()
            if len(df) > 50:
                df = df.head(50)
            return {"text": (text or "Here's what the live shelf shows:"), "df": df}
        if sql:                          # Analyst returned SQL we won't run → grounded answer instead
            return {"text": _ground(q)}
        if text:
            return {"text": text}
    except Exception:
        pass
    return {"text": _ground(q)}


def _chat_panel():
    if "live_chat" not in st.session_state:
        st.session_state.live_chat = []
    st.caption("Live answers from Snowflake Cortex over your __BRAND__ semantic model — ask about share, pricing, AI presence or reviews.")
    box = st.container()
    q = None
    try:
        q = st.chat_input("Ask anything about __BRAND__'s shelf…")
    except Exception:
        with st.form("nwsform", clear_on_submit=True):
            _qt = st.text_input("Ask the shelf")
            if st.form_submit_button("Ask") and _qt:
                q = _qt
    if q:
        st.session_state.live_chat.append(("user", q, None))
        with st.spinner("Cortex is analysing the live shelf…"):
            _r = ask_live(q)
        st.session_state.live_chat.append(("assistant", _r["text"], _r.get("df")))
    with box:
        if not st.session_state.live_chat:
            st.markdown("Try: *Where am I losing share of shelf and why?* · *Compare __BRAND__ vs a competitor on price.* · *Which sources do AI engines cite most?*")
        for _role, _txt, _df in st.session_state.live_chat:
            try:
                with st.chat_message(_role):
                    st.markdown(_txt)
                    if _df is not None and len(_df):
                        st.dataframe(_df)
            except Exception:
                st.markdown(("**You:** " if _role == "user" else "**Analyst:** ") + _txt)


# Floating launcher → opens a modal with the live chat (native button, fixed bottom-right).
if hasattr(st, "dialog"):
    st.markdown('<div id="nws-anchor"></div>', unsafe_allow_html=True)
    st.markdown("""<style>
    div:has(#nws-anchor)+div button{position:fixed;bottom:22px;right:22px;z-index:1000;border:none;border-radius:999px;
      background:linear-gradient(135deg,#FFE066,#FFC542 55%,#FF9E1C);color:#7C3A03;font-weight:700;font-size:14px;
      padding:11px 22px;box-shadow:0 8px 22px rgba(217,119,6,.30),0 0 0 1px rgba(180,83,9,.16);}
    div:has(#nws-anchor)+div button:hover{box-shadow:0 12px 30px rgba(217,119,6,.36);transform:translateY(-1px);}
    </style>""", unsafe_allow_html=True)

    @st.dialog("Nimble Web Search")
    def _nws_dialog():
        _chat_panel()

    if st.button("✦  Nimble Web Search", key="nws_open"):
        _nws_dialog()
else:
    st.divider()
    st.markdown("#### ✦  Nimble Web Search")
    _chat_panel()
