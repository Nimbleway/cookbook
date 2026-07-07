import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown, CalendarDays } from 'lucide-react';
import type { PriceData } from '@/types/earnings';

interface PostEarningsMovesProps {
  priceData: PriceData;
}

interface EarningsMove {
  date: string;
  oneDay: number | null;
  fiveDay: number | null;
}

function getPriceOnOrAfter(
  prices: PriceData['prices'],
  targetDate: string,
  offsetDays: number
): number | null {
  // Find the index of the nearest trading day at or after targetDate
  const sorted = [...prices].sort((a, b) => a.date.localeCompare(b.date));
  let baseIdx = -1;
  for (let i = 0; i < sorted.length; i++) {
    if (sorted[i].date >= targetDate) {
      baseIdx = i;
      break;
    }
  }
  if (baseIdx === -1) return null;
  const targetIdx = baseIdx + offsetDays;
  if (targetIdx < 0 || targetIdx >= sorted.length) return null;
  return sorted[targetIdx].close;
}

function calculateMoves(priceData: PriceData): EarningsMove[] {
  const recentDates = [...priceData.earningsDates]
    .sort((a, b) => b.localeCompare(a))
    .slice(0, 4);

  return recentDates.map(date => {
    const base = getPriceOnOrAfter(priceData.prices, date, 0);
    const plus1 = getPriceOnOrAfter(priceData.prices, date, 1);
    const plus5 = getPriceOnOrAfter(priceData.prices, date, 5);

    const oneDay = base && plus1 ? ((plus1 - base) / base) * 100 : null;
    const fiveDay = base && plus5 ? ((plus5 - base) / base) * 100 : null;

    return { date, oneDay, fiveDay };
  });
}

function MoveCell({ value }: { value: number | null }) {
  if (value === null) return <span className="text-slate-500">—</span>;
  const positive = value >= 0;
  const Icon = positive ? TrendingUp : TrendingDown;
  return (
    <span className={`flex items-center justify-end gap-1 font-semibold text-sm ${positive ? 'text-green-400' : 'text-red-400'}`}>
      <Icon className="w-3.5 h-3.5" />
      {positive ? '+' : ''}{value.toFixed(2)}%
    </span>
  );
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function PostEarningsMoves({ priceData }: PostEarningsMovesProps) {
  const moves = calculateMoves(priceData);

  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-100 text-base font-semibold flex items-center gap-2">
          <CalendarDays className="w-4 h-4 text-blue-400" />
          Post-Earnings Price Moves
        </CardTitle>
        <p className="text-slate-500 text-xs">Price change after each earnings report</p>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left text-slate-400 text-xs font-medium pb-2 pr-4">Earnings Date</th>
                <th className="text-right text-slate-400 text-xs font-medium pb-2 pr-4">+1 Day</th>
                <th className="text-right text-slate-400 text-xs font-medium pb-2">+5 Days</th>
              </tr>
            </thead>
            <tbody>
              {moves.length === 0 ? (
                <tr>
                  <td colSpan={3} className="text-slate-500 text-xs text-center py-6">
                    No earnings dates available
                  </td>
                </tr>
              ) : (
                moves.map((move, i) => (
                  <tr key={i} className="border-b border-slate-700/50 last:border-0">
                    <td className="py-3 pr-4 text-slate-300">{formatDate(move.date)}</td>
                    <td className="py-3 pr-4 text-right">
                      <MoveCell value={move.oneDay} />
                    </td>
                    <td className="py-3 text-right">
                      <MoveCell value={move.fiveDay} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
