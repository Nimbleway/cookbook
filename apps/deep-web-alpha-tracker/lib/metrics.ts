import type { CompanyRecord, Confidence, Evidence } from './types';

export type ConfidenceFilter = Record<Confidence, boolean>;

const keep = (allowed: ConfidenceFilter) => (e: Evidence) => allowed[e.confidence];

/** The record with every row below the selected confidence levels removed; all metrics read from this. */
export function filterRecord(rec: CompanyRecord, allowed: ConfidenceFilter): CompanyRecord {
  const k = keep(allowed);
  return {
    ...rec,
    deepDive: rec.deepDive && {
      moat: rec.deepDive.moat.filter(k),
      signals: rec.deepDive.signals.filter(k),
      risks: rec.deepDive.risks.filter((x) => allowed[x.evidence.confidence]),
    },
    channel: rec.channel && { ...rec.channel, observations: rec.channel.observations.filter(k) },
    filings: rec.filings.filter(k),
    forensic: rec.forensic && { ...rec.forensic, flags: rec.forensic.flags.filter(k) },
    management: rec.management && {
      ...rec.management,
      commitments: rec.management.commitments.filter(k),
      leadershipChanges: rec.management.leadershipChanges.filter(k),
      insiderTrades: rec.management.insiderTrades.filter(k),
    },
    catalysts: rec.catalysts.filter(k),
    supplyChain: rec.supplyChain.filter(k),
    competitors: rec.competitors.filter(k),
    gov: rec.gov.filter(k),
  };
}

export function allEvidence(rec: CompanyRecord): Evidence[] {
  return [
    ...(rec.deepDive?.moat ?? []),
    ...(rec.deepDive?.signals ?? []),
    ...(rec.deepDive?.risks.map((x) => x.evidence) ?? []),
    ...(rec.channel?.observations ?? []),
    ...rec.filings,
    ...(rec.forensic?.flags ?? []),
    ...(rec.management?.commitments ?? []),
    ...(rec.management?.leadershipChanges ?? []),
    ...(rec.management?.insiderTrades ?? []),
    ...rec.catalysts,
    ...rec.supplyChain,
    ...rec.competitors,
    ...rec.gov,
  ];
}

export function daysUntil(date: string, now = new Date()): number {
  return Math.round((Date.parse(`${date}T00:00:00Z`) - Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())) / 86_400_000);
}

export interface ScorePart {
  label: string;
  points: number;
}

export interface Metrics {
  alphaScore: number;
  scoreParts: ScorePart[];
  channelNet: number;
  channelAnswer: string;
  hiringDeltaPct: number | null;
  rivalsRising: number;
  forensicRisk: 'low' | 'medium' | 'high' | null;
  openFlags: number;
  hitRatePct: number | null;
  mgmtPattern: string | null;
  insiderNetUsd: number;
  leadershipExits: number;
  nextCatalyst: { date: string; days: number; description: string } | null;
  catalysts90: number;
  highFilingChanges: number;
  govObligatedUsd: number;
  govCeilingUsd: number;
  govAwards: number;
  topCustomerPct: number | null;
  relationships: number;
  moatNet: number;
  datapoints: number;
  citations: number;
  sources: number;
  primaryPct: number;
  mix: Record<Confidence, number>;
}

export function metrics(rec: CompanyRecord, now = new Date()): Metrics {
  const obs = rec.channel?.observations ?? [];
  const channelNet = obs.filter((o) => o.readsAs === 'supports').length - obs.filter((o) => o.readsAs === 'contradicts').length;
  const hiring = obs.filter((o) => o.type === 'hiring' && o.prior);
  const hiringDeltaPct = hiring.length
    ? Math.round((hiring.reduce((s, o) => s + (o.value ?? 0), 0) / hiring.reduce((s, o) => s + (o.prior ?? 0), 0) - 1) * 100)
    : null;
  const rivalsRising = new Set(rec.competitors.filter((c) => c.threat === 'rising').map((c) => c.competitor)).size;
  const openFlags = rec.forensic?.flags.filter((f) => f.status !== 'resolved').length ?? 0;
  const highOpen = rec.forensic?.flags.filter((f) => f.status !== 'resolved' && f.severity === 'high').length ?? 0;
  const forensicRisk = rec.forensic ? (highOpen ? 'high' : openFlags > 1 ? 'medium' : 'low') : null;
  const decided = rec.management?.commitments.filter((c) => !['pending', 'cannot_verify'].includes(c.outcome)) ?? [];
  const hits = decided.filter((c) => c.outcome === 'met' || c.outcome === 'exceeded').length;
  const hitRatePct = decided.length ? Math.round((hits / decided.length) * 100) : null;
  const insiderNetUsd = (rec.management?.insiderTrades ?? []).reduce(
    (s, t) => s + (t.transaction === 'open_market_buy' ? 1 : t.transaction === 'open_market_sell' ? -1 : 0) * (t.valueUsd ?? 0),
    0
  );
  const leadershipExits = rec.management?.leadershipChanges.filter((l) => l.change === 'departed').length ?? 0;
  const upcoming = rec.catalysts
    .filter((c) => c.date && daysUntil(c.date, now) >= 0)
    .sort((a, b) => (a.date ?? '').localeCompare(b.date ?? ''));
  const nextCatalyst = upcoming[0]?.date ? { date: upcoming[0].date, days: daysUntil(upcoming[0].date, now), description: upcoming[0].description } : null;
  const catalysts90 = upcoming.filter((c) => daysUntil(c.date!, now) <= 90).length;
  const moatNet =
    (rec.deepDive?.moat.filter((m) => m.direction === 'strengthening').length ?? 0) - (rec.deepDive?.moat.filter((m) => m.direction === 'weakening').length ?? 0);
  const govObligatedUsd = rec.gov.reduce((s, g) => s + (g.obligatedUsd ?? 0), 0);
  const govCeilingUsd = rec.gov.reduce((s, g) => s + (g.ceilingUsd ?? 0), 0);
  const shares = rec.supplyChain.map((s) => s.revenueSharePct ?? 0).filter(Boolean);

  const parts: ScorePart[] = [
    { label: 'Channel momentum', points: channelNet * 5 },
    { label: 'Moat trend', points: moatNet * 3 },
    { label: 'Management delivery', points: hitRatePct === null ? 0 : Math.round((hitRatePct - 60) / 4) },
    { label: 'Insider buying', points: insiderNetUsd > 0 ? 6 : insiderNetUsd < -5_000_000 ? -3 : 0 },
    { label: 'Near-term catalysts', points: Math.min(catalysts90, 4) * 2 },
    { label: 'Rivals gaining', points: -rivalsRising * 3 },
    { label: 'Forensic flags', points: forensicRisk === 'high' ? -18 : forensicRisk === 'medium' ? -7 : 0 },
    { label: 'Leadership exits', points: -leadershipExits * 3 },
  ];
  const alphaScore = Math.max(0, Math.min(100, 50 + parts.reduce((s, p) => s + p.points, 0)));

  const evidence = allEvidence(rec);
  const urls = new Set<string>();
  let primary = 0;
  let cites = 0;
  for (const e of evidence) {
    for (const c of e.citations) {
      cites += 1;
      urls.add(c.url);
      if (c.sourceType === 'primary') primary += 1;
    }
  }
  const mix = { high: 0, medium: 0, low: 0 };
  for (const e of evidence) mix[e.confidence] += 1;

  return {
    alphaScore,
    scoreParts: parts.filter((p) => p.points !== 0),
    channelNet,
    channelAnswer: rec.channel?.answer ?? 'insufficient',
    hiringDeltaPct,
    rivalsRising,
    forensicRisk,
    openFlags,
    hitRatePct,
    mgmtPattern: rec.management?.pattern ?? null,
    insiderNetUsd,
    leadershipExits,
    nextCatalyst,
    catalysts90,
    highFilingChanges: rec.filings.filter((f) => f.relevance === 'high').length,
    govObligatedUsd,
    govCeilingUsd,
    govAwards: rec.gov.filter((g) => g.type !== 'protest').length,
    topCustomerPct: shares.length ? Math.max(...shares) : null,
    relationships: rec.supplyChain.length,
    moatNet,
    datapoints: evidence.length,
    citations: cites,
    sources: urls.size,
    primaryPct: cites ? Math.round((primary / cites) * 100) : 0,
    mix,
  };
}

export function usd(n: number): string {
  const a = Math.abs(n);
  const s = a >= 1e9 ? `${(a / 1e9).toFixed(1)}B` : a >= 1e6 ? `${(a / 1e6).toFixed(a >= 1e8 ? 0 : 1)}M` : a >= 1e3 ? `${Math.round(a / 1e3)}K` : `${a}`;
  return `${n < 0 ? '-' : ''}$${s}`;
}
