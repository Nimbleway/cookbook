import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, useMock } from "$lib/server/agent";

// Three adjacent idea variants to branch a delivery into. Proxies the bridge.
export const POST: RequestHandler = async ({ request }) => {
  let body: { idea?: unknown; gap?: unknown };
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid request" }, { status: 400 });
  }
  const idea = typeof body.idea === "string" ? body.idea.trim() : "";
  if (!idea) return json({ error: "idea is required" }, { status: 400 });
  const gap = typeof body.gap === "string" ? body.gap : "";

  if (useMock()) {
    return json({
      variants: [
        "same-day grooming, but only for senior and anxious dogs",
        "a subscription that guarantees a monthly grooming slot",
        "white-glove mobile grooming for luxury high-rise buildings",
      ],
    });
  }

  try {
    const res = await fetch(`${agentUrl()}/remix`, {
      method: "POST",
      headers: { "content-type": "application/json", ...bridgeHeaders() },
      body: JSON.stringify({ idea, gap }),
    });
    if (!res.ok) return json({ variants: [] }, { status: 200 });
    return json(await res.json());
  } catch (err) {
    console.error(`[remix] agent unreachable: ${String(err)}`);
    return json({ variants: [] }, { status: 200 });
  }
};
