import { NextRequest, NextResponse } from 'next/server';
import { getEarningsData } from '@/lib/earnings';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker')?.toUpperCase();

  if (!ticker) {
    return NextResponse.json({ error: 'Ticker is required' }, { status: 400 });
  }

  const data = await getEarningsData(ticker);
  return NextResponse.json(data);
}
