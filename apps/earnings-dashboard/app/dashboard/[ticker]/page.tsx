import { Suspense } from 'react';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, TrendingUp, RefreshCw, AlertCircle, Calendar } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import EarningsSummary from '@/components/earnings-summary';
import ChangesCard from '@/components/changes-card';
import SentimentGauge from '@/components/sentiment-gauge';
import NewsFeed from '@/components/news-feed';
import PriceChartWrapper from '@/components/price-chart-wrapper';
import TickerInput from '@/components/ticker-input';
import PostEarningsMoves from '@/components/post-earnings-moves';
import BullBearCard from '@/components/bull-bear-card';
import SurpriseHistory from '@/components/surprise-history';
import KeyMetrics from '@/components/key-metrics';
import GuidanceTracker from '@/components/guidance-tracker';
import TranscriptHighlights from '@/components/transcript-highlights';
import WatchButton from '@/components/watch-button';
import { getEarningsData } from '@/lib/earnings';
import { getPriceData } from '@/lib/price';
import type { EarningsData, PriceData } from '@/types/earnings';
import type { Metadata } from 'next';

interface PageProps {
  params: Promise<{ ticker: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { ticker } = await params;
  const upperTicker = ticker.toUpperCase();

  if (!/^[A-Z]{1,5}$/.test(upperTicker)) {
    return { title: 'EarningsIQ' };
  }

  let earningsData: EarningsData | null = null;
  try {
    earningsData = await getEarningsData(upperTicker) as EarningsData;
  } catch {
    // fall through to defaults
  }

  const companyName = earningsData?.companyName ?? `${upperTicker} Corporation`;
  const epsActual = earningsData?.latestEarnings?.eps?.actual;
  const epsEst = earningsData?.latestEarnings?.eps?.estimate;
  const epsBeat = earningsData?.latestEarnings?.eps?.beat;
  const revActual = earningsData?.latestEarnings?.revenue?.actual;
  const revBeat = earningsData?.latestEarnings?.revenue?.beat;
  const sentiment = earningsData?.sentiment?.overall ?? 'neutral';
  const quarter = earningsData?.latestEarnings?.quarter ?? '';

  const ogParams = new URLSearchParams({ ticker: upperTicker, company: companyName, sentiment });
  if (epsActual !== null && epsActual !== undefined) ogParams.set('eps', String(epsActual));
  if (epsEst !== null && epsEst !== undefined) ogParams.set('epsEst', String(epsEst));
  if (epsBeat !== null && epsBeat !== undefined) ogParams.set('epsBeat', String(epsBeat));
  if (revActual !== null && revActual !== undefined) ogParams.set('rev', String(revActual));
  if (revBeat !== null && revBeat !== undefined) ogParams.set('revBeat', String(revBeat));

  const ogImageUrl = `/api/og?${ogParams.toString()}`;
  const title = `${upperTicker} Earnings — ${quarter} | EarningsIQ`;
  const description = `${companyName} ${quarter} earnings analysis: EPS ${epsBeat ? 'beat' : 'miss'}, revenue ${revBeat ? 'beat' : 'miss'}. Analyst sentiment: ${sentiment}.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      images: [{ url: ogImageUrl, width: 1200, height: 630, alt: `${upperTicker} Earnings` }],
      type: 'website',
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [ogImageUrl],
    },
  };
}

export default async function DashboardPage({ params }: PageProps) {
  const { ticker } = await params;
  const upperTicker = ticker.toUpperCase();

  if (!/^[A-Z]{1,5}$/.test(upperTicker)) {
    notFound();
  }

  let earningsData: EarningsData;
  let priceData: PriceData;

  try {
    [earningsData, priceData] = await Promise.all([
      getEarningsData(upperTicker) as Promise<EarningsData>,
      getPriceData(upperTicker, '2y') as Promise<PriceData>,
    ]);
  } catch (error) {
    console.error('Dashboard fetch error:', error);
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-white text-xl font-semibold mb-2">Failed to load data</h2>
          <p className="text-slate-400 mb-6">Could not fetch data for {upperTicker}. Please try again.</p>
          <Link
            href="/"
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            Try another ticker
          </Link>
        </div>
      </div>
    );
  }

  const currentPrice = priceData.prices[priceData.prices.length - 1]?.close;

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-850">
      {/* Top navigation */}
      <nav className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
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
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/watchlist"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-400 hover:text-white rounded-lg text-xs font-medium transition-colors"
            >
              <Calendar className="w-3.5 h-3.5" />
              Watchlist
            </Link>
            <TickerInput compact />
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-3xl font-bold text-white font-mono">{upperTicker}</h1>
              {(earningsData as EarningsData & { _fallback?: boolean })._fallback && (
                <Badge className="bg-yellow-900/50 text-yellow-400 border-yellow-700 text-xs">
                  Demo Data
                </Badge>
              )}
              <WatchButton ticker={upperTicker} />
            </div>
            <div className="flex items-center gap-3">
              <p className="text-slate-400 text-lg">{earningsData.companyName}</p>
              <span className="text-slate-600">|</span>
              <p className="text-slate-500 text-sm">
                Latest: {earningsData.latestEarnings.quarter} · {earningsData.latestEarnings.date}
              </p>
            </div>
          </div>
          {currentPrice && (
            <div className="text-right">
              <div className="text-3xl font-bold text-white">${currentPrice.toFixed(2)}</div>
              <div className="text-slate-500 text-xs mt-0.5">Last close</div>
            </div>
          )}
        </div>

        {/* Price chart - full width */}
        <Suspense fallback={<div className="h-80 bg-slate-800 rounded-xl animate-pulse" />}>
          <PriceChartWrapper priceData={priceData} ticker={upperTicker} />
        </Suspense>

        {/* Post-Earnings Price Moves */}
        <PostEarningsMoves priceData={priceData} />

        {/* What Changed + Sentiment */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <ChangesCard
              changes={earningsData.changes}
              summary={earningsData.summary}
            />
          </div>
          <div>
            <SentimentGauge sentiment={earningsData.sentiment} />
          </div>
        </div>

        {/* Bull vs Bear */}
        {(earningsData.bullCase || earningsData.bearCase) && (
          <BullBearCard
            bullCase={earningsData.bullCase ?? ''}
            bearCase={earningsData.bearCase ?? ''}
          />
        )}

        {/* Earnings summaries */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <EarningsSummary
            earnings={earningsData.latestEarnings}
            title="Latest Earnings"
          />
          <EarningsSummary
            earnings={earningsData.previousEarnings}
            title="Previous Earnings"
          />
        </div>

        {/* Surprise History + Key Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            {earningsData.surpriseHistory && earningsData.surpriseHistory.length > 0 && (
              <SurpriseHistory data={earningsData.surpriseHistory} />
            )}
          </div>
          <div>
            {earningsData.keyMetrics && (
              <KeyMetrics data={earningsData.keyMetrics} />
            )}
          </div>
        </div>

        {/* Guidance Tracker */}
        {earningsData.guidanceHistory && earningsData.guidanceHistory.length > 0 && (
          <GuidanceTracker data={earningsData.guidanceHistory} />
        )}

        {/* Transcript Highlights */}
        {earningsData.transcriptHighlights && earningsData.transcriptHighlights.length > 0 && (
          <TranscriptHighlights highlights={earningsData.transcriptHighlights} />
        )}

        {/* Analyst Reactions */}
        <NewsFeed reactions={earningsData.analystReactions} />

        {/* Footer note */}
        <div className="flex items-center gap-2 text-slate-600 text-xs py-2">
          <RefreshCw className="w-3 h-3" />
          <span>Data refreshes every hour. Powered by Nimble Web API + Claude AI. Not financial advice.</span>
        </div>
      </div>
    </div>
  );
}
