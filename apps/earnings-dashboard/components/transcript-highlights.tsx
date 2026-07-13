import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { MessageSquareQuote } from 'lucide-react';
import type { TranscriptHighlight } from '@/types/earnings';

interface TranscriptHighlightsProps {
  highlights: TranscriptHighlight[];
}

const sentimentConfig = {
  positive: {
    badge: 'bg-green-900/50 text-green-400 border-green-700',
    border: 'border-l-green-500',
    label: 'Positive',
  },
  negative: {
    badge: 'bg-red-900/50 text-red-400 border-red-700',
    border: 'border-l-red-500',
    label: 'Negative',
  },
  neutral: {
    badge: 'bg-yellow-900/30 text-yellow-400 border-yellow-700',
    border: 'border-l-yellow-500',
    label: 'Neutral',
  },
};

export default function TranscriptHighlights({ highlights }: TranscriptHighlightsProps) {
  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-100 text-base font-semibold flex items-center gap-2">
          <MessageSquareQuote className="w-4 h-4 text-blue-400" />
          Transcript Highlights
        </CardTitle>
        <p className="text-slate-500 text-xs">Notable quotes from the earnings call</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {highlights.map((highlight, i) => {
          const config = sentimentConfig[highlight.sentiment];
          return (
            <div
              key={i}
              className={`border-l-4 pl-4 py-1 ${config.border}`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-slate-300 text-xs font-semibold uppercase tracking-wide">
                  {highlight.speaker}
                </span>
                <Badge className={`text-xs ${config.badge}`}>
                  {config.label}
                </Badge>
              </div>
              <p className="text-slate-300 text-sm leading-relaxed italic">
                &ldquo;{highlight.quote}&rdquo;
              </p>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
