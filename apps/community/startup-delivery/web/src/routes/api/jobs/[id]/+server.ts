import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, useMock, MOCK_PACKAGE } from "$lib/server/agent";

const NO_STORE = { "cache-control": "no-store" };
const VALID_ID = /^DEL-\d{8}-(?:[A-Z0-9]{4}|[A-Z0-9]{8})$/i;

export const GET: RequestHandler = async ({ params }) => {
  const id = params.id.trim().toUpperCase();
  if (!VALID_ID.test(id)) return json({ error: "not found" }, { status: 404, headers: NO_STORE });

  if (useMock()) {
    return json(
      {
        status: "done",
        trackingId: id,
        idea: MOCK_PACKAGE.idea,
        buildLanding: false,
        createdAt: null,
        updatedAt: null,
        phase: "done",
        steps: [],
        partial: null,
        package: { ...MOCK_PACKAGE, trackingId: id },
        error: null,
      },
      { headers: NO_STORE },
    );
  }

  try {
    const res = await fetch(`${agentUrl()}/jobs/${encodeURIComponent(id)}`, {
      headers: bridgeHeaders(),
    });
    if (res.status === 404) return json({ error: "not found" }, { status: 404, headers: NO_STORE });
    if (!res.ok) return json({ error: "unavailable" }, { status: 502, headers: NO_STORE });
    return json(await res.json(), { headers: NO_STORE });
  } catch (err) {
    console.error(`[api/jobs/${id}] agent unreachable: ${String(err)}`);
    return json({ error: "unavailable" }, { status: 502, headers: NO_STORE });
  }
};
