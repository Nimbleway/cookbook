import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, useMock, MOCK_PACKAGE } from "$lib/server/agent";

// Machine-readable single delivery — the lakehouse row as an addressable, reusable
// asset (not just rendered HTML). Backs the "view JSON" link on the permalink.
const VALID_ID = /^DEL-\d{8}-(?:[A-Z0-9]{4}|[A-Z0-9]{8})$/i;

export const GET: RequestHandler = async ({ params }) => {
  const id = params.id.trim().toUpperCase();
  if (!VALID_ID.test(id)) return json({ error: "not found" }, { status: 404 });

  if (useMock()) {
    return json({ ...MOCK_PACKAGE, trackingId: id });
  }

  try {
    const res = await fetch(`${agentUrl()}/deliveries/${encodeURIComponent(id)}`, {
      headers: bridgeHeaders(),
    });
    if (res.status === 404) return json({ error: "not found" }, { status: 404 });
    if (!res.ok) return json({ error: "unavailable" }, { status: 502 });
    return json(await res.json());
  } catch (err) {
    console.error(`[api/deliveries/${id}] agent unreachable: ${String(err)}`);
    return json({ error: "unavailable" }, { status: 502 });
  }
};
