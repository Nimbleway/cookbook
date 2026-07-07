'use client';

import { useState, useEffect } from 'react';
import { Star } from 'lucide-react';

const STORAGE_KEY = 'earningsiq_watchlist';

function getWatchlist(): string[] {
  if (typeof window === 'undefined') return [];
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch { return []; }
}

export default function WatchButton({ ticker }: { ticker: string }) {
  const [watching, setWatching] = useState(false);

  useEffect(() => {
    setWatching(getWatchlist().includes(ticker));
  }, [ticker]);

  function toggle() {
    const list = getWatchlist();
    const next = watching
      ? list.filter(t => t !== ticker)
      : [...list, ticker];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setWatching(!watching);
  }

  return (
    <button
      onClick={toggle}
      title={watching ? 'Remove from watchlist' : 'Add to watchlist'}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
        watching
          ? 'bg-yellow-900/40 border-yellow-700/60 text-yellow-300 hover:bg-yellow-900/60'
          : 'bg-slate-800 border-slate-600 text-slate-400 hover:text-yellow-300 hover:border-yellow-700/60'
      }`}
    >
      <Star className={`w-3.5 h-3.5 ${watching ? 'fill-yellow-300' : ''}`} />
      {watching ? 'Watching' : 'Watch'}
    </button>
  );
}
