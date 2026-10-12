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

const RANK: Record<Confidence, number> = { low: 0, medium: 1, high: 2 };
// The fields that establish that an event happened. Exposures and impact are the agent's
// reading of the event against the watchlist, so they don't count toward "is it real".
const CORE_FIELDS = ["headline", "event_type", "location", "event_date"];

function lowest(grades: string[]): Confidence {
  const known = grades.filter((g): g is Confidence => g in RANK);
  if (!known.length) return "low";
  return known.reduce((a, b) => (RANK[b] < RANK[a] ? b : a));
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
    const core = own.filter((c) => CORE_FIELDS.some((f) => c.path === `$.events[${i}].${f}`));
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
      confidence: lowest((core.length ? core : own).map((c) => c.confidence ?? "")),
      citations: citationsFrom(own),
      runIds: [result.runId],
    };
    return { eventKey: eventKeyOf(e), ...e };
  });

  return { events, leads: body.unverified ?? [] };
}

// ── Same event? ───────────────────────────────────────────────────────────

const STOP = new Set(["the", "of", "and", "in", "at", "port", "province", "city", "near", "china", "region"]);

function words(s: string): Set<string> {
  return new Set(s.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 2 && !STOP.has(w)));
}

function overlap(a: string, b: string): number {
  const A = words(a);
  const B = words(b);
  if (!A.size || !B.size) return 0;
  let shared = 0;
  for (const w of A) if (B.has(w)) shared++;
  return shared / Math.min(A.size, B.size);
}

function daysApart(a: string, b: string): number {
  const d = Math.abs(Date.parse(a) - Date.parse(b)) / 86_400_000;
  return Number.isNaN(d) ? Infinity : d;
}

// Deterministic first pass. Anything this misses goes to the triage agent, which sees
// recent events and can mark a near-duplicate.
export function sameEvent(a: MonitoredEvent, b: MonitoredEvent): boolean {
  if (a.sourceUrl && b.sourceUrl && normalizeUrl(a.sourceUrl) === normalizeUrl(b.sourceUrl)) return true;
  return a.eventType === b.eventType && overlap(a.location, b.location) >= 0.5 && daysApart(a.eventDate, b.eventDate) <= 3;
}

function union<T>(a: T[], b: T[]): T[] {
  return [...new Set([...a, ...b])];
}

export function mergeInto(target: MonitoredEvent, other: MonitoredEvent): MonitoredEvent {
  const better = RANK[other.confidence] > RANK[target.confidence] ? other : target;
  const citations = new Map(target.citations.map((c) => [normalizeUrl(c.url), c]));
  for (const c of other.citations) if (!citations.has(normalizeUrl(c.url))) citations.set(normalizeUrl(c.url), c);
  return {
    ...better,
    eventKey: target.eventKey,
    exposures: union(target.exposures, other.exposures),
    products: union(target.products, other.products),
    citations: [...citations.values()],
    runIds: union(target.runIds, other.runIds),
    triage: target.triage,
  };
}

// One event reported by several products' runs becomes one event touching all of them.
export function mergeAcrossProducts(events: MonitoredEvent[]): MonitoredEvent[] {
  const merged: MonitoredEvent[] = [];
  for (const e of events) {
    const i = merged.findIndex((m) => sameEvent(m, e));
    if (i === -1) merged.push(e);
    else merged[i] = mergeInto(merged[i], e);
  }
  return merged;
}

export type Diff = {
  fresh: MonitoredEvent[]; // never reported before
  updates: MonitoredEvent[]; // reported before, status changed
  repeats: MonitoredEvent[]; // reported before, nothing new
};

export function diffAgainst(known: MonitoredEvent[], incoming: MonitoredEvent[]): Diff {
  const diff: Diff = { fresh: [], updates: [], repeats: [] };
  for (const e of incoming) {
    const prior = known.find((k) => sameEvent(k, e));
    if (!prior) {
      diff.fresh.push(e);
      continue;
    }
    const combined = mergeInto(prior, e);
    if (e.status && prior.status !== e.status) {
      diff.updates.push({ ...combined, status: e.status, previousStatus: prior.status });
    } else {
      diff.repeats.push(combined);
    }
  }
  return diff;
}
