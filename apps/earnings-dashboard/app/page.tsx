import Link from 'next/link';
import { TrendingUp, BarChart2, Zap, Shield, Calendar } from 'lucide-react';
import TickerInput from '@/components/ticker-input';

const features = [
  {
    icon: BarChart2,
    title: 'Earnings Analysis',
    description: 'Deep dive into EPS, revenue, and guidance with beat/miss tracking.',
  },
  {
    icon: Zap,
    title: 'AI-Powered Insights',
    description: 'Claude analyzes earnings transcripts to surface key changes and signals.',
  },
  {
    icon: TrendingUp,
    title: 'Price + Earnings Chart',
    description: 'Overlay stock price history with earnings dates for visual context.',
  },
  {
    icon: Shield,
    title: 'Analyst Sentiment',
    description: 'Aggregated analyst reactions with bullish/bearish/neutral scoring.',
  },
];

export default function Home() {
  return (
    <main className="flex-1 flex flex-col">
      {/* Hero section */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-16 bg-gradient-to-b from-slate-900 via-slate-900 to-slate-800">
        <div className="w-full max-w-4xl mx-auto text-center">
          {/* Logo */}
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-4xl font-bold text-white tracking-tight">
              Earnings<span className="text-blue-400">IQ</span>
            </h1>
          </div>

          <p className="text-xl text-slate-400 mb-3 font-medium">
            AI-powered earnings analysis for any stock
          </p>
          <p className="text-slate-500 mb-10 max-w-lg mx-auto">
            Instantly analyze earnings reports, track what changed vs. prior guidance,
            and gauge analyst sentiment — powered by live web data and Claude AI.
          </p>

          {/* Search input */}
          <TickerInput />

          <div className="mt-6">
            <Link
              href="/watchlist"
              className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-500 text-slate-400 hover:text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Calendar className="w-4 h-4" />
              Manage Watchlist & Earnings Calendar
            </Link>
          </div>
        </div>
      </div>

      {/* Features grid */}
      <div className="bg-slate-800/50 border-t border-slate-700 py-12 px-4">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-center text-slate-400 text-sm font-semibold uppercase tracking-widest mb-8">
            What you get
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {features.map((feature, i) => {
              const Icon = feature.icon;
              return (
                <div
                  key={i}
                  className="p-5 bg-slate-800 rounded-xl border border-slate-700 hover:border-slate-600 transition-colors"
                >
                  <div className="w-9 h-9 rounded-lg bg-blue-900/50 flex items-center justify-center mb-3">
                    <Icon className="w-5 h-5 text-blue-400" />
                  </div>
                  <h3 className="text-white font-semibold text-sm mb-1">{feature.title}</h3>
                  <p className="text-slate-400 text-xs leading-relaxed">{feature.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-slate-900 border-t border-slate-800 py-4 px-4">
        <p className="text-center text-slate-600 text-xs">
          EarningsIQ — powered by Nimble Web API and Claude AI. For informational purposes only.
        </p>
      </footer>
    </main>
  );
}
