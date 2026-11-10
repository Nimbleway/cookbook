'use client';

import { useMemo, useState } from 'react';
import { AGENT_BY_KEY, AGENTS } from '@/lib/agents';
import { daysUntil, usd, type Metrics } from '@/lib/metrics';
import type { AgentKey, ChangeEvent, CompanyRecord } from '@/lib/types';
import { Arrow, Bar, Cite, ConfDot, label, MixBar, Panel, Pill, Segmented, Table, type Column, type Tone } from './ui';

export interface Row {
  rec: CompanyRecord;
  m: Metrics;
}

interface TabProps {
  rows: Row[];
  changes: ChangeEvent[];
  onSelect: (ticker: string) => void;
}

const riskTone = (r: string | null): Tone => (r === 'high' ? 'down' : r === 'medium' ? 'warn' : r === 'low' ? 'up' : 'mute');
const patternTone = (p: string | null): Tone => (p === 'delivers' ? 'up' : p === 'overpromises' ? 'down' : p === 'sandbags' ? 'accent' : 'mute');
const scoreTone = (s: number) => (s >= 65 ? 'up' : s <= 40 ? 'down' : 'accent');
const signed = (n: number | null, suffix = '') => (n === null ? '—' : `${n > 0 ? '+' : ''}${n}${suffix}`);

function Ticker({ rec }: { rec: CompanyRecord }) {
  return (
    <span className="flex items-baseline gap-2">
      <span className="w-12 font-mono font-semibold text-ink">{rec.company.ticker}</span>
      <span className="max-w-40 truncate text-soft">{rec.company.name}</span>
    </span>
  );
}

function ScoreCell({ m }: { m: Metrics }) {
  return (
    <span className="group relative inline-flex items-center gap-2">
      <span className="w-7 text-right font-mono font-semibold">{m.alphaScore}</span>
      <Bar value={m.alphaScore} max={100} tone={scoreTone(m.alphaScore)} width="w-16" />
      <span className="pointer-events-none absolute left-0 top-6 z-20 hidden w-56 rounded-lg border border-line2 bg-panel2 p-2 text-[11px] shadow-xl group-hover:block">
        <span className="mb-1 block text-mute">Base 50, adjusted by:</span>
        {m.scoreParts.map((p) => (
          <span key={p.label} className="flex justify-between">
            <span className="text-soft">{p.label}</span>
            <span className={`font-mono ${p.points > 0 ? 'text-up' : 'text-down'}`}>{signed(p.points)}</span>
          </span>
        ))}
      </span>
    </span>
  );
}

/* ─── Watchlist ─────────────────────────────────────────────────────────── */

export function WatchlistTab({ rows, onSelect }: TabProps) {
  const columns: Column<Row>[] = [
    { key: 'ticker', label: 'Company', render: (r) => <Ticker rec={r.rec} />, sort: (r) => r.rec.company.ticker },
    { key: 'sector', label: 'Sleeve', render: (r) => <span className="text-mute">{r.rec.company.sector}</span>, sort: (r) => r.rec.company.sector },
    { key: 'score', label: 'Alpha score', title: 'Composite of the signals below; hover for the breakdown', render: (r) => <ScoreCell m={r.m} />, sort: (r) => r.m.alphaScore },
    {
      key: 'channel',
      label: 'Channel',
      title: 'Channel-check observations supporting minus contradicting accelerating demand',
      render: (r) => (
        <span className={`font-mono ${r.m.channelNet > 0 ? 'text-up' : r.m.channelNet < 0 ? 'text-down' : 'text-mute'}`}>{signed(r.m.channelNet)}</span>
      ),
      sort: (r) => r.m.channelNet,
      align: 'right',
    },
    { key: 'hiring', label: 'Hiring Δ', render: (r) => <span className="font-mono">{signed(r.m.hiringDeltaPct, '%')}</span>, sort: (r) => r.m.hiringDeltaPct ?? -999, align: 'right' },
    { key: 'rivals', label: 'Rivals ▲', title: 'Distinct competitors with rising momentum', render: (r) => <span className="font-mono">{r.m.rivalsRising}</span>, sort: (r) => r.m.rivalsRising, align: 'right' },
    { key: 'forensic', label: 'Forensic', render: (r) => <Pill tone={riskTone(r.m.forensicRisk)}>{r.m.forensicRisk ?? '—'}</Pill>, sort: (r) => ['low', 'medium', 'high'].indexOf(r.m.forensicRisk ?? ''), align: 'center' },
    { key: 'hit', label: 'Mgmt hit rate', render: (r) => <span className="font-mono">{r.m.hitRatePct === null ? '—' : `${r.m.hitRatePct}%`}</span>, sort: (r) => r.m.hitRatePct ?? -1, align: 'right' },
    {
      key: 'insider',
      label: 'Insider net',
      render: (r) => <span className={`font-mono ${r.m.insiderNetUsd > 0 ? 'text-up' : r.m.insiderNetUsd < 0 ? 'text-down' : 'text-mute'}`}>{r.m.insiderNetUsd ? usd(r.m.insiderNetUsd) : '—'}</span>,
      sort: (r) => r.m.insiderNetUsd,
      align: 'right',
    },
    {
      key: 'catalyst',
      label: 'Next catalyst',
      render: (r) =>
        r.m.nextCatalyst ? (
          <span className="flex items-center gap-2">
            <span className="w-9 text-right font-mono text-ink">{r.m.nextCatalyst.days}d</span>
            <span className="max-w-36 truncate text-mute">{r.m.nextCatalyst.description}</span>
          </span>
        ) : (
          '—'
        ),
      sort: (r) => -(r.m.nextCatalyst?.days ?? 9999),
    },
    { key: 'gov', label: 'Gov obligated', render: (r) => <span className="font-mono">{r.m.govObligatedUsd ? usd(r.m.govObligatedUsd) : '—'}</span>, sort: (r) => r.m.govObligatedUsd, align: 'right' },
    { key: 'conc', label: 'Top customer', render: (r) => <span className="font-mono">{r.m.topCustomerPct ? `${r.m.topCustomerPct}%` : '—'}</span>, sort: (r) => r.m.topCustomerPct ?? 0, align: 'right' },
    { key: 'mix', label: 'Confidence', render: (r) => <MixBar mix={r.m.mix} />, sort: (r) => r.m.mix.high / Math.max(1, r.m.datapoints) },
    { key: 'sources', label: 'Sources', render: (r) => <span className="font-mono text-soft">{r.m.sources}</span>, sort: (r) => r.m.sources, align: 'right' },
  ];
  return (
    <Panel>
      <Table rows={rows} columns={columns} rowKey={(r) => r.rec.company.ticker} onRow={(r) => onSelect(r.rec.company.ticker)} initialSort={{ key: 'score', desc: true }} />
    </Panel>
  );
}

/* ─── Signal feed ───────────────────────────────────────────────────────── */

export function SignalsTab({ rows, changes, onSelect }: TabProps) {
  const [agent, setAgent] = useState<AgentKey | 'all'>('all');
  const [dir, setDir] = useState<'all' | 'bullish' | 'bearish'>('all');
  const sectorOf = useMemo(() => new Map(rows.map((r) => [r.rec.company.ticker, r.rec.company.sector])), [rows]);
  const list = changes.filter((c) => (agent === 'all' || c.agent === agent) && (dir === 'all' || c.direction === dir));
  const byAgent = AGENTS.map((a) => ({ a, n: changes.filter((c) => c.agent === a.key).length })).filter((x) => x.n);
  const maxAgent = Math.max(1, ...byAgent.map((x) => x.n));
  const sectors = [...new Set(rows.map((r) => r.rec.company.sector))].map((s) => {
    const cs = changes.filter((c) => sectorOf.get(c.ticker) === s);
    return { s, up: cs.filter((c) => c.direction === 'bullish').length, down: cs.filter((c) => c.direction === 'bearish').length };
  });
  const maxSector = Math.max(1, ...sectors.map((x) => x.up + x.down));
  const names = [...new Set(changes.map((c) => c.ticker))]
    .map((t) => ({ t, net: changes.filter((c) => c.ticker === t).reduce((s, c) => s + (c.direction === 'bullish' ? c.magnitude : c.direction === 'bearish' ? -c.magnitude : 0), 0) }))
    .sort((a, b) => b.net - a.net);

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
      <Panel
        title={`Meaningful changes · ${list.length}`}
        right={
          <div className="flex gap-2">
            <select value={agent} onChange={(e) => setAgent(e.target.value as AgentKey | 'all')} className="rounded-md border border-line bg-panel2 px-2 py-1 text-[12px]">
              <option value="all">All agents</option>
              {AGENTS.map((a) => (
                <option key={a.key} value={a.key}>
                  {a.short}
                </option>
              ))}
            </select>
            <Segmented value={dir} onChange={setDir} options={[{ value: 'all', label: 'All' }, { value: 'bullish', label: '▲ Bullish' }, { value: 'bearish', label: '▼ Bearish' }]} />
          </div>
        }
      >
        <div className="scroll-thin max-h-[640px] divide-y divide-line/60 overflow-y-auto">
          {list.length === 0 && <div className="px-4 py-8 text-center text-mute">No changes at this confidence level</div>}
          {list.map((c) => (
            <div key={c.id} className="grid grid-cols-[84px_56px_96px_16px_1fr_44px_auto] items-center gap-3 px-4 py-2 hover:bg-panel2">
              <span className="font-mono text-mute">{c.date}</span>
              <button type="button" onClick={() => onSelect(c.ticker)} className="text-left font-mono font-semibold hover:text-accent">
                {c.ticker}
              </button>
              <Pill>{AGENT_BY_KEY[c.agent].short}</Pill>
              <Arrow d={c.direction} />
              <span className="truncate text-ink">{c.headline}</span>
              <span className="font-mono tracking-tighter text-accent" title="Magnitude">
                {'■'.repeat(c.magnitude)}
                <span className="text-line2">{'■'.repeat(3 - c.magnitude)}</span>
              </span>
              <Cite e={c} />
            </div>
          ))}
        </div>
      </Panel>
      <div className="grid content-start gap-4">
        <Panel title="Changes by agent">
          <div className="space-y-1.5 p-4">
            {byAgent.map(({ a, n }) => (
              <div key={a.key} className="grid grid-cols-[100px_1fr_28px] items-center gap-2">
                <span className="text-soft">{a.short}</span>
                <Bar value={n} max={maxAgent} width="w-full" />
                <span className="text-right font-mono">{n}</span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Bullish vs bearish by sleeve">
          <div className="space-y-2 p-4">
            {sectors.map((x) => (
              <div key={x.s}>
                <div className="flex justify-between text-[12px]">
                  <span className="text-soft">{x.s}</span>
                  <span className="font-mono">
                    <span className="text-up">{x.up}</span> / <span className="text-down">{x.down}</span>
                  </span>
                </div>
                <div className="mt-1 flex h-1.5 overflow-hidden rounded-full bg-line" style={{ width: `${((x.up + x.down) / maxSector) * 100}%` }}>
                  <span className="bg-up" style={{ width: `${(x.up / Math.max(1, x.up + x.down)) * 100}%` }} />
                  <span className="flex-1 bg-down" />
                </div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Net signal, top and bottom">
          <div className="grid grid-cols-2 gap-x-4 p-4 font-mono text-[12px]">
            <div className="space-y-1">
              {names.slice(0, 6).map((n) => (
                <div key={n.t} className="flex justify-between">
                  <span>{n.t}</span>
                  <span className="text-up">{signed(n.net)}</span>
                </div>
              ))}
            </div>
            <div className="space-y-1">
              {names.slice(-6).reverse().map((n) => (
                <div key={n.t} className="flex justify-between">
                  <span>{n.t}</span>
                  <span className="text-down">{signed(n.net)}</span>
                </div>
              ))}
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

/* ─── Catalysts ─────────────────────────────────────────────────────────── */

export function CatalystsTab({ rows, onSelect }: TabProps) {
  const [horizon, setHorizon] = useState<'30' | '90' | '180' | '365'>('90');
  const [type, setType] = useState('all');
  const all = rows.flatMap((r) => r.rec.catalysts.filter((c) => c.date).map((c) => ({ ...c, ticker: r.rec.company.ticker, days: daysUntil(c.date!) })));
  const types = [...new Set(all.map((c) => c.type))];
  const list = all.filter((c) => c.days >= 0 && c.days <= Number(horizon) && (type === 'all' || c.type === type)).sort((a, b) => a.days - b.days);
  const weeks = Array.from({ length: 26 }, (_, w) => all.filter((c) => c.days >= w * 7 && c.days < (w + 1) * 7 && (type === 'all' || c.type === type)).length);
  const maxWeek = Math.max(1, ...weeks);
  const certaintyTone: Record<string, Tone> = { confirmed: 'up', statutory: 'accent', company_guided: 'warn', estimated: 'mute' };
  const guided = rows.flatMap((r) => r.rec.catalysts.filter((c) => !c.date).map((c) => ({ ...c, ticker: r.rec.company.ticker })));

  const columns: Column<(typeof list)[number]>[] = [
    { key: 'date', label: 'Date', render: (c) => <span className="font-mono">{c.date}</span>, sort: (c) => c.days },
    { key: 'days', label: 'In', render: (c) => <span className="font-mono text-accent">{c.days}d</span>, sort: (c) => c.days, align: 'right' },
    { key: 'ticker', label: 'Ticker', render: (c) => <span className="font-mono font-semibold">{c.ticker}</span>, sort: (c) => c.ticker },
    { key: 'type', label: 'Type', render: (c) => <Pill>{label(c.type)}</Pill>, sort: (c) => c.type },
    { key: 'desc', label: 'Event', render: (c) => <span className="text-soft">{c.description}</span> },
    { key: 'cert', label: 'Date certainty', render: (c) => <Pill tone={certaintyTone[c.certainty]}>{label(c.certainty)}</Pill>, sort: (c) => c.certainty },
    { key: 'ev', label: 'Evidence', render: (c) => <Cite e={c} />, sort: (c) => c.confidence },
  ];

  return (
    <div className="grid gap-4">
      <Panel title="Catalyst density, next 26 weeks">
        <div className="flex h-24 items-end gap-1 px-4 pb-3 pt-4">
          {weeks.map((n, w) => (
            <div key={w} className="flex flex-1 flex-col items-center gap-1" title={`Week ${w + 1}: ${n} events`}>
              <div className="w-full rounded-sm bg-accent/70" style={{ height: `${(n / maxWeek) * 64}px` }} />
              {w % 4 === 0 && <span className="text-[10px] text-mute">W{w + 1}</span>}
            </div>
          ))}
        </div>
      </Panel>
      <Panel
        title={`Dated catalysts · ${list.length}`}
        right={
          <div className="flex gap-2">
            <select value={type} onChange={(e) => setType(e.target.value)} className="rounded-md border border-line bg-panel2 px-2 py-1 text-[12px]">
              <option value="all">All types</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  {label(t)}
                </option>
              ))}
            </select>
            <Segmented value={horizon} onChange={setHorizon} options={[{ value: '30', label: '30d' }, { value: '90', label: '90d' }, { value: '180', label: '180d' }, { value: '365', label: '1y' }]} />
          </div>
        }
      >
        <Table rows={list} columns={columns} rowKey={(c) => `${c.ticker}-${c.key}`} onRow={(c) => onSelect(c.ticker)} />
      </Panel>
      {guided.length > 0 && (
        <Panel title={`Company-guided windows · ${guided.length}`}>
          <div className="flex flex-wrap gap-2 p-4">
            {guided.map((c) => (
              <span key={`${c.ticker}-${c.key}`} className="inline-flex items-center gap-2 rounded-lg border border-line bg-panel2 px-2.5 py-1">
                <span className="font-mono font-semibold">{c.ticker}</span>
                <span className="text-soft">{c.description}</span>
                <span className="font-mono text-warn">{c.dateText}</span>
                <ConfDot c={c.confidence} />
              </span>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

/* ─── Channel & competition ─────────────────────────────────────────────── */

function heat(pct: number | null, goodWhenUp: boolean) {
  if (pct === null) return 'bg-transparent text-line2';
  const good = goodWhenUp ? pct > 0 : pct < 0;
  const a = Math.min(Math.abs(pct), 60) / 60;
  const alpha = Math.round((0.12 + a * 0.6) * 100) / 100;
  return { backgroundColor: good ? `rgba(52,196,124,${alpha})` : `rgba(240,98,98,${alpha})` };
}

export function ChannelTab({ rows, onSelect }: TabProps) {
  const measures = [...new Set(rows.flatMap((r) => r.rec.channel?.observations.map((o) => o.measure) ?? []))];
  const inverse = new Set(['Promo depth', 'Distributor lead time', 'Status page incidents']);
  const rivals = new Map<string, { tickers: Set<string>; signals: number; types: Map<string, number> }>();
  for (const r of rows) {
    for (const s of r.rec.competitors.filter((x) => x.threat === 'rising')) {
      const e = rivals.get(s.competitor) ?? { tickers: new Set<string>(), signals: 0, types: new Map<string, number>() };
      e.tickers.add(r.rec.company.ticker);
      e.signals += 1;
      e.types.set(s.type, (e.types.get(s.type) ?? 0) + 1);
      rivals.set(s.competitor, e);
    }
  }
  const rivalRows = [...rivals.entries()].map(([name, e]) => ({ name, ...e })).sort((a, b) => b.tickers.size - a.tickers.size || b.signals - a.signals);
  const sorted = [...rows].sort((a, b) => b.m.channelNet - a.m.channelNet);

  return (
    <div className="grid gap-4 2xl:grid-cols-[1fr_420px]">
      <Panel title="Channel-check heatmap · change since last quarter" right={<span className="text-[11px] text-mute">green = supports accelerating demand</span>}>
        <div className="scroll-thin overflow-x-auto p-3">
          <table className="border-separate border-spacing-0.5 text-[11px]">
            <thead>
              <tr>
                <th />
                {measures.map((m) => (
                  <th key={m} className="w-20 px-1 pb-1 text-left align-bottom font-medium text-mute">
                    {m}
                  </th>
                ))}
                <th className="px-2 text-mute">Read</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.rec.company.ticker}>
                  <td className="pr-2">
                    <button type="button" onClick={() => onSelect(r.rec.company.ticker)} className="font-mono font-semibold hover:text-accent">
                      {r.rec.company.ticker}
                    </button>
                  </td>
                  {measures.map((m) => {
                    const o = r.rec.channel?.observations.find((x) => x.measure === m);
                    const pct = o && o.prior ? Math.round(((o.value ?? 0) / o.prior - 1) * 100) : null;
                    const style = heat(pct, !inverse.has(m));
                    return (
                      <td key={m} className="h-6 rounded text-center font-mono" style={typeof style === 'string' ? undefined : style} title={o ? `${o.value} vs ${o.prior} ${o.unit ?? ''} · ${o.confidence} confidence` : 'Not observed'}>
                        {pct === null ? <span className="text-line2">·</span> : signed(pct, '%')}
                      </td>
                    );
                  })}
                  <td className="px-2">
                    <Pill tone={r.m.channelAnswer === 'yes' ? 'up' : r.m.channelAnswer === 'no' ? 'down' : 'mute'}>{r.m.channelAnswer}</Pill>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title={`Rivals gaining ground · ${rivalRows.length}`}>
        <Table
          rows={rivalRows}
          rowKey={(r) => r.name}
          initialSort={{ key: 'names', desc: true }}
          columns={[
            { key: 'name', label: 'Rival', render: (r) => <span className="text-ink">{r.name}</span>, sort: (r) => r.name },
            { key: 'names', label: 'Names hit', render: (r) => <span className="font-mono">{r.tickers.size}</span>, sort: (r) => r.tickers.size, align: 'right' },
            { key: 'signals', label: 'Signals', render: (r) => <span className="font-mono">{r.signals}</span>, sort: (r) => r.signals, align: 'right' },
            {
              key: 'top',
              label: 'Top move',
              render: (r) => <span className="text-mute">{label([...r.types.entries()].sort((a, b) => b[1] - a[1])[0][0])}</span>,
            },
            { key: 'tickers', label: 'Exposed', render: (r) => <span className="font-mono text-[11px] text-soft">{[...r.tickers].slice(0, 4).join(' ')}</span> },
          ]}
        />
      </Panel>
    </div>
  );
}

/* ─── Risk & governance ─────────────────────────────────────────────────── */

export function RiskTab({ rows, onSelect }: TabProps) {
  const categories = [...new Set(rows.flatMap((r) => r.rec.forensic?.flags.map((f) => f.category) ?? []))].sort();
  const sevColor = { high: 'bg-down', medium: 'bg-warn', low: 'bg-mute' } as const;
  const flagged = rows.filter((r) => r.rec.forensic?.flags.length).sort((a, b) => ['low', 'medium', 'high'].indexOf(b.m.forensicRisk ?? '') - ['low', 'medium', 'high'].indexOf(a.m.forensicRisk ?? ''));
  const filings = rows.flatMap((r) => r.rec.filings.filter((f) => f.relevance === 'high').map((f) => ({ ...f, ticker: r.rec.company.ticker })));
  const patternCounts = ['delivers', 'sandbags', 'mixed', 'overpromises', 'too_early'].map((p) => ({ p, n: rows.filter((r) => r.m.mgmtPattern === p).length }));

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Panel title={`Forensic red-flag matrix · ${flagged.length} names flagged`} className="xl:col-span-2">
        <div className="scroll-thin overflow-x-auto p-3">
          <table className="border-separate border-spacing-1 text-[11px]">
            <thead>
              <tr>
                <th />
                <th className="px-2 text-left font-medium text-mute">Overall</th>
                {categories.map((c) => (
                  <th key={c} className="w-24 px-1 text-left align-bottom font-medium text-mute">
                    {label(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {flagged.map((r) => (
                <tr key={r.rec.company.ticker}>
                  <td className="pr-2">
                    <button type="button" onClick={() => onSelect(r.rec.company.ticker)} className="font-mono font-semibold hover:text-accent">
                      {r.rec.company.ticker}
                    </button>
                  </td>
                  <td className="px-2">
                    <Pill tone={riskTone(r.m.forensicRisk)}>{r.m.forensicRisk}</Pill>
                  </td>
                  {categories.map((c) => {
                    const f = r.rec.forensic?.flags.find((x) => x.category === c);
                    return (
                      <td key={c} className="h-6 text-center">
                        {f ? (
                          <span title={`${f.finding} · ${f.status} · ${f.confidence} confidence`} className={`inline-block h-4 w-10 rounded ${sevColor[f.severity]} ${f.status === 'resolved' ? 'opacity-30' : ''}`} />
                        ) : (
                          <span className="text-line2">·</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-2 flex gap-4 px-1 text-[11px] text-mute">
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-5 rounded bg-down" /> high</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-5 rounded bg-warn" /> medium</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-5 rounded bg-mute" /> low</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-5 rounded bg-down opacity-30" /> resolved</span>
          </div>
        </div>
      </Panel>
      <Panel title="Management credibility" right={<div className="flex gap-1.5">{patternCounts.map((x) => <Pill key={x.p} tone={patternTone(x.p)}>{label(x.p)} {x.n}</Pill>)}</div>}>
        <Table
          rows={rows}
          rowKey={(r) => r.rec.company.ticker}
          onRow={(r) => onSelect(r.rec.company.ticker)}
          initialSort={{ key: 'hit', desc: false }}
          columns={[
            { key: 't', label: 'Ticker', render: (r) => <span className="font-mono font-semibold">{r.rec.company.ticker}</span>, sort: (r) => r.rec.company.ticker },
            { key: 'p', label: 'Pattern', render: (r) => <Pill tone={patternTone(r.m.mgmtPattern)}>{label(r.m.mgmtPattern ?? '—')}</Pill>, sort: (r) => r.m.mgmtPattern ?? '' },
            { key: 'hit', label: 'Hit rate', render: (r) => (r.m.hitRatePct === null ? '—' : <span className="flex items-center gap-2"><span className="w-9 text-right font-mono">{r.m.hitRatePct}%</span><Bar value={r.m.hitRatePct} max={100} tone={r.m.hitRatePct >= 70 ? 'up' : r.m.hitRatePct < 50 ? 'down' : 'warn'} width="w-16" /></span>), sort: (r) => r.m.hitRatePct ?? -1 },
            { key: 'c', label: 'Commitments', render: (r) => <span className="font-mono">{r.rec.management?.commitments.length ?? 0}</span>, sort: (r) => r.rec.management?.commitments.length ?? 0, align: 'right' },
            { key: 'x', label: 'Exits', render: (r) => <span className={`font-mono ${r.m.leadershipExits ? 'text-down' : ''}`}>{r.m.leadershipExits}</span>, sort: (r) => r.m.leadershipExits, align: 'right' },
            { key: 'i', label: 'Insider net', render: (r) => <span className={`font-mono ${r.m.insiderNetUsd > 0 ? 'text-up' : r.m.insiderNetUsd < 0 ? 'text-down' : 'text-mute'}`}>{r.m.insiderNetUsd ? usd(r.m.insiderNetUsd) : '—'}</span>, sort: (r) => r.m.insiderNetUsd, align: 'right' },
          ]}
        />
      </Panel>
      <Panel title={`High-relevance filing changes · ${filings.length}`}>
        <div className="scroll-thin max-h-[520px] divide-y divide-line/60 overflow-y-auto">
          {filings.length === 0 && <div className="px-4 py-8 text-center text-mute">No changes at this confidence level</div>}
          {filings
            .sort((a, b) => b.filedDate.localeCompare(a.filedDate))
            .map((f, i) => (
              <div key={`${f.ticker}-${i}`} className="grid grid-cols-[56px_48px_120px_1fr_auto] items-center gap-3 px-4 py-2">
                <button type="button" onClick={() => onSelect(f.ticker)} className="text-left font-mono font-semibold hover:text-accent">
                  {f.ticker}
                </button>
                <span className="font-mono text-mute">{f.form}</span>
                <Pill tone={f.changeType === 'added' ? 'accent' : f.changeType === 'removed' ? 'warn' : 'mute'}>{label(f.area)}</Pill>
                <span className="truncate text-soft">{f.summary}</span>
                <Cite e={f} />
              </div>
            ))}
        </div>
      </Panel>
    </div>
  );
}

/* ─── Supply chain ──────────────────────────────────────────────────────── */

export function SupplyTab({ rows, onSelect }: TabProps) {
  const [rel, setRel] = useState('all');
  const shared = new Map<string, { tickers: Set<string>; rels: Map<string, number>; ended: number; shares: number[] }>();
  for (const r of rows) {
    for (const s of r.rec.supplyChain.filter((x) => rel === 'all' || x.relationship === rel)) {
      const e = shared.get(s.counterparty) ?? { tickers: new Set<string>(), rels: new Map<string, number>(), ended: 0, shares: [] as number[] };
      e.tickers.add(r.rec.company.ticker);
      e.rels.set(s.relationship, (e.rels.get(s.relationship) ?? 0) + 1);
      if (s.status === 'ended') e.ended += 1;
      if (s.revenueSharePct) e.shares.push(s.revenueSharePct);
      shared.set(s.counterparty, e);
    }
  }
  const sharedRows = [...shared.entries()].map(([name, e]) => ({ name, ...e }));
  const maxExposure = Math.max(1, ...sharedRows.map((x) => x.tickers.size));
  const conc = rows
    .flatMap((r) => r.rec.supplyChain.filter((s) => s.revenueSharePct).map((s) => ({ ticker: r.rec.company.ticker, ...s })))
    .sort((a, b) => (b.revenueSharePct ?? 0) - (a.revenueSharePct ?? 0));
  const rels = [...new Set(rows.flatMap((r) => r.rec.supplyChain.map((s) => s.relationship)))];

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_440px]">
      <Panel
        title="Shared counterparties across the watchlist"
        right={
          <select value={rel} onChange={(e) => setRel(e.target.value)} className="rounded-md border border-line bg-panel2 px-2 py-1 text-[12px]">
            <option value="all">All relationships</option>
            {rels.map((r) => (
              <option key={r} value={r}>
                {label(r)}
              </option>
            ))}
          </select>
        }
      >
        <Table
          rows={sharedRows}
          rowKey={(r) => r.name}
          initialSort={{ key: 'exp', desc: true }}
          columns={[
            { key: 'name', label: 'Counterparty', render: (r) => <span className="text-ink">{r.name}</span>, sort: (r) => r.name },
            { key: 'exp', label: 'Names exposed', render: (r) => <span className="flex items-center gap-2"><span className="w-5 text-right font-mono">{r.tickers.size}</span><Bar value={r.tickers.size} max={maxExposure} width="w-20" /></span>, sort: (r) => r.tickers.size },
            { key: 'rel', label: 'Role', render: (r) => <span className="flex gap-1">{[...r.rels.keys()].map((k) => <Pill key={k}>{label(k)}</Pill>)}</span> },
            { key: 'share', label: 'Max rev. share', render: (r) => <span className="font-mono">{r.shares.length ? `${Math.max(...r.shares)}%` : '—'}</span>, sort: (r) => Math.max(0, ...r.shares), align: 'right' },
            { key: 'ended', label: 'Ended', render: (r) => <span className={`font-mono ${r.ended ? 'text-down' : 'text-mute'}`}>{r.ended}</span>, sort: (r) => r.ended, align: 'right' },
            { key: 'tickers', label: 'Tickers', render: (r) => <span className="font-mono text-[11px] text-soft">{[...r.tickers].slice(0, 6).join(' ')}{r.tickers.size > 6 ? ` +${r.tickers.size - 6}` : ''}</span> },
          ]}
        />
      </Panel>
      <Panel title={`Disclosed customer concentration · ${conc.length}`}>
        <div className="scroll-thin max-h-[600px] space-y-1.5 overflow-y-auto p-4">
          {conc.length === 0 && <div className="py-6 text-center text-mute">No disclosed shares at this confidence level</div>}
          {conc.map((c, i) => (
            <div key={`${c.ticker}-${c.counterparty}-${i}`} className="grid grid-cols-[52px_1fr_40px_auto] items-center gap-2">
              <button type="button" onClick={() => onSelect(c.ticker)} className="text-left font-mono font-semibold hover:text-accent">
                {c.ticker}
              </button>
              <span className="flex items-center gap-2">
                <Bar value={c.revenueSharePct ?? 0} max={30} tone={(c.revenueSharePct ?? 0) >= 20 ? 'down' : 'warn'} width="w-full" />
              </span>
              <span className="text-right font-mono">{c.revenueSharePct}%</span>
              <span className="flex items-center gap-2">
                <span className="w-28 truncate text-mute">{c.counterparty}</span>
                <Cite e={c} />
              </span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

/* ─── Government ────────────────────────────────────────────────────────── */

export function GovTab({ rows, onSelect }: TabProps) {
  const withGov = rows.filter((r) => r.rec.gov.length).sort((a, b) => b.m.govCeilingUsd - a.m.govCeilingUsd);
  const maxCeiling = Math.max(1, ...withGov.map((r) => r.m.govCeilingUsd));
  const awards = rows.flatMap((r) => r.rec.gov.map((g) => ({ ...g, ticker: r.rec.company.ticker })));
  const agencies = new Map<string, number>();
  for (const a of awards) agencies.set(a.agency, (agencies.get(a.agency) ?? 0) + (a.obligatedUsd ?? 0));
  const agencyRows = [...agencies.entries()].sort((a, b) => b[1] - a[1]);
  const maxAgency = Math.max(1, ...agencyRows.map((x) => x[1]));
  const statusTone: Record<string, Tone> = { awarded: 'up', modified: 'accent', recompete_pending: 'warn', protested: 'warn', protest_denied: 'up', protest_sustained: 'down' };

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <Panel title="Obligated vs ceiling by company" right={<span className="text-[11px] text-mute">solid = obligated · outline = ceiling</span>}>
        <div className="space-y-2 p-4">
          {withGov.length === 0 && <div className="py-6 text-center text-mute">No awards at this confidence level</div>}
          {withGov.map((r) => (
            <div key={r.rec.company.ticker} className="grid grid-cols-[52px_1fr_150px] items-center gap-3">
              <button type="button" onClick={() => onSelect(r.rec.company.ticker)} className="text-left font-mono font-semibold hover:text-accent">
                {r.rec.company.ticker}
              </button>
              <div className="relative h-4">
                <div className="absolute inset-y-0 left-0 rounded border border-accent/50" style={{ width: `${(r.m.govCeilingUsd / maxCeiling) * 100}%` }} />
                <div className="absolute inset-y-0 left-0 rounded bg-accent" style={{ width: `${(r.m.govObligatedUsd / maxCeiling) * 100}%` }} />
              </div>
              <span className="text-right font-mono text-[12px]">
                {usd(r.m.govObligatedUsd)} <span className="text-mute">/ {usd(r.m.govCeilingUsd)}</span>
              </span>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Obligations by agency">
        <div className="space-y-1.5 p-4">
          {agencyRows.map(([agency, n]) => (
            <div key={agency} className="grid grid-cols-[1fr_70px] items-center gap-2">
              <div>
                <div className="truncate text-soft">{agency}</div>
                <Bar value={n} max={maxAgency} width="w-full" />
              </div>
              <span className="text-right font-mono">{usd(n)}</span>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title={`Awards, task orders and protests · ${awards.length}`} className="xl:col-span-2">
        <Table
          rows={awards}
          rowKey={(a) => `${a.ticker}-${a.awardId}`}
          onRow={(a) => onSelect(a.ticker)}
          initialSort={{ key: 'date', desc: true }}
          columns={[
            { key: 'date', label: 'Action date', render: (a) => <span className="font-mono">{a.actionDate}</span>, sort: (a) => a.actionDate },
            { key: 't', label: 'Ticker', render: (a) => <span className="font-mono font-semibold">{a.ticker}</span>, sort: (a) => a.ticker },
            { key: 'id', label: 'Award ID', render: (a) => <span className="font-mono text-soft">{a.awardId}</span> },
            { key: 'ag', label: 'Agency', render: (a) => <span className="text-soft">{a.agency}</span>, sort: (a) => a.agency },
            { key: 'type', label: 'Type', render: (a) => <Pill>{label(a.type)}</Pill>, sort: (a) => a.type },
            { key: 'ob', label: 'Obligated', render: (a) => <span className="font-mono">{a.obligatedUsd === null ? '—' : usd(a.obligatedUsd)}</span>, sort: (a) => a.obligatedUsd ?? 0, align: 'right' },
            { key: 'ce', label: 'Ceiling', render: (a) => <span className="font-mono text-mute">{a.ceilingUsd === null ? '—' : usd(a.ceilingUsd)}</span>, sort: (a) => a.ceilingUsd ?? 0, align: 'right' },
            { key: 's', label: 'Status', render: (a) => <Pill tone={statusTone[a.status] ?? 'mute'}>{label(a.status)}</Pill>, sort: (a) => a.status },
            { key: 'e', label: 'Evidence', render: (a) => <Cite e={a} /> },
          ]}
        />
      </Panel>
    </div>
  );
}
