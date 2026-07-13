import { NextRequest, NextResponse } from 'next/server';
import { getEarningsData } from '@/lib/earnings';

const TICKER_RE = /^[A-Z]{1,5}$/;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker')?.toUpperCase();

  if (!ticker || !TICKER_RE.test(ticker)) {
    return NextResponse.json({ error: 'Valid ticker (1-5 letters) is required' }, { status: 400 });
  }

  try {
    const data = await getEarningsData(ticker);
    return NextResponse.json(data);
  } catch (err) {
    console.error('[api/earnings] error:', err);
    return NextResponse.json({ error: 'Failed to fetch earnings data' }, { status: 502 });
  }
}
