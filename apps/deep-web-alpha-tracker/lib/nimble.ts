import type { Effort } from './types';

const BASE = 'https://sdk.nimbleway.com/v2';

async function call<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<{ status: number; data: T }> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { Authorization: `Bearer ${process.env.NIMBLE_API_KEY}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  });
  const text = await res.text();
  return { status: res.status, data: (text ? JSON.parse(text) : null) as T };
}

export interface RunState {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  is_active: boolean;
}

export async function startRun(agentId: string, input: string, effort: Effort): Promise<RunState> {
  const { status, data } = await call<RunState & { detail?: unknown }>('POST', `/agents/${agentId}/runs`, { input, effort });
  if (status >= 300) throw new Error(`start run ${status}: ${JSON.stringify(data).slice(0, 300)}`);
  return data;
}

export async function getRun(agentId: string, runId: string): Promise<RunState> {
  const { status, data } = await call<RunState>('GET', `/agents/${agentId}/runs/${runId}`);
  if (status >= 300) throw new Error(`get run ${status}`);
  return data;
}

export interface RunResult {
  output?: { content: unknown; trust?: { claims?: { path: string; confidence?: string; citations?: { url?: string; title?: string; source_type?: string }[] }[] } };
}

export async function getResult(agentId: string, runId: string): Promise<RunResult> {
  const { status, data } = await call<RunResult>('GET', `/agents/${agentId}/runs/${runId}/result`);
  if (status >= 300) throw new Error(`get result ${status}`);
  return data;
}
