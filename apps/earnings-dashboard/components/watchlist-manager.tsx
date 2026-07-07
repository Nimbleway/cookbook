'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Plus, Star, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import type { UpcomingEarnings } from '@/lib/upcoming';

const STORAGE_KEY = 'earningsiq_watchlist';
const POPULAR = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META', 'GOOGL', 'AMZN', 'AMD', 'NFLX', 'COIN'];

function loadWatchlist(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch { return []; }
}

function saveWatchlist(tickers: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tickers));
}

function makeGCalUrl(e: UpcomingEarnings): string {
  // Format: YYYYMMDDTHHmmssZ  — use all-day event
  const d = e.date.replace(/-/g, '');
  const next = new Date(e.date);
  next.setDate(next.getDate() + 1);
  const d2 = next.toISOString().split('T')[0].replace(/-/g, '');
  const text = encodeURIComponent(`${e.ticker} Earnings — ${e.quarter}`);
  const details = encodeURIComponent(
    `${e.companyName} ${e.quarter} earnings release. ${e.time !== 'unknown' ? (e.time === 'BMO' ? 'Before market open.' : 'After market close.') : ''}\n\nView full analysis: ${typeof window !== 'undefined' ? window.location.origin : 'https://earningsiq.vercel.app'}/dashboard/${e.ticker}`
  );
  return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${text}&dates=${d}/${d2}&details=${details}`;
}

export default function WatchlistManager() {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [input, setInput] = useState('');
  const [upcoming, setUpcoming] = useState<UpcomingEarnings[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeMonth, setActiveMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  useEffect(() => {
    setWatchlist(loadWatchlist());
  }, []);

  const fetchUpcoming = useCallback(async (tickers: string[]) => {
    if (!tickers.length) { setUpcoming([]); return; }
    setLoading(true);
    try {
      const res = await fetch(`/api/upcoming?tickers=${tickers.join(',')}`);
      const data = await res.json();
      setUpcoming(data);
    } catch { /* keep stale */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchUpcoming(watchlist);
  }, [watchlist, fetchUpcoming]);

  function addTicker() {
    const t = input.trim().toUpperCase().replace(/[^A-Z]/g, '').slice(0, 5);
    if (!t || watchlist.includes(t)) { setInput(''); return; }
    const next = [...watchlist, t];
    setWatchlist(next);
    saveWatchlist(next);
    setInput('');
  }

  function removeTicker(t: string) {
    const next = watchlist.filter(w => w !== t);
    setWatchlist(next);
    saveWatchlist(next);
  }

  // Calendar grid
  const year = activeMonth.getFullYear();
  const month = activeMonth.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const earningsByDate: Record<string, UpcomingEarnings[]> = {};
  for (const e of upcoming) {
    const d = new Date(e.date + 'T12:00:00'); // noon to avoid TZ shift
    if (d.getFullYear() === year && d.getMonth() === month) {
      const key = d.getDate().toString();
      earningsByDate[key] = [...(earningsByDate[key] || []), e];
    }
  }

  const today = new Date();
  const isToday = (day: number) =>
    day === today.getDate() && month === today.getMonth() && year === today.getFullYear();

  const prevMonth = () => setActiveMonth(new Date(year, month - 1, 1));
  const nextMonth = () => setActiveMonth(new Date(year, month + 1, 1));
  const monthLabel = activeMonth.toLocaleString('default', { month: 'long', year: 'numeric' });

  // Upcoming list — sorted by date, future only
  const sortedUpcoming = [...upcoming]
    .filter(e => new Date(e.date) >= new Date(today.toDateString()))
    .sort((a, b) => a.date.localeCompare(b.date));

  return (
    <div className="space-y-6">
      {/* Add tickers */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
        <h2 className="text-slate-100 font-semibold mb-3 flex items-center gap-2">
          <Star className="w-4 h-4 text-yellow-400" /> Watchlist
        </h2>

        <div className="flex gap-2 mb-4">
          <input
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && addTicker()}
            placeholder="Add ticker…"
            maxLength={5}
            className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono uppercase"
          />
          <button
            onClick={addTicker}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium flex items-center gap-1.5 transition-colors"
          >
            <Plus className="w-4 h-4" /> Add
          </button>
        </div>

        {/* Popular quick-add */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {POPULAR.filter(t => !watchlist.includes(t)).slice(0, 8).map(t => (
            <button
              key={t}
              onClick={() => {
                const next = [...watchlist, t];
                setWatchlist(next);
                saveWatchlist(next);
              }}
              className="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded text-xs font-mono transition-colors"
            >
              + {t}
            </button>
          ))}
        </div>

        {/* Current watchlist */}
        {watchlist.length === 0 ? (
          <p className="text-slate-500 text-sm">No tickers yet. Add some above.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {watchlist.map(t => (
              <div key={t} className="flex items-center gap-1.5 bg-slate-700 border border-slate-600 rounded-lg px-3 py-1.5">
                <Link href={`/dashboard/${t}`} className="text-blue-400 hover:text-blue-300 font-mono text-sm font-semibold transition-colors">
                  {t}
                </Link>
                <button onClick={() => removeTicker(t)} className="text-slate-500 hover:text-red-400 transition-colors ml-1">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {watchlist.length > 0 && (
        <>
          {/* Calendar */}
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-slate-100 font-semibold">Earnings Calendar</h2>
              <div className="flex items-center gap-2">
                {loading && <RefreshCw className="w-3.5 h-3.5 text-slate-500 animate-spin" />}
                <button onClick={prevMonth} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors text-sm">‹</button>
                <span className="text-slate-300 text-sm font-medium w-36 text-center">{monthLabel}</span>
                <button onClick={nextMonth} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors text-sm">›</button>
              </div>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 mb-1">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
                <div key={d} className="text-center text-slate-500 text-xs py-1.5 font-medium">{d}</div>
              ))}
            </div>

            {/* Calendar cells */}
            <div className="grid grid-cols-7 gap-px bg-slate-700 rounded-lg overflow-hidden">
              {cells.map((day, i) => {
                const earningsHere = day ? (earningsByDate[day.toString()] || []) : [];
                const hasEarnings = earningsHere.length > 0;
                return (
                  <div
                    key={i}
                    className={`bg-slate-800 min-h-[60px] p-1.5 ${day ? '' : 'opacity-30'} ${isToday(day!) ? 'ring-1 ring-inset ring-blue-500' : ''}`}
                  >
                    {day && (
                      <>
                        <span className={`text-xs font-medium block mb-1 ${isToday(day) ? 'text-blue-400' : 'text-slate-400'}`}>
                          {day}
                        </span>
                        {hasEarnings && earningsHere.map(e => (
                          <a
                            key={e.ticker}
                            href={makeGCalUrl(e)}
                            target="_blank"
                            rel="noopener noreferrer"
                            title={`Add ${e.ticker} earnings to Google Calendar`}
                            className="block w-full text-left mb-0.5"
                          >
                            <span className="inline-block bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 rounded px-1.5 py-0.5 text-xs font-mono font-semibold hover:bg-yellow-500/40 transition-colors cursor-pointer w-full truncate">
                              📅 {e.ticker}
                            </span>
                          </a>
                        ))}
                      </>
                    )}
                  </div>
                );
              })}
            </div>

            <p className="text-slate-600 text-xs mt-2">Click a ticker to add it to Google Calendar</p>
          </div>

          {/* Upcoming list */}
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
            <h2 className="text-slate-100 font-semibold mb-4">Upcoming Earnings</h2>
            {loading && !upcoming.length ? (
              <div className="space-y-2">
                {[1, 2, 3].map(i => <div key={i} className="h-14 bg-slate-700 rounded-lg animate-pulse" />)}
              </div>
            ) : sortedUpcoming.length === 0 ? (
              <p className="text-slate-500 text-sm">No upcoming earnings found for your watchlist.</p>
            ) : (
              <div className="space-y-2">
                {sortedUpcoming.map(e => {
                  const d = new Date(e.date + 'T12:00:00');
                  const daysUntil = Math.ceil((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
                  return (
                    <div key={e.ticker} className="flex items-center justify-between bg-slate-750 border border-slate-700 rounded-lg px-4 py-3 hover:bg-slate-700 transition-colors">
                      <div className="flex items-center gap-3">
                        <Link href={`/dashboard/${e.ticker}`} className="font-mono font-bold text-blue-400 hover:text-blue-300 text-sm w-14 transition-colors">
                          {e.ticker}
                        </Link>
                        <div>
                          <div className="text-slate-200 text-sm">{e.companyName !== e.ticker ? e.companyName : ''} <span className="text-slate-500 text-xs">{e.quarter}</span></div>
                          <div className="text-slate-400 text-xs mt-0.5">
                            {d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                            {e.time !== 'unknown' && <span className="ml-1.5 text-slate-500">· {e.time === 'BMO' ? 'Before open' : 'After close'}</span>}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          daysUntil <= 7 ? 'bg-orange-900/40 text-orange-300 border border-orange-700/40' :
                          daysUntil <= 30 ? 'bg-blue-900/40 text-blue-300 border border-blue-700/40' :
                          'bg-slate-700 text-slate-400 border border-slate-600'
                        }`}>
                          {daysUntil === 0 ? 'Today' : daysUntil === 1 ? 'Tomorrow' : `${daysUntil}d`}
                        </span>
                        <a
                          href={makeGCalUrl(e)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 px-3 py-1.5 bg-slate-700 hover:bg-blue-700 border border-slate-600 hover:border-blue-500 text-slate-300 hover:text-white rounded-lg text-xs font-medium transition-colors"
                          title="Add to Google Calendar"
                        >
                          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM7 10h5v5H7z"/>
                          </svg>
                          Add to Calendar
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
