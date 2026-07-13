import Link from 'next/link';
import { ArrowLeft, TrendingUp, Calendar } from 'lucide-react';
import WatchlistManager from '@/components/watchlist-manager';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Watchlist & Earnings Calendar | EarningsIQ',
  description: 'Track upcoming earnings dates for your watchlist and add them to Google Calendar.',
};

export default function WatchlistPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-850">
      <nav className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur border-b border-slate-800">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">Back</span>
          </Link>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
              <TrendingUp className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold text-white text-sm">EarningsIQ</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-400 text-sm ml-1">
            <Calendar className="w-3.5 h-3.5" />
            <span>Watchlist</span>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-1">Earnings Watchlist</h1>
          <p className="text-slate-400 text-sm">
            Track upcoming earnings dates and add them to Google Calendar with one click.
          </p>
        </div>
        <WatchlistManager />
      </div>
    </div>
  );
}
