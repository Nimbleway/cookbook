import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ExternalLink, Newspaper } from 'lucide-react';
import type { AnalystReaction } from '@/types/earnings';

interface NewsFeedProps {
  reactions: AnalystReaction[];
}

const sentimentStyles = {
  bullish: {
    badge: 'bg-green-900/50 text-green-400 border-green-700',
    dot: 'bg-green-400',
  },
  bearish: {
    badge: 'bg-red-900/50 text-red-400 border-red-700',
    dot: 'bg-red-400',
  },
  neutral: {
    badge: 'bg-yellow-900/50 text-yellow-400 border-yellow-700',
    dot: 'bg-yellow-400',
  },
};

export default function NewsFeed({ reactions }: NewsFeedProps) {
  return (
    <Card className="bg-slate-800 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-100 text-base font-semibold flex items-center gap-2">
          <Newspaper className="w-4 h-4 text-blue-400" />
          Analyst Reactions
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {reactions.length === 0 ? (
          <p className="text-slate-500 text-sm">No analyst reactions found.</p>
        ) : (
          reactions.map((reaction, i) => {
            const styles = sentimentStyles[reaction.sentiment] || sentimentStyles.neutral;
            return (
              <div
                key={i}
                className="p-3 rounded-lg bg-slate-750 border border-slate-700 hover:border-slate-600 transition-colors"
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 mt-1 ${styles.dot}`} />
                    <span className="text-slate-400 text-xs font-medium">{reaction.source}</span>
                    <span className="text-slate-600 text-xs">{reaction.date}</span>
                  </div>
                  <Badge className={`text-xs flex-shrink-0 ${styles.badge}`}>
                    {reaction.sentiment.charAt(0).toUpperCase() + reaction.sentiment.slice(1)}
                  </Badge>
                </div>
                <a
                  href={reaction.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group"
                >
                  <p className="text-white text-sm font-medium group-hover:text-blue-400 transition-colors flex items-start gap-1">
                    {reaction.headline}
                    <ExternalLink className="w-3 h-3 mt-0.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </p>
                </a>
                {reaction.excerpt && (
                  <p className="text-slate-400 text-xs mt-1 leading-relaxed line-clamp-2">
                    {reaction.excerpt}
                  </p>
                )}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
