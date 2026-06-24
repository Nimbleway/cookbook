import { ImageResponse } from "@vercel/og";
import { agentUrl, bridgeHeaders, useMock, MOCK_PACKAGE } from "$lib/server/agent";
import type { DeliveryPackage, VerdictCall } from "$lib/types";
import type { RequestHandler } from "./$types";

// Pin the same Vercel runtime as the rest of the app. @vercel/og (>=0.5) renders
// via bundled WASM on the Node runtime, so no edge function is needed.
export const config = { runtime: "nodejs22.x" };

// --- Palette (hex approximations of the oklch tokens in app.css; Satori can't
// parse oklch). Dark warm espresso surfaces + coral accent. ---
const BG = "#1b1410";
const SURFACE = "#241c15";
const SURFACE_LINE = "#2e251d";
const BORDER = "#3a312a";
const CORAL = "#e07a52";
const CORAL_BRIGHT = "#f2986e";
const TEXT_PRIMARY = "#f6f1ea";
const TEXT_SECONDARY = "#cabcab";
const TEXT_MUTED = "#9c9082";
const GREEN = "#5fc08c";
const AMBER = "#e2b94f";
const RED = "#db6c54";

const MONO = "ui-monospace, SFMono-Regular, Menlo, monospace";

// Build/pivot/pass → the shipment language used on the unbox stamp.
const STAMP: Record<VerdictCall, string> = {
  build: "DELIVERED",
  pivot: "RE-ROUTED",
  pass: "RETURNED",
};
const STAMP_COLOR: Record<VerdictCall, string> = {
  build: GREEN,
  pivot: AMBER,
  pass: RED,
};

// Tiny JSX-free element factory; Satori only needs { type, props:{ style, children } }.
type Node = { type: string; props: Record<string, unknown> };
function el(
  type: string,
  style: Record<string, unknown>,
  children?: Node | Node[] | string | (Node | string)[],
): Node {
  return { type, props: { style, children } };
}

function truncate(s: string, max: number): string {
  if (!s) return "";
  return s.length > max ? s.slice(0, max - 1).trimEnd() + "…" : s;
}

async function loadPackage(id: string): Promise<DeliveryPackage | null> {
  if (useMock()) {
    return { ...MOCK_PACKAGE, trackingId: id };
  }
  try {
    const res = await fetch(`${agentUrl()}/deliveries/${encodeURIComponent(id)}`, {
      headers: bridgeHeaders(),
    });
    if (!res.ok) return null;
    return (await res.json()) as DeliveryPackage;
  } catch {
    return null;
  }
}

function card(pkg: DeliveryPackage | null, fallbackId: string): Node {
  const brand = pkg?.brand?.trim() || "startup.delivery";
  const domain = pkg?.domain?.trim() || "your-startup.delivery";
  const dot = domain.lastIndexOf(".");
  const domainName = dot > 0 ? domain.slice(0, dot) : domain;
  const domainTld = dot > 0 ? domain.slice(dot) : "";
  const price =
    typeof pkg?.priceUsd === "number" ? `$${pkg.priceUsd.toFixed(2)}/yr` : "available";
  const call: VerdictCall = pkg?.verdict?.call ?? "build";
  const score = pkg?.verdict?.score;
  const verdictLabel = pkg
    ? `${call.toUpperCase()}${typeof score === "number" ? ` · ${score}/100` : ""}`
    : "ONE SENTENCE IN · PROOF OUT";
  const headline =
    pkg?.verdict?.headline?.trim() ||
    pkg?.positioningGap?.trim() ||
    "Live market recon, a real domain, and a launch-ready package — delivered in minutes.";
  const tracking = pkg?.trackingId?.trim() || fallbackId || "DEL-PENDING";

  return el(
    "div",
    {
      width: "1200px",
      height: "630px",
      display: "flex",
      flexDirection: "column",
      backgroundColor: BG,
      backgroundImage: `radial-gradient(1100px 520px at 78% -12%, rgba(224,122,82,0.22), transparent 60%)`,
      padding: "64px 72px",
      fontFamily: MONO,
      color: TEXT_PRIMARY,
    },
    [
      // Top row: wordmark + verdict stamp
      el(
        "div",
        { display: "flex", alignItems: "center", justifyContent: "space-between" },
        [
          el(
            "div",
            { display: "flex", alignItems: "center", fontSize: "30px", fontWeight: 700, letterSpacing: "-0.02em" },
            [
              el("span", { color: TEXT_PRIMARY }, "startup"),
              el("span", { color: CORAL }, "."),
              el("span", { color: TEXT_PRIMARY }, "delivery"),
            ],
          ),
          el(
            "div",
            {
              display: "flex",
              alignItems: "center",
              padding: "10px 22px",
              borderRadius: "9999px",
              border: `2px solid ${STAMP_COLOR[call]}`,
              color: STAMP_COLOR[call],
              fontSize: "24px",
              fontWeight: 700,
              letterSpacing: "0.14em",
              transform: "rotate(-3deg)",
            },
            pkg ? STAMP[call] : "INTAKE",
          ),
        ],
      ),

      // Middle: brand + domain
      el(
        "div",
        { display: "flex", flexDirection: "column", marginTop: "52px", flexGrow: 1 },
        [
          el(
            "div",
            { display: "flex", color: TEXT_MUTED, fontSize: "22px", letterSpacing: "0.18em", marginBottom: "8px" },
            "SECURED DELIVERY",
          ),
          // Domain thesis on the shared card: the namespace reframe travels with
          // every receipt that gets posted to Devpost / socials.
          el(
            "div",
            { display: "flex", color: CORAL, fontSize: "24px", fontWeight: 600, letterSpacing: "0.01em", marginBottom: "16px" },
            "we deliver startups, not dinner",
          ),
          el(
            "div",
            {
              display: "flex",
              fontSize: "104px",
              fontWeight: 700,
              letterSpacing: "-0.03em",
              lineHeight: 1,
              color: TEXT_PRIMARY,
            },
            truncate(brand, 22),
          ),
          // Domain chip (mono) + price
          el(
            "div",
            { display: "flex", alignItems: "center", marginTop: "30px" },
            [
              el(
                "div",
                {
                  display: "flex",
                  alignItems: "center",
                  backgroundColor: SURFACE,
                  border: `1px solid ${BORDER}`,
                  borderRadius: "14px",
                  padding: "16px 26px",
                  fontSize: "42px",
                  fontWeight: 600,
                },
                [
                  el("span", { color: TEXT_PRIMARY }, truncate(domainName, 26)),
                  el("span", { color: CORAL_BRIGHT }, domainTld),
                ],
              ),
              el(
                "div",
                { display: "flex", marginLeft: "22px", color: TEXT_SECONDARY, fontSize: "34px", fontWeight: 600 },
                price,
              ),
            ],
          ),
          // Verdict line + headline
          el(
            "div",
            { display: "flex", alignItems: "center", marginTop: "34px" },
            [
              el(
                "div",
                {
                  display: "flex",
                  color: STAMP_COLOR[call],
                  fontSize: "26px",
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  marginRight: "18px",
                },
                verdictLabel,
              ),
              el(
                "div",
                { display: "flex", color: TEXT_SECONDARY, fontSize: "26px", lineHeight: 1.25, flexShrink: 1 },
                truncate(headline, 86),
              ),
            ],
          ),
        ],
      ),

      // Footer: tracking number + delivered-by, separated by a torn-receipt rule
      el(
        "div",
        { display: "flex", flexDirection: "column", marginTop: "20px" },
        [
          el("div", { display: "flex", height: "1px", backgroundColor: SURFACE_LINE, marginBottom: "26px" }, ""),
          el(
            "div",
            { display: "flex", alignItems: "center", justifyContent: "space-between" },
            [
              el(
                "div",
                { display: "flex", alignItems: "center", color: TEXT_MUTED, fontSize: "26px", letterSpacing: "0.04em" },
                [
                  el("span", { color: TEXT_MUTED, marginRight: "12px" }, "TRACKING"),
                  el("span", { color: TEXT_PRIMARY, fontWeight: 700 }, truncate(tracking, 24)),
                ],
              ),
              el(
                "div",
                { display: "flex", alignItems: "center", color: TEXT_MUTED, fontSize: "24px" },
                [
                  // CSS-drawn parcel glyph (no emoji → no Satori CDN fetch at render time).
                  el(
                    "div",
                    {
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "26px",
                      height: "26px",
                      borderRadius: "5px",
                      border: `2px solid ${CORAL}`,
                      marginRight: "12px",
                    },
                    el("div", { display: "flex", width: "26px", height: "3px", backgroundColor: CORAL }, ""),
                  ),
                  el("span", {}, "Delivered by Startup.Delivery"),
                ],
              ),
            ],
          ),
        ],
      ),
    ],
  );
}

// A shipment tracking number: DEL-YYYYMMDD-XXXXXXXX. Only well-formed ids trigger
// the (expensive) bridge fetch + WASM render; anything else gets the cheap generic card.
// This stops an attacker from defeating the URL-keyed CDN cache with unique random
// ids to amplify a cheap request into a costly bridge call + image render.
const VALID_ID = /^DEL-\d{8}-(?:[A-Z0-9]{4}|[A-Z0-9]{8})$/i;

export const GET: RequestHandler = async ({ params }) => {
  const rawId = (params.id ?? "").trim();
  const valid = VALID_ID.test(rawId);

  const headers = {
    // Long crawler cache; deliveries are immutable once shipped.
    "cache-control": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800",
  };

  // Malformed ids never name a real delivery, so skip the (expensive) WASM render
  // entirely and point crawlers at the static homepage card. This stops an attacker
  // from defeating the URL-keyed CDN cache with unique junk ids to force a fresh
  // render per request.
  if (!valid) {
    return new Response(null, { status: 302, headers: { ...headers, location: "/og.png" } });
  }

  const safeId = rawId.toUpperCase();
  let pkg: DeliveryPackage | null = null;
  try {
    pkg = await loadPackage(rawId);
  } catch {
    pkg = null;
  }

  type OgElement = ConstructorParameters<typeof ImageResponse>[0];
  try {
    return new ImageResponse(card(pkg, safeId) as unknown as OgElement, {
      width: 1200,
      height: 630,
      headers,
    });
  } catch {
    // Fallback render — itself wrapped, so a Satori edge case can never 500.
    try {
      return new ImageResponse(card(null, safeId) as unknown as OgElement, {
        width: 1200,
        height: 630,
        headers,
      });
    } catch {
      // Absolute last resort: point crawlers at the static homepage card.
      return new Response(null, { status: 302, headers: { ...headers, location: "/og.png" } });
    }
  }
};
