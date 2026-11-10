'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AGENTS } from '@/lib/agents';
import { filterRecord, metrics, type ConfidenceFilter } from '@/lib/metrics';
import type { AgentKey, Confidence, Effort, Snapshot } from '@/lib/types';
import { CompanyDrawer } from './CompanyDrawer';
import { CatalystsTab, ChannelTab, GovTab, RiskTab, SignalsTab, SupplyTab, WatchlistTab, type Row } from './tabs';
import { CONF_COLOR, Stat } from './ui';

type Tab = 'watchlist' | 'signals' | 'catalysts' | 'channel' | 'risk' | 'supply' | 'gov';
const TABS: { key: Tab; label: string }[] = [
  { key: 'watchlist', label: 'Watchlist' },
  { key: 'signals', label: 'Signal feed' },
  { key: 'catalysts', label: 'Catalysts' },
  { key: 'channel', label: 'Channel & competition' },
  { key: 'risk', label: 'Risk & governance' },
  { key: 'supply', label: 'Supply chain' },
  { key: 'gov', label: 'Government' },
];

interface RefreshState {
  refresh: {
    id: string;
    effort: Effort;
    finishedAt: string | null;
    counts: Record<'pending' | 'running' | 'completed' | 'failed' | 'skipped', number>;
    changesFound: number;
    alertsSent: number;
  } | null;
  agents: { key: AgentKey; label: string; configured: boolean }[];
  protected: boolean;
}

function RefreshControl({ onDone }: { onDone: () => void }) {
  const [state, setState] = useState<RefreshState | null>(null);
  const [open, setOpen] = useState(false);
  const [effort, setEffort] = useState<Effort>('high');
  const [picked, setPicked] = useState<AgentKey[]>(AGENTS.map((a) => a.key));
  const [key, setKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const wasRunning = useRef(false);

  const poll = useCallback(async () => {
    const res = await fetch('/api/refresh', { cache: 'no-store' }).catch(() => null);
    if (!res?.ok) return;
    const next = (await res.json()) as RefreshState;
    setState(next);
    const running = Boolean(next.refresh && !next.refresh.finishedAt);
    if (wasRunning.current && !running) onDone();
    wasRunning.current = running;
  }, [onDone]);

  useEffect(() => {
    try {
      setKey(localStorage.getItem('dwa-refresh-key') ?? '');
    } catch {}
    poll();
  }, [poll]);

  const running = Boolean(state?.refresh && !state.refresh.finishedAt);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(poll, 15_000);
    return () => clearInterval(t);
  }, [running, poll]);

  async function start() {
    setError(null);
    const res = await fetch('/api/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(key ? { 'x-refresh-key': key } : {}) },
      body: JSON.stringify({ effort, agents: picked }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(body.error ?? `Refresh failed (${res.status})`);
      return;
    }
    try {
      if (key) localStorage.setItem('dwa-refresh-key', key);
    } catch {}
    setOpen(false);
    wasRunning.current = true;
    poll();
  }

  const c = state?.refresh?.counts;
  const total = c ? c.pending + c.running + c.completed + c.failed : 0;
  const done = c ? c.completed + c.failed : 0;
  const configured = new Set(state?.agents.filter((a) => a.configured).map((a) => a.key));

  return (
    <div className="relative flex items-center gap-3">
      {running && c && (
        <div className="flex items-center gap-2 text-[12px] text-soft">
          <span className="font-mono">
            {done}/{total} runs
          </span>
          <span className="h-1.5 w-28 overflow-hidden rounded-full bg-line">
            <span className="block h-full bg-accent transition-all" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
          </span>
          {c.failed > 0 && <span className="text-down">{c.failed} failed</span>}
        </div>
      )}
      {!running && state?.refresh?.finishedAt && (
        <span className="text-[12px] text-mute">
          Last refresh {state.refresh.finishedAt.slice(0, 16).replace('T', ' ')} · {state.refresh.changesFound} changes · {state.refresh.alertsSent} alerted
        </span>
      )}
      <button
        type="button"
        disabled={running}
        onClick={() => setOpen((v) => !v)}
        className="rounded-lg bg-accent px-3.5 py-1.5 text-[13px] font-semibold text-white hover:bg-accent/85 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {running ? 'Refreshing…' : 'Refresh ▾'}
      </button>
      {open && (
        <div className="absolute right-0 top-10 z-30 w-80 rounded-xl border border-line2 bg-panel2 p-4 shadow-2xl shadow-black/60">
          <label className="block text-[11px] uppercase tracking-wide text-mute">Effort</label>
          <select value={effort} onChange={(e) => setEffort(e.target.value as Effort)} className="mt-1 w-full rounded-md border border-line bg-panel px-2 py-1.5">
            <option value="low">Low · quick sweep</option>
            <option value="medium">Medium · multi-source</option>
            <option value="high">High · deep cross-source (recommended)</option>
            <option value="x-high">X-high · exhaustive</option>
          </select>
          <div className="mt-3 flex items-center justify-between text-[11px] uppercase tracking-wide text-mute">
            <span>Agents</span>
            <span className="font-mono normal-case">{picked.filter((k) => configured.has(k)).length * 50} runs</span>
          </div>
          <div className="mt-1 space-y-1">
            {AGENTS.map((a) => (
              <label key={a.key} className={`flex items-center justify-between gap-2 ${configured.has(a.key) ? '' : 'opacity-40'}`}>
                <span className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    disabled={!configured.has(a.key)}
                    checked={picked.includes(a.key) && configured.has(a.key)}
                    onChange={(e) => setPicked((p) => (e.target.checked ? [...p, a.key] : p.filter((k) => k !== a.key)))}
                    className="accent-[#5b93f8]"
                  />
                  {a.label}
                </span>
                {!configured.has(a.key) && <span className="text-[11px] text-mute">no ID</span>}
              </label>
            ))}
          </div>
          {state?.protected && (
            <input
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="Refresh key"
              className="mt-3 w-full rounded-md border border-line bg-panel px-2 py-1.5"
            />
          )}
          {error && <div className="mt-2 text-[12px] text-down">{error}</div>}
          <button type="button" onClick={start} className="mt-3 w-full rounded-lg bg-accent py-1.5 font-semibold text-white hover:bg-accent/85">
            Run agents
          </button>
        </div>
      )}
    </div>
  );
}

export function Dashboard({ snapshot, liveShare, note }: { snapshot: Snapshot; liveShare: number; note?: string }) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('watchlist');
  const [conf, setConf] = useState<ConfidenceFilter>({ high: true, medium: true, low: true });
  const [sector, setSector] = useState('all');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string | null>(null);

  const sectors = useMemo(() => [...new Set(snapshot.records.map((r) => r.company.sector))], [snapshot]);
  const rows: Row[] = useMemo(() => {
    const q = query.trim().toLowerCase();
    return snapshot.records
      .filter((r) => (sector === 'all' || r.company.sector === sector) && (!q || r.company.ticker.toLowerCase().includes(q) || r.company.name.toLowerCase().includes(q)))
      .map((r) => {
        const rec = filterRecord(r, conf);
        return { rec, m: metrics(rec) };
      });
  }, [snapshot, conf, sector, query]);
  const tickers = useMemo(() => new Set(rows.map((r) => r.rec.company.ticker)), [rows]);
  const changes = useMemo(() => snapshot.changes.filter((c) => conf[c.confidence] && tickers.has(c.ticker)), [snapshot, conf, tickers]);

  const totals = useMemo(() => {
    const t = { datapoints: 0, citations: 0, high: 0, primary: 0 };
    const urls = new Set<string>();
    for (const r of rows) {
      t.datapoints += r.m.datapoints;
      t.citations += r.m.citations;
      t.high += r.m.mix.high;
      t.primary += Math.round((r.m.primaryPct / 100) * r.m.citations);
    }
    for (const r of rows) for (const e of [...r.rec.filings, ...r.rec.catalysts, ...r.rec.gov, ...r.rec.supplyChain, ...r.rec.competitors]) for (const c of e.citations) urls.add(c.url);
    return { ...t, sources: urls.size };
  }, [rows]);
  const weekAgo = new Date(Date.now() - 7 * 86_400_000).toISOString().slice(0, 10);
  const recent = changes.filter((c) => c.date >= weekAgo);
  const selectedRow = rows.find((r) => r.rec.company.ticker === selected) ?? null;
  const tabProps = { rows, changes, onSelect: setSelected };
  const isSample = snapshot.source === 'sample' || liveShare < 1;

  return (
    <main className="mx-auto max-w-[1600px] px-4 pb-16 pt-6 sm:px-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-semibold tracking-tight">Deep Web Alpha Tracker</h1>
            {isSample && (
              <span className="rounded border border-warn/30 bg-warn/10 px-1.5 py-px text-[11px] text-warn" title="Sample rows are generated, not researched. A refresh replaces them with live agent results.">
                {liveShare > 0 ? `${Math.round(liveShare * 100)}% live · rest sample` : 'Sample data'}
              </span>
            )}
          </div>
          <p className="mt-1 text-soft">
            Deep web context on {snapshot.records.length} tech names from {AGENTS.length} Nimble Web Search Agents, cited and confidence-graded, to boost your alpha.
          </p>
          {note && <p className="mt-1 text-[12px] text-warn">{note}</p>}
        </div>
        <RefreshControl onDone={() => router.refresh()} />
      </header>

      <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Datapoints" value={totals.datapoints.toLocaleString()} sub="every row cited" />
        <Stat label="Citations" value={totals.citations.toLocaleString()} sub={`${totals.citations ? Math.round((totals.primary / totals.citations) * 100) : 0}% primary sources`} />
        <Stat label="Distinct sources" value={totals.sources.toLocaleString()} sub="filings, registries, sites" />
        <Stat label="High confidence" value={`${totals.datapoints ? Math.round((totals.high / totals.datapoints) * 100) : 0}%`} sub="of datapoints shown" />
        <Stat label="Changes, 7 days" value={recent.length} sub={`${recent.filter((c) => c.magnitude >= 2).length} meaningful`} />
        <Stat label="Names covered" value={`${rows.length}/${snapshot.records.length}`} sub={`updated ${snapshot.generatedAt.slice(0, 10)}`} />
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-b border-line">
        <nav className="scroll-thin -mb-px flex gap-1 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] ${tab === t.key ? 'border-accent text-ink' : 'border-transparent text-mute hover:text-ink'}`}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="flex flex-wrap items-center gap-2 pb-2">
          <div className="flex items-center gap-1 rounded-lg border border-line bg-panel p-0.5" role="group" aria-label="Confidence filter">
            {(['high', 'medium', 'low'] as Confidence[]).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setConf((s) => ({ ...s, [c]: !s[c] }))}
                className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] capitalize ${conf[c] ? 'bg-panel2 text-ink' : 'text-mute line-through'}`}
              >
                <span className={`h-2 w-2 rounded-full ${CONF_COLOR[c]} ${conf[c] ? '' : 'opacity-30'}`} />
                {c}
              </button>
            ))}
          </div>
          <select value={sector} onChange={(e) => setSector(e.target.value)} className="rounded-lg border border-line bg-panel px-2 py-1.5 text-[12px]">
            <option value="all">All sleeves</option>
            {sectors.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ticker or name" className="w-36 rounded-lg border border-line bg-panel px-2 py-1.5 text-[12px] placeholder:text-mute" />
        </div>
      </div>

      <div className="mt-4">
        {tab === 'watchlist' && <WatchlistTab {...tabProps} />}
        {tab === 'signals' && <SignalsTab {...tabProps} />}
        {tab === 'catalysts' && <CatalystsTab {...tabProps} />}
        {tab === 'channel' && <ChannelTab {...tabProps} />}
        {tab === 'risk' && <RiskTab {...tabProps} />}
        {tab === 'supply' && <SupplyTab {...tabProps} />}
        {tab === 'gov' && <GovTab {...tabProps} />}
      </div>

      {selectedRow && <CompanyDrawer rec={selectedRow.rec} m={selectedRow.m} onClose={() => setSelected(null)} />}
    </main>
  );
}
