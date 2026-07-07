import PriceChart from './price-chart';
import type { PriceData } from '@/types/earnings';

interface PriceChartWrapperProps {
  priceData: PriceData;
  ticker: string;
}

export default function PriceChartWrapper({ priceData, ticker }: PriceChartWrapperProps) {
  return <PriceChart priceData={priceData} ticker={ticker} />;
}
