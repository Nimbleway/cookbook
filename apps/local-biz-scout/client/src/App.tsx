import { useState, useMemo, useEffect, useCallback } from 'react';
import { useAnalyticsQuery } from '@databricks/appkit-ui/react';
import { sql } from '@databricks/appkit-ui/js';
import { BarChart } from '@databricks/appkit-ui/react';
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Skeleton,
  Slider,
  Spinner,
} from '@databricks/appkit-ui/react';
import { MapPin, Star, Search } from 'lucide-react';

const NIMBLE_YELLOW = '#edc602';

function toNum(v: unknown): number | null {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function stars(rating: unknown): string {
  const n = toNum(rating);
  if (n === null) return '—';
  return `${n.toFixed(1)} ★`;
}

function fmt(n: unknown): string {
  const v = toNum(n);
  if (v === null) return '—';
  return v.toLocaleString();
}

type ScoutStatus = 'idle' | 'running' | 'succeeded' | 'failed';

export default function App() {
  const [businessType, setBusinessType] = useState('');
  const [location, setLocation] = useState('');
  const [maxResults, setMaxResults] = useState(10);

  const [status, setStatus] = useState<ScoutStatus>('idle');
  const [statusError, setStatusError] = useState<string | null>(null);
  const [statementId, setStatementId] = useState<string | null>(null);
  const [pendingSearchId, setPendingSearchId] = useState<string | null>(null);
  const [currentSearchId, setCurrentSearchId] = useState('');
  const [currentLabel, setCurrentLabel] = useState('');

  // Poll statement status until done
  useEffect(() => {
    if (status !== 'running' || !statementId) return;
    const interval = setInterval(async () => {
      try {
        const r = await fetch(`/api/scout/status/${statementId}`);
        const data = await r.json() as { state: string; error: string | null };
        if (data.state === 'SUCCEEDED') {
          setCurrentSearchId(pendingSearchId ?? '');
          setStatus('succeeded');
          clearInterval(interval);
        } else if (data.state === 'FAILED' || data.state === 'CANCELED') {
          setStatus('failed');
          setStatusError(data.error ?? 'Search failed');
          clearInterval(interval);
        }
      } catch {
        setStatus('failed');
        setStatusError('Network error polling status');
        clearInterval(interval);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [status, statementId, pendingSearchId]);

  const handleScout = useCallback(async () => {
    if (!businessType.trim() || !location.trim()) return;
    setStatus('running');
    setStatusError(null);
    setCurrentLabel(`${businessType.trim()} in ${location.trim()}`);
    try {
      const r = await fetch('/api/scout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ businessType, location, maxResults }),
      });
      const data = await r.json() as { statementId: string; searchId: string; error?: string };
      if (data.error) {
        setStatus('failed');
        setStatusError(data.error);
        return;
      }
      setStatementId(data.statementId);
      setPendingSearchId(data.searchId);
    } catch {
      setStatus('failed');
      setStatusError('Failed to start search');
    }
  }, [businessType, location, maxResults]);

  // Query params — memoized so hooks don't loop
  const searchIdParam = useMemo(
    () => ({ search_id: sql.string(currentSearchId) }),
    [currentSearchId],
  );
  const emptyParams = useMemo(() => ({}), []);

  const { data: kpis, loading: kpisLoading } = useAnalyticsQuery(
    'kpis',
    searchIdParam,
    { autoStart: status === 'succeeded' || currentSearchId !== '' },
  );
  const { data: leaderboard, loading: leaderLoading } = useAnalyticsQuery(
    'leaderboard',
    searchIdParam,
    { autoStart: status === 'succeeded' || currentSearchId !== '' },
  );
  const { data: history } = useAnalyticsQuery('history', emptyParams);

  const kpi = kpis?.[0];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MapPin className="h-5 w-5" style={{ color: NIMBLE_YELLOW }} />
          <h1 className="text-xl font-bold text-foreground">Local Business Scout</h1>
        </div>
        <span
          className="text-xs font-semibold px-2 py-1 rounded"
          style={{ background: NIMBLE_YELLOW, color: '#1a1a1a' }}
        >
          Powered by Nimble
        </span>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">

        {/* Search Panel */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-4 w-4" />
              Find Local Businesses
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col md:flex-row gap-4 items-end">
              <div className="flex-1">
                <label className="text-sm font-medium text-muted-foreground mb-1 block">
                  Business type
                </label>
                <Input
                  placeholder="e.g. coffee shops"
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                  disabled={status === 'running'}
                />
              </div>
              <div className="flex-1">
                <label className="text-sm font-medium text-muted-foreground mb-1 block">
                  Location
                </label>
                <Input
                  placeholder="e.g. Astoria, Queens"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  disabled={status === 'running'}
                  onKeyDown={(e) => e.key === 'Enter' && handleScout()}
                />
              </div>
              <div className="w-48">
                <label className="text-sm font-medium text-muted-foreground mb-1 block">
                  Results: {maxResults}
                </label>
                <Slider
                  min={5}
                  max={50}
                  step={5}
                  value={[maxResults]}
                  onValueChange={([v]) => setMaxResults(v)}
                  disabled={status === 'running'}
                  className="mt-2"
                />
              </div>
              <Button
                onClick={handleScout}
                disabled={status === 'running' || !businessType.trim() || !location.trim()}
                style={
                  status !== 'running' && businessType.trim() && location.trim()
                    ? { background: NIMBLE_YELLOW, color: '#1a1a1a', border: 'none' }
                    : {}
                }
                className="min-w-[120px]"
              >
                {status === 'running' ? (
                  <span className="flex items-center gap-2">
                    <Spinner className="h-4 w-4" /> Scouting…
                  </span>
                ) : (
                  'Scout →'
                )}
              </Button>
            </div>

            {/* Status bar */}
            {status === 'running' && (
              <p className="mt-4 text-sm text-muted-foreground">
                Searching <span className="font-medium text-foreground">"{currentLabel}"</span> via
                Nimble Search API → enriching with Google Maps… (~30s)
              </p>
            )}
            {status === 'failed' && statusError && (
              <p className="mt-4 text-sm text-destructive">Error: {statusError}</p>
            )}
            {status === 'succeeded' && (
              <p className="mt-4 text-sm" style={{ color: NIMBLE_YELLOW }}>
                ✓ Results loaded for "{currentLabel}"
              </p>
            )}
          </CardContent>
        </Card>

        {/* KPI Row */}
        {(status === 'succeeded' || currentSearchId) && (
          <div className="grid grid-cols-3 gap-4">
            {[
              {
                label: 'Businesses found',
                value: kpisLoading ? null : fmt(kpi?.total_businesses),
              },
              {
                label: 'Average rating',
                value: kpisLoading ? null : stars(kpi?.avg_rating),
              },
              {
                label: 'Avg review count',
                value: kpisLoading ? null : fmt(kpi?.avg_reviews),
              },
            ].map(({ label, value }) => (
              <Card key={label}>
                <CardContent className="pt-6">
                  <p className="text-sm text-muted-foreground">{label}</p>
                  {value === null ? (
                    <Skeleton className="h-8 w-20 mt-1" />
                  ) : (
                    <p className="text-3xl font-bold text-foreground mt-1">{value}</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Leaderboard + Chart */}
        {(status === 'succeeded' || currentSearchId) && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Leaderboard */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>
                  <Star className="inline h-4 w-4 mr-1" style={{ color: NIMBLE_YELLOW }} />
                  Top Results
                </CardTitle>
              </CardHeader>
              <CardContent>
                {leaderLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : !leaderboard?.length ? (
                  <p className="text-sm text-muted-foreground">No results yet.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-muted-foreground">
                          <th className="text-left py-2 pr-4 font-medium">#</th>
                          <th className="text-left py-2 pr-4 font-medium">Name</th>
                          <th className="text-left py-2 pr-4 font-medium">Rating</th>
                          <th className="text-left py-2 pr-4 font-medium">Reviews</th>
                          <th className="text-left py-2 pr-4 font-medium">Category</th>
                          <th className="text-left py-2 font-medium">Link</th>
                        </tr>
                      </thead>
                      <tbody>
                        {leaderboard.map((row, i) => (
                          <tr key={i} className="border-b last:border-0 hover:bg-muted/40">
                            <td className="py-2 pr-4 text-muted-foreground font-mono">{i + 1}</td>
                            <td className="py-2 pr-4 font-medium">
                              {row.name ?? row.search_title ?? '—'}
                            </td>
                            <td className="py-2 pr-4">
                              <span
                                className="font-semibold"
                                style={{
                                  color:
                                    (toNum(row.rating) ?? 0) >= 4.5
                                      ? '#16a34a'
                                      : (toNum(row.rating) ?? 0) >= 4
                                      ? '#ca8a04'
                                      : '#6b7280',
                                }}
                              >
                                {stars(row.rating)}
                              </span>
                            </td>
                            <td className="py-2 pr-4 text-muted-foreground">
                              {fmt(row.review_count)}
                            </td>
                            <td className="py-2 pr-4 text-muted-foreground text-xs">
                              {row.category ?? '—'}
                            </td>
                            <td className="py-2">
                              {row.place_url ? (
                                <a
                                  href={row.place_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs underline"
                                  style={{ color: NIMBLE_YELLOW }}
                                >
                                  Maps ↗
                                </a>
                              ) : (
                                '—'
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Ratings Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Ratings Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <BarChart
                  queryKey="ratings_dist"
                  parameters={searchIdParam}
                  xKey="rating_bucket"
                  yKey="businesses"
                  orientation="horizontal"
                  height={260}
                  colors={[NIMBLE_YELLOW]}
                />
              </CardContent>
            </Card>
          </div>
        )}

        {/* Search History */}
        <Card>
          <CardHeader>
            <CardTitle>Search History</CardTitle>
          </CardHeader>
          <CardContent>
            {!history?.length ? (
              <p className="text-sm text-muted-foreground">No searches yet. Run your first scout above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="text-left py-2 pr-4 font-medium">Business type</th>
                      <th className="text-left py-2 pr-4 font-medium">Location</th>
                      <th className="text-left py-2 pr-4 font-medium">Businesses</th>
                      <th className="text-left py-2 pr-4 font-medium">Avg rating</th>
                      <th className="text-left py-2 pr-4 font-medium">Time</th>
                      <th className="text-left py-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((row) => (
                      <tr key={row.search_id} className="border-b last:border-0 hover:bg-muted/40">
                        <td className="py-2 pr-4 font-medium">{row.business_type}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{row.location}</td>
                        <td className="py-2 pr-4">{fmt(row.businesses)}</td>
                        <td className="py-2 pr-4">{stars(row.avg_rating)}</td>
                        <td className="py-2 pr-4 text-muted-foreground text-xs">{row.search_time}</td>
                        <td className="py-2">
                          <button
                            className="text-xs underline"
                            style={{ color: NIMBLE_YELLOW }}
                            onClick={() => setCurrentSearchId(row.search_id)}
                          >
                            Load
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
