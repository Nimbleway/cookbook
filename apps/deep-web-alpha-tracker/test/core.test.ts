import assert from 'node:assert/strict';
import { test } from 'node:test';
import { AGENT_BY_KEY } from '../lib/agents';
import { alertable, diffRecord } from '../lib/diff';
import { filterRecord, metrics } from '../lib/metrics';
import { sampleSnapshot } from '../lib/sample';
import { slackMessage } from '../lib/slack';
import { evidenceFor } from '../lib/trust';
import type { CompanyRecord } from '../lib/types';

const claims = [
  { path: '$.red_flags[0].finding', confidence: 'high', citations: [{ url: 'https://sec.gov/a', title: 'A', source_type: 'primary' }] },
  { path: '$.red_flags[0].date', confidence: 'medium', citations: [{ url: 'https://sec.gov/a', title: 'A', source_type: 'primary' }] },
  { path: '$.red_flags[0].status', confidence: 'low', citations: [{ url: 'https://news.example.com/b', source_type: 'secondary' }] },
  { path: '$.red_flags[10].finding', confidence: 'high', citations: [{ url: 'https://other.example.com' }] },
];

test('row evidence takes the median claim grade and dedupes citations under the row path only', () => {
  const e = evidenceFor(claims, '$.red_flags[0]');
  assert.equal(e.confidence, 'medium');
  assert.deepEqual(e.citations.map((c) => c.url), ['https://sec.gov/a', 'https://news.example.com/b']);
});

test('a row with no claims falls back to its source_url at low confidence', () => {
  const e = evidenceFor([], '$[3]', 'https://www.usaspending.gov/award/X');
  assert.equal(e.confidence, 'low');
  assert.equal(e.citations[0].url, 'https://www.usaspending.gov/award/X');
});

test('the forensic mapper reads the agent output schema', () => {
  const mapped = AGENT_BY_KEY.forensic.map(
    { overall_risk: 'high', red_flags: [{ category: 'auditor_change', severity: 'high', status: 'open', finding: 'Auditor resigned', date: '2024-10-24', source_url: 'https://sec.gov/a' }] },
    claims
  );
  assert.equal(mapped.forensic?.overallRisk, 'high');
  assert.equal(mapped.forensic?.flags[0].confidence, 'medium');
});

function withUpdate(rec: CompanyRecord, agent: keyof CompanyRecord['updatedAt'], patch: Partial<CompanyRecord>): CompanyRecord {
  return { ...rec, ...patch, updatedAt: { ...rec.updatedAt, [agent]: '2099-01-01T00:00:00Z' } };
}

test('diff flags a new forensic red flag and a moved catalyst, and ignores agents that did not rerun', () => {
  const base = sampleSnapshot(new Date('2026-11-10T00:00:00Z')).records.find((r) => r.company.ticker === 'NVDA')!;
  const prev: CompanyRecord = { ...base, forensic: { overallRisk: 'low', flags: [] } };
  const flag = { category: 'restatement', severity: 'high' as const, status: 'open' as const, finding: 'Non-reliance 8-K', date: '2026-11-01', confidence: 'high' as const, citations: [] };
  let next = withUpdate(prev, 'forensic', { forensic: { overallRisk: 'high', flags: [flag] } });
  const moved = prev.catalysts.map((c, i) => (i === 0 ? { ...c, dateText: '2099-01-01' } : c));
  next = withUpdate(next, 'catalysts', { catalysts: moved });
  const changes = diffRecord(prev, next, '2026-11-10');
  assert.ok(changes.some((c) => c.agent === 'forensic' && c.headline.includes('restatement') && c.magnitude === 3));
  assert.ok(changes.some((c) => c.agent === 'forensic' && c.headline.includes('low → high')));
  assert.ok(changes.some((c) => c.agent === 'catalysts' && c.headline.includes('moved')));
  assert.ok(!changes.some((c) => c.agent === 'gov'));
});

test('only magnitude 2+ changes above low confidence are alerted', () => {
  const base = { id: 'x', date: '2026-11-10', ticker: 'NVDA', agent: 'gov' as const, headline: 'h', direction: 'bullish' as const, citations: [] };
  const out = alertable([
    { ...base, id: 'a', magnitude: 3, confidence: 'high' },
    { ...base, id: 'b', magnitude: 1, confidence: 'high' },
    { ...base, id: 'c', magnitude: 3, confidence: 'low' },
  ]);
  assert.deepEqual(out.map((c) => c.id), ['a']);
});

test('the confidence filter removes rows and the metrics follow', () => {
  const rec = sampleSnapshot(new Date('2026-11-10T00:00:00Z')).records[0];
  const highOnly = filterRecord(rec, { high: true, medium: false, low: false });
  const m = metrics(highOnly);
  assert.equal(m.mix.medium + m.mix.low, 0);
  assert.ok(m.alphaScore >= 0 && m.alphaScore <= 100);
});

test('the sample snapshot covers 50 companies with cited rows', () => {
  const snap = sampleSnapshot(new Date('2026-11-10T00:00:00Z'));
  assert.equal(snap.records.length, 50);
  assert.ok(snap.changes.length > 50);
  assert.ok(snap.records.every((r) => r.catalysts.every((c) => c.citations.every((x) => x.url.startsWith('https://')))));
});

test('the Slack message groups changes by ticker and links sources', () => {
  const msg = slackMessage(
    [{ id: 'a', date: '2026-11-10', ticker: 'NVDA', agent: 'gov', headline: 'New award', direction: 'bullish', magnitude: 2, confidence: 'high', citations: [{ url: 'https://usaspending.gov/x', title: 'x', sourceType: 'primary' }] }],
    'https://example.com'
  );
  const text = JSON.stringify(msg.blocks);
  assert.ok(text.includes('*NVDA*'));
  assert.ok(text.includes('<https://usaspending.gov/x|source>'));
});
