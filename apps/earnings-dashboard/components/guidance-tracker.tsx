'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Target } from 'lucide-react';
import type { GuidanceHistoryItem } from '@/types/earnings';

interface GuidanceTrackerProps {
  data: GuidanceHistoryItem[];
}

interface TooltipPayloadItem {
  name: string;
  value: number | null;
  color: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 shadow-xl text-xs">
      <p className="text-slate-300 font-semibold mb-2">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {p.value !== null ? `$${p.value?.toFixed(2)}` : 'N/A'}
        </p>
      ))}
    </div>
  );
}

export default function GuidanceTracker({ data }: GuidanceTrackerProps) {
  const epsData = data
    .filter(d => d.guidedEps !== null || d.actualEps !== null)
    .map(d => ({
      quarter: d.quarter,
      Guided: d.guidedEps,
      Actual: d.actualEps,
    }));

  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-100 text-base font-semibold flex items-center gap-2">
          <Target className="w-4 h-4 text-blue-400" />
          Guidance vs. Actual EPS
        </CardTitle>
        <p className="text-slate-500 text-xs">Management guidance compared to reported results</p>
      </CardHeader>
      <CardContent>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={epsData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }} barGap={3}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis
                dataKey="quarter"
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                width={48}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 11, color: '#94a3b8' }}
              />
              <Bar dataKey="Guided" fill="#60a5fa" fillOpacity={0.7} radius={[3, 3, 0, 0]} />
              <Bar dataKey="Actual" fill="#4ade80" fillOpacity={0.85} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
