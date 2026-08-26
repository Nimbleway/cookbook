/**
 * POST /api/research
 *
 * Accepts a patent cliff task (drug list), starts or resumes a Nimble
 * Web Search Agent run, and returns a JSON response with the runId.
 *
 * The UI polls this endpoint to check progress and fetch the final report.
 *
 * Environment:
 *   NIMBLE_API_KEY      — from online.nimbleway.com
 *   NIMBLE_AGENT_ID     — pre-created Web Search Agent from Nimble console
 *   RESEARCH_PROVIDER   — openrouter | openai | gateway
 *   RESEARCH_MODEL      — model id for that provider, must support tool calling
 *   <PROVIDER>_API_KEY  — spent once per report, to start the run via the connector
 */
import { NextResponse } from 'next/server';
import {
  ConfigurationError,
  researchErrorMessage,
  startPatentCliffPhase,
  resumePatentCliffPhase,
} from '@/lib/agent';

export const maxDuration = 60;
export const runtime = 'nodejs';

/**
 * The brief is concatenated into the model prompt, so an unbounded one can blow
 * the context window or run up tokens before the Nimble run even starts. This
 * is a generous ceiling for a drug list, not a tuning knob.
 */
const MAX_TASK_CHARS = 20_000;

/**
 * A local misconfiguration is not a failure upstream at Nimble. Returning 502
 * for it makes a config problem look like an outage.
 */
function errorStatus(error: unknown) {
  return error instanceof ConfigurationError ? 500 : 502;
}

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Request body must be valid JSON.' }, { status: 400 });
  }

  const { task, runId } = (body && typeof body === 'object' ? body : {}) as {
    task?: unknown;
    runId?: unknown;
  };

  if (typeof runId === 'string' && runId.trim()) {
    try {
      const { text, result } = await resumePatentCliffPhase(runId.trim(), { abortSignal: req.signal });
      return NextResponse.json({ text, result });
    } catch (error) {
      console.error('Failed to resume Nimble research run', error);
      const message = researchErrorMessage(error, 'Unable to retrieve this research run.');
      return NextResponse.json({ error: message }, { status: errorStatus(error) });
    }
  }

  if (typeof task !== 'string' || !task.trim()) {
    return NextResponse.json(
      { error: 'Missing "task" in request body.' },
      { status: 400 }
    );
  }

  const trimmedTask = task.trim();
  if (trimmedTask.length > MAX_TASK_CHARS) {
    return NextResponse.json(
      {
        error: `The research brief is ${trimmedTask.length} characters. Keep it under ${MAX_TASK_CHARS}.`,
      },
      { status: 400 }
    );
  }

  try {
    const { text, runId: newRunId, effort, status } = await startPatentCliffPhase(trimmedTask);
    return NextResponse.json({ text, runId: newRunId, effort, status });
  } catch (error) {
    console.error('Failed to start Nimble research run', error);
    const message = researchErrorMessage(error, 'Unable to start research. Check the Nimble configuration and try again.');
    return NextResponse.json({ error: message }, { status: errorStatus(error) });
  }
}
