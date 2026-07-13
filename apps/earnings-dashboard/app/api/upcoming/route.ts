import { NextRequest, NextResponse } from 'next/server';
import { getUpcomingEarnings } from '@/lib/upcoming';

const TICKER_RE = /^[A-Z]{1,5}$/;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const tickersParam = searchParams.get('tickers');

  if (!tickersParam) {
    return NextResponse.json({ error: 'tickers param required' }, { status: 400 });
  }

  const tickers = tickersParam
    .split(',')
    .map(t => t.trim().toUpperCase())
    .filter(t => TICKER_RE.test(t))
    .slice(0, 20);

  if (tickers.length === 0) {
    return NextResponse.json({ error: 'No valid tickers provided' }, { status: 400 });
  }

  try {
    const data = await getUpcomingEarnings(tickers);
    return NextResponse.json(data);
  } catch (err) {
    console.error('[api/upcoming] error:', err);
    return NextResponse.json({ error: 'Failed to fetch upcoming earnings' }, { status: 502 });
  }
}
