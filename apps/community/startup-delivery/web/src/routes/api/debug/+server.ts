import { json, error } from "@sveltejs/kit";
import { env } from "$env/dynamic/private";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, useMock } from "$lib/server/agent";

// Proxy the bridge's secret-gated GET /debug so you can confirm the live prod
// config (model, name.com base = dev vs prod, persist flag, deliveries-log path +
// count, env presence) from the browser without SSHing into Fly. Never returns
// secret VALUES — the bridge only emits a non-secret snapshot.
//
// Closed by default: the route requires a DEBUG_TOKEN that the caller must echo
// via ?token= or the x-debug-token header. If DEBUG_TOKEN is unset, or the token
// doesn't match, we 404 (not 401) so the endpoint's existence stays unadvertised.
export const GET: RequestHandler = async ({ url, request }) => {
  const expected = (env.DEBUG_TOKEN ?? "").trim();
  const provided = url.searchParams.get("token") ?? request.headers.get("x-debug-token") ?? "";
  if (!expected || provided !== expected) {
    throw error(404, "Not Found");
  }

  if (useMock()) {
    return json({ mock: true, note: "MOCK=1 — bridge not contacted" });
  }

  try {
    const res = await fetch(`${agentUrl()}/debug`, { headers: bridgeHeaders() });
    if (!res.ok) {
      const detail = await res.text();
      console.error(`[debug] bridge ${res.status}: ${detail}`);
      return json(
        { error: "bridge debug unavailable", status: res.status },
        { status: 200 },
      );
    }
    return json(await res.json());
  } catch (err) {
    console.error(`[debug] agent unreachable: ${String(err)}`);
    return json({ error: "agent unreachable", detail: String(err) }, { status: 200 });
  }
};
