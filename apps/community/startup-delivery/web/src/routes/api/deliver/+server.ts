import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, landingBuildEnabled, MOCK_PACKAGE, useMock } from "$lib/server/agent";
import type { DeliveryPackage } from "$lib/types";

// A full delivery can take ~30s on the bridge; raise the function timeout.
export const config = { maxDuration: 60 };

// Non-streaming delivery surface, mirroring the agent bridge's POST /deliver.
// The web UI uses the SSE stream endpoint; this one-shot route is kept as a
// programmatic API (returns the final DeliveryPackage in a single response) for
// callers that don't want server-sent events.
export const POST: RequestHandler = async ({ request }) => {
  let idea: unknown;
  let buildLanding: unknown;
  try {
    ({ idea, buildLanding } = await request.json());
  } catch {
    return json({ error: "invalid request" }, { status: 400 });
  }

  if (typeof idea !== "string" || idea.trim() === "") {
    return json({ error: "idea is required" }, { status: 400 });
  }

  if (useMock()) {
    return json({ ...MOCK_PACKAGE, idea: idea.trim() } satisfies DeliveryPackage);
  }

  try {
    const res = await fetch(`${agentUrl()}/deliver`, {
      method: "POST",
      headers: { "content-type": "application/json", ...bridgeHeaders() },
      body: JSON.stringify({ idea: idea.trim(), buildLanding: Boolean(buildLanding) && landingBuildEnabled() }),
    });
    if (!res.ok) {
      console.error(`[deliver] bridge ${res.status}: ${await res.text()}`);
      return json({ error: "delivery failed" }, { status: res.status });
    }
    const pkg = (await res.json()) as DeliveryPackage;
    return json(pkg);
  } catch (err) {
    console.error(`[deliver] agent unreachable: ${String(err)}`);
    return json({ error: "delivery failed" }, { status: 502 });
  }
};
