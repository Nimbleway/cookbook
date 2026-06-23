import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, useMock } from "$lib/server/agent";

// Ungated proxy of the bridge's public GET /health. Unlike /api/debug (token-
// gated), this is open so the client-side DomainSourceBadge can read the honest
// `domainSource` provenance ({ env, trustworthy, ... }) by default. /health is a
// light, non-secret, presence-only snapshot on the bridge — safe to expose.
// Degrades to a body with no `domainSource` (so the badge renders nothing) on any
// failure or in MOCK mode.
export const GET: RequestHandler = async () => {
  if (useMock()) {
    // No bridge in mock; omit domainSource so the badge stays hidden.
    return json({ ok: true, mock: true });
  }

  try {
    const res = await fetch(`${agentUrl()}/health`, { headers: bridgeHeaders() });
    if (!res.ok) {
      console.error(`[health] bridge ${res.status}: ${await res.text()}`);
      return json({ ok: false }, { status: 200 });
    }
    return json(await res.json());
  } catch (err) {
    console.error(`[health] agent unreachable: ${String(err)}`);
    return json({ ok: false }, { status: 200 });
  }
};
