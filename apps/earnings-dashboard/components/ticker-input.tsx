'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Search, TrendingUp } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

const POPULAR_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META', 'GOOGL', 'AMZN'];

const TICKER_NAMES: Record<string, string> = {
  AAPL: 'Apple',
  MSFT: 'Microsoft',
  NVDA: 'NVIDIA',
  TSLA: 'Tesla',
  META: 'Meta',
  GOOGL: 'Alphabet',
  AMZN: 'Amazon',
  NFLX: 'Netflix',
  AMD: 'AMD',
  INTC: 'Intel',
  CRM: 'Salesforce',
  ORCL: 'Oracle',
  JPM: 'JPMorgan',
  BAC: 'Bank of America',
  V: 'Visa',
  MA: 'Mastercard',
};

interface TickerInputProps {
  initialTicker?: string;
  compact?: boolean;
}

export default function TickerInput({ initialTicker = '', compact = false }: TickerInputProps) {
  const router = useRouter();
  const [ticker, setTicker] = useState(initialTicker);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInput = (value: string) => {
    const upper = value.toUpperCase();
    setTicker(upper);
    if (upper.length >= 1) {
      const filtered = Object.keys(TICKER_NAMES).filter(t =>
        t.startsWith(upper) || TICKER_NAMES[t].toLowerCase().includes(upper.toLowerCase())
      );
      setSuggestions(filtered.slice(0, 6));
      setShowSuggestions(filtered.length > 0);
    } else {
      setShowSuggestions(false);
    }
  };

  const handleSearch = (t?: string) => {
    const searchTicker = (t || ticker).toUpperCase().trim();
    if (!searchTicker) return;
    setShowSuggestions(false);
    router.push(`/dashboard/${searchTicker}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
    if (e.key === 'Escape') setShowSuggestions(false);
  };

  if (compact) {
    return (
      <div ref={containerRef} className="relative flex gap-2">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            ref={inputRef}
            value={ticker}
            onChange={e => handleInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => ticker.length >= 1 && setShowSuggestions(suggestions.length > 0)}
            placeholder="Search ticker..."
            className="pl-9 w-40 bg-slate-700 border-slate-600 text-white placeholder:text-slate-400 focus:border-blue-500"
          />
          {showSuggestions && (
            <div className="absolute top-full mt-1 left-0 w-48 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-50">
              {suggestions.map(s => (
                <button
                  key={s}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-slate-700 text-white flex justify-between items-center"
                  onClick={() => { setTicker(s); handleSearch(s); }}
                >
                  <span className="font-mono font-semibold">{s}</span>
                  <span className="text-slate-400 text-xs">{TICKER_NAMES[s]}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <Button
          onClick={() => handleSearch()}
          className="bg-blue-600 hover:bg-blue-700 text-white"
          size="sm"
        >
          Go
        </Button>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full max-w-2xl mx-auto">
      <div className="relative flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <Input
            ref={inputRef}
            value={ticker}
            onChange={e => handleInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => ticker.length >= 1 && setShowSuggestions(suggestions.length > 0)}
            placeholder="Enter stock ticker (e.g. AAPL, MSFT, NVDA...)"
            className="pl-12 py-6 text-lg bg-slate-800 border-slate-600 text-white placeholder:text-slate-500 focus:border-blue-500 rounded-xl"
          />
          {showSuggestions && (
            <div className="absolute top-full mt-2 left-0 right-0 bg-slate-800 border border-slate-600 rounded-xl shadow-2xl z-50">
              {suggestions.map(s => (
                <button
                  key={s}
                  className="w-full text-left px-4 py-3 hover:bg-slate-700 text-white flex justify-between items-center first:rounded-t-xl last:rounded-b-xl"
                  onClick={() => { setTicker(s); handleSearch(s); }}
                >
                  <span className="font-mono font-bold text-blue-400">{s}</span>
                  <span className="text-slate-400">{TICKER_NAMES[s]}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <Button
          onClick={() => handleSearch()}
          size="lg"
          className="px-8 py-6 text-lg bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold"
        >
          Analyze
        </Button>
      </div>

      <div className="mt-6">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-slate-400" />
          <span className="text-sm text-slate-400 font-medium">Popular tickers</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {POPULAR_TICKERS.map(t => (
            <button
              key={t}
              onClick={() => handleSearch(t)}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-blue-500 text-slate-300 hover:text-white rounded-lg text-sm font-mono font-semibold transition-all duration-150"
            >
              {t}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
