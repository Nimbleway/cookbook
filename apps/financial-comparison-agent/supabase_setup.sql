-- Comps Agent — Supabase schema.
-- Run once in the Supabase SQL Editor (Dashboard -> SQL Editor -> New query).

create table if not exists comps_runs (
    id            uuid primary key default gen_random_uuid(),
    created_at    timestamptz not null default now(),
    target_ticker text not null,
    target_name   text,
    verdict       text,
    catalysts     jsonb not null default '[]'::jsonb,
    model         text
);

create table if not exists comps_metrics (
    id            bigint generated always as identity primary key,
    run_id        uuid not null references comps_runs(id) on delete cascade,
    ticker        text not null,
    name          text,
    is_target     boolean not null default false,
    market_cap_b  double precision,
    pe            double precision,
    forward_pe    double precision,
    ps            double precision,
    ev_ebitda     double precision,
    peg           double precision,
    rev_growth    double precision,
    gross_margin  double precision,
    op_margin     double precision,
    profit_margin double precision,
    roe           double precision,
    price_target  double precision,
    analyst_recom double precision,
    source_url    text
);

create index if not exists comps_metrics_run_id_idx on comps_metrics (run_id);
