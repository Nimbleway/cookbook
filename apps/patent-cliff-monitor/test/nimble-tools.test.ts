import assert from 'node:assert/strict';
import test from 'node:test';
import { tool } from 'ai';
import { z } from 'zod';
import { nimbleResearchTools, runTool } from '../src/lib/nimble-tools';
import { DEFAULT_BRIEF, RESEARCH_DIRECTIVES, buildResearchBrief } from '../src/lib/brief';

test('registers Nimble agent-run tools through the Vercel AI SDK connector', () => {
  const tools = nimbleResearchTools();

  assert.equal(typeof tools.startResearch.execute, 'function');
  assert.equal(typeof tools.checkResearch.execute, 'function');
  assert.equal(typeof tools.getResearchResult.execute, 'function');
});

test('invokes a connector tool directly, without a model in the loop', async () => {
  let received: { runId: string } | null = null;

  const fake = tool({
    description: 'stand-in for a Nimble connector tool',
    inputSchema: z.object({ runId: z.string() }),
    execute: async input => {
      received = input;
      return { ready: false as const, status: 'running' as const };
    },
  });

  const output = await runTool(fake, { runId: 'task_run_abc123' });

  assert.deepEqual(received, { runId: 'task_run_abc123' });
  assert.deepEqual(output, { ready: false, status: 'running' });
});

test('wraps a bare drug list in the standing research brief', () => {
  const brief = buildResearchBrief('Humira (adalimumab), expiry 2023');

  assert.ok(brief.includes('Humira (adalimumab), expiry 2023'));
  assert.ok(brief.includes(RESEARCH_DIRECTIVES));
});

test('does not repeat directives a caller already supplied', () => {
  const wrappedTwice = buildResearchBrief(DEFAULT_BRIEF);

  assert.equal(wrappedTwice, DEFAULT_BRIEF.trim());
  assert.equal(wrappedTwice.split('For each drug, research:').length - 1, 1);
});
