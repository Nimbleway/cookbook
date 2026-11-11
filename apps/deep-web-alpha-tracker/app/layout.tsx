import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Deep Web Alpha Tracker',
  description: 'Deep web context on a 50-name tech watchlist, researched by Nimble Web Search Agents, to boost your alpha.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans text-[13px] antialiased">{children}</body>
    </html>
  );
}
