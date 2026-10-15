// What the monitor found and reported: events, leads, and runs that failed to start. The
// collect workflow writes these; the digest and the investigator read them.
import type { MonitoredEvent } from "./events";
import { db, init, now } from "./db";

// ── Events ────────────────────────────────────────────────────────────────

export async function recentEvents(days = 14): Promise<MonitoredEvent[]> {
  await init();
  const since = new Date(Date.now() - days * 86_400_000).toISOString();
  const r = await db().execute({
    sql: "SELECT json, alerted_status FROM events WHERE last_seen_at >= ? ORDER BY last_seen_at DESC",
    args: [since],
  });
  return r.rows.map((row) => ({
    ...(JSON.parse(row.json as string) as MonitoredEvent),
    alertedStatus: (row.alerted_status as string | null) ?? undefined,
  }));
}

// `changed` is true for a new event or a status change, false for a repeat sighting.
export async function upsertEvent(e: MonitoredEvent, changed: boolean): Promise<void> {
  await init();
  const at = now();
  await db().execute({
    sql: `INSERT INTO events (event_key, json, first_seen_at, last_seen_at, changed_at) VALUES (?, ?, ?, ?, ?)
          ON CONFLICT(event_key) DO UPDATE SET json = excluded.json, last_seen_at = excluded.last_seen_at,
            changed_at = CASE WHEN ? THEN excluded.changed_at ELSE events.changed_at END`,
    args: [e.eventKey, JSON.stringify(e), at, at, at, changed ? 1 : 0],
  });
}

export async function markAlerted(eventKey: string, status: string): Promise<void> {
  await init();
  await db().execute({
    sql: "UPDATE events SET alerted_at = ?, alerted_status = ? WHERE event_key = ?",
    args: [now(), status, eventKey],
  });
}

// Events that were new, or changed status, on this date.
export async function eventsChangedOn(date: string): Promise<MonitoredEvent[]> {
  await init();
  const r = await db().execute({
    sql: "SELECT json FROM events WHERE substr(changed_at, 1, 10) = ? ORDER BY changed_at",
    args: [date],
  });
  return r.rows.map((row) => JSON.parse(row.json as string) as MonitoredEvent);
}

// ── Start failures ────────────────────────────────────────────────────────

export async function recordStartFailure(product: string, createOutcome: string, message: string): Promise<void> {
  await init();
  await db().execute({
    sql: "INSERT INTO start_failures (product, at, create_outcome, message) VALUES (?, ?, ?, ?)",
    args: [product, now(), createOutcome, message],
  });
}

// ── Leads (a run's `unverified` list: things it saw but could not confirm) ─────

export async function recordLeads(runId: string, product: string, leads: string[]): Promise<void> {
  if (!leads.length) return;
  await init();
  const at = now();
  await db().batch(
    leads.map((text) => ({
      sql: "INSERT OR IGNORE INTO leads (run_id, product, text, seen_at) VALUES (?, ?, ?, ?)",
      args: [runId, product, text, at],
    })),
    "write",
  );
}

export async function leadsOn(date: string) {
  await init();
  const r = await db().execute({
    sql: "SELECT product, text FROM leads WHERE substr(seen_at, 1, 10) = ? ORDER BY id",
    args: [date],
  });
  return r.rows.map((row) => ({ product: row.product as string, text: row.text as string }));
}

export async function startFailuresOn(date: string) {
  await init();
  const r = await db().execute({
    sql: "SELECT product, create_outcome, message FROM start_failures WHERE substr(at, 1, 10) = ?",
    args: [date],
  });
  return r.rows.map((row) => ({ ...row }));
}
