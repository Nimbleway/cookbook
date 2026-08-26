import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Patent Cliff Monitor',
  description: 'Async pharma patent-cliff research powered by Nimble Web Search Agents.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
