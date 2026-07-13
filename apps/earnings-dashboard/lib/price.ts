import type { PriceData, PricePoint } from '@/types/earnings';

const YAHOO_BASE = 'https://query1.finance.yahoo.com/v8/finance/chart';

function periodToRange(period: string): { range: string; interval: string } {
  switch (period) {
    case '6m': return { range: '6mo', interval: '1d' };
    case '1y': return { range: '1y', interval: '1d' };
    case '2y':
    default:   return { range: '2y', interval: '1d' };
  }
}

export async function getPriceData(ticker: string, period = '2y'): Promise<PriceData> {
  const { range, interval } = periodToRange(period);
  const url = `${YAHOO_BASE}/${encodeURIComponent(ticker)}?range=${range}&interval=${interval}&includePrePost=false&events=div%2Csplits`;

  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      next: { revalidate: 3600 },
    });

    if (!res.ok) {
      return { ticker, prices: [], earningsDates: [], error: `Yahoo Finance returned ${res.status}` };
    }

    const json = await res.json();
    const chart = json?.chart?.result?.[0];
    if (!chart) {
      return { ticker, prices: [], earningsDates: [], error: 'No data from Yahoo Finance' };
    }

    const timestamps: number[] = chart.timestamp ?? [];
    const closes: number[] = chart.indicators?.quote?.[0]?.close ?? [];

    const prices: PricePoint[] = timestamps
      .map((ts, i) => ({
        date: new Date(ts * 1000).toISOString().split('T')[0],
        close: closes[i] ?? null,
      }))
      .filter((p): p is PricePoint => p.close !== null && !isNaN(p.close));

    // Earnings dates come from Nimble search separately — return empty for now
    // (the earnings API route provides them when aggregating full data)
    const earningsDates: string[] = [];

    return { ticker, prices, earningsDates };
  } catch (err) {
    return { ticker, prices: [], earningsDates: [], error: String(err) };
  }
}
