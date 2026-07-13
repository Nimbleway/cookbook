import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { EarningsMetrics } from '@/types/earnings';

interface EarningsSummaryProps {
  earnings: EarningsMetrics;
  title: string;
}

function formatRevenue(val: number | null): string {
  if (val === null) return 'N/A';
  if (val >= 1000) return `$${(val / 1000).toFixed(1)}T`;
  if (val >= 1) return `$${val.toFixed(1)}B`;
  return `$${(val * 1000).toFixed(0)}M`;
}

function BeatBadge({ beat }: { beat: boolean | null }) {
  if (beat === null) return null;
  if (beat) return <Badge className="bg-green-900/50 text-green-400 border-green-700 text-xs">BEAT</Badge>;
  return <Badge className="bg-red-900/50 text-red-400 border-red-700 text-xs">MISS</Badge>;
}

function MetricRow({
  label,
  actual,
  estimate,
  beat,
  format,
}: {
  label: string;
  actual: number | null;
  estimate: number | null;
  beat: boolean | null;
  format: (v: number | null) => string;
}) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-slate-700 last:border-0">
      <span className="text-slate-400 text-sm">{label}</span>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <div className="text-white font-semibold">{format(actual)}</div>
          {estimate !== null && (
            <div className="text-slate-500 text-xs">est. {format(estimate)}</div>
          )}
        </div>
        <BeatBadge beat={beat} />
      </div>
    </div>
  );
}

export default function EarningsSummary({ earnings, title }: EarningsSummaryProps) {
  const GuidanceIcon = earnings.guidance.raised === true
    ? TrendingUp
    : earnings.guidance.raised === false
      ? TrendingDown
      : Minus;

  const guidanceColor = earnings.guidance.raised === true
    ? 'text-green-400'
    : earnings.guidance.raised === false
      ? 'text-red-400'
      : 'text-yellow-400';

  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-slate-100 text-base font-semibold">{title}</CardTitle>
          <div className="text-right">
            <Badge variant="outline" className="border-slate-600 text-slate-300 text-xs">
              {earnings.quarter}
            </Badge>
            <div className="text-slate-500 text-xs mt-1">{earnings.date}</div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <MetricRow
          label="EPS"
          actual={earnings.eps.actual}
          estimate={earnings.eps.estimate}
          beat={earnings.eps.beat}
          format={v => v !== null ? `$${v.toFixed(2)}` : 'N/A'}
        />
        <MetricRow
          label="Revenue"
          actual={earnings.revenue.actual}
          estimate={earnings.revenue.estimate}
          beat={earnings.revenue.beat}
          format={formatRevenue}
        />
        <div className="flex items-start gap-2 pt-3">
          <GuidanceIcon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${guidanceColor}`} />
          <div>
            <span className={`text-xs font-semibold uppercase tracking-wide ${guidanceColor}`}>
              {earnings.guidance.raised === true ? 'Guidance Raised' : earnings.guidance.raised === false ? 'Guidance Lowered' : 'Guidance'}
            </span>
            <p className="text-slate-300 text-sm mt-0.5">{earnings.guidance.details}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
