import Anthropic from '@anthropic-ai/sdk';
import { cache } from 'react';
import type { EarningsData } from '@/types/earnings';

const NIMBLE_API_KEY = process.env.NIMBLE_API_KEY;
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;

async function nimbleSearch(query: string): Promise<Array<{ title: string; url: string; snippet: string }>> {
  if (!NIMBLE_API_KEY) return [];
  try {
    const res = await fetch('https://api.nimbleway.com/v1/realtime/serp', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${NIMBLE_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        search_engine: 'google_search',
        num_results: 5,
        country: 'US',
      }),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.organic_results ?? []).map((r: { title?: string; url?: string; snippet?: string }) => ({
      title: r.title ?? '',
      url: r.url ?? '',
      snippet: r.snippet ?? '',
    }));
  } catch {
    return [];
  }
}

async function nimbleExtract(url: string): Promise<string> {
  if (!NIMBLE_API_KEY) return '';
  try {
    const res = await fetch('https://api.nimbleway.com/v1/realtime/url', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${NIMBLE_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url,
        render: true,
        output_format: 'markdown',
      }),
    });
    if (!res.ok) return '';
    const data = await res.json();
    return data.content ?? data.markdown ?? '';
  } catch {
    return '';
  }
}

function getFallbackData(ticker: string): EarningsData {
  return {
    ticker,
    companyName: `${ticker} Corporation`,
    latestEarnings: {
      eps: { actual: null, estimate: null, beat: null },
      revenue: { actual: null, estimate: null, beat: null },
      guidance: { raised: null, details: 'No data available' },
      date: 'N/A',
      quarter: 'N/A',
    },
    previousEarnings: {
      eps: { actual: null, estimate: null, beat: null },
      revenue: { actual: null, estimate: null, beat: null },
      guidance: { raised: null, details: 'No data available' },
      date: 'N/A',
      quarter: 'N/A',
    },
    changes: [{ type: 'neutral', text: 'No data available — check API keys' }],
    analystReactions: [],
    sentiment: { bullish: 34, neutral: 33, bearish: 33, overall: 'neutral' },
    summary: 'Could not load earnings data. Please ensure NIMBLE_API_KEY and ANTHROPIC_API_KEY are set.',
    _fallback: true,
  } as EarningsData & { _fallback: boolean };
}

async function fetchAndAnalyze(ticker: string): Promise<EarningsData> {
  // Step 1: Search for latest earnings transcript
  const [latestResults, priorResults, analystResults] = await Promise.all([
    nimbleSearch(`${ticker} earnings transcript Q4 2024 site:seekingalpha.com OR site:fool.com`),
    nimbleSearch(`${ticker} earnings transcript Q3 2024 site:seekingalpha.com OR site:fool.com`),
    nimbleSearch(`${ticker} earnings analyst reaction price target 2024`),
  ]);

  // Step 2: Extract content from top results
  const [latestContent, priorContent] = await Promise.all([
    latestResults[0]?.url ? nimbleExtract(latestResults[0].url) : Promise.resolve(''),
    priorResults[0]?.url ? nimbleExtract(priorResults[0].url) : Promise.resolve(''),
  ]);

  if (!ANTHROPIC_API_KEY) {
    return getFallbackData(ticker);
  }

  // Step 3: Claude analysis
  const client = new Anthropic({ apiKey: ANTHROPIC_API_KEY });

  const analystSnippets = analystResults
    .slice(0, 3)
    .map(r => `${r.title}: ${r.snippet}`)
    .join('\n');

  const prompt = `You are a financial analyst. Analyze the following earnings information for ${ticker} and return a JSON object matching the schema exactly.

Latest earnings content:
${latestContent.slice(0, 4000) || 'Not available'}

Prior quarter content:
${priorContent.slice(0, 2000) || 'Not available'}

Analyst reactions:
${analystSnippets || 'Not available'}

Return ONLY valid JSON with this exact structure (no markdown, no explanation):
{
  "ticker": "${ticker}",
  "companyName": "Full company name",
  "latestEarnings": {
    "eps": { "actual": number_or_null, "estimate": number_or_null, "beat": boolean_or_null },
    "revenue": { "actual": number_in_billions_or_null, "estimate": number_in_billions_or_null, "beat": boolean_or_null },
    "guidance": { "raised": boolean_or_null, "details": "string" },
    "date": "YYYY-MM-DD",
    "quarter": "Q4 2024"
  },
  "previousEarnings": {
    "eps": { "actual": number_or_null, "estimate": number_or_null, "beat": boolean_or_null },
    "revenue": { "actual": number_in_billions_or_null, "estimate": number_in_billions_or_null, "beat": boolean_or_null },
    "guidance": { "raised": boolean_or_null, "details": "string" },
    "date": "YYYY-MM-DD",
    "quarter": "Q3 2024"
  },
  "changes": [
    { "type": "positive|negative|neutral", "text": "bullet point" }
  ],
  "analystReactions": [
    { "source": "string", "headline": "string", "sentiment": "bullish|bearish|neutral", "url": "string", "date": "YYYY-MM-DD", "excerpt": "string" }
  ],
  "sentiment": { "bullish": number_0_100, "neutral": number_0_100, "bearish": number_0_100, "overall": "bullish|neutral|bearish" },
  "summary": "2-3 sentence summary",
  "surpriseHistory": [
    { "quarter": "Q4 2024", "epsSurprise": number_percent, "revenueSurprise": number_percent }
  ],
  "guidanceHistory": [
    { "quarter": "Q4 2024", "guidedEps": number_or_null, "actualEps": number_or_null, "guidedRevenue": number_or_null, "actualRevenue": number_or_null }
  ],
  "keyMetrics": {
    "grossMargin": { "current": number_percent, "prior": number_percent },
    "operatingMargin": { "current": number_percent, "prior": number_percent },
    "freeCashFlow": { "current": number_billions, "prior": number_billions }
  },
  "transcriptHighlights": [
    { "speaker": "string", "quote": "string", "sentiment": "positive|negative|neutral" }
  ],
  "bullCase": "paragraph",
  "bearCase": "paragraph"
}`;

  try {
    const response = await client.messages.create({
      model: 'claude-opus-4-5',
      max_tokens: 4096,
      messages: [{ role: 'user', content: prompt }],
    });

    const text = response.content[0].type === 'text' ? response.content[0].text : '';
    const parsed = JSON.parse(text) as EarningsData;
    return parsed;
  } catch {
    return getFallbackData(ticker);
  }
}

// Use React's cache() to deduplicate calls within the same request
// (generateMetadata and the page component both call this)
export const getEarningsData = cache(fetchAndAnalyze);
