-- Diligence Desk schema. Run once in the Supabase SQL editor.

create table if not exists dd_memos (
  id bigint generated always as identity primary key,
  company text not null,
  input_prompt text not null,
  run_id text,
  interaction_id text,
  status text not null default 'running',
  verdict text,
  data_as_of_date text,
  raw_result jsonb,          -- verbatim AgentRunResult, saved before any transform
  memo_narrative text,       -- Editor (crew) output
  evidence_gaps jsonb,       -- Risk Officer output
  pdf_path text,
  emailed_to text[],
  created_at timestamptz not null default now()
);

create table if not exists dd_claims (
  id bigint generated always as identity primary key,
  memo_id bigint not null references dd_memos(id) on delete cascade,
  path text,
  confidence text,
  reasoning text,
  citations jsonb,
  created_at timestamptz not null default now()
);
create index if not exists dd_claims_memo_idx on dd_claims(memo_id);

create table if not exists dd_followups (
  id bigint generated always as identity primary key,
  memo_id bigint not null references dd_memos(id) on delete cascade,
  question text not null,
  answer text,
  key_points jsonb,
  interaction_id text,
  raw_result jsonb,
  created_at timestamptz not null default now()
);
create index if not exists dd_followups_memo_idx on dd_followups(memo_id);

create table if not exists dd_agent_updates (
  id bigint generated always as identity primary key,
  instruction text not null,
  expertise_before text,
  expertise_after text,
  created_at timestamptz not null default now()
);
