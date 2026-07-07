import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Lightweight lead capture for the in-app "want to know more" form. Captures
// name + email (+ the category/brand they were viewing) and fans it out to:
//   1. the server log (always),
//   2. HubSpot (a Contact via the Forms Submission API) when configured,
//   3. LEAD_WEBHOOK_URL (Slack / Pipedream / Zapier) for an instant ping.
// No report generation here — pure lead capture.
export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as {
    firstName?: string;
    lastName?: string;
    company?: string;
    email?: string;
    keyword?: string;
    brand?: string;
  };
  const email = (body.email ?? "").trim();
  if (!EMAIL_RE.test(email)) {
    return json({ error: "Please enter a valid email." }, 400);
  }
  const firstName = (body.firstName ?? "").trim();
  const lastName = (body.lastName ?? "").trim();
  const company = (body.company ?? "").trim();
  const name = [firstName, lastName].filter(Boolean).join(" ");
  const keyword = (body.keyword ?? "").trim();
  const brand = (body.brand ?? "").trim();

  console.log(
    `[lead] ${name || "(no name)"} <${email}>${company ? ` @ ${company}` : ""}${keyword ? ` — "${keyword}"` : ""}${brand ? ` (brand: ${brand})` : ""}`,
  );

  // Forward to HubSpot + Slack in parallel; neither should block or fail the
  // user's submission (the lead is already logged above).
  await Promise.allSettled([
    forwardToHubSpot({ email, firstName, lastName, company }),
    forwardToSlack({ name, email, company, keyword, brand }),
  ]);

  return json({ ok: true });
}

// HubSpot Forms Submission API — creates/updates a Contact. No API key needed;
// it authenticates by portal + form GUID (the same IDs in the public embed).
async function forwardToHubSpot(d: {
  email: string;
  firstName: string;
  lastName: string;
  company: string;
}) {
  const portalId = process.env.HUBSPOT_PORTAL_ID;
  const formGuid = process.env.HUBSPOT_FORM_GUID;
  if (!portalId || !formGuid) return; // not configured → skip silently

  const region = process.env.HUBSPOT_REGION || "na1";
  const host = region === "na1" ? "api.hsforms.com" : `api-${region}.hsforms.com`;
  const url = `https://${host}/submissions/v3/integration/submit/${portalId}/${formGuid}`;

  // Only fields that exist on the form may be sent — these four map to standard
  // HubSpot contact properties (email/firstname/lastname/company).
  const fields: Array<{ name: string; value: string }> = [
    { name: "email", value: d.email },
  ];
  if (d.firstName) fields.push({ name: "firstname", value: d.firstName });
  if (d.lastName) fields.push({ name: "lastname", value: d.lastName });
  if (d.company) fields.push({ name: "company", value: d.company });

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fields,
        context: { pageName: "Nimble Retail Intelligence — Shoptalk" },
      }),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      console.error(`[lead] HubSpot submit failed (${res.status}): ${detail}`);
    }
  } catch (err) {
    console.error("[lead] HubSpot submit error:", err);
  }
}

// Optional instant ping (Slack incoming webhook / Pipedream / Zapier). The flat
// fields are included so non-Slack consumers can use the payload directly.
async function forwardToSlack(d: {
  name: string;
  email: string;
  company: string;
  keyword: string;
  brand: string;
}) {
  const webhook = process.env.LEAD_WEBHOOK_URL;
  if (!webhook) return;
  const ctx = [d.keyword && `“${d.keyword}”`, d.brand && `brand: ${d.brand}`]
    .filter(Boolean)
    .join(" · ");
  try {
    await fetch(webhook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: `🔔 New Shoptalk lead: ${d.name || "(no name)"}${d.company ? ` @ ${d.company}` : ""} <${d.email}>${ctx ? ` — ${ctx}` : ""}`,
        name: d.name,
        email: d.email,
        company: d.company || null,
        keyword: d.keyword || null,
        brand: d.brand || null,
        at: new Date().toISOString(),
      }),
    });
  } catch {
    /* non-blocking */
  }
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
