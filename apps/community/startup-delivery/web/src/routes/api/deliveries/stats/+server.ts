import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, useMock } from "$lib/server/agent";

// Aggregate lakehouse stats for the Loading Dock panel. Proxies the bridge.
export const GET: RequestHandler = async () => {
  if (useMock()) {
    return json({
      total: 12,
      verdicts: { build: 7, pivot: 4, pass: 1 },
      avgScore: 68,
      securedValueUsd: 214.88,
      topTlds: [
        { tld: "com", count: 6 },
        { tld: "app", count: 3 },
        { tld: "ai", count: 2 },
        { tld: "co", count: 1 },
      ],
      topThemes: [
        { token: "ai", count: 4 },
        { token: "dog", count: 2 },
        { token: "groom", count: 2 },
      ],
    });
  }

  try {
    const res = await fetch(`${agentUrl()}/deliveries/stats`, { headers: bridgeHeaders() });
    if (!res.ok) return json({ total: 0 }, { status: 200 });
    return json(await res.json());
  } catch (err) {
    console.error(`[deliveries/stats] agent unreachable: ${String(err)}`);
    return json({ total: 0 }, { status: 200 });
  }
};
