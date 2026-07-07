import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface BullBearCardProps {
  bullCase: string;
  bearCase: string;
}

export default function BullBearCard({ bullCase, bearCase }: BullBearCardProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Bull Case */}
      <Card className="bg-green-900/20 border-green-800/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-green-400 text-base font-semibold flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Bull Case
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-green-100/80 text-sm leading-relaxed">{bullCase}</p>
        </CardContent>
      </Card>

      {/* Bear Case */}
      <Card className="bg-red-900/20 border-red-800/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-red-400 text-base font-semibold flex items-center gap-2">
            <TrendingDown className="w-4 h-4" />
            Bear Case
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-red-100/80 text-sm leading-relaxed">{bearCase}</p>
        </CardContent>
      </Card>
    </div>
  );
}
