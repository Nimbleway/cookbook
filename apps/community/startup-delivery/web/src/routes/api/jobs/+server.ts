import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, landingBuildEnabled, useMock } from "$lib/server/agent";

const NO_STORE = { "cache-control": "no-store" };

function mockTrackingId(): string {
  const now = new Date();
  const stamp = `${now.getUTCFullYear()}${String(now.getUTCMonth() + 1).padStart(2, "0")}${String(now.getUTCDate()).padStart(2, "0")}`;
  return `DEL-${stamp}-M0CKJ0B5`;
}

export const POST: RequestHandler = async ({ request }) => {
  let body: { idea?: unknown; buildLanding?: unknown };
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid request" }, { status: 400, headers: NO_STORE });
  }

  if (!body || typeof body !== "object") {
    return json({ error: "invalid request" }, { status: 400, headers: NO_STORE });
  }

  const idea = typeof body.idea === "string" ? body.idea.trim() : "";
  if (!idea) return json({ error: "idea is required" }, { status: 400, headers: NO_STORE });

  const buildLanding = Boolean(body.buildLanding) && landingBuildEnabled();

  if (useMock()) {
    return json({ trackingId: mockTrackingId(), status: "running" }, { status: 202, headers: NO_STORE });
  }

  try {
    const res = await fetch(`${agentUrl()}/jobs`, {
      method: "POST",
      headers: { "content-type": "application/json", ...bridgeHeaders() },
      body: JSON.stringify({ idea, buildLanding }),
    });
    if (!res.ok) {
      console.error(`[jobs] bridge ${res.status}: ${await res.text()}`);
      // Don't echo the upstream bridge status (401/403/etc. leaks internal auth state);
      // collapse everything except the user-meaningful "busy" to a generic 502.
      const status = res.status === 429 ? 429 : 502;
      return json({ error: status === 429 ? "busy" : "delivery failed" }, { status, headers: NO_STORE });
    }
    return json(await res.json(), { status: 202, headers: NO_STORE });
  } catch (err) {
    console.error(`[jobs] agent unreachable: ${String(err)}`);
    return json({ error: "delivery failed" }, { status: 502, headers: NO_STORE });
  }
};
