import { error } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";
import { agentUrl, bridgeHeaders, useMock, MOCK_PACKAGE } from "$lib/server/agent";
import type { DeliveryPackage, JobEnvelope, JobPartial, JobPhase } from "$lib/types";

// A shipment tracking number: DEL-YYYYMMDD-XXXXXXXX. Reject malformed ids before
// the bridge fetch so random ids can't be used to hammer the agent / image render.
// Four-char legacy suffixes stay readable for already-shared demo links.
const VALID_ID = /^DEL-\d{8}-(?:[A-Z0-9]{4}|[A-Z0-9]{8})$/i;

export interface PageData {
  status: "done" | "running" | "error";
  trackingId: string;
  idea: string;
  ogImageUrl: string;
  pkg: DeliveryPackage | null;
  partial: JobPartial | null;
  phase: JobPhase | null;
  errorMessage: string | null;
}

export const load: PageServerLoad = async ({ params, url }): Promise<PageData> => {
  const id = params.id.trim().toUpperCase();
  if (!VALID_ID.test(id)) throw error(404, "That delivery has shipped out of view");

  // Absolute URL for the per-delivery share card (crawlers need a full origin).
  const ogImageUrl = `${url.origin}/d/${encodeURIComponent(id)}/og.png`;

  if (useMock()) {
    const pkg = { ...MOCK_PACKAGE, trackingId: id } satisfies DeliveryPackage;
    return { status: "done", trackingId: id, idea: pkg.idea, ogImageUrl, pkg, partial: null, phase: "done", errorMessage: null };
  }

  // Primary: fetch from the jobs endpoint (durable, includes running/error states).
  let jobRes: Response;
  try {
    jobRes = await fetch(`${agentUrl()}/jobs/${encodeURIComponent(id)}`, {
      headers: bridgeHeaders(),
    });
  } catch (err) {
    console.error(`[d/${id}] agent unreachable: ${String(err)}`);
    throw error(502, "Could not reach the delivery service");
  }

  // 404 from jobs → fallback to the legacy /deliveries endpoint (deploy-order
  // safety: if the job was pruned but the lakehouse row still exists).
  if (jobRes.status === 404) {
    let delRes: Response;
    try {
      delRes = await fetch(`${agentUrl()}/deliveries/${encodeURIComponent(id)}`, {
        headers: bridgeHeaders(),
      });
    } catch (err) {
      console.error(`[d/${id}] agent unreachable (deliveries fallback): ${String(err)}`);
      throw error(502, "Could not reach the delivery service");
    }
    if (delRes.status === 404) throw error(404, "That delivery has shipped out of view");
    if (!delRes.ok) throw error(502, "Could not load this delivery");
    const pkg = (await delRes.json()) as DeliveryPackage;
    return { status: "done", trackingId: id, idea: pkg.idea ?? "", ogImageUrl, pkg, partial: null, phase: "done", errorMessage: null };
  }

  if (!jobRes.ok) throw error(502, "Could not load this delivery");

  const envelope = (await jobRes.json()) as JobEnvelope;

  if (envelope.status === "done") {
    return {
      status: "done",
      trackingId: id,
      idea: envelope.idea,
      ogImageUrl,
      pkg: envelope.package,
      partial: null,
      phase: "done",
      errorMessage: null,
    };
  }

  if (envelope.status === "error") {
    return {
      status: "error",
      trackingId: id,
      idea: envelope.idea,
      ogImageUrl,
      pkg: null,
      partial: envelope.partial,
      phase: envelope.phase,
      errorMessage: envelope.error,
    };
  }

  // running
  return {
    status: "running",
    trackingId: id,
    idea: envelope.idea,
    ogImageUrl,
    pkg: null,
    partial: envelope.partial,
    phase: envelope.phase,
    errorMessage: null,
  };
};
