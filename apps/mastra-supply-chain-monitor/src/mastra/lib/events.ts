// From a raw sweep result to events the monitor can act on.
//
// Every value in a sweep result has its own claim in `trust.claims`, keyed by JSON path
// (`$.events[2].location`). That is what lets each event carry its own citations and
// confidence, instead of inheriting one grade for the whole run.
import { productsTouchedBy } from "../watchlist";

export type Confidence = "high" | "medium" | "low";

export type Citation = {
  url: string;
  title?: string;
  sourceType?: string;
  sourceCategory?: string;
  excerpts: string[];
};

export type Triage = {
  severity: "critical" | "high" | "medium" | "low";
  rationale: string;
  recommendedAction: string;
};

export type MonitoredEvent = {
  eventKey: string;
  headline: string;
  eventType: string;
  summary: string;
  location: string;
  eventDate: string;
  status: string;
  expectedDuration: string | null;
  impactMechanism: string;
  sourceUrl: string;
  publishedAt: string;
  exposures: string[];
  products: string[];
  confidence: Confidence;
  citations: Citation[];
  runIds: string[];
  // Set when an already-reported event comes back with a different status.
  previousStatus?: string;
  triage?: Triage;
  // The status it was last alerted at. Read from the ledger, never from a run. An event
  // alerts again when its status changes, for example announced -> escalating.
  alertedStatus?: string;
};

type RawClaim = {
  path?: string;
  confidence?: string;
  citations?: Array<{
    url?: string;
    title?: string;
    source_type?: string;
    source_category?: string;
    excerpts?: string[] | null;
  }> | null;
};

type RawEvent = {
  headline?: string;
  event_type?: string;
  summary?: string;
  location?: string;
  affected_exposures?: string[];
  event_date?: string;
  status?: string;
  expected_duration?: string | null;
  impact_mechanism?: string;
  source_url?: string;
  published_at?: string;
};

export const RANK: Record<Confidence, number> = { low: 0, medium: 1, high: 2 };
// The fields that establish that an event happened. Exposures and impact are the agent's
// reading of the event against the watchlist, so they don't count toward "is it real".
const CORE_FIELDS = ["headline", "event_type", "location", "event_date"];

// `pre_existing` means the value came from the task input, not from research, so it is not
// evidence. Unknown or missing grades count as low.
function lowest(grades: string[]): Confidence {
  if (!grades.length) return "low";
  return grades
    .map((g): Confidence => (Object.hasOwn(RANK, g) ? (g as Confidence) : "low"))
    .reduce((a, b) => (RANK[b] < RANK[a] ? b : a));
}

export function union<T>(a: T[], b: T[]): T[] {
  return [...new Set([...a, ...b])];
}

export function normalizeUrl(url: string): string {
  try {
    const u = new URL(url);
    return `${u.hostname.replace(/^www\./, "")}${u.pathname.replace(/\/+$/, "")}`.toLowerCase();
  } catch {
    return url.trim().toLowerCase();
  }
}

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
}

export function eventKeyOf(e: { eventType: string; location: string; eventDate: string }): string {
  return `${slug(e.eventType)}|${slug(e.location)}|${e.eventDate}`;
}

// Claims for one event: every path under `$.events[i]`.
function claimsFor(claims: RawClaim[], i: number): RawClaim[] {
  const prefix = `$.events[${i}]`;
  return claims.filter((c) => c.path === prefix || c.path?.startsWith(`${prefix}.`) || c.path?.startsWith(`${prefix}[`));
}

function citationsFrom(claims: RawClaim[]): Citation[] {
  const byUrl = new Map<string, Citation>();
  for (const claim of claims) {
    for (const c of claim.citations ?? []) {
      if (!c.url) continue;
      const key = normalizeUrl(c.url);
      const existing = byUrl.get(key);
      const excerpts = (c.excerpts ?? []).filter(Boolean);
      if (existing) {
        existing.excerpts = [...new Set([...existing.excerpts, ...excerpts])];
      } else {
        byUrl.set(key, {
          url: c.url,
          // The API sometimes repeats the URL as the title; drop it so renderers fall back cleanly.
          title: c.title && c.title !== c.url && !c.title.startsWith("http") ? c.title : undefined,
          sourceType: c.source_type,
          sourceCategory: c.source_category,
          excerpts,
        });
      }
    }
  }
  return [...byUrl.values()];
}

// The completed-result payload the package returns (`ready: true`).
export type CompletedResult = {
  ready: true;
  runId: string;
  output: { type: "json" | "text"; json?: unknown; text?: string; trust?: { claims?: RawClaim[] } };
};

export function eventsFromResult(
  result: CompletedResult,
  productSlug: string,
): { events: MonitoredEvent[]; leads: string[] } {
  const body = (result.output.json ?? {}) as { events?: RawEvent[]; unverified?: string[] };
  const claims = result.output.trust?.claims ?? [];

  const events = (body.events ?? []).map((raw, i): MonitoredEvent => {
    const own = claimsFor(claims, i);
    // Every core field needs its own researched claim. A missing one grades the event low.
    const coreGrades = CORE_FIELDS.map((f) => {
      const forField = own.filter((c) => c.path === `$.events[${i}].${f}`);
      return forField.length ? lowest(forField.map((c) => c.confidence ?? "")) : "low";
    });
    const exposures = raw.affected_exposures ?? [];
    const e = {
      headline: raw.headline ?? "(no headline)",
      eventType: raw.event_type ?? "other",
      summary: raw.summary ?? "",
      location: raw.location ?? "",
      eventDate: raw.event_date ?? "",
      status: raw.status ?? "announced",
      expectedDuration: raw.expected_duration ?? null,
      impactMechanism: raw.impact_mechanism ?? "",
      sourceUrl: raw.source_url ?? "",
      publishedAt: raw.published_at ?? "",
      exposures,
      // The run's own product, plus every product that shares a touched exposure.
      products: union([productSlug], productsTouchedBy(exposures)),
      confidence: lowest(coreGrades),
      citations: citationsFrom(own),
      runIds: [result.runId],
    };
    return { eventKey: eventKeyOf(e), ...e };
  });

  return { events, leads: body.unverified ?? [] };
}
