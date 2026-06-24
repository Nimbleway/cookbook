import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, landingBuildEnabled, useMock } from "$lib/server/agent";

// Building just the landing page reuses cached recon + the claimed brand/domain,
// so it's cheaper than a full delivery — but still an LLM call, so allow headroom.
export const config = { maxDuration: 60 };

// Mirror the bridge's server-side cap (~250 KB). landingHtml is LLM-generated and
// only ever fed to a fully-sandboxed <iframe srcdoc>, but we still bound it so a
// runaway generation can't bloat the response.
const MAX_LANDING_HTML_BYTES = 250 * 1024;

function capLandingHtml(html: string): string {
  if (!html) return "";
  const encoded = new TextEncoder().encode(html);
  if (encoded.length <= MAX_LANDING_HTML_BYTES) return html;
  return new TextDecoder("utf-8").decode(encoded.slice(0, MAX_LANDING_HTML_BYTES));
}

// Small canned page so the mock path also renders a real srcdoc preview.
function mockLandingHtml(brand: string, domain: string): string {
  const safeBrand = brand.replace(/[<>&]/g, "");
  const safeDomain = domain.replace(/[<>&]/g, "");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${safeBrand}</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, system-ui, sans-serif; color: #0b1020;
    background: radial-gradient(1200px 600px at 50% -10%, #eef2ff, #fff); }
  .wrap { max-width: 720px; margin: 0 auto; padding: 96px 24px; text-align: center; }
  .pill { display: inline-block; font-size: 13px; letter-spacing: .04em; text-transform: uppercase;
    color: #4338ca; background: #e0e7ff; border-radius: 999px; padding: 6px 14px; }
  h1 { font-size: 48px; line-height: 1.05; margin: 20px 0 12px; }
  p { font-size: 18px; color: #475569; margin: 0 auto 28px; max-width: 540px; }
  .cta { display: inline-block; background: #4338ca; color: #fff; text-decoration: none;
    font-weight: 600; padding: 14px 26px; border-radius: 12px; }
  .domain { margin-top: 18px; font-size: 14px; color: #94a3b8; }
</style></head>
<body><main class="wrap">
  <span class="pill">Now in early access</span>
  <h1>${safeBrand}</h1>
  <p>The fastest way to get what you need, when you need it. Built for people who refuse to wait.</p>
  <a class="cta" href="#">Get early access</a>
  <div class="domain">${safeDomain}</div>
</main></body></html>`;
}

// Landing-only surface: builds ONLY the landing page for an already-delivered
// package (no new tracking id, no duplicate deliveries-log row). Proxies to the
// agent bridge's POST /build-landing.
export const POST: RequestHandler = async ({ request }) => {
  let body: { idea?: unknown; brand?: unknown; domain?: unknown };
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid request" }, { status: 400 });
  }

  const idea = typeof body.idea === "string" ? body.idea.trim() : "";
  const brand = typeof body.brand === "string" ? body.brand.trim() : "";
  const domain = typeof body.domain === "string" ? body.domain.trim() : "";
  if (!idea || !brand || !domain) {
    return json({ error: "idea, brand and domain are required" }, { status: 400 });
  }

  if (useMock()) {
    return json({
      landingHtml: capLandingHtml(mockLandingHtml(brand, domain)),
      landingUrl: `/deliveries/${domain.toLowerCase()}/index.html`,
    });
  }

  if (!landingBuildEnabled()) {
    return json({ error: "landing build is disabled on this deploy" }, { status: 403 });
  }

  try {
    const res = await fetch(`${agentUrl()}/build-landing`, {
      method: "POST",
      headers: { "content-type": "application/json", ...bridgeHeaders() },
      body: JSON.stringify({ idea, brand, domain }),
    });
    if (!res.ok) {
      console.error(`[build-landing] bridge ${res.status}: ${await res.text()}`);
      return json({ error: "build landing failed" }, { status: res.status });
    }
    const data = await res.json();

    // landingHtml drives the hostless sandboxed srcdoc preview (works on Vercel —
    // no file hosting needed). Treat it as an opaque string: capped here and only
    // ever passed to a fully-sandboxed <iframe srcdoc>, never injected into the DOM.
    const landingHtml =
      typeof data.landingHtml === "string" ? capLandingHtml(data.landingHtml) : "";

    // landingUrl stays for back-compat (local dev where the file is served same-origin).
    const landingUrl = typeof data.landingUrl === "string" ? data.landingUrl.trim() : "";
    // Allowlist (mirrors landingHref's accepted set): root-relative "/deliveries/…"
    // or an http(s) absolute URL (collapsed to same-origin client-side). Anything else
    // — file:/javascript:/data:/mailto:/protocol-relative "//" — is rejected (-> null).
    const rootRelative = landingUrl.startsWith("/") && !landingUrl.startsWith("//");
    const httpAbsolute = /^https?:\/\//i.test(landingUrl);
    const safeUrl = landingUrl && (rootRelative || httpAbsolute) ? landingUrl : null;

    // With srcdoc, a missing/rejected url is fine as long as we have the html. Only
    // fail when neither preview source is usable.
    if (!landingHtml && !safeUrl) {
      return json({ error: "landing page unavailable on this deploy" }, { status: 502 });
    }
    return json({ landingHtml, landingUrl: safeUrl });
  } catch (err) {
    console.error(`[build-landing] agent unreachable: ${String(err)}`);
    return json({ error: "build landing failed" }, { status: 502 });
  }
};
