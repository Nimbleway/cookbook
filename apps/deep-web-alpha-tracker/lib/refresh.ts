import { AGENT_BY_KEY, AGENTS, agentId } from './agents';
import { changeRows, db, loadCompanies, loadRecord, must, saveAgentResult } from './db';
import { alertable, diffRecord } from './diff';
import { getResult, getRun, startRun } from './nimble';
import { postToSlack } from './slack';
import type { AgentKey, ChangeEvent, Effort } from './types';

/**
 * A refresh queues one run per company x agent and is advanced in steps: each step polls running runs,
 * stores finished results, diffs them against the previous result and starts queued runs up to the
 * concurrency cap. The dashboard calls a step while a refresh is open; the daily cron calls one too.
 */

interface RunRow {
  id: number;
  ticker: string;
  agent: AgentKey;
  agent_id: string | null;
  run_id: string | null;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
}

export interface RefreshStatus {
  id: string;
  effort: Effort;
  startedAt: string;
  finishedAt: string | null;
  counts: Record<RunRow['status'], number>;
  changesFound: number;
  alertsSent: number;
}

const STEP_BUDGET_MS = 45_000;
const maxConcurrent = () => Number(process.env.MAX_CONCURRENT_RUNS || 25);

function sinceDate(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 90);
  return d.toISOString().slice(0, 10);
}

export async function openRefresh(): Promise<{ id: string } | null> {
  const rows = must(await db().from('dwa_refreshes').select('id').is('finished_at', null).order('started_at', { ascending: false }).limit(1));
  return (rows as { id: string }[])[0] ?? null;
}

export async function startRefresh(effort: Effort, agents: AgentKey[]): Promise<RefreshStatus> {
  const open = await openRefresh();
  if (open) return status(open.id);
  const chosen = AGENTS.filter((a) => agents.includes(a.key));
  const refresh = must(await db().from('dwa_refreshes').insert({ effort, agents: chosen.map((a) => a.key) }).select('id').single()) as { id: string };
  const companies = await loadCompanies();
  const rows = companies.flatMap((c) =>
    chosen.map((a) => {
      const id = agentId(a);
      return { refresh_id: refresh.id, ticker: c.ticker, agent: a.key, agent_id: id, status: id ? 'pending' : 'skipped' };
    })
  );
  for (let i = 0; i < rows.length; i += 500) must(await db().from('dwa_runs').insert(rows.slice(i, i + 500)));
  await advance(refresh.id);
  return status(refresh.id);
}

export async function status(refreshId: string): Promise<RefreshStatus> {
  const r = must(await db().from('dwa_refreshes').select('*').eq('id', refreshId).single()) as Record<string, unknown>;
  const runs = must(await db().from('dwa_runs').select('status').eq('refresh_id', refreshId)) as { status: RunRow['status'] }[];
  const counts = { pending: 0, running: 0, completed: 0, failed: 0, skipped: 0 };
  for (const run of runs) counts[run.status] += 1;
  return {
    id: refreshId,
    effort: r.effort as Effort,
    startedAt: String(r.started_at),
    finishedAt: (r.finished_at as string) ?? null,
    counts,
    changesFound: Number(r.changes_found),
    alertsSent: Number(r.alerts_sent),
  };
}

async function lock(refreshId: string): Promise<boolean> {
  const now = new Date();
  const until = new Date(now.getTime() + 55_000).toISOString();
  const res = must(
    await db()
      .from('dwa_refreshes')
      .update({ locked_until: until })
      .eq('id', refreshId)
      .is('finished_at', null)
      .or(`locked_until.is.null,locked_until.lt.${now.toISOString()}`)
      .select('id')
  );
  return (res as unknown[]).length > 0;
}

async function collect(run: RunRow, refreshId: string): Promise<ChangeEvent[]> {
  const state = await getRun(run.agent_id!, run.run_id!);
  if (state.is_active) return [];
  if (state.status !== 'completed') {
    must(await db().from('dwa_runs').update({ status: 'failed', error: state.status, completed_at: new Date().toISOString() }).eq('id', run.id));
    return [];
  }
  const result = await getResult(run.agent_id!, run.run_id!);
  const content = result.output?.content;
  const mapped = AGENT_BY_KEY[run.agent].map(content, result.output?.trust?.claims ?? []);
  const company = (must(await db().from('dwa_companies').select('ticker,name,domain,sector').eq('ticker', run.ticker).single()) as never);
  const before = await loadRecord(company);
  const prevRow = before.rows.find((r) => r.agent === run.agent);
  const prev = prevRow && prevRow.source === 'live' ? before.record : null;
  await saveAgentResult(run.ticker, run.agent, mapped, run.run_id, 'live');
  const after = await loadRecord(company);
  const changes = prev ? diffRecord(prev, after.record, new Date().toISOString().slice(0, 10)) : [];
  if (changes.length) must(await db().from('dwa_changes').upsert(changeRows(changes, refreshId, 'live')));
  must(await db().from('dwa_runs').update({ status: 'completed', output: result.output ?? null, completed_at: new Date().toISOString() }).eq('id', run.id));
  return changes;
}

/** One step of a refresh. Safe to call concurrently: a lock keeps steps from overlapping. */
export async function advance(refreshId: string): Promise<void> {
  if (!(await lock(refreshId))) return;
  const deadline = Date.now() + STEP_BUDGET_MS;
  const refresh = must(await db().from('dwa_refreshes').select('effort').eq('id', refreshId).single()) as { effort: Effort };
  const running = must(await db().from('dwa_runs').select('*').eq('refresh_id', refreshId).eq('status', 'running')) as RunRow[];

  for (let i = 0; i < running.length && Date.now() < deadline; i += 8) {
    await Promise.all(
      running.slice(i, i + 8).map((run) =>
        collect(run, refreshId).catch(async (err: Error) => {
          must(await db().from('dwa_runs').update({ status: 'failed', error: err.message.slice(0, 500) }).eq('id', run.id));
        })
      )
    );
  }

  const active = (must(await db().from('dwa_runs').select('id').eq('refresh_id', refreshId).eq('status', 'running')) as unknown[]).length;
  const slots = Math.max(0, maxConcurrent() - active);
  const pending = must(await db().from('dwa_runs').select('*').eq('refresh_id', refreshId).eq('status', 'pending').order('id').limit(slots)) as RunRow[];
  const companies = new Map((await loadCompanies()).map((c) => [c.ticker, c]));
  const since = sinceDate();
  for (const run of pending) {
    if (Date.now() > deadline) break;
    try {
      const started = await startRun(run.agent_id!, AGENT_BY_KEY[run.agent].prompt(companies.get(run.ticker)!, since), refresh.effort);
      must(await db().from('dwa_runs').update({ status: 'running', run_id: started.id, started_at: new Date().toISOString() }).eq('id', run.id));
    } catch (err) {
      must(await db().from('dwa_runs').update({ status: 'failed', error: (err as Error).message.slice(0, 500) }).eq('id', run.id));
    }
  }

  const s = await status(refreshId);
  if (s.counts.pending === 0 && s.counts.running === 0) await finish(refreshId);
  else must(await db().from('dwa_refreshes').update({ locked_until: null }).eq('id', refreshId));
}

async function finish(refreshId: string): Promise<void> {
  const rows = must(await db().from('dwa_changes').select('*').eq('refresh_id', refreshId)) as Record<string, unknown>[];
  const changes: ChangeEvent[] = rows.map((c) => ({
    id: String(c.id),
    date: String(c.date),
    ticker: String(c.ticker),
    agent: c.agent as AgentKey,
    headline: String(c.headline),
    direction: c.direction as ChangeEvent['direction'],
    magnitude: c.magnitude as ChangeEvent['magnitude'],
    confidence: c.confidence as ChangeEvent['confidence'],
    citations: (c.citations as ChangeEvent['citations']) ?? [],
  }));
  const alerts = alertable(changes);
  const sent = await postToSlack(alerts).catch(() => false);
  if (sent && alerts.length) must(await db().from('dwa_changes').update({ alerted: true }).in('id', alerts.map((a) => a.id)));
  must(
    await db()
      .from('dwa_refreshes')
      .update({ finished_at: new Date().toISOString(), locked_until: null, changes_found: changes.length, alerts_sent: sent ? alerts.length : 0 })
      .eq('id', refreshId)
  );
}
