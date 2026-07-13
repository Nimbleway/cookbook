import { NextRequest, NextResponse } from 'next/server';
import { getPriceData } from '@/lib/price';

const TICKER_RE = /^[A-Z]{1,5}$/;
const ALLOWED_PERIODS = new Set(['6m', '1y', '2y']);

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker')?.toUpperCase();
  const period = searchParams.get('period') ?? '2y';

  if (!ticker || !TICKER_RE.test(ticker)) {
    return NextResponse.json({ error: 'Valid ticker (1-5 letters) is required' }, { status: 400 });
  }
  if (!ALLOWED_PERIODS.has(period)) {
    return NextResponse.json({ error: `period must be one of: ${[...ALLOWED_PERIODS].join(', ')}` }, { status: 400 });
  }

  try {
    const data = await getPriceData(ticker, period);
    return NextResponse.json(data);
  } catch (err) {
    console.error('[api/price] error:', err);
    return NextResponse.json({ error: 'Failed to fetch price data' }, { status: 502 });
  }
}
