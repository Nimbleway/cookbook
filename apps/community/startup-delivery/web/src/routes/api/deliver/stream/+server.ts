import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, landingBuildEnabled, useMock } from "$lib/server/agent";

// A live delivery streams for ~30s; let the serverless function stay open.
// (Vercel Hobby caps at 60s; Pro allows more.)
export const config = { maxDuration: 60 };

export const GET: RequestHandler = async ({ url }) => {
  const idea = url.searchParams.get("idea")?.trim() ?? "";
  const buildLanding = url.searchParams.get("buildLanding") === "true" && landingBuildEnabled();

  if (!idea) {
    return json({ error: "idea is required" }, { status: 400 });
  }

  if (useMock()) {
    return mockStream(idea, buildLanding);
  }

  const params = new URLSearchParams({ idea, buildLanding: String(buildLanding) });
  const upstream = `${agentUrl()}/deliver/stream?${params}`;

  try {
    const res = await fetch(upstream, { headers: bridgeHeaders() });
    if (!res.ok || !res.body) {
      console.error(`[deliver/stream] bridge ${res.status}: ${await res.text()}`);
      return json({ error: "delivery failed" }, { status: res.status });
    }

    const trackingId = res.headers.get("x-tracking-id")?.trim();
    const body = trackingId ? prependStartEvent(res.body, idea, trackingId) : res.body;

    return new Response(body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (err) {
    console.error(`[deliver/stream] agent unreachable: ${String(err)}`);
    return json({ error: "delivery failed" }, { status: 502 });
  }
};

function prependStartEvent(body: ReadableStream<Uint8Array>, idea: string, trackingId: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const reader = body.getReader();
  let cancelled = false;

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        controller.enqueue(encoder.encode(sse("start", { idea, trackingId })));
        while (!cancelled) {
          const { done, value } = await reader.read();
          if (done) break;
          if (value) controller.enqueue(value);
        }
        controller.close();
      } catch (err) {
        try {
          controller.error(err);
        } catch {
          /* already closed */
        }
      }
    },
    cancel() {
      cancelled = true;
      reader.cancel().catch(() => {});
    },
  });
}

/** Scripted SSE for UI dev when MOCK=1 (tracking id varies per run). */
function mockStream(idea: string, buildLanding: boolean): Response {
  const encoder = new TextEncoder();
  const competitors = [
    {
      name: "Rover",
      url: "https://rover.com",
      positioning: "Pet-care marketplace, no same-day grooming focus",
      pricing: "15% take rate",
      sourceUrl: "https://rover.com",
      kind: "marketplace",
    },
    {
      name: "Barkbus",
      url: "https://barkbus.com",
      positioning: "Mobile grooming vans, a handful of metros only",
      pricing: "$89–$150 per visit",
      sourceUrl: "https://barkbus.com",
      kind: "agency",
    },
    {
      name: "Wag",
      url: "https://wagwalking.com",
      positioning: "On-demand dog walking; grooming is an afterthought",
      pricing: "$20 per walk",
      sourceUrl: "https://wagwalking.com",
      kind: "marketplace",
    },
  ];
  const marketSummary =
    "Grooming is hyper-local and phone-booked. The big marketplaces optimize for walking and sitting, not same-day grooming, so there is no national layer that guarantees a slot today.";
  const positioningGap =
    "Nobody owns same-day grooming nationally. Win the 'my dog needs a bath before guests arrive tonight' moment and you own a wedge the marketplaces structurally ignore.";
  const verdict = {
    call: "build",
    score: 74,
    headline:
      "Real, recurring demand and a wedge the big marketplaces structurally ignore. Build it, but move fast on the same-day promise.",
    risks: [
      "Rover and Wag have the audience and could bolt on grooming.",
      "Same-day fulfillment is an ops problem, not just an app problem.",
    ],
    nextSteps: [
      "Interview 5 dog owners who needed grooming in under 24 hours.",
      "Line up 3 mobile groomers willing to take same-day jobs.",
      "Launch a one-city landing page and measure booking intent.",
    ],
  };

  const now = new Date();
  const reconAt = now.toISOString();
  const stamp = `${now.getUTCFullYear()}${String(now.getUTCMonth() + 1).padStart(2, "0")}${String(now.getUTCDate()).padStart(2, "0")}`;
  const trackingId = `DEL-${stamp}-${Math.floor(now.getTime() % 0xffffffff).toString(16).toUpperCase().padStart(8, "0")}`;
  const marketHeat = {
    niche: idea,
    competitorCount: competitors.length,
    crowded: competitors.length >= 5,
    refreshedAt: reconAt,
  };
  const complaints = [
    "No same-day or next-day availability when you actually need it",
    "Booking flow is clunky and built for the groomer, not the owner",
    "Prices and add-ons are unclear until checkout",
  ];

  // Representative TLD grids so the multi-TLD domain moment renders offline.
  const freshpawsVariants = [
    { domain: "freshpaws.delivery", tld: "delivery", available: true, priceUsd: 8.99, renewalPriceUsd: 77.99 },
    { domain: "freshpaws.com", tld: "com", available: false, priceUsd: null },
    { domain: "freshpaws.app", tld: "app", available: true, priceUsd: 12.99, renewalPriceUsd: 18.99 },
    { domain: "freshpaws.ai", tld: "ai", available: true, priceUsd: 199.98, renewalPriceUsd: 199.98, premium: true },
    { domain: "freshpaws.io", tld: "io", available: false, priceUsd: null },
    { domain: "freshpaws.co", tld: "co", available: true, priceUsd: 29.99, renewalPriceUsd: 34.99 },
  ];
  const groomnowVariants = [
    { domain: "groomnow.delivery", tld: "delivery", available: false, priceUsd: null },
    { domain: "groomnow.com", tld: "com", available: false, priceUsd: null },
    { domain: "groomnow.app", tld: "app", available: false, priceUsd: null },
    { domain: "groomnow.co", tld: "co", available: false, priceUsd: null },
  ];
  const sudsyVariants = [
    { domain: "sudsy.delivery", tld: "delivery", available: false, priceUsd: null },
    { domain: "sudsy.com", tld: "com", available: false, priceUsd: null },
    { domain: "sudsy.app", tld: "app", available: false, priceUsd: null },
    { domain: "sudsy.ai", tld: "ai", available: false, priceUsd: null },
  ];

  const lines: string[] = [
    sse("start", { idea, trackingId }),
    sse("see", { competitors, marketSummary, reconAt, marketHeat, complaints }),
    sse("think", {
      positioningGap,
      candidates: [
        { name: "FreshPaws", domain: "freshpaws.delivery", reasoning: "Short, mobile-first" },
        { name: "GroomNow", domain: "groomnow.delivery", reasoning: "Action-oriented urgency" },
        { name: "Sudsy", domain: "sudsy.delivery", reasoning: "Playful, memorable" },
      ],
    }),
    sse("verdict", { verdict }),
    sse("check", {
      candidate: {
        name: "GroomNow",
        domain: "groomnow.delivery",
        available: false,
        priceUsd: null,
        variants: groomnowVariants,
      },
    }),
    sse("check", {
      candidate: {
        name: "Sudsy",
        domain: "sudsy.delivery",
        available: false,
        priceUsd: null,
        variants: sudsyVariants,
      },
    }),
    sse("check", {
      candidate: {
        name: "FreshPaws",
        domain: "freshpaws.delivery",
        available: true,
        priceUsd: 8.99,
        variants: freshpawsVariants,
      },
    }),
    sse("secured", {
      candidate: {
        name: "FreshPaws",
        domain: "freshpaws.delivery",
        available: true,
        priceUsd: 8.99,
        variants: freshpawsVariants,
      },
    }),
    ...(buildLanding ? [sse("build", { domain: "freshpaws.delivery" })] : []),
    sse("package", {
      idea,
      brand: "FreshPaws",
      domain: "freshpaws.delivery",
      priceUsd: 8.99,
      positioningGap,
      marketSummary,
      competitors,
      reconAt,
      marketHeat,
      complaints,
      domainOptions: freshpawsVariants,
      trackingId,
      verdict,
      suggestions: [
        { domain: "freshpaws.app", tld: "app", available: true, priceUsd: 12.99, renewalPriceUsd: 18.99 },
        { domain: "freshpaws.co", tld: "co", available: true, priceUsd: 29.99 },
        { domain: "freshpaws.ai", tld: "ai", available: true, priceUsd: 199.98, premium: true },
      ],
      launchKit: [
        { domain: "getfreshpaws.com", tld: "com", available: true, priceUsd: 12.99 },
        { domain: "tryfreshpaws.com", tld: "com", available: true, priceUsd: 12.99 },
      ],
      learnedFrom: [
        { brand: "GroomGo", domain: "groomgo.app", trackingId: "DEL-20260601-AA01BEEF" },
        { brand: "Pawband", domain: "pawband.com", trackingId: "DEL-20260601-BB02CAFE" },
      ],
      landingUrl: buildLanding ? "/deliveries/freshpaws.delivery/index.html" : undefined,
    }),
  ];

  let timer: ReturnType<typeof setTimeout> | undefined;
  let cancelled = false;

  const stream = new ReadableStream({
    start(controller) {
      let i = 0;
      const push = () => {
        if (cancelled) return;
        if (i >= lines.length) {
          try {
            controller.close();
          } catch {
            /* already closed by a client disconnect */
          }
          return;
        }
        try {
          controller.enqueue(encoder.encode(lines[i]));
        } catch {
          return; // client went away; stop pushing
        }
        i += 1;
        // let each domain check land with a beat of tension (the hero moment)
        timer = setTimeout(push, i >= 3 && i <= 6 ? 480 : 650);
      };
      push();
    },
    // EventSource.close() / navigation cancels the stream: stop the timer so we
    // never enqueue onto a closed controller (which crashes the dev server).
    cancel() {
      cancelled = true;
      clearTimeout(timer);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
    },
  });
}

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}
