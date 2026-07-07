import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Minus, Zap } from 'lucide-react';
import type { ChangeItem } from '@/types/earnings';

interface ChangesCardProps {
  changes: ChangeItem[];
  summary: string;
}

const changeConfig = {
  positive: {
    icon: TrendingUp,
    bg: 'bg-green-900/30',
    border: 'border-green-800',
    iconColor: 'text-green-400',
    textColor: 'text-green-100',
  },
  negative: {
    icon: TrendingDown,
    bg: 'bg-red-900/30',
    border: 'border-red-800',
    iconColor: 'text-red-400',
    textColor: 'text-red-100',
  },
  neutral: {
    icon: Minus,
    bg: 'bg-yellow-900/20',
    border: 'border-yellow-800',
    iconColor: 'text-yellow-400',
    textColor: 'text-yellow-100',
  },
};

export default function ChangesCard({ changes, summary }: ChangesCardProps) {
  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-100 text-base font-semibold flex items-center gap-2">
          <Zap className="w-4 h-4 text-blue-400" />
          What Changed
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-slate-400 text-sm leading-relaxed border-b border-slate-700 pb-3">
          {summary}
        </p>
        <div className="space-y-2">
          {changes.map((change, i) => {
            const config = changeConfig[change.type];
            const Icon = config.icon;
            return (
              <div
                key={i}
                className={`flex items-start gap-3 p-3 rounded-lg ${config.bg} border ${config.border}`}
              >
                <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${config.iconColor}`} />
                <span className={`text-sm ${config.textColor}`}>{change.text}</span>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
