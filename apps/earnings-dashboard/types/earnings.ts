export interface EarningsMetrics {
  eps: {
    actual: number | null;
    estimate: number | null;
    beat: boolean | null;
  };
  revenue: {
    actual: number | null;
    estimate: number | null;
    beat: boolean | null;
  };
  guidance: {
    raised: boolean | null;
    details: string;
  };
  date: string;
  quarter: string;
}

export interface ChangeItem {
  type: 'positive' | 'negative' | 'neutral';
  text: string;
}

export interface AnalystReaction {
  source: string;
  headline: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  url: string;
  date: string;
  excerpt: string;
}

export interface SentimentBreakdown {
  bullish: number;
  neutral: number;
  bearish: number;
  overall: 'bullish' | 'neutral' | 'bearish';
}

export interface SurpriseHistoryItem {
  quarter: string;
  epsSurprise: number;
  revenueSurprise: number;
}

export interface GuidanceHistoryItem {
  quarter: string;
  guidedEps: number | null;
  actualEps: number | null;
  guidedRevenue: number | null;
  actualRevenue: number | null;
}

export interface MarginMetric {
  current: number;
  prior: number;
}

export interface KeyMetrics {
  grossMargin: MarginMetric;
  operatingMargin: MarginMetric;
  freeCashFlow: MarginMetric;
}

export interface TranscriptHighlight {
  speaker: string;
  quote: string;
  sentiment: 'positive' | 'negative' | 'neutral';
}

export interface EarningsData {
  ticker: string;
  companyName: string;
  latestEarnings: EarningsMetrics;
  previousEarnings: EarningsMetrics;
  changes: ChangeItem[];
  analystReactions: AnalystReaction[];
  sentiment: SentimentBreakdown;
  summary: string;
  surpriseHistory?: SurpriseHistoryItem[];
  guidanceHistory?: GuidanceHistoryItem[];
  keyMetrics?: KeyMetrics;
  transcriptHighlights?: TranscriptHighlight[];
  bullCase?: string;
  bearCase?: string;
  error?: string;
}

export interface PricePoint {
  date: string;
  close: number;
  isEarningsDate?: boolean;
  earningsSummary?: string;
}

export interface PriceData {
  ticker: string;
  prices: PricePoint[];
  earningsDates: string[];
  error?: string;
}
