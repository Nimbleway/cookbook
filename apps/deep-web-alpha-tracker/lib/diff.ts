import type { AgentKey, ChangeEvent, CompanyRecord, Direction, Evidence } from './types';

/**
 * Meaningful changes between two versions of a company record. Each rule names a change an analyst
 * would act on; everything else (reworded rows, re-ordered lists) is ignored.
 */
export function diffRecord(prev: CompanyRecord | null, next: CompanyRecord, date: string): ChangeEvent[] {
  const t = next.company.ticker;
  const out: ChangeEvent[] = [];
  const add = (agent: AgentKey, headline: string, direction: Direction, magnitude: 1 | 2 | 3, e: Evidence) =>
    out.push({ id: `${t}-${agent}-${date}-${out.length}`, date, ticker: t, agent, headline, direction, magnitude, confidence: e.confidence, citations: e.citations });
  const fresh = (agent: AgentKey) => next.updatedAt[agent] && next.updatedAt[agent] !== prev?.updatedAt[agent];
  const noEvidence: Evidence = { confidence: 'medium', citations: [] };

  if (fresh('forensic') && next.forensic) {
    const before = new Set(prev?.forensic?.flags.map((f) => `${f.category}:${f.date}`) ?? []);
    for (const f of next.forensic.flags) {
      if (f.status !== 'resolved' && !before.has(`${f.category}:${f.date}`))
        add('forensic', `New red flag: ${f.category.replaceAll('_', ' ')}`, 'bearish', f.severity === 'high' ? 3 : 2, f);
    }
    if (prev?.forensic && prev.forensic.overallRisk !== next.forensic.overallRisk) {
      const worse = ['low', 'medium', 'high'].indexOf(next.forensic.overallRisk) > ['low', 'medium', 'high'].indexOf(prev.forensic.overallRisk);
      add('forensic', `Forensic risk ${prev.forensic.overallRisk} → ${next.forensic.overallRisk}`, worse ? 'bearish' : 'bullish', 3, next.forensic.flags[0] ?? noEvidence);
    }
  }

  if (fresh('management') && next.management) {
    if (prev?.management && prev.management.pattern !== next.management.pattern)
      add('management', `Management read ${prev.management.pattern} → ${next.management.pattern}`, next.management.pattern === 'delivers' ? 'bullish' : 'bearish', 2, next.management.commitments[0] ?? noEvidence);
    const seen = new Set(prev?.management?.leadershipChanges.map((l) => `${l.person}:${l.role}:${l.change}`) ?? []);
    for (const l of next.management.leadershipChanges)
      if (l.change === 'departed' && !seen.has(`${l.person}:${l.role}:${l.change}`)) add('management', `${l.role} departed`, 'bearish', 2, l);
    const trades = new Set(prev?.management?.insiderTrades.map((x) => `${x.date}:${x.insider}`) ?? []);
    for (const x of next.management.insiderTrades) {
      if (trades.has(`${x.date}:${x.insider}`) || (x.valueUsd ?? 0) < 1_000_000) continue;
      if (x.transaction === 'open_market_buy') add('management', `Insider open-market buy, $${((x.valueUsd ?? 0) / 1e6).toFixed(1)}M`, 'bullish', 2, x);
      if (x.transaction === 'open_market_sell') add('management', `Insider open-market sale, $${((x.valueUsd ?? 0) / 1e6).toFixed(1)}M`, 'bearish', 2, x);
    }
  }

  if (fresh('catalysts')) {
    const before = new Map(prev?.catalysts.map((c) => [c.key, c]) ?? []);
    for (const c of next.catalysts) {
      const old = before.get(c.key);
      if (old && old.dateText !== c.dateText) add('catalysts', `${c.description} moved ${old.dateText} → ${c.dateText}`, 'neutral', 2, c);
      else if (!old && prev) add('catalysts', `New catalyst: ${c.description} (${c.dateText})`, 'neutral', 1, c);
    }
  }

  if (fresh('filings')) {
    const before = new Set(prev?.filings.map((f) => f.summary) ?? []);
    for (const f of next.filings) if (f.relevance === 'high' && !before.has(f.summary)) add('filings', `${f.form}: ${f.summary}`, 'neutral', 2, f);
  }

  if (fresh('channel') && next.channel) {
    if (prev?.channel && prev.channel.answer !== next.channel.answer)
      add('channel', `Channel read ${prev.channel.answer} → ${next.channel.answer}`, next.channel.answer === 'yes' ? 'bullish' : next.channel.answer === 'no' ? 'bearish' : 'neutral', 3, next.channel.observations[0] ?? noEvidence);
    for (const o of next.channel.observations) {
      if (!o.prior || o.value === null) continue;
      const pct = Math.round((o.value / o.prior - 1) * 100);
      if (Math.abs(pct) >= 25) add('channel', `${o.measure} ${pct > 0 ? '+' : ''}${pct}%`, o.readsAs === 'supports' ? 'bullish' : o.readsAs === 'contradicts' ? 'bearish' : 'neutral', 2, o);
    }
  }

  if (fresh('competitors')) {
    const before = new Set(prev?.competitors.filter((c) => c.threat === 'rising').map((c) => c.competitor) ?? []);
    const rising = [...new Set(next.competitors.filter((c) => c.threat === 'rising').map((c) => c.competitor))].filter((n) => !before.has(n));
    if (rising.length) add('competitors', `Rivals gaining: ${rising.slice(0, 3).join(', ')}`, 'bearish', rising.length >= 3 ? 2 : 1, next.competitors.find((c) => c.competitor === rising[0])!);
  }

  if (fresh('gov')) {
    const before = new Set(prev?.gov.map((g) => g.awardId) ?? []);
    for (const g of next.gov) {
      if (before.has(g.awardId)) continue;
      if (g.status === 'protest_sustained') add('gov', `Bid protest sustained (${g.agency})`, 'bearish', 3, g);
      else if ((g.obligatedUsd ?? 0) >= 25_000_000) add('gov', `New award, $${Math.round((g.obligatedUsd ?? 0) / 1e6)}M obligated (${g.agency})`, 'bullish', 2, g);
    }
  }

  if (fresh('supplyChain') && prev) {
    const before = new Map(prev.supplyChain.map((s) => [`${s.counterparty}:${s.relationship}`, s]));
    for (const s of next.supplyChain) {
      const old = before.get(`${s.counterparty}:${s.relationship}`);
      if (old && old.status !== 'ended' && s.status === 'ended') add('supplyChain', `${s.relationship} relationship ended: ${s.counterparty}`, 'bearish', 2, s);
      if (!old && s.relationship === 'customer' && s.revenueSharePct) add('supplyChain', `New disclosed customer: ${s.counterparty} (${s.revenueSharePct}% of revenue)`, 'neutral', 2, s);
    }
  }

  if (fresh('deepDive') && prev?.deepDive && next.deepDive) {
    const before = new Map(prev.deepDive.moat.map((m) => [m.factor, m.direction]));
    for (const m of next.deepDive.moat) {
      const old = before.get(m.factor);
      if (old && old !== m.direction && m.direction !== 'cannot_verify') add('deepDive', `${m.factor}: ${old} → ${m.direction}`, m.direction === 'strengthening' ? 'bullish' : 'bearish', 2, m);
    }
  }

  return out;
}

/** Changes worth a Slack message: magnitude 2+ and not resting on low-confidence evidence. */
export function alertable(changes: ChangeEvent[]): ChangeEvent[] {
  return changes.filter((c) => c.magnitude >= 2 && c.confidence !== 'low');
}
