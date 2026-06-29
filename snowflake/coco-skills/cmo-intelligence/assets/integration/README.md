# Bundled Nimble × Snowflake integration

These two files are **verbatim copies** of the canonical integration so the skill can install the
prerequisite when it's missing and the user is `ACCOUNTADMIN` (the skill ships standalone, so it
carries its own copy rather than relying on a relative path to the cookbook):

- `setup.sql` — copy of [`snowflake/setup/setup.sql`](https://github.com/Nimbleway/cookbook/blob/main/snowflake/setup/setup.sql)
  (role, DB, warehouse, network rule, secret, External Access Integration).
- `nimble_agent_run.sql` — copy of [`snowflake/udtf-data-feeds/nimble_agent_run.sql`](https://github.com/Nimbleway/cookbook/blob/main/snowflake/udtf-data-feeds/nimble_agent_run.sql)
  (the `NIMBLE_AGENT_RUN` UDTF).

**Source of truth is the cookbook.** Keep these in sync — if the canonical files change, re-copy them
(they should stay byte-identical). The skill substitutes `<<YOUR_NIMBLE_API_KEY>>` in `setup.sql` with
the key the user provides at install time; the key lands only in the Snowflake `SECRET`.

**Expected integration version: `1.0.0`** — the version these bundled copies install (see
`NIMBLE_INTEGRATION.TOOLS.INTEGRATION_VERSION` in `setup.sql`). Phase 0 compares the *installed*
version against this and recommends an upgrade if the account is older. When you re-sync these files
after a canonical change, bump this number to match `setup.sql`.
