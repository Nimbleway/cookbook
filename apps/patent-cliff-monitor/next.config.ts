import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  turbopack: {
    // Keep file tracing inside this cookbook when other projects have lockfiles.
    root: __dirname,
  },
};

export default nextConfig;
