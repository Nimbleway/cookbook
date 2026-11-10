import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { AGENTS } from './agents';
import type { AgentKey, ChangeEvent, Company, CompanyRecord, Snapshot } from './types';

let client: SupabaseClient | null = null;

export function db(): SupabaseClient {
  if (!client) {
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!url || !key) throw new Error('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set');
    client = createClient(url, key, { auth: { persistSession: false } });
  }
  return client;
}

export function must<T>(res: { data: T | null; error: { message: string } | null }): T {
  if (res.error) throw new Error(res.error.message);
  return res.data as T;
}

export interface AgentDataRow {
  ticker: string;
  agent: AgentKey;
  source: 'sample' | 'live';
  data: Partial<CompanyRecord>;
  run_id: string | null;
  updated_at: string;
}

export function emptyRecord(company: Company): CompanyRecord {
  return {
    company,
    updatedAt: Object.fromEntries(AGENTS.map((a) => [a.key, null])) as Record<AgentKey, string | null>,
    deepDive: null,
    channel: null,
    filings: [],
    forensic: null,
    management: null,
    catalysts: [],
    supplyChain: [],
    competitors: [],
    gov: [],
  };
}

export function assemble(company: Company, rows: AgentDataRow[]): CompanyRecord {
  const rec = emptyRecord(company);
  for (const row of rows) {
    Object.assign(rec, row.data);
    rec.updatedAt[row.agent] = row.updated_at;
  }
  return rec;
}

export async function loadCompanies(): Promise<Company[]> {
  return must(await db().from('dwa_companies').select('ticker,name,domain,sector').order('ticker'));
}

async function loadAgentRows(ticker?: string): Promise<AgentDataRow[]> {
  const out: AgentDataRow[] = [];
  for (let from = 0; ; from += 1000) {
    let q = db().from('dwa_agent_data').select('ticker,agent,source,data,run_id,updated_at').range(from, from + 999);
    if (ticker) q = q.eq('ticker', ticker);
    const page = must(await q) as AgentDataRow[];
    out.push(...page);
    if (page.length < 1000) return out;
  }
}

export async function loadRecord(company: Company): Promise<{ record: CompanyRecord; rows: AgentDataRow[] }> {
  const rows = await loadAgentRows(company.ticker);
  return { record: assemble(company, rows), rows };
}

export async function loadSnapshot(): Promise<Snapshot & { liveShare: number }> {
  const [companies, rows, changes] = await Promise.all([
    loadCompanies(),
    loadAgentRows(),
    db().from('dwa_changes').select('*').order('date', { ascending: false }).limit(600).then(must),
  ]);
  const byTicker = new Map<string, AgentDataRow[]>();
  for (const r of rows) byTicker.set(r.ticker, [...(byTicker.get(r.ticker) ?? []), r]);
  const live = rows.filter((r) => r.source === 'live').length;
  const latest = rows.reduce((m, r) => (r.updated_at > m ? r.updated_at : m), '');
  return {
    generatedAt: latest || new Date().toISOString(),
    source: live ? 'live' : 'sample',
    liveShare: rows.length ? live / rows.length : 0,
    records: companies.map((c) => assemble(c, byTicker.get(c.ticker) ?? [])),
    changes: (changes as Record<string, unknown>[]).map((c) => ({
      id: String(c.id),
      date: String(c.date),
      ticker: String(c.ticker),
      agent: c.agent as AgentKey,
      headline: String(c.headline),
      direction: c.direction as ChangeEvent['direction'],
      magnitude: c.magnitude as ChangeEvent['magnitude'],
      confidence: c.confidence as ChangeEvent['confidence'],
      citations: (c.citations as ChangeEvent['citations']) ?? [],
    })),
  };
}

export async function saveAgentResult(ticker: string, agent: AgentKey, data: Partial<CompanyRecord>, runId: string | null, source: 'sample' | 'live') {
  const updated_at = new Date().toISOString();
  must(await db().from('dwa_agent_data').upsert({ ticker, agent, source, data, run_id: runId, updated_at }));
  must(await db().from('dwa_agent_history').insert({ ticker, agent, source, data, run_id: runId, captured_at: updated_at }));
}

export function changeRows(changes: ChangeEvent[], refreshId: string | null, source: 'sample' | 'live') {
  return changes.map((c) => ({
    id: c.id,
    refresh_id: refreshId,
    date: c.date,
    ticker: c.ticker,
    agent: c.agent,
    headline: c.headline,
    direction: c.direction,
    magnitude: c.magnitude,
    confidence: c.confidence,
    citations: c.citations,
    source,
  }));
}
