import { AGENTS } from './agents';
import { COMPANIES } from './companies';
import type {
  AgentKey,
  ChangeEvent,
  Citation,
  Company,
  CompanyRecord,
  Confidence,
  Direction,
  Evidence,
  Snapshot,
} from './types';

/**
 * Sample snapshot shown until the first live refresh. Shaped exactly like mapped agent output so the
 * UI exercises the same code paths; values are generated, not researched.
 */

function rng(seed: string) {
  let h = 2166136261;
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

type Rand = () => number;
const pick = <T,>(r: Rand, xs: readonly T[]): T => xs[Math.floor(r() * xs.length)];
const int = (r: Rand, lo: number, hi: number) => lo + Math.floor(r() * (hi - lo + 1));
const conf = (r: Rand, bias = 0): Confidence => {
  const x = r() + bias;
  return x > 0.45 ? 'high' : x > 0.18 ? 'medium' : 'low';
};

function day(offset: number, base = new Date()): string {
  const d = new Date(base);
  d.setUTCDate(d.getUTCDate() + offset);
  return d.toISOString().slice(0, 10);
}

const SRC = {
  edgar: (c: Company, form = '10-K'): Citation => ({
    url: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${c.ticker}&type=${form}`,
    title: `SEC EDGAR · ${c.ticker} ${form}`,
    sourceType: 'primary',
  }),
  site: (c: Company): Citation => ({ url: `https://www.${c.domain}/`, title: c.domain, sourceType: 'primary' }),
  archive: (c: Company): Citation => ({ url: `https://web.archive.org/web/2026*/${c.domain}`, title: 'Wayback Machine', sourceType: 'primary' }),
  usaspending: (): Citation => ({ url: 'https://www.usaspending.gov/search', title: 'USAspending.gov', sourceType: 'primary' }),
  gao: (): Citation => ({ url: 'https://www.gao.gov/legal/bid-protests/search', title: 'GAO bid protests', sourceType: 'primary' }),
  courts: (c: Company): Citation => ({ url: `https://www.courtlistener.com/?q=%22${encodeURIComponent(c.name)}%22`, title: 'CourtListener', sourceType: 'primary' }),
  news: (c: Company): Citation => ({ url: `https://news.google.com/search?q=${encodeURIComponent(c.name)}`, title: 'News coverage', sourceType: 'secondary' }),
  pcaob: (): Citation => ({ url: 'https://pcaobus.org/resources/auditorsearch', title: 'PCAOB AuditorSearch', sourceType: 'primary' }),
};

function ev(r: Rand, citations: Citation[], bias = 0): Evidence {
  return { confidence: conf(r, bias), citations };
}

const MOAT = ['Pricing power', 'Switching costs', 'Scale economics', 'Network effects', 'Proprietary IP', 'Distribution', 'New entrant pressure'];
const SIGNAL_TYPES = ['hiring', 'pricing', 'product', 'customer', 'partnership', 'footprint', 'regulatory', 'insider'] as const;
const SIGNAL_TEXT: Record<(typeof SIGNAL_TYPES)[number], string[]> = {
  hiring: ['GPU cluster engineering roles up', 'Enterprise sales hiring paused in EMEA', 'New AI research hub roles posted'],
  pricing: ['List price raised on top tier', 'Usage discounts widened', 'New premium SKU launched'],
  product: ['GA launch of agentic suite', 'Next-gen platform sampling early', 'Legacy product sunset notice'],
  customer: ['Fortune 100 case study published', 'Top customer named as dual-sourcing', 'Public-sector logo added'],
  partnership: ['Hyperscaler co-sell agreement', 'OEM design win announced', 'Channel partner program expanded'],
  footprint: ['New data center site permit filed', 'Subsidiary registered in India', 'Office lease expanded in Austin'],
  regulatory: ['EU AI Act filing listed', 'Export license condition disclosed', 'FTC inquiry referenced'],
  insider: ['Director open-market purchase', 'CFO 10b5-1 sales resumed', 'Cluster of insider buys'],
};
const RISKS = [
  ['Customer concentration in top 3 buyers', 'financial'],
  ['Export controls on advanced chips', 'regulatory'],
  ['Hyperscaler in-house silicon', 'competitive'],
  ['Elevated stock-based compensation', 'governance'],
  ['Capacity constraints at foundry partner', 'operational'],
  ['Pending securities class action', 'legal'],
] as const;
const CHANNEL_MEASURES = [
  ['Open engineering roles', 'hiring', 'roles'],
  ['Open sales roles', 'hiring', 'roles'],
  ['Top-tier list price', 'pricing_offer', 'USD/mo'],
  ['Promo depth', 'pricing_offer', '%'],
  ['Partner marketplace listings', 'customer', 'listings'],
  ['Distributor lead time', 'supply', 'weeks'],
  ['New site permits', 'footprint', 'permits'],
  ['Status page incidents', 'public_record', 'incidents'],
] as const;
const FILING_AREAS = ['risk_factors', 'mda_outlook', 'liquidity_debt', 'customer_concentration', 'controls', 'legal_proceedings', 'segments', 'accounting'];
const FILING_TEXT: Record<string, string[]> = {
  risk_factors: ['New risk factor on AI model liability', 'Export-control risk expanded to new regions', 'Cyber incident risk reworded'],
  mda_outlook: ['Outlook hedge added on enterprise demand', 'Backlog disclosure dropped', 'Gross margin guide language softened'],
  liquidity_debt: ['New $2B revolver disclosed', 'Covenant amendment added', 'Convertible notes due 2028 repurchased'],
  customer_concentration: ['Customer A rose to 18% of revenue', 'Second 10% customer disclosed', 'Concentration note removed'],
  controls: ['Material weakness remediated', 'New IT general controls finding', 'Auditor attestation unchanged'],
  legal_proceedings: ['New patent suit in E.D. Tex.', 'Shareholder suit dismissed', 'DOJ subpoena disclosed'],
  segments: ['New AI segment reported', 'Segments consolidated from 4 to 3', 'Data center split out'],
  accounting: ['Revenue recognition for multi-year deals changed', 'Useful life of servers extended', 'Capitalized software policy changed'],
};
const FORENSIC = [
  ['auditor_change', 'Auditor dismissed; no disagreements reported'],
  ['sec_comment_letter', 'Repeated SEC comments on non-GAAP metrics'],
  ['related_party', 'Supplier owned by director family member'],
  ['insider_selling', 'Insider sales above 12-month average'],
  ['earnings_quality', 'Receivables growing faster than revenue'],
  ['executive_turnover', 'Chief accounting officer departed'],
  ['short_report', 'Activist short report published'],
  ['material_weakness', 'Material weakness in revenue controls'],
  ['capital_raises', 'Third equity raise in 18 months'],
] as const;
const COMMITMENTS = ['Operating margin target', 'Product launch date', 'Cost savings program', 'Free cash flow target', 'Revenue growth guide', 'Capex envelope', 'Net retention target'];
const ROLES = ['CFO', 'COO', 'Chief Accounting Officer', 'CTO', 'President, Cloud', 'General Counsel', 'Director'];
const PEOPLE = ['A. Chen', 'M. Patel', 'J. Alvarez', 'S. Okafor', 'R. Novak', 'L. Haddad', 'K. Tanaka', 'D. Weiss'];
const CATALYSTS = [
  ['earnings', 'Quarterly earnings', 'confirmed'],
  ['investor_day', 'Investor day', 'confirmed'],
  ['conference', 'Tech conference keynote', 'confirmed'],
  ['product_launch', 'Next-gen platform launch', 'company_guided'],
  ['lockup_expiry', 'Lockup expiry', 'statutory'],
  ['debt_maturity', 'Convertible notes maturity', 'statutory'],
  ['shareholder_meeting', 'Annual meeting', 'estimated'],
  ['index_change', 'Index rebalance', 'estimated'],
  ['court_date', 'Patent trial date', 'confirmed'],
  ['contract_decision', 'Federal contract award decision', 'estimated'],
] as const;
type Party = readonly [string, string | null, string, string];
const COUNTERPARTIES: Record<string, Party[]> = {
  Semis: [
    ['TSMC', 'TSM', 'supplier', 'Wafer fabrication'], ['SK hynix', null, 'supplier', 'HBM memory'], ['ASML', null, 'supplier', 'Lithography tools'],
    ['Amkor Technology', null, 'supplier', 'Advanced packaging'], ['Microsoft', 'MSFT', 'customer', 'Accelerators'], ['Meta Platforms', 'META', 'customer', 'Custom silicon'],
    ['Amazon Web Services', 'AMZN', 'customer', 'Data center chips'], ['Arrow Electronics', null, 'distributor', 'Distribution'], ['Foxconn', null, 'contract_manufacturer', 'Board assembly'],
  ],
  'AI infrastructure': [
    ['NVIDIA', 'NVDA', 'supplier', 'GPUs'], ['AMD', 'AMD', 'supplier', 'Accelerators'], ['Broadcom', 'AVGO', 'supplier', 'Networking silicon'], ['Microsoft', 'MSFT', 'customer', 'GPU capacity'],
    ['OpenAI', null, 'customer', 'Compute contracts'], ['Meta Platforms', 'META', 'customer', 'Clusters'], ['Jabil', null, 'contract_manufacturer', 'Rack integration'], ['Equinix', null, 'partner', 'Colocation'],
  ],
  'Cloud & data': [
    ['Amazon Web Services', 'AMZN', 'partner', 'Marketplace and hosting'], ['Microsoft Azure', 'MSFT', 'partner', 'Hosting'], ['Google Cloud', 'GOOGL', 'partner', 'Hosting'],
    ['NVIDIA', 'NVDA', 'supplier', 'GPU capacity'], ['Accenture', null, 'partner', 'Systems integration'], ['Capital One', null, 'customer', 'Platform'], ['U.S. federal civilian agencies', null, 'customer', 'FedRAMP services'],
  ],
  Security: [
    ['Amazon Web Services', 'AMZN', 'partner', 'Marketplace'], ['Microsoft', 'MSFT', 'partner', 'Integrations'], ['CDW', null, 'distributor', 'Reseller channel'], ['Optiv', null, 'distributor', 'Reseller channel'],
    ['U.S. Department of Defense', null, 'customer', 'Endpoint and network security'], ['Google Cloud', 'GOOGL', 'partner', 'Hosting'], ['Deloitte', null, 'partner', 'Managed services'],
  ],
  'AI software': [
    ['Amazon Web Services', 'AMZN', 'partner', 'Hosting'], ['Microsoft Azure', 'MSFT', 'partner', 'Hosting'], ['OpenAI', null, 'supplier', 'Foundation models'], ['Anthropic', null, 'supplier', 'Foundation models'],
    ['Accenture', null, 'partner', 'Implementation'], ['Deloitte', null, 'partner', 'Implementation'], ['U.S. Army', null, 'customer', 'Software licenses'], ['Snowflake', 'SNOW', 'partner', 'Data integration'],
  ],
  'Consumer internet': [
    ['Apple App Store', null, 'distributor', 'App distribution'], ['Google Play', 'GOOGL', 'distributor', 'App distribution'], ['Amazon Web Services', 'AMZN', 'supplier', 'Hosting'],
    ['Google Cloud', 'GOOGL', 'supplier', 'Hosting'], ['Stripe', null, 'supplier', 'Payments'], ['Unity Software', null, 'partner', 'Ad mediation'], ['NVIDIA', 'NVDA', 'supplier', 'GPU compute'],
  ],
  'Space & defense tech': [
    ['U.S. Department of Defense', null, 'customer', 'Programs'], ['NASA', null, 'customer', 'Launch and missions'], ['Space Development Agency', null, 'customer', 'Satellites'],
    ['L3Harris', null, 'partner', 'Payloads'], ['Lockheed Martin', null, 'partner', 'Subcontracts'], ['Amazon Web Services', 'AMZN', 'partner', 'Ground stations'], ['AT&T', null, 'partner', 'Spectrum'],
  ],
};
const RIVALS: Record<string, string[]> = {
  Semis: ['Groq', 'Cerebras', 'Tenstorrent', 'SambaNova', 'Etched', 'Lightmatter'],
  'AI infrastructure': ['Lambda', 'Crusoe', 'Together AI', 'Vast Data', 'Fluidstack', 'Hyperbolic'],
  'Cloud & data': ['Databricks', 'ClickHouse', 'Supabase', 'Grafana Labs', 'Vercel', 'Chronosphere'],
  Security: ['Wiz', 'Abnormal Security', 'Cyera', 'Island', 'Chainguard', 'Vanta'],
  'AI software': ['Glean', 'Sierra', 'Harvey', 'Writer', 'Notion', 'Retool'],
  'Consumer internet': ['Perplexity', 'Character.AI', 'Speak', 'Discord', 'Whatnot', 'Canva'],
  'Space & defense tech': ['Anduril', 'Shield AI', 'Firefly Aerospace', 'Relativity Space', 'PsiQuantum', 'Saronic'],
};
const COMP_TYPES = ['product_launch', 'pricing_change', 'funding', 'hiring', 'customer_win', 'partnership', 'expansion'];
const COMP_TEXT: Record<string, string> = {
  product_launch: 'Launched competing product',
  pricing_change: 'Cut list price on core plan',
  funding: 'Raised growth round',
  hiring: 'Open roles up quarter over quarter',
  customer_win: 'Won shared enterprise customer',
  partnership: 'Signed hyperscaler partnership',
  expansion: 'Opened new region',
};
const AGENCIES = ['Dept. of Defense · Army', 'Dept. of Defense · Air Force', 'Dept. of Defense · Navy', 'Dept. of Homeland Security', 'Dept. of Veterans Affairs', 'NASA', 'Dept. of Energy', 'GSA'];
const GOV_HEAVY = new Set(['PLTR', 'KTOS', 'RKLB', 'ASTS', 'MSFT', 'AMZN', 'GOOGL', 'ORCL', 'CRWD', 'PANW', 'DELL', 'AI']);

function record(c: Company, now: Date): CompanyRecord {
  const r = rng(c.ticker);
  const updated = day(-int(r, 0, 2), now);
  const updatedAt = Object.fromEntries(AGENTS.map((a) => [a.key, updated])) as Record<AgentKey, string>;
  const ago = (lo: number, hi: number) => day(-int(r, lo, hi), now);
  const ahead = (lo: number, hi: number) => day(int(r, lo, hi), now);

  const deepDive = {
    moat: MOAT.filter(() => r() > 0.4).map((factor) => ({
      factor,
      direction: pick(r, ['strengthening', 'strengthening', 'stable', 'weakening', 'cannot_verify'] as const),
      ...ev(r, [SRC.edgar(c), SRC.site(c)]),
    })),
    signals: Array.from({ length: int(r, 4, 8) }, () => {
      const type = pick(r, SIGNAL_TYPES);
      return {
        type,
        observation: pick(r, SIGNAL_TEXT[type]),
        date: ago(1, 60),
        readsAs: pick(r, ['supports', 'supports', 'contradicts', 'neutral'] as const),
        ...ev(r, [type === 'hiring' || type === 'pricing' ? SRC.archive(c) : SRC.news(c), SRC.site(c)], -0.05),
      };
    }),
    risks: Array.from({ length: int(r, 2, 4) }, () => {
      const [risk, category] = pick(r, RISKS);
      return { risk, category, severity: pick(r, ['high', 'medium', 'medium', 'low'] as const), evidence: ev(r, [SRC.edgar(c)]) };
    }),
  };

  const observations = CHANNEL_MEASURES.filter(() => r() > 0.35).map(([measure, type, unit]) => {
    const RANGE: Record<string, [number, number]> = { roles: [20, 600], 'USD/mo': [20, 250], '%': [5, 30], listings: [10, 140], weeks: [6, 30], permits: [1, 12], incidents: [1, 18] };
    const [lo, hi] = RANGE[unit] ?? [5, 100];
    const prior = int(r, lo, hi);
    const value = Math.max(0, Math.round(prior * (0.7 + r() * 0.7)));
    const up = value >= prior;
    const goodWhenUp = !['Promo depth', 'Distributor lead time', 'Status page incidents'].includes(measure);
    return {
      measure,
      type,
      value,
      prior,
      unit,
      readsAs: value === prior ? ('neutral' as const) : up === goodWhenUp ? ('supports' as const) : ('contradicts' as const),
      observedDate: ago(0, 3),
      ...ev(r, [SRC.site(c), SRC.archive(c)], 0.05),
    };
  });
  const supports = observations.filter((o) => o.readsAs === 'supports').length;
  const contradicts = observations.filter((o) => o.readsAs === 'contradicts').length;

  const filings = Array.from({ length: int(r, 2, 6) }, () => {
    const area = pick(r, FILING_AREAS);
    const form = pick(r, ['10-Q', '10-Q', '10-K']);
    return {
      area,
      changeType: pick(r, ['added', 'modified', 'modified', 'removed'] as const),
      relevance: pick(r, ['high', 'medium', 'medium', 'low'] as const),
      summary: pick(r, FILING_TEXT[area]),
      form,
      filedDate: ago(5, 40),
      ...ev(r, [SRC.edgar(c, form)], 0.15),
    };
  });

  const flags = FORENSIC.filter(() => r() > 0.86).map(([category, finding]) => ({
    category,
    severity: pick(r, ['high', 'medium', 'medium', 'low', 'low', 'low'] as const),
    status: pick(r, ['open', 'resolved', 'resolved', 'disputed'] as const),
    finding,
    date: ago(10, 400),
    ...ev(r, [category === 'auditor_change' ? SRC.pcaob() : category === 'short_report' ? SRC.news(c) : SRC.edgar(c, '8-K')], 0.05),
  }));
  const openHigh = flags.filter((f) => f.severity === 'high' && f.status !== 'resolved').length;
  const overallRisk = openHigh > 0 ? 'high' : flags.filter((f) => f.status !== 'resolved').length > 1 ? 'medium' : 'low';

  const commitments = Array.from({ length: int(r, 4, 8) }, () => ({
    commitment: pick(r, COMMITMENTS),
    outcome: pick(r, ['met', 'met', 'exceeded', 'missed', 'partially_met', 'withdrawn', 'pending'] as const),
    madeDate: ago(60, 900),
    ...ev(r, [SRC.edgar(c, '8-K')], 0.1),
  }));
  const met = commitments.filter((x) => x.outcome === 'met' || x.outcome === 'exceeded').length;
  const missed = commitments.filter((x) => x.outcome === 'missed' || x.outcome === 'withdrawn').length;
  const management = {
    pattern: met >= missed * 3 ? 'delivers' : missed > met ? 'overpromises' : r() > 0.7 ? 'sandbags' : 'mixed',
    commitments,
    leadershipChanges: Array.from({ length: int(r, 0, 3) }, () => ({
      date: ago(5, 500),
      person: pick(r, PEOPLE),
      role: pick(r, ROLES),
      change: pick(r, ['appointed', 'departed', 'retired', 'interim']),
      ...ev(r, [SRC.edgar(c, '8-K')], 0.2),
    })),
    insiderTrades: Array.from({ length: int(r, 1, 6) }, () => {
      const transaction = pick(r, ['open_market_buy', 'open_market_sell', 'planned_10b5_1_sale', 'planned_10b5_1_sale', 'option_exercise']);
      return {
        date: ago(1, 180),
        insider: `${pick(r, PEOPLE)}, ${pick(r, ROLES)}`,
        transaction,
        valueUsd: int(r, 2, 400) * 50_000,
        ...ev(r, [SRC.edgar(c, '4')], 0.25),
      };
    }),
  } as CompanyRecord['management'];

  const catalysts = CATALYSTS.filter(([type]) => type === 'earnings' || r() > 0.55).map(([type, description, certainty], i) => {
    const date = type === 'earnings' ? ahead(3, 85) : ahead(5, 330);
    return {
      key: `${type}_${i}`,
      type,
      date: certainty === 'company_guided' ? null : date,
      dateText: certainty === 'company_guided' ? `${date.slice(0, 4)}-H${Number(date.slice(5, 7)) > 6 ? 2 : 1}` : date,
      certainty,
      description,
      ...ev(r, [type === 'court_date' ? SRC.courts(c) : SRC.site(c)], certainty === 'confirmed' ? 0.25 : -0.1),
    };
  });

  const supplyChain = (COUNTERPARTIES[c.sector] ?? COUNTERPARTIES['AI software']).filter(([name]) => name !== c.name && r() > 0.4).map(([counterparty, t, relationship, whatFlows]) => ({
    counterparty,
    counterpartyTicker: t,
    relationship,
    whatFlows,
    revenueSharePct: relationship === 'customer' && r() > 0.6 ? int(r, 10, 28) : null,
    evidenceType: pick(r, ['company_filing', 'counterparty_filing', 'press_release', 'case_study', 'import_record', 'trade_press']),
    status: pick(r, ['active', 'active', 'active', 'announced', 'ended'] as const),
    ...ev(r, [SRC.edgar(c), SRC.news(c)]),
  }));

  const rivals = RIVALS[c.sector] ?? RIVALS['AI software'];
  const competitors = Array.from({ length: int(r, 4, 12) }, () => {
    const type = pick(r, COMP_TYPES);
    return {
      competitor: pick(r, rivals),
      competitorStatus: 'private',
      type,
      observation: COMP_TEXT[type],
      date: ago(1, 120),
      threat: pick(r, ['rising', 'rising', 'neutral', 'falling', 'cannot_verify'] as const),
      ...ev(r, [SRC.news(c)], -0.1),
    };
  });

  const govCount = GOV_HEAVY.has(c.ticker) ? int(r, 4, 12) : r() > 0.6 ? int(r, 1, 3) : 0;
  const gov = Array.from({ length: govCount }, (_, i) => {
    const ceiling = (GOV_HEAVY.has(c.ticker) ? int(r, 5, 900) : int(r, 1, 40)) * 1_000_000;
    const type = pick(r, ['idiq', 'task_order', 'task_order', 'definitive_contract', 'ota', 'protest']);
    return {
      awardId: `${pick(r, ['W', 'FA', 'N', 'HS', '70', '80'])}${int(r, 10000, 99999)}-26-${type === 'protest' ? 'B' : 'C'}-${String(i).padStart(4, '0')}`,
      agency: pick(r, AGENCIES),
      type,
      actionDate: ago(1, 300),
      obligatedUsd: type === 'protest' ? null : Math.round(ceiling * (0.05 + r() * 0.6)),
      ceilingUsd: type === 'protest' ? null : ceiling,
      status: type === 'protest' ? pick(r, ['protested', 'protest_denied', 'protest_sustained']) : pick(r, ['awarded', 'awarded', 'modified', 'recompete_pending']),
      ...ev(r, [type === 'protest' ? SRC.gao() : SRC.usaspending()], 0.3),
    };
  });

  return {
    company: c,
    updatedAt,
    deepDive,
    channel: {
      question: `Is ${c.name}'s demand accelerating since last quarter?`,
      answer: supports > contradicts + 1 ? 'yes' : contradicts > supports + 1 ? 'no' : 'mixed',
      answerConfidence: conf(r),
      observations,
    },
    filings,
    forensic: { overallRisk, flags },
    management,
    catalysts,
    supplyChain,
    competitors,
    gov,
  };
}

function changesFor(rec: CompanyRecord, now: Date): ChangeEvent[] {
  const r = rng(`${rec.company.ticker}:changes`);
  const out: ChangeEvent[] = [];
  const t = rec.company.ticker;
  const push = (agent: AgentKey, headline: string, direction: Direction, magnitude: 1 | 2 | 3, e: Evidence, date = day(-int(r, 0, 29), now)) =>
    out.push({ id: `${t}-${agent}-${out.length}`, date, ticker: t, agent, headline, direction, magnitude, confidence: e.confidence, citations: e.citations });

  for (const f of rec.forensic?.flags ?? []) {
    if (f.status !== 'resolved' && r() > 0.4) push('forensic', f.finding, 'bearish', f.severity === 'high' ? 3 : 2, f);
  }
  for (const f of rec.filings.filter((x) => x.relevance !== 'low').slice(0, 2)) push('filings', f.summary, pick(r, ['bearish', 'neutral', 'bullish'] as const), f.relevance === 'high' ? 2 : 1, f, f.filedDate);
  for (const o of rec.channel?.observations.filter((x) => x.readsAs !== 'neutral').slice(0, 2) ?? []) {
    const pct = o.prior ? Math.round(((o.value ?? 0) / o.prior - 1) * 100) : 0;
    push('channel', `${o.measure} ${pct >= 0 ? '+' : ''}${pct}%`, o.readsAs === 'supports' ? 'bullish' : 'bearish', Math.abs(pct) > 25 ? 2 : 1, o, o.observedDate);
  }
  for (const s of rec.competitors.filter((x) => x.threat === 'rising').slice(0, 2)) push('competitors', `${s.competitor}: ${s.observation.toLowerCase()}`, 'bearish', 1, s, s.date);
  for (const g of rec.gov.filter((x) => (x.obligatedUsd ?? 0) > 50_000_000).slice(0, 2))
    push('gov', `${g.agency.split(' · ').pop()} award, $${Math.round((g.obligatedUsd ?? 0) / 1e6)}M obligated`, 'bullish', 2, g, g.actionDate);
  for (const l of rec.management?.leadershipChanges.filter((x) => x.change === 'departed').slice(0, 1) ?? []) push('management', `${l.role} departed`, 'bearish', 2, l);
  for (const k of rec.catalysts.filter((x) => x.certainty === 'confirmed' && x.type !== 'earnings').slice(0, 1)) push('catalysts', `${k.description} set for ${k.dateText}`, 'neutral', 1, k);
  for (const s of rec.deepDive?.signals.filter((x) => x.readsAs !== 'neutral').slice(0, 1) ?? []) push('deepDive', s.observation, s.readsAs === 'supports' ? 'bullish' : 'bearish', 1, s, s.date ?? undefined);
  for (const tr of rec.management?.insiderTrades.filter((x) => x.transaction === 'open_market_buy').slice(0, 1) ?? [])
    push('management', `Insider open-market buy, $${((tr.valueUsd ?? 0) / 1e6).toFixed(1)}M`, 'bullish', 2, tr, tr.date);
  return out;
}

export function sampleSnapshot(now = new Date()): Snapshot {
  const records = COMPANIES.map((c) => record(c, now));
  const changes = records.flatMap((rec) => changesFor(rec, now)).sort((a, b) => b.date.localeCompare(a.date));
  return { generatedAt: now.toISOString(), source: 'sample', records, changes };
}
