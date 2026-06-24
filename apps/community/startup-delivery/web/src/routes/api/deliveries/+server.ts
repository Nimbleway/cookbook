import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, MOCK_PACKAGE, useMock } from "$lib/server/agent";
import type { DeliveryPackage } from "$lib/types";

// The public "Loading Dock": recent deliveries from the lakehouse mirror.
// Proxies the bridge's GET /deliveries; serves a small mock set when MOCK=1.
export const GET: RequestHandler = async ({ url }) => {
  const limit = Number(url.searchParams.get("limit") ?? "24");

  if (useMock()) {
    return json({ deliveries: mockDeliveries() });
  }

  try {
    const res = await fetch(`${agentUrl()}/deliveries?limit=${encodeURIComponent(String(limit))}`, {
      headers: bridgeHeaders(),
    });
    if (!res.ok) {
      console.error(`[deliveries] bridge ${res.status}: ${await res.text()}`);
      return json({ deliveries: [] }, { status: 200 });
    }
    return json(await res.json());
  } catch (err) {
    console.error(`[deliveries] agent unreachable: ${String(err)}`);
    return json({ deliveries: [] }, { status: 200 });
  }
};

function mockDeliveries(): DeliveryPackage[] {
  const second: DeliveryPackage = {
    idea: "a tool that turns voice memos into blog posts",
    brand: "Memocast",
    domain: "memocast.app",
    priceUsd: 12.99,
    positioningGap:
      "Transcription tools stop at text. Nobody turns a rambling voice memo into a structured, publishable post in one step.",
    marketSummary: "Crowded transcription market; thin layer for long-form repurposing.",
    competitors: [],
    reconAt: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
    marketHeat: { niche: "voice to blog", competitorCount: 6, crowded: true, refreshedAt: new Date().toISOString() },
    trackingId: "DEL-20260603-1C0ABEEF",
    verdict: { call: "pivot", score: 52, headline: "Real demand, but the space is crowded — sharpen the wedge.", risks: [], nextSteps: [] },
  };
  const third: DeliveryPackage = {
    idea: "a marketplace for vintage synthesizers",
    brand: "Wavevault",
    domain: "wavevault.com",
    priceUsd: 12.99,
    positioningGap:
      "Reverb is general gear. No trusted, curated home exists just for vintage analog synths with provenance and serviced condition.",
    competitors: [],
    marketSummary: "Fragmented; general marketplaces dominate, no niche authority.",
    reconAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    marketHeat: { niche: "vintage synths", competitorCount: 3, crowded: false, refreshedAt: new Date().toISOString() },
    trackingId: "DEL-20260603-77E2CAFE",
    verdict: { call: "build", score: 81, headline: "Open niche with passionate buyers. Build the trusted home.", risks: [], nextSteps: [] },
  };
  return [MOCK_PACKAGE, second, third];
}
