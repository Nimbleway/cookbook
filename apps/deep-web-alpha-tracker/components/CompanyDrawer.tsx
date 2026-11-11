'use client';

import { useEffect, type ReactNode } from 'react';
import { AGENT_BY_KEY } from '@/lib/agents';
import { usd, type Metrics } from '@/lib/metrics';
import type { AgentKey, CompanyRecord } from '@/lib/types';
import { Arrow, Cite, label, MixBar, Pill, type Tone } from './ui';

function Section({ agent, rec, count, children }: { agent: AgentKey; rec: CompanyRecord; count: number; children: ReactNode }) {
  const updated = rec.updatedAt[agent];
  return (
    <section className="border-t border-line px-5 py-4">
      <header className="mb-2 flex items-center justify-between">
        <h4 className="text-[12px] font-semibold uppercase tracking-wide text-soft">
          {AGENT_BY_KEY[agent].label} <span className="ml-1 font-mono text-mute">{count}</span>
        </h4>
        <span className="font-mono text-[11px] text-mute">{updated ? updated.slice(0, 10) : 'not run'}</span>
      </header>
      {count === 0 ? <div className="text-mute">Nothing at this confidence level</div> : <div className="space-y-1">{children}</div>}
    </section>
  );
}

function Line({ children, e }: { children: ReactNode; e: Parameters<typeof Cite>[0]['e'] }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded px-1 py-1 hover:bg-panel2">
      <span className="flex min-w-0 items-center gap-2">{children}</span>
      <Cite e={e} />
    </div>
  );
}

const sev: Record<string, Tone> = { high: 'down', medium: 'warn', low: 'mute' };

export function CompanyDrawer({ rec, m, onClose }: { rec: CompanyRecord; m: Metrics; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const c = rec.company;
  const kpis: [string, ReactNode][] = [
    ['Alpha score', m.alphaScore],
    ['Channel net', m.channelNet > 0 ? `+${m.channelNet}` : m.channelNet],
    ['Hiring Δ', m.hiringDeltaPct === null ? '—' : `${m.hiringDeltaPct}%`],
    ['Rivals ▲', m.rivalsRising],
    ['Hit rate', m.hitRatePct === null ? '—' : `${m.hitRatePct}%`],
    ['Insider net', m.insiderNetUsd ? usd(m.insiderNetUsd) : '—'],
    ['Gov obligated', m.govObligatedUsd ? usd(m.govObligatedUsd) : '—'],
    ['Next catalyst', m.nextCatalyst ? `${m.nextCatalyst.days}d` : '—'],
  ];

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50" onClick={onClose}>
      <aside className="scroll-thin h-full w-full max-w-[680px] overflow-y-auto border-l border-line2 bg-panel" onClick={(e) => e.stopPropagation()}>
        <header className="sticky top-0 z-10 border-b border-line bg-panel/95 px-5 py-4 backdrop-blur">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-2xl font-semibold">{c.ticker}</span>
                <span className="text-lg text-soft">{c.name}</span>
              </div>
              <div className="mt-1 flex items-center gap-3 text-[12px] text-mute">
                <span>{c.sector}</span>
                <a href={`https://${c.domain}`} target="_blank" rel="noreferrer" className="hover:text-accent">
                  {c.domain}
                </a>
                <span>
                  {m.datapoints} datapoints · {m.sources} sources · {m.primaryPct}% primary
                </span>
                <MixBar mix={m.mix} />
              </div>
            </div>
            <button type="button" onClick={onClose} className="rounded-md border border-line px-2 py-1 text-mute hover:text-ink" aria-label="Close">
              ✕
            </button>
          </div>
          <div className="mt-3 grid grid-cols-4 gap-2">
            {kpis.map(([k, v]) => (
              <div key={k} className="rounded-lg border border-line bg-panel2 px-2.5 py-1.5">
                <div className="text-[10px] uppercase tracking-wide text-mute">{k}</div>
                <div className="font-mono font-semibold">{v}</div>
              </div>
            ))}
          </div>
          {m.scoreParts.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {m.scoreParts.map((p) => (
                <Pill key={p.label} tone={p.points > 0 ? 'up' : 'down'}>
                  {p.label} {p.points > 0 ? '+' : ''}
                  {p.points}
                </Pill>
              ))}
            </div>
          )}
        </header>

        <Section agent="channel" rec={rec} count={rec.channel?.observations.length ?? 0}>
          {rec.channel?.observations.map((o, i) => (
            <Line key={i} e={o}>
              <Arrow d={o.readsAs === 'supports' ? 'bullish' : o.readsAs === 'contradicts' ? 'bearish' : 'neutral'} />
              <span className="w-44 truncate text-soft">{o.measure}</span>
              <span className="font-mono">
                {o.value} <span className="text-mute">vs {o.prior}</span> <span className="text-mute">{o.unit}</span>
              </span>
            </Line>
          ))}
        </Section>

        <Section agent="catalysts" rec={rec} count={rec.catalysts.length}>
          {[...rec.catalysts].sort((a, b) => (a.date ?? a.dateText).localeCompare(b.date ?? b.dateText)).map((k) => (
            <Line key={k.key} e={k}>
              <span className="w-24 font-mono text-accent">{k.dateText}</span>
              <Pill>{label(k.type)}</Pill>
              <span className="truncate text-soft">{k.description}</span>
            </Line>
          ))}
        </Section>

        <Section agent="forensic" rec={rec} count={rec.forensic?.flags.length ?? 0}>
          {rec.forensic?.flags.map((f, i) => (
            <Line key={i} e={f}>
              <Pill tone={sev[f.severity]}>{f.severity}</Pill>
              <span className="truncate text-soft">{f.finding}</span>
              <span className="text-[11px] text-mute">{f.status}</span>
            </Line>
          ))}
        </Section>

        <Section agent="management" rec={rec} count={(rec.management?.commitments.length ?? 0) + (rec.management?.leadershipChanges.length ?? 0) + (rec.management?.insiderTrades.length ?? 0)}>
          {rec.management?.commitments.map((x, i) => (
            <Line key={`c${i}`} e={x}>
              <Pill tone={x.outcome === 'met' || x.outcome === 'exceeded' ? 'up' : x.outcome === 'missed' || x.outcome === 'withdrawn' ? 'down' : 'mute'}>{label(x.outcome)}</Pill>
              <span className="truncate text-soft">{x.commitment}</span>
              <span className="font-mono text-[11px] text-mute">{x.madeDate}</span>
            </Line>
          ))}
          {rec.management?.leadershipChanges.map((x, i) => (
            <Line key={`l${i}`} e={x}>
              <Pill tone={x.change === 'departed' ? 'down' : 'accent'}>{x.change}</Pill>
              <span className="truncate text-soft">
                {x.role} · {x.person}
              </span>
              <span className="font-mono text-[11px] text-mute">{x.date}</span>
            </Line>
          ))}
          {rec.management?.insiderTrades.map((x, i) => (
            <Line key={`t${i}`} e={x}>
              <Pill tone={x.transaction === 'open_market_buy' ? 'up' : x.transaction === 'open_market_sell' ? 'down' : 'mute'}>{label(x.transaction)}</Pill>
              <span className="truncate text-soft">{x.insider}</span>
              <span className="font-mono">{x.valueUsd ? usd(x.valueUsd) : '—'}</span>
            </Line>
          ))}
        </Section>

        <Section agent="filings" rec={rec} count={rec.filings.length}>
          {rec.filings.map((f, i) => (
            <Line key={i} e={f}>
              <Pill tone={sev[f.relevance]}>{f.relevance}</Pill>
              <span className="font-mono text-mute">{f.form}</span>
              <span className="truncate text-soft">{f.summary}</span>
            </Line>
          ))}
        </Section>

        <Section agent="deepDive" rec={rec} count={(rec.deepDive?.moat.length ?? 0) + (rec.deepDive?.signals.length ?? 0)}>
          {rec.deepDive?.moat.map((x, i) => (
            <Line key={`m${i}`} e={x}>
              <Pill tone={x.direction === 'strengthening' ? 'up' : x.direction === 'weakening' ? 'down' : 'mute'}>{label(x.direction)}</Pill>
              <span className="truncate text-soft">{x.factor}</span>
            </Line>
          ))}
          {rec.deepDive?.signals.map((x, i) => (
            <Line key={`s${i}`} e={x}>
              <Arrow d={x.readsAs === 'supports' ? 'bullish' : x.readsAs === 'contradicts' ? 'bearish' : 'neutral'} />
              <Pill>{label(x.type)}</Pill>
              <span className="truncate text-soft">{x.observation}</span>
            </Line>
          ))}
        </Section>

        <Section agent="competitors" rec={rec} count={rec.competitors.length}>
          {rec.competitors.map((x, i) => (
            <Line key={i} e={x}>
              <Pill tone={x.threat === 'rising' ? 'down' : x.threat === 'falling' ? 'up' : 'mute'}>{x.threat}</Pill>
              <span className="w-28 truncate text-ink">{x.competitor}</span>
              <span className="truncate text-soft">{x.observation}</span>
            </Line>
          ))}
        </Section>

        <Section agent="supplyChain" rec={rec} count={rec.supplyChain.length}>
          {rec.supplyChain.map((x, i) => (
            <Line key={i} e={x}>
              <Pill>{label(x.relationship)}</Pill>
              <span className="w-36 truncate text-ink">{x.counterparty}</span>
              <span className="truncate text-mute">{x.whatFlows}</span>
              {x.revenueSharePct && <span className="font-mono text-warn">{x.revenueSharePct}%</span>}
            </Line>
          ))}
        </Section>

        <Section agent="gov" rec={rec} count={rec.gov.length}>
          {rec.gov.map((x) => (
            <Line key={x.awardId} e={x}>
              <span className="font-mono text-mute">{x.actionDate}</span>
              <span className="w-40 truncate text-soft">{x.agency}</span>
              <span className="font-mono">{x.obligatedUsd ? usd(x.obligatedUsd) : label(x.status)}</span>
            </Line>
          ))}
        </Section>
      </aside>
    </div>
  );
}
