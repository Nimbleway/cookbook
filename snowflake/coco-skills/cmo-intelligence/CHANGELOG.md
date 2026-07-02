# Changelog

All notable changes to the **CMO Intelligence** Cortex Code skill are recorded here.
The version lives in `SKILL.md` frontmatter (`version:`); this file follows
[Keep a Changelog](https://keepachangelog.com/) and [Semantic Versioning](https://semver.org/)
(`MAJOR.MINOR.PATCH`). Bump on every change: PATCH for fixes/copy, MINOR for new
capability, MAJOR for a breaking change to the provisioned objects or the invocation.

## [1.0.0] — 2026-07-02

First versioned release. The skill provisions a complete, in-tenant digital-shelf
intelligence app from a plain-English brief, entirely inside Snowflake.

### Added
- Conversational provisioning end to end: per-app schema, config tables (`CFG_APP` /
  `CFG_QUERIES`), scheduled `NIMBLE_AGENT_RUN` ingestion, Cortex brand resolver,
  analytics views, a Cortex Analyst semantic view (`SHELF_SV`), a Cortex agent, and a
  branded Streamlit-in-Snowflake cockpit. Stays updatable after creation (add a keyword
  = one row).
- Cortex agent with a **live web tool** (`NIMBLE_SEARCH`) alongside `analyze_shelf`.
- **Share of AI Answer** (`REFRESH_GEO`): real Perplexity/ChatGPT/Gemini answers via
  Nimble's LLM agents → `GEO_ANSWERS` / `GEO_SOURCES`. Two-tier cadence — a small
  first-setup seed (`GEO_SEED_TASK`) + a full weekly refresh (`WEEKLY_GEO_TASK`). Cockpit
  shows a "being generated" placeholder until the first run lands.
- **Active Alerts** (`V_ALERTS`): multi-signal — out of stock, weak content (D/F), and
  lost page-1 rank — so alerts are meaningful at any catalog size.
- Retailer view: **average price by brand × retailer** (on `best_price`, populated for all
  retailers).
- Per-app cockpit naming (unique object + brand `TITLE`); latest-*complete*-snapshot logic
  so a mid-run day never renders an empty retailer.

### Uses
- Snowflake AISQL (`AI_COMPLETE`, latest available Sonnet + Haiku, region-probed).
- Requires the Nimble × Snowflake integration **≥ 1.1.0** (EAI + secret + `NIMBLE_AGENT_RUN`
  UDTF + `NIMBLE_SEARCH` UDF).
