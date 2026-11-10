import type { AgentKey, Company, CompanyRecord } from './types';
import { evidenceFor, type RawClaim } from './trust';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Row = Record<string, any>;

export interface AgentDef {
  key: AgentKey;
  label: string;
  short: string;
  /** Gallery template the agent was created from (agent_name gallery-<template>). */
  template: string;
  envVar: string;
  prompt: (company: Company, since: string) => string;
  /** Maps a completed run's output to the part of the company record this agent owns. */
  map: (content: any, claims: RawClaim[]) => Partial<CompanyRecord>;
}

const rows = (value: unknown): Row[] => (Array.isArray(value) ? value : []);
const tag = (c: Company) => `${c.name} (${c.ticker}, ${c.domain})`;

export const AGENTS: AgentDef[] = [
  {
    key: 'deepDive',
    label: 'Fundamental deep dive',
    short: 'Deep dive',
    template: 'hf-fundamental-deep-dive',
    envVar: 'NIMBLE_AGENT_DEEP_DIVE',
    prompt: (c) => `Do a fundamental deep dive on ${tag(c)} for a long/short technology fund.`,
    map: (content, claims) => ({
      deepDive: {
        moat: rows(content?.moat_and_competition).map((r, i) => ({
          factor: r.factor,
          direction: r.direction,
          ...evidenceFor(claims, `$.moat_and_competition[${i}]`, r.source_url),
        })),
        signals: rows(content?.alpha_signals).map((r, i) => ({
          type: r.signal_type,
          observation: r.observation,
          date: r.date ?? null,
          readsAs: r.reads_as,
          ...evidenceFor(claims, `$.alpha_signals[${i}]`, r.source_url),
        })),
        risks: rows(content?.risks).map((r, i) => ({
          risk: r.risk,
          category: r.category,
          severity: r.severity,
          evidence: evidenceFor(claims, `$.risks[${i}]`, r.source_url),
        })),
      },
    }),
  },
  {
    key: 'channel',
    label: 'Channel check',
    short: 'Channel',
    template: 'hf-channel-check',
    envVar: 'NIMBLE_AGENT_CHANNEL_CHECK',
    prompt: (c, since) =>
      `Channel check on ${c.name} (${c.ticker}): is demand accelerating across hiring, pricing, product availability and customer activity since ${since}?`,
    map: (content, claims) => ({
      channel: {
        question: content?.question?.restated ?? '',
        answer: content?.answer?.evidence_direction ?? 'insufficient',
        answerConfidence: content?.answer?.confidence ?? 'low',
        observations: rows(content?.observations).map((r, i) => ({
          measure: r.measure,
          type: r.measure_type,
          value: r.value_number ?? null,
          prior: r.prior_value_number ?? null,
          unit: r.unit ?? null,
          readsAs: r.reads_as,
          observedDate: r.observed_date,
          ...evidenceFor(claims, `$.observations[${i}]`, r.source_url),
        })),
      },
    }),
  },
  {
    key: 'filings',
    label: 'Filing change detector',
    short: 'Filings',
    template: 'hf-filing-changes',
    envVar: 'NIMBLE_AGENT_FILING_CHANGES',
    prompt: (c) => `What changed in ${c.name}'s (${c.ticker}) latest 10-Q or 10-K compared with the prior comparable filing?`,
    map: (content, claims) => ({
      filings: rows(content?.changes).map((r, i) => ({
        area: r.area,
        changeType: r.change_type,
        relevance: r.alpha_relevance,
        summary: r.summary,
        form: content?.filing?.form_type ?? '',
        filedDate: content?.filing?.filed_date ?? '',
        ...evidenceFor(claims, `$.changes[${i}]`, r.source_url),
      })),
    }),
  },
  {
    key: 'forensic',
    label: 'Forensic red-flag screen',
    short: 'Forensic',
    template: 'hf-forensic-red-flags',
    envVar: 'NIMBLE_AGENT_FORENSIC',
    prompt: (c) => `Run a forensic red-flag screen on ${tag(c)}.`,
    map: (content, claims) => ({
      forensic: {
        overallRisk: content?.overall_risk ?? 'low',
        flags: rows(content?.red_flags).map((r, i) => ({
          category: r.category,
          severity: r.severity,
          status: r.status,
          finding: r.finding,
          date: r.date ?? null,
          ...evidenceFor(claims, `$.red_flags[${i}]`, r.source_url),
        })),
      },
    }),
  },
  {
    key: 'management',
    label: 'Management track record',
    short: 'Management',
    template: 'hf-management-track-record',
    envVar: 'NIMBLE_AGENT_MANAGEMENT',
    prompt: (c) => `Check management's track record at ${c.name} (${c.ticker}) over the last three years.`,
    map: (content, claims) => ({
      management: {
        pattern: content?.credibility_read?.pattern ?? 'too_early',
        commitments: rows(content?.commitments).map((r, i) => ({
          commitment: r.commitment,
          outcome: r.outcome,
          madeDate: r.made_date,
          ...evidenceFor(claims, `$.commitments[${i}]`, r.source_url),
        })),
        leadershipChanges: rows(content?.leadership_changes).map((r, i) => ({
          date: r.date,
          person: r.person,
          role: r.role,
          change: r.change,
          ...evidenceFor(claims, `$.leadership_changes[${i}]`, r.source_url),
        })),
        insiderTrades: rows(content?.insider_trades).map((r, i) => ({
          date: r.date,
          insider: r.insider,
          transaction: r.transaction,
          valueUsd: typeof r.shares === 'number' && typeof r.price === 'number' ? r.shares * r.price : null,
          ...evidenceFor(claims, `$.insider_trades[${i}]`, r.source_url),
        })),
      },
    }),
  },
  {
    key: 'catalysts',
    label: 'Catalyst calendar',
    short: 'Catalysts',
    template: 'hf-catalyst-calendar',
    envVar: 'NIMBLE_AGENT_CATALYSTS',
    prompt: (c) => `Build a catalyst calendar for ${c.name} (${c.ticker}) for the next 12 months.`,
    map: (content, claims) => ({
      catalysts: rows(content?.events).map((r, i) => ({
        key: r.key,
        type: r.event_type,
        date: r.expected_date ?? null,
        dateText: r.date_text,
        certainty: r.certainty,
        description: r.description,
        ...evidenceFor(claims, `$.events[${i}]`, r.source_url),
      })),
    }),
  },
  {
    key: 'supplyChain',
    label: 'Customer and supplier map',
    short: 'Supply chain',
    template: 'hf-customer-supplier-map',
    envVar: 'NIMBLE_AGENT_SUPPLY_CHAIN',
    prompt: (c) => `Map the key customers and suppliers of ${tag(c)}: up to 20 relationships, each with evidence.`,
    map: (content, claims) => ({
      supplyChain: rows(content).map((r, i) => ({
        counterparty: r.counterparty,
        counterpartyTicker: r.counterparty_ticker ?? null,
        relationship: r.relationship,
        whatFlows: r.what_flows,
        revenueSharePct: r.revenue_share_pct ?? null,
        evidenceType: r.evidence_type,
        status: r.status,
        ...evidenceFor(claims, `$[${i}]`, r.source_url),
      })),
    }),
  },
  {
    key: 'competitors',
    label: 'Competitor momentum scan',
    short: 'Competitors',
    template: 'hf-competitor-momentum',
    envVar: 'NIMBLE_AGENT_COMPETITORS',
    prompt: (c, since) =>
      `Which competitors, including private ones, are gaining ground on ${c.name} (${c.ticker}) since ${since}? Return up to 15 dated signals.`,
    map: (content, claims) => ({
      competitors: rows(content).map((r, i) => ({
        competitor: r.competitor,
        competitorStatus: r.competitor_status,
        type: r.signal_type,
        observation: r.observation,
        date: r.date,
        threat: r.threat_to_company,
        ...evidenceFor(claims, `$[${i}]`, r.source_url),
      })),
    }),
  },
  {
    key: 'gov',
    label: 'Government contract exposure',
    short: 'Gov contracts',
    template: 'hf-government-contracts',
    envVar: 'NIMBLE_AGENT_GOV_CONTRACTS',
    prompt: (c, since) =>
      `List federal contract awards, task orders and bid protests for ${c.name} (${c.ticker}) since ${since}, up to 20 rows.`,
    map: (content, claims) => ({
      gov: rows(content).map((r, i) => ({
        awardId: r.award_id,
        agency: r.agency,
        type: r.award_type,
        actionDate: r.action_date,
        obligatedUsd: r.obligated_usd ?? null,
        ceilingUsd: r.ceiling_usd ?? null,
        status: r.status,
        ...evidenceFor(claims, `$[${i}]`, r.source_url),
      })),
    }),
  },
];

export const AGENT_BY_KEY = Object.fromEntries(AGENTS.map((a) => [a.key, a])) as Record<AgentKey, AgentDef>;

export function agentId(agent: AgentDef): string | null {
  return process.env[agent.envVar]?.trim() || null;
}
