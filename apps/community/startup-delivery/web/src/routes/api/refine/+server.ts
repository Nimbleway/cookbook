import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, useMock } from "$lib/server/agent";
import type { NameCandidate } from "$lib/types";

// Refine reuses cached recon but re-runs naming + name.com checks (~10-15s).
export const config = { maxDuration: 60 };

// Founder-steered re-naming: reuses cached recon on the bridge, returns a fresh,
// domain-checked batch of names for the given angle (or the existing gap).
export const POST: RequestHandler = async ({ request }) => {
  let body: { idea?: unknown; gap?: unknown; angle?: unknown; excludeDomains?: unknown };
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid request" }, { status: 400 });
  }

  const idea = typeof body.idea === "string" ? body.idea.trim() : "";
  if (!idea) return json({ error: "idea is required" }, { status: 400 });

  const gap = typeof body.gap === "string" ? body.gap : "";
  const angle = typeof body.angle === "string" && body.angle.trim() ? body.angle.trim() : null;
  const excludeDomains = Array.isArray(body.excludeDomains)
    ? body.excludeDomains.filter((d): d is string => typeof d === "string")
    : [];

  if (useMock()) {
    return json({ gap: angle ?? gap, candidates: mockNames(angle) });
  }

  try {
    const res = await fetch(`${agentUrl()}/refine`, {
      method: "POST",
      headers: { "content-type": "application/json", ...bridgeHeaders() },
      body: JSON.stringify({ idea, gap, angle, excludeDomains }),
    });
    if (!res.ok) {
      console.error(`[refine] bridge ${res.status}: ${await res.text()}`);
      return json({ error: "refine failed" }, { status: res.status });
    }
    return json(await res.json());
  } catch (err) {
    console.error(`[refine] agent unreachable: ${String(err)}`);
    return json({ error: "refine failed" }, { status: 502 });
  }
};

function mockNames(angle: string | null): NameCandidate[] {
  const tag = angle ? "angle" : "more";
  return [
    {
      name: tag === "angle" ? "Tonight" : "Pawly",
      domain: tag === "angle" ? "tonight.pet" : "pawly.app",
      available: true,
      priceUsd: 14.99,
      reasoning: angle ? `Leans into your angle: ${angle}` : "Fresh take, still on-brief",
      variants: [
        { domain: tag === "angle" ? "tonight.com" : "pawly.com", tld: "com", available: false },
        { domain: tag === "angle" ? "tonight.pet" : "pawly.app", tld: tag === "angle" ? "pet" : "app", available: true, priceUsd: 14.99 },
      ],
    },
    {
      name: tag === "angle" ? "SameDay" : "Scrub",
      domain: tag === "angle" ? "sameday.dog" : "scrub.pet",
      available: true,
      priceUsd: 19.99,
      reasoning: angle ? "Names the urgency directly" : "Short, punchy, available",
      variants: [
        { domain: tag === "angle" ? "sameday.dog" : "scrub.pet", tld: tag === "angle" ? "dog" : "pet", available: true, priceUsd: 19.99 },
      ],
    },
  ];
}
