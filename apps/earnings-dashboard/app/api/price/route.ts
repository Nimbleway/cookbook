import { NextRequest, NextResponse } from 'next/server';
import { getPriceData } from '@/lib/price';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker')?.toUpperCase();
  const period = searchParams.get('period') || '2y';

  if (!ticker) {
    return NextResponse.json({ error: 'Ticker is required' }, { status: 400 });
  }

  const data = await getPriceData(ticker, period);
  return NextResponse.json(data);
}
