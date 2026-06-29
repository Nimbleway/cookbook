/*
 * coco-skills/cmo-intelligence/sql/semantic_view.sql — Cortex Analyst semantic view
 *
 * Role:     NIMBLE_ROLE
 * Creates:  __DB__.__SCHEMA__.SHELF_SV
 * Prereq:   views.sql (V_BRAND_CLASSIFIED + V_SHARE_OF_SHELF)
 *
 * SHELF_SV is the governed semantic layer the Cortex agent queries on the user's
 * behalf (NL -> SQL). Phase 1 grounds it on shelf / price / sponsored;
 * sentiment, content, AI-answer and NBA live in cockpit-only views for now and
 * can be folded in by widening this view as those sections graduate.
 *
 * TEMPLATE PLACEHOLDERS: __DB__ __SCHEMA__ __BRAND__   (see config.sql)
 */

USE ROLE NIMBLE_ROLE;
USE SCHEMA __DB__.__SCHEMA__;

CREATE OR REPLACE SEMANTIC VIEW __DB__.__SCHEMA__.SHELF_SV
tables (
    SHELF as __DB__.__SCHEMA__.V_BRAND_CLASSIFIED primary key (RETAILER, PRODUCT_ID, SNAPSHOT_DATE) with synonyms=('products', 'skus', 'shelf'),
    RANK  as __DB__.__SCHEMA__.V_SHARE_OF_SHELF   primary key (RETAILER, SNAPSHOT_DATE, BRAND_TIER) with synonyms=('share of shelf', 'brand share')
)
facts (
    SHELF.PRICE      as best_price,
    SHELF.UNIT_PRICE as unit_price_amount,
    SHELF.POS        as position
)
dimensions (
    SHELF.RETAILER     as retailer     with synonyms=('store', 'channel'),
    SHELF.BRAND_TIER   as brand_tier   with synonyms=('brand', 'competitor'),
    SHELF.IS_FOCAL     as is_focal     with synonyms=('focal'),
    SHELF.PRODUCT_NAME as product_name,
    SHELF.IS_SPONSORED as sponsored,
    SHELF.IS_OOS       as product_out_of_stock,
    RANK.RETAILER      as rank_retailer,
    RANK.BRAND_TIER    as rank_brand_tier
)
metrics (
    SHELF.PRODUCTS       as COUNT(shelf.product_id),
    SHELF.FOCAL_SHARE    as SUM(CASE WHEN shelf.is_focal THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(shelf.product_id), 0) with synonyms=('share of shelf', '__BRAND__ share'),
    SHELF.AVG_PRICE      as AVG(shelf.best_price),
    SHELF.AVG_UNIT_PRICE as AVG(shelf.unit_price_amount) with synonyms=('unit price', 'price per unit'),
    RANK.TIER_SHARE      as AVG(rank.share_of_shelf_pct) with synonyms=('competitor share'),
    RANK.TIER_SPONSORED  as AVG(rank.sponsored_share_pct) with synonyms=('sponsored share')
);
