import { NextRequest, NextResponse } from 'next/server';
import { getUpcomingEarnings } from '@/lib/upcoming';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const tickersParam = searchParams.get('tickers');

  if (!tickersParam) {
    return NextResponse.json({ error: 'tickers param required' }, { status: 400 });
  }

  const tickers = tickersParam.split(',').map(t => t.trim().toUpperCase()).filter(Boolean).slice(0, 20);
  const data = await getUpcomingEarnings(tickers);
  return NextResponse.json(data);
}
