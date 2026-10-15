// Is this the event already on file? Matching, merging and diffing against the ledger.
import { normalizeUrl, RANK, union, type MonitoredEvent } from "./events";

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
    alertedStatus: target.alertedStatus,
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
