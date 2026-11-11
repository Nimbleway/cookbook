import { NextResponse } from 'next/server';
import { AGENTS, agentId } from '@/lib/agents';
import { db, must } from '@/lib/db';
import { advance, openRefresh, startRefresh, status } from '@/lib/refresh';
import type { AgentKey, Effort } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const maxDuration = 60;

const EFFORTS: Effort[] = ['low', 'medium', 'high', 'x-high'];

function authorized(req: Request): boolean {
  const key = process.env.REFRESH_KEY;
  if (!key) return true;
  return req.headers.get('x-refresh-key') === key || req.headers.get('authorization') === `Bearer ${process.env.CRON_SECRET ?? key}`;
}

async function current() {
  const open = await openRefresh();
  if (open) {
    await advance(open.id);
    return status(open.id);
  }
  const last = must(await db().from('dwa_refreshes').select('id').order('started_at', { ascending: false }).limit(1)) as { id: string }[];
  return last[0] ? status(last[0].id) : null;
}

/** Status of the open (or last) refresh. While a refresh is open, each call advances it one step. */
export async function GET() {
  const ready = Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY);
  const refresh = ready ? await current().catch(() => null) : null;
  const agents = AGENTS.map((a) => ({ key: a.key, label: a.label, configured: Boolean(agentId(a)) }));
  return NextResponse.json({ refresh, agents, protected: Boolean(process.env.REFRESH_KEY) });
}

/** Queue one run per company x selected agent at the chosen effort. */
export async function POST(req: Request) {
  if (!authorized(req)) return NextResponse.json({ error: 'refresh key required' }, { status: 401 });
  if (!process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_ROLE_KEY) return NextResponse.json({ error: 'Supabase is not configured' }, { status: 400 });
  if (!process.env.NIMBLE_API_KEY) return NextResponse.json({ error: 'NIMBLE_API_KEY is not set' }, { status: 400 });
  const body = (await req.json().catch(() => ({}))) as { effort?: Effort; agents?: AgentKey[] };
  const effort = EFFORTS.includes(body.effort as Effort) ? (body.effort as Effort) : 'high';
  const agents = (body.agents?.length ? body.agents : AGENTS.map((a) => a.key)).filter((k) => AGENTS.some((a) => a.key === k));
  if (!AGENTS.some((a) => agents.includes(a.key) && agentId(a))) {
    return NextResponse.json({ error: 'None of the selected agents has an ID configured' }, { status: 400 });
  }
  return NextResponse.json({ refresh: await startRefresh(effort, agents) });
}
