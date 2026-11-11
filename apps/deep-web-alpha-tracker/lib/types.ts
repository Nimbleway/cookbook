export type Confidence = 'high' | 'medium' | 'low';
export type Effort = 'low' | 'medium' | 'high' | 'x-high';

export type AgentKey =
  | 'deepDive'
  | 'channel'
  | 'filings'
  | 'forensic'
  | 'management'
  | 'catalysts'
  | 'supplyChain'
  | 'competitors'
  | 'gov';

export interface Citation {
  url: string;
  title: string;
  sourceType: 'primary' | 'secondary' | 'tertiary' | 'unknown';
}

/** Every row the UI shows carries a confidence grade and the pages behind it. */
export interface Evidence {
  confidence: Confidence;
  citations: Citation[];
}

export interface Company {
  ticker: string;
  name: string;
  domain: string;
  sector: string;
}

export type Direction = 'bullish' | 'bearish' | 'neutral';

export interface MoatFactor extends Evidence {
  factor: string;
  direction: 'strengthening' | 'weakening' | 'stable' | 'cannot_verify';
}

export interface AlphaSignal extends Evidence {
  type: string;
  observation: string;
  date: string | null;
  readsAs: 'supports' | 'contradicts' | 'neutral';
}

export interface DeepDive {
  moat: MoatFactor[];
  signals: AlphaSignal[];
  risks: { risk: string; category: string; severity: 'high' | 'medium' | 'low'; evidence: Evidence }[];
}

export interface ChannelObservation extends Evidence {
  measure: string;
  type: 'pricing_offer' | 'footprint' | 'supply' | 'hiring' | 'customer' | 'public_record';
  value: number | null;
  prior: number | null;
  unit: string | null;
  readsAs: 'supports' | 'contradicts' | 'neutral';
  observedDate: string;
}

export interface ChannelCheck {
  question: string;
  answer: 'yes' | 'no' | 'mixed' | 'insufficient';
  answerConfidence: Confidence;
  observations: ChannelObservation[];
}

export interface FilingChange extends Evidence {
  area: string;
  changeType: 'added' | 'removed' | 'modified';
  relevance: 'high' | 'medium' | 'low';
  summary: string;
  form: string;
  filedDate: string;
}

export interface ForensicFlag extends Evidence {
  category: string;
  severity: 'high' | 'medium' | 'low';
  status: 'open' | 'resolved' | 'disputed' | 'cannot_verify';
  finding: string;
  date: string | null;
}

export interface Forensic {
  overallRisk: 'low' | 'medium' | 'high';
  flags: ForensicFlag[];
}

export type CommitmentOutcome = 'met' | 'exceeded' | 'missed' | 'partially_met' | 'withdrawn' | 'pending' | 'cannot_verify';

export interface Management {
  pattern: 'delivers' | 'sandbags' | 'overpromises' | 'mixed' | 'too_early';
  commitments: ({ commitment: string; outcome: CommitmentOutcome; madeDate: string } & Evidence)[];
  leadershipChanges: ({ date: string; person: string; role: string; change: string } & Evidence)[];
  insiderTrades: ({ date: string; insider: string; transaction: string; valueUsd: number | null } & Evidence)[];
}

export interface Catalyst extends Evidence {
  key: string;
  type: string;
  date: string | null;
  dateText: string;
  certainty: 'confirmed' | 'company_guided' | 'statutory' | 'estimated';
  description: string;
}

export interface Relationship extends Evidence {
  counterparty: string;
  counterpartyTicker: string | null;
  relationship: string;
  whatFlows: string;
  revenueSharePct: number | null;
  evidenceType: string;
  status: 'active' | 'ended' | 'announced' | 'cannot_verify';
}

export interface CompetitorSignal extends Evidence {
  competitor: string;
  competitorStatus: string;
  type: string;
  observation: string;
  date: string;
  threat: 'rising' | 'falling' | 'neutral' | 'cannot_verify';
}

export interface GovAward extends Evidence {
  awardId: string;
  agency: string;
  type: string;
  actionDate: string;
  obligatedUsd: number | null;
  ceilingUsd: number | null;
  status: string;
}

export interface CompanyRecord {
  company: Company;
  updatedAt: Record<AgentKey, string | null>;
  deepDive: DeepDive | null;
  channel: ChannelCheck | null;
  filings: FilingChange[];
  forensic: Forensic | null;
  management: Management | null;
  catalysts: Catalyst[];
  supplyChain: Relationship[];
  competitors: CompetitorSignal[];
  gov: GovAward[];
}

export interface ChangeEvent extends Evidence {
  id: string;
  date: string;
  ticker: string;
  agent: AgentKey;
  headline: string;
  direction: Direction;
  magnitude: 1 | 2 | 3;
}

export interface Snapshot {
  generatedAt: string;
  source: 'sample' | 'live';
  records: CompanyRecord[];
  changes: ChangeEvent[];
}

export interface RunJob {
  ticker: string;
  agent: AgentKey;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  runId?: string;
  agentId?: string;
  error?: string;
}

export interface RefreshLedger {
  id: string;
  effort: Effort;
  startedAt: string;
  finishedAt: string | null;
  jobs: RunJob[];
}
