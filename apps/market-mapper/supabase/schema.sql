-- Market Mapper — Supabase schema.
-- Run once in the Supabase SQL Editor (Dashboard -> SQL Editor -> New query).

create table if not exists mm_runs (
    id               uuid primary key default gen_random_uuid(),
    created_at       timestamptz not null default now(),
    icp_prompt       text not null,
    exclude_domains  jsonb not null default '[]'::jsonb,
    agent_id         text,                 -- WSA v2 agent id (wsa_...)
    run_id           text,                 -- task_run_...
    interaction_id   text,                 -- pass back as previous_interaction_id to expand the map
    status           text not null default 'running',
    discovered_count integer,
    completed_at     timestamptz,
    raw_result       jsonb                 -- verbatim discovery result (incl. trust)
);

create table if not exists mm_companies (
    id               bigint generated always as identity primary key,
    run_id           uuid not null references mm_runs(id) on delete cascade,
    created_at       timestamptz not null default now(),

    -- discovery fields (all text; numerics stay strings by design)
    company_name     text not null,
    domain           text not null,
    website          text,
    linkedin_url     text,
    industry         text,
    employee_count   text,
    headquarters     text,
    recent_funding   text,
    icp_fit_reason   text,
    source_url       text,
    size_flag        text,                 -- null | 'out_of_band' (post-hoc constraint check)

    -- enrichment fields
    funding_stage    text,
    total_funding    text,
    headcount_estimate text,
    key_investors    jsonb,
    tech_stack       jsonb,
    key_contacts     jsonb,
    buying_signals   jsonb,
    summary          text,
    enrich_status    text not null default 'pending',   -- pending | running | enriched | failed | skipped
    enriched_at      timestamptz,

    -- trust
    enrichment_confidence text,            -- high | medium | low | pre_existing
    claims           jsonb,                -- per-field claims from the enrichment trust object
    raw_enrichment   jsonb,                -- verbatim enrichment result

    unique (run_id, domain)
);

create index if not exists mm_companies_run_idx on mm_companies (run_id);
create index if not exists mm_companies_status_idx on mm_companies (enrich_status);
