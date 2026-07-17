"""Catalog whitespace math: find empty/weak cells in subcategory x price band x rating.

Zero API runs - pure SQL over the Delta catalog. Produces candidate gap cells that
the synthesis loop turns into verified gap statements.

Usage: python gaps.py   # prints the whitespace report
"""
import config as C
import delta

BAND_SQL = """
CASE
  WHEN price_usd < 50 THEN '<$50'
  WHEN price_usd < 150 THEN '$50-150'
  WHEN price_usd < 400 THEN '$150-400'
  ELSE '$400+'
END"""


def normalize_subcat_sql():
    """Map free-text subcategory values onto the six chunk families."""
    return """
    CASE
      WHEN LOWER(CONCAT(COALESCE(subcategory, ''), ' ', chunk_id)) RLIKE 'espresso' THEN 'espresso'
      WHEN LOWER(CONCAT(COALESCE(subcategory, ''), ' ', chunk_id)) RLIKE 'single|pod|k-cup' THEN 'single-serve'
      WHEN LOWER(CONCAT(COALESCE(subcategory, ''), ' ', chunk_id)) RLIKE 'drip' THEN 'drip'
      WHEN LOWER(CONCAT(COALESCE(subcategory, ''), ' ', chunk_id)) RLIKE 'french|pour|moka|specialty' THEN 'specialty'
      WHEN LOWER(CONCAT(COALESCE(subcategory, ''), ' ', chunk_id)) RLIKE 'cold|iced' THEN 'cold-brew'
      WHEN LOWER(CONCAT(COALESCE(subcategory, ''), ' ', chunk_id)) RLIKE 'combo|grind|dual' THEN 'combo'
      ELSE 'other'
    END"""


def whitespace_cells():
    """Every (subcategory, band) cell with counts + quality stats."""
    cols, rows = delta.query(f"""
        SELECT {normalize_subcat_sql()} AS subcat, {BAND_SQL} AS band,
               COUNT(*) AS n_products,
               SUM(CASE WHEN rating >= 4.2 THEN 1 ELSE 0 END) AS n_wellrated,
               ROUND(AVG(rating), 2) AS avg_rating,
               MAX(review_count) AS max_reviews
        FROM {C.DBX_SCHEMA}.catalog
        WHERE price_usd IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1, 2""")
    return cols, rows


def candidate_cells(min_products=3, min_wellrated=1):
    """Cells that look like whitespace: few products, or none well-rated.

    A cell with products but zero rated >=4.2 is a QUALITY gap (demand exists,
    nothing satisfies it) - usually the more interesting story than a bare empty cell.
    """
    cols, rows = whitespace_cells()
    idx = {c: i for i, c in enumerate(cols)}
    out = []
    for r in rows:
        subcat, band = r[idx["subcat"]], r[idx["band"]]
        n, wr = r[idx["n_products"]], r[idx["n_wellrated"]]
        if subcat == "other":
            continue
        if n < min_products:
            out.append({"subcat": subcat, "band": band, "kind": "assortment gap",
                        "detail": f"only {n} products in cell"})
        elif wr < min_wellrated:
            out.append({"subcat": subcat, "band": band, "kind": "quality gap",
                        "detail": f"{n} products, none rated >=4.2"})
    return out


if __name__ == "__main__":
    cols, rows = whitespace_cells()
    print(f"{'subcat':13}{'band':10}{'n':>4}{'4.2+':>6}{'avg':>6}{'maxRev':>8}")
    for r in rows:
        print(f"{str(r[0]):13}{str(r[1]):10}{r[2]:>4}{r[3]:>6}{str(r[4]):>6}{str(r[5]):>8}")
    print("\ncandidates:")
    for c in candidate_cells():
        print(" ", c)
