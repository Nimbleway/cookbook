'use client';

import { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart2 } from 'lucide-react';
import type { PriceData } from '@/types/earnings';

interface PriceChartProps {
  priceData: PriceData;
  ticker: string;
}

const PERIODS = ['6M', '1Y', '2Y'] as const;
type Period = typeof PERIODS[number];

function filterByPeriod(prices: PriceData['prices'], period: Period) {
  const now = new Date();
  const cutoff = new Date(now);
  if (period === '6M') cutoff.setMonth(now.getMonth() - 6);
  else if (period === '1Y') cutoff.setFullYear(now.getFullYear() - 1);
  else cutoff.setFullYear(now.getFullYear() - 2);
  return prices.filter(p => new Date(p.date) >= cutoff);
}

interface TooltipPayloadItem {
  value: number;
}

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayloadItem[]; label?: string }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 shadow-xl">
      <p className="text-slate-400 text-xs mb-1">{label}</p>
      <p className="text-white font-semibold">${payload[0]?.value?.toFixed(2)}</p>
    </div>
  );
}

export default function PriceChart({ priceData, ticker }: PriceChartProps) {
  const [period, setPeriod] = useState<Period>('1Y');

  const filteredPrices = useMemo(
    () => filterByPeriod(priceData.prices, period),
    [priceData.prices, period]
  );

  const earningsDatesInRange = useMemo(
    () => priceData.earningsDates.filter(d => {
      const date = new Date(d);
      const now = new Date();
      const cutoff = new Date(now);
      if (period === '6M') cutoff.setMonth(now.getMonth() - 6);
      else if (period === '1Y') cutoff.setFullYear(now.getFullYear() - 1);
      else cutoff.setFullYear(now.getFullYear() - 2);
      return date >= cutoff && date <= now;
    }),
    [priceData.earningsDates, period]
  );

  const minClose = useMemo(
    () => Math.min(...filteredPrices.map(p => p.close)) * 0.95,
    [filteredPrices]
  );
  const maxClose = useMemo(
    () => Math.max(...filteredPrices.map(p => p.close)) * 1.05,
    [filteredPrices]
  );

  // Snap each earnings date to the nearest available trading day in filteredPrices
  const snappedEarningsDates = useMemo(() => {
    const dates = filteredPrices.map(p => p.date);
    return earningsDatesInRange.map(ed => {
      // Find the closest date in the price data
      let closest = dates[0];
      let minDiff = Infinity;
      for (const d of dates) {
        const diff = Math.abs(new Date(d).getTime() - new Date(ed).getTime());
        if (diff < minDiff) { minDiff = diff; closest = d; }
      }
      return closest;
    }).filter(Boolean);
  }, [filteredPrices, earningsDatesInRange]);

  // Downsample for performance but always keep earnings date points
  const chartData = useMemo(() => {
    if (filteredPrices.length <= 200) return filteredPrices;
    const keepDates = new Set(snappedEarningsDates);
    const step = Math.ceil(filteredPrices.length / 200);
    return filteredPrices.filter((p, i) =>
      i % step === 0 || i === filteredPrices.length - 1 || keepDates.has(p.date)
    );
  }, [filteredPrices, snappedEarningsDates]);

  const currentPrice = priceData.prices[priceData.prices.length - 1]?.close;
  const startPrice = filteredPrices[0]?.close;
  const priceChange = currentPrice && startPrice ? ((currentPrice - startPrice) / startPrice) * 100 : null;

  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-blue-400" />
            <CardTitle className="text-slate-100 text-base font-semibold">
              {ticker} Price History
            </CardTitle>
            {priceChange !== null && (
              <span className={`text-sm font-semibold ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(1)}%
              </span>
            )}
          </div>
          <div className="flex gap-1">
            {PERIODS.map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  period === p
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-white'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 bg-blue-400" />
            <span>Stock Price</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-0.5 h-3 bg-yellow-400/70" />
            <span>Earnings Date</span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: string) => {
                  const d = new Date(v);
                  return `${d.toLocaleString('default', { month: 'short' })} '${String(d.getFullYear()).slice(2)}`;
                }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                domain={[minClose, maxClose]}
                width={55}
              />
              <Tooltip content={<CustomTooltip />} />
              {snappedEarningsDates.map(date => (
                <ReferenceLine
                  key={date}
                  x={date}
                  stroke="#fbbf24"
                  strokeDasharray="4 4"
                  strokeOpacity={0.7}
                  label={{ value: 'E', position: 'top', fill: '#fbbf24', fontSize: 10 }}
                />
              ))}
              <Line
                type="monotone"
                dataKey="close"
                stroke="#60a5fa"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#60a5fa', stroke: '#1e40af' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        {(priceData as PriceData & { _fallback?: boolean })._fallback && (
          <p className="text-slate-600 text-xs text-center mt-2">* Showing estimated price data</p>
        )}
      </CardContent>
    </Card>
  );
}
