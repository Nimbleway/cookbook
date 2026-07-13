import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react';
import type { KeyMetrics as KeyMetricsType } from '@/types/earnings';

interface KeyMetricsProps {
  data: KeyMetricsType;
}

function TrendIcon({ current, prior }: { current: number; prior: number }) {
  const diff = current - prior;
  if (Math.abs(diff) < 0.1) return <Minus className="w-4 h-4 text-yellow-400" />;
  if (diff > 0) return <TrendingUp className="w-4 h-4 text-green-400" />;
  return <TrendingDown className="w-4 h-4 text-red-400" />;
}

function trendColor(current: number, prior: number) {
  const diff = current - prior;
  if (Math.abs(diff) < 0.1) return 'text-yellow-400';
  return diff > 0 ? 'text-green-400' : 'text-red-400';
}

function formatDiff(current: number, prior: number, suffix: string) {
  const diff = current - prior;
  const sign = diff > 0 ? '+' : '';
  return `${sign}${diff.toFixed(1)}${suffix} vs prior qtr`;
}

interface MetricCardProps {
  label: string;
  current: number;
  prior: number;
  format: (v: number) => string;
  suffix: string;
}

function MetricCard({ label, current, prior, format, suffix }: MetricCardProps) {
  return (
    <div className="bg-slate-700/50 rounded-lg p-4 flex flex-col gap-2">
      <span className="text-slate-400 text-xs uppercase tracking-wide font-medium">{label}</span>
      <div className="flex items-end justify-between">
        <span className="text-white text-2xl font-bold">{format(current)}</span>
        <div className={`flex items-center gap-1 text-xs font-semibold ${trendColor(current, prior)}`}>
          <TrendIcon current={current} prior={prior} />
        </div>
      </div>
      <span className={`text-xs ${trendColor(current, prior)}`}>
        {formatDiff(current, prior, suffix)}
      </span>
    </div>
  );
}

export default function KeyMetrics({ data }: KeyMetricsProps) {
  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-100 text-base font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-400" />
          Key Metrics
        </CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3">
        <MetricCard
          label="Gross Margin"
          current={data.grossMargin.current}
          prior={data.grossMargin.prior}
          format={v => `${v.toFixed(1)}%`}
          suffix="%"
        />
        <MetricCard
          label="Operating Margin"
          current={data.operatingMargin.current}
          prior={data.operatingMargin.prior}
          format={v => `${v.toFixed(1)}%`}
          suffix="%"
        />
        <MetricCard
          label="Free Cash Flow"
          current={data.freeCashFlow.current}
          prior={data.freeCashFlow.prior}
          format={v => `$${v.toFixed(1)}B`}
          suffix="B"
        />
      </CardContent>
    </Card>
  );
}
