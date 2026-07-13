'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart2 } from 'lucide-react';
import type { SurpriseHistoryItem } from '@/types/earnings';

interface SurpriseHistoryProps {
  data: SurpriseHistoryItem[];
}

interface TooltipPayloadItem {
  name: string;
  value: number;
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
      <p className="text-slate-300 font-semibold mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {p.value > 0 ? '+' : ''}{p.value.toFixed(1)}%
        </p>
      ))}
    </div>
  );
}

export default function SurpriseHistory({ data }: SurpriseHistoryProps) {
  const displayData = data.slice(-8).reverse();

  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-100 text-base font-semibold flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-blue-400" />
          EPS Surprise History
        </CardTitle>
        <p className="text-slate-500 text-xs">Beat/miss % vs consensus estimate</p>
      </CardHeader>
      <CardContent>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={displayData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
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
                tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v}%`}
                width={42}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
              <Bar dataKey="epsSurprise" name="EPS Surprise" radius={[3, 3, 0, 0]}>
                {displayData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.epsSurprise >= 0 ? '#4ade80' : '#f87171'}
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
