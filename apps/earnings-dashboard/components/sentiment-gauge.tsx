'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Minus, Users } from 'lucide-react';
import type { SentimentBreakdown } from '@/types/earnings';

interface SentimentGaugeProps {
  sentiment: SentimentBreakdown;
}

export default function SentimentGauge({ sentiment }: SentimentGaugeProps) {
  const overallConfig = {
    bullish: { color: 'text-green-400', bg: 'bg-green-400', Icon: TrendingUp, label: 'Bullish' },
    neutral: { color: 'text-yellow-400', bg: 'bg-yellow-400', Icon: Minus, label: 'Neutral' },
    bearish: { color: 'text-red-400', bg: 'bg-red-400', Icon: TrendingDown, label: 'Bearish' },
  };

  const config = overallConfig[sentiment.overall];
  const Icon = config.Icon;

  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-100 text-base font-semibold flex items-center gap-2">
          <Users className="w-4 h-4 text-blue-400" />
          Analyst Sentiment
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Overall */}
        <div className="flex items-center justify-between">
          <span className="text-slate-400 text-sm">Overall</span>
          <div className={`flex items-center gap-1.5 font-semibold ${config.color}`}>
            <Icon className="w-4 h-4" />
            <span>{config.label}</span>
          </div>
        </div>

        {/* Bar chart */}
        <div className="space-y-2">
          <SentimentBar label="Bullish" value={sentiment.bullish} color="bg-green-500" textColor="text-green-400" />
          <SentimentBar label="Neutral" value={sentiment.neutral} color="bg-yellow-500" textColor="text-yellow-400" />
          <SentimentBar label="Bearish" value={sentiment.bearish} color="bg-red-500" textColor="text-red-400" />
        </div>

        {/* Stacked bar */}
        <div className="h-3 rounded-full overflow-hidden flex">
          <div
            className="bg-green-500 transition-all duration-500"
            style={{ width: `${sentiment.bullish}%` }}
          />
          <div
            className="bg-yellow-500 transition-all duration-500"
            style={{ width: `${sentiment.neutral}%` }}
          />
          <div
            className="bg-red-500 transition-all duration-500"
            style={{ width: `${sentiment.bearish}%` }}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function SentimentBar({
  label,
  value,
  color,
  textColor,
}: {
  label: string;
  value: number;
  color: string;
  textColor: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-slate-400 text-xs w-14">{label}</span>
      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-700`}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className={`text-xs font-semibold w-8 text-right ${textColor}`}>{value}%</span>
    </div>
  );
}
