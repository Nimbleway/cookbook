export interface UpcomingEarnings {
  ticker: string;
  date: string | null;
  quarter: string | null;
  error?: string;
}

export async function getUpcomingEarnings(tickers: string[]): Promise<UpcomingEarnings[]> {
  const NIMBLE_API_KEY = process.env.NIMBLE_API_KEY;

  if (!NIMBLE_API_KEY) {
    return tickers.map(ticker => ({ ticker, date: null, quarter: null }));
  }

  return Promise.all(tickers.map(ticker => fetchUpcomingForTicker(ticker, NIMBLE_API_KEY)));
}

async function fetchUpcomingForTicker(ticker: string, apiKey: string): Promise<UpcomingEarnings> {
  try {
    const searchRes = await fetch('https://api.nimbleway.com/v1/realtime/serp', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: `${ticker} earnings date 2025 when next earnings`,
        search_engine: 'google_search',
        num_results: 3,
        country: 'US',
      }),
    });

    if (!searchRes.ok) {
      return { ticker, date: null, quarter: null };
    }

    const searchData = await searchRes.json();
    const snippets = searchData.organic_results?.map((r: { snippet?: string; title?: string }) => `${r.title ?? ''} ${r.snippet ?? ''}`).join('\n') ?? '';

    // Parse date from snippets
    const dateMatch = snippets.match(/(\w+ \d{1,2},?\s*202[5-9])/i);
    const quarterMatch = snippets.match(/Q[1-4]\s*202[5-9]/i);

    return {
      ticker,
      date: dateMatch ? new Date(dateMatch[1]).toISOString().split('T')[0] : null,
      quarter: quarterMatch ? quarterMatch[0] : null,
    };
  } catch {
    return { ticker, date: null, quarter: null };
  }
}
