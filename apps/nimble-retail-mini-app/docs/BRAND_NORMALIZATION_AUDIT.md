# Brand Normalization Audit (P0)

**Problem:** product sub-lines are treated as separate competing brands — e.g. *Monster Energy*, *Monster Ultra*, *Monster Open*, *Monster Wireless* all count as distinct brands. This corrupts every brand-keyed insight.
**Date:** 2026-06-01 · *Audit + strategy only — no code yet.*

---

## 1. Current extraction logic

**Where brand is set:** `deriveBrand(row, title)` in `src/services/nimble-serp.ts:109` (live) and the mock generator in `mock-data.ts` (demo).

```
1. If the row has an explicit field (brand / brand_name / manufacturer) → use it verbatim.
2. Else parse the title: skip stopwords (the, a, new, premium, original, fresh),
   then take token 1, and token 2 as well if it's also Capitalized
   ("Premier Protein", "Black Rifle"). Strip punctuation.
```

**Where it's consumed:** `computeBrandShare(rows)` in `insight-engine.ts:27` groups by the **raw `r.brand` string** (`map.get(r.brand)`). Everything downstream keys off that map:

- Share of Shelf (`brandShare`)
- Executive Verdicts (Winner = `brandShare[0]`, Threat = `brandShare[1]`, Opportunity)
- `priceGap` / Cross-Retailer differences (per-retailer `topBrand`)
- Run My Brand (`analyzeBrand` matches against `brandShare`)
- Email report tables

**Root cause:** there is **no canonicalization step**. Whatever string `deriveBrand` produces (or the agent's explicit `brand` field) is the grouping key. So:

| Raw brand string | Today | Should be |
|---|---|---|
| "Monster Energy" | Monster Energy | **Monster** |
| "Monster Ultra" | Monster Ultra | **Monster** |
| "Monster Open" / "Monster Wireless" | separate brands | **Monster** |
| "Premier Protein Shake" | Premier Protein Shake | **Premier Protein** |
| "Red Bull Sugar Free" | Red Bull Sugar Free | **Red Bull** |

Effect: a true category leader (Monster) gets its share **split across 4–6 phantom brands**, so it can drop out of the leader/threat slots entirely — breaking Winner/Threat/Opportunity, Share of Shelf, Run My Brand matching, and the cross-retailer leader comparison.

---

## 2. Canonical brand strategy

Introduce one normalization layer, applied **once at the boundary of `buildInsights`** (map every row's brand → canonical before any aggregation). Keep the original on the row as `brandRaw` / `productTitle` for the raw-shelf table. New module: `src/lib/brand-normalize.ts` exporting `canonicalizeBrand(raw, title?) → { brand, confidence }`.

**Canonical dictionary (seed):** we already maintain the real brand list — `BRAND_DOMAINS` keys in `mock-data.ts` (~50 brands across the 5 categories) plus the per-category `CATEGORIES[].brands`. Use these as the authoritative set of canonical names (Monster, Red Bull, Celsius, Premier Protein, Quest, RXBAR, LaCroix, Liquid Death, Purina, Folgers, Starbucks, …).

**Resolution order (first match wins):**
1. **Exact canonical match** — normalized raw equals a canonical name → that canonical (confidence 1.0).
2. **Known-brand prefix / contains** — raw or title *leads with* a canonical name on a token boundary (e.g. "Monster Ultra" starts with "Monster"; "Premier Protein Shake" starts with "Premier Protein") → that canonical (0.9). Use the **longest** matching canonical to avoid "Red" vs "Red Bull" collisions.
3. **Alias map** — explicit overrides for cases the dictionary can't infer (0.85; §3).
4. **Sub-line suffix strip** — strip a curated sub-line lexicon (Energy, Ultra, Zero, Open, Wireless, Rehab, Java, Reserve, Hydro, Sugar Free, Shake, Bar) **only** when the remainder is itself a canonical brand (0.8). Guards against eating real names (e.g. never reduce "Liquid Death").
5. **Fallback** — keep `deriveBrand`'s first-token result as-is (confidence ≤ 0.5) and **do not merge**.

All strategic insights (share, verdicts, threat, opportunity, Run My Brand, cross-retailer) then operate on the canonical brand. The raw shelf explorer keeps the full product title.

---

## 3. Alias strategy

A small explicit map for things the dictionary/heuristics can't catch, keyed by normalized raw → canonical:

```
"monsterenergy" | "monsterultra" | "monsteropen" | "monsterwireless"
   | "monsterrehab" | "monsterjava" | "monsterreserve"        → "Monster"
"redbullsugarfree" | "redbulleditions"                        → "Red Bull"
"premierproteinshake" | "premiernutrition"                    → "Premier Protein"
"celsiusessentials" | "celsiusheat"                           → "Celsius"
"bangenergy"                                                  → "Bang"
"questnutrition" | "questbar"                                 → "Quest"
"gatoradezero"                                                → "Gatorade"
```

Seeded now from the known catalog; extended as live data surfaces new sub-lines. The map is a thin override on top of the dictionary — most rollups should resolve via rule 2 without an explicit entry.

---

## 4. Brand-family rollup strategy

- **Family = canonical brand.** All sub-lines (flavor, format, size, sub-brand) roll up to the family for *strategic* metrics.
- **Rollup is aggregation-time, not destructive.** `row.brand` becomes canonical; `row.brandRaw` + `row.productTitle` preserve the sub-line so the raw-shelf table and any future "sub-line drill-down" still work.
- **Cross-retailer & price gap** compare canonical families (so "Monster on Amazon vs Walmart" is apples-to-apples).
- **Run My Brand** matches the typed brand against canonical families, so "Monster" finds the whole family, not one flavor.
- **Optional later:** a sub-line breakdown *within* a brand drawer (not needed for P0).

---

## 5. Confidence thresholds

| Confidence | Rule | Action |
|---|---|---|
| 1.0 | exact canonical match | merge |
| 0.9 | known-brand leading match (longest) | merge |
| 0.85 | explicit alias map | merge |
| 0.8 | sub-line suffix strip → remainder is canonical | merge |
| ≤ 0.5 | heuristic first-token only | **keep separate** (no merge) |

**Merge only at ≥ 0.7.** Below that we leave the brand as extracted — under-merging (a stray sub-line shows once) is far safer than over-merging (collapsing two real brands). Optionally log low-confidence brands in dev to grow the dictionary/alias map over time.

**Verification when built:** run Energy Drinks live; assert Monster appears **once** (not Energy/Ultra/Open split), that its share = sum of its sub-lines, and that Winner/Threat/Run-My-Brand reflect the consolidated family. Repeat for Protein Bars (Premier Protein) and a Red Bull query.
