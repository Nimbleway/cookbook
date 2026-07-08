import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Funnel the original (already-shared) URL to the clean canonical one.
  // Host-based 308 so anyone who clicks a previously-sent
  // nimble-retail-mini-app.vercel.app link lands on nimble-retail.vercel.app,
  // path preserved. Only the old host matches, so there's no redirect loop.
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "nimble-retail-mini-app.vercel.app" }],
        destination: "https://nimble-retail.vercel.app/:path*",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
