-- Deep Web Alpha Tracker: every company, agent result, run, refresh and change lives in these tables.
-- The app reads and writes them server-side with the service role key; RLS is on with no policies,
-- so the anon key cannot read them.

create table if not exists dwa_companies (
  ticker text primary key,
  name text not null,
  domain text not null,
  sector text not null,
  created_at timestamptz not null default now()
);

create table if not exists dwa_refreshes (
  id uuid primary key default gen_random_uuid(),
  effort text not null check (effort in ('low', 'medium', 'high', 'x-high')),
  agents text[] not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  locked_until timestamptz,
  changes_found int not null default 0,
  alerts_sent int not null default 0
);

-- One row per company x agent per refresh: the Nimble run, its status and the raw output it returned.
create table if not exists dwa_runs (
  id bigint generated always as identity primary key,
  refresh_id uuid not null references dwa_refreshes (id) on delete cascade,
  ticker text not null references dwa_companies (ticker),
  agent text not null,
  agent_id text,
  run_id text,
  status text not null check (status in ('pending', 'running', 'completed', 'failed', 'skipped')),
  error text,
  output jsonb,
  started_at timestamptz,
  completed_at timestamptz
);
create index if not exists dwa_runs_refresh_status on dwa_runs (refresh_id, status);

-- Latest mapped result per company x agent (what the dashboard shows).
create table if not exists dwa_agent_data (
  ticker text not null references dwa_companies (ticker),
  agent text not null,
  source text not null check (source in ('sample', 'live')),
  data jsonb not null,
  run_id text,
  updated_at timestamptz not null default now(),
  primary key (ticker, agent)
);

-- Every mapped result ever stored, for trends and audit.
create table if not exists dwa_agent_history (
  id bigint generated always as identity primary key,
  ticker text not null references dwa_companies (ticker),
  agent text not null,
  source text not null,
  data jsonb not null,
  run_id text,
  captured_at timestamptz not null default now()
);
create index if not exists dwa_agent_history_lookup on dwa_agent_history (ticker, agent, captured_at desc);

-- Meaningful changes found between two results; alerted marks the ones sent to Slack.
create table if not exists dwa_changes (
  id text primary key,
  refresh_id uuid references dwa_refreshes (id) on delete set null,
  date date not null,
  ticker text not null references dwa_companies (ticker),
  agent text not null,
  headline text not null,
  direction text not null check (direction in ('bullish', 'bearish', 'neutral')),
  magnitude int not null check (magnitude between 1 and 3),
  confidence text not null check (confidence in ('high', 'medium', 'low')),
  citations jsonb not null default '[]',
  source text not null default 'live' check (source in ('sample', 'live')),
  alerted boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists dwa_changes_date on dwa_changes (date desc);

alter table dwa_companies enable row level security;
alter table dwa_refreshes enable row level security;
alter table dwa_runs enable row level security;
alter table dwa_agent_data enable row level security;
alter table dwa_agent_history enable row level security;
alter table dwa_changes enable row level security;
