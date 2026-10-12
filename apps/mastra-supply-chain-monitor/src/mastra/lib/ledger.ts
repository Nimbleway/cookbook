// The monitor's memory between ticks. The server can sleep between a sweep and a collect,
// so everything a later tick needs lives here: every run ID the sweep started, the raw
// result once collected, and every event already reported.
import { createClient, type Client } from "@libsql/client";
import { config } from "../config";
import type { MonitoredEvent } from "./events";

let client: Client | undefined;
let ready: Promise<void> | undefined;

function db(): Client {
  client ??= createClient({ url: config.databaseUrl, authToken: config.databaseAuthToken });
  return client;
}

async function init(): Promise<void> {
  ready ??= db()
    .batch(
      [
        `CREATE TABLE IF NOT EXISTS sweeps (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          started_at TEXT NOT NULL,
          live INTEGER NOT NULL
        )`,
        `CREATE TABLE IF NOT EXISTS runs (
          run_id TEXT PRIMARY KEY,
          product TEXT NOT NULL,
          window_start TEXT NOT NULL,
          window_end TEXT NOT NULL,
          started_at TEXT NOT NULL,
          state TEXT NOT NULL,          -- pending | collecting | collected | failed
          claimed_at TEXT,              -- when a collect tick took it; stale claims are retried
          collected_at TEXT,
          raw_json TEXT,                -- the result exactly as returned, saved before any transform
          error TEXT
        )`,
        `CREATE TABLE IF NOT EXISTS start_failures (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product TEXT NOT NULL,
          at TEXT NOT NULL,
          create_outcome TEXT NOT NULL, -- not-created | unknown
          message TEXT NOT NULL
        )`,
        `CREATE TABLE IF NOT EXISTS events (
          event_key TEXT PRIMARY KEY,
          json TEXT NOT NULL,           -- the MonitoredEvent
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          changed_at TEXT NOT NULL,     -- first seen, or last status change: what the digest reports
          alerted_at TEXT
        )`,
        `CREATE TABLE IF NOT EXISTS leads (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          run_id TEXT NOT NULL,
          product TEXT NOT NULL,
          text TEXT NOT NULL,
          seen_at TEXT NOT NULL
        )`,
      ],
      "write",
    )
    // Ledgers created before claimed_at existed get the column added; the error on a
    // ledger that already has it is expected.
    .then(() => db().execute("ALTER TABLE runs ADD COLUMN claimed_at TEXT").catch(() => undefined))
    // A retried collect tick must not list the same lead twice.
    .then(() => db().execute("CREATE UNIQUE INDEX IF NOT EXISTS leads_run_text ON leads (run_id, text)"))
    .then(() => undefined);
  return ready;
}

const now = () => new Date().toISOString();

// ── Sweeps ────────────────────────────────────────────────────────────────

// Claims the right to start a sweep, atomically: the insert happens only if no sweep
// started within the last `minMinutes`. Two overlapping requests can't both pass.
// Returns the start time, or undefined if refused.
export async function claimSweep(live: boolean, minMinutes: number, force = false): Promise<string | undefined> {
  await init();
  const at = now();
  const since = new Date(Date.now() - minMinutes * 60_000).toISOString();
  const r = force
    ? await db().execute({ sql: "INSERT INTO sweeps (started_at, live) VALUES (?, ?)", args: [at, live ? 1 : 0] })
    : await db().execute({
        sql: `INSERT INTO sweeps (started_at, live)
              SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM sweeps WHERE started_at > ?)`,
        args: [at, live ? 1 : 0, since],
      });
  return r.rowsAffected === 1 ? at : undefined;
}

// Gives a claim back when planning failed before any run started, so a retry can sweep.
export async function releaseSweep(startedAt: string): Promise<void> {
  await init();
  await db().execute({ sql: "DELETE FROM sweeps WHERE started_at = ?", args: [startedAt] });
}

export async function lastSweepStartedAt(): Promise<string | undefined> {
  await init();
  const r = await db().execute("SELECT started_at FROM sweeps ORDER BY id DESC LIMIT 1");
  return r.rows[0]?.started_at as string | undefined;
}

// ── Runs ──────────────────────────────────────────────────────────────────

export type RunRow = {
  runId: string;
  product: string;
  windowStart: string;
  windowEnd: string;
  startedAt: string;
};

// A collect tick that dies mid-way leaves its runs claimed; after this long another tick
// may take them over. Results stay fetchable, so nothing is lost.
const STALE_CLAIM_MINUTES = 15;
const staleBefore = () => new Date(Date.now() - STALE_CLAIM_MINUTES * 60_000).toISOString();

export async function recordRunStarted(r: RunRow): Promise<void> {
  await init();
  await db().execute({
    sql: `INSERT OR IGNORE INTO runs (run_id, product, window_start, window_end, started_at, state)
          VALUES (?, ?, ?, ?, ?, 'pending')`,
    args: [r.runId, r.product, r.windowStart, r.windowEnd, r.startedAt],
  });
}

export async function recordStartFailure(product: string, createOutcome: string, message: string): Promise<void> {
  await init();
  await db().execute({
    sql: "INSERT INTO start_failures (product, at, create_outcome, message) VALUES (?, ?, ?, ?)",
    args: [product, now(), createOutcome, message],
  });
}

// Runs a collect tick could take: pending, or claimed by a tick that never finished.
export async function collectableRuns(): Promise<RunRow[]> {
  await init();
  const r = await db().execute({
    sql: `SELECT run_id, product, window_start, window_end, started_at FROM runs
          WHERE state = 'pending' OR (state = 'collecting' AND claimed_at < ?) ORDER BY started_at`,
    args: [staleBefore()],
  });
  return r.rows.map((row) => ({
    runId: row.run_id as string,
    product: row.product as string,
    windowStart: row.window_start as string,
    windowEnd: row.window_end as string,
    startedAt: row.started_at as string,
  }));
}

// Takes a run for this tick, atomically. False means another tick has it.
export async function claimRun(runId: string): Promise<boolean> {
  await init();
  const r = await db().execute({
    sql: `UPDATE runs SET state = 'collecting', claimed_at = ?
          WHERE run_id = ? AND (state = 'pending' OR (state = 'collecting' AND claimed_at < ?))`,
    args: [now(), runId, staleBefore()],
  });
  return r.rowsAffected === 1;
}

// Not finished yet: hand it back for the next tick.
export async function releaseRun(runId: string): Promise<void> {
  await init();
  await db().execute({
    sql: "UPDATE runs SET state = 'pending', claimed_at = NULL WHERE run_id = ? AND state = 'collecting'",
    args: [runId],
  });
}

// The raw result, saved before any transform. The run stays claimed until its events are
// recorded (markCollected), so a tick that fails part-way leaves it to be retried.
export async function saveRaw(runId: string, raw: unknown): Promise<void> {
  await init();
  await db().execute({ sql: "UPDATE runs SET raw_json = ? WHERE run_id = ?", args: [JSON.stringify(raw), runId] });
}

export async function markCollected(runIds: string[]): Promise<void> {
  if (!runIds.length) return;
  await init();
  const at = now();
  await db().batch(
    runIds.map((runId) => ({
      sql: "UPDATE runs SET state = 'collected', collected_at = ? WHERE run_id = ?",
      args: [at, runId],
    })),
    "write",
  );
}

export async function markFailed(runId: string, error: string): Promise<void> {
  await init();
  await db().execute({
    sql: "UPDATE runs SET state = 'failed', collected_at = ?, error = ? WHERE run_id = ?",
    args: [now(), error, runId],
  });
}

// The newest window_end already researched for a product; the next sweep starts from there.
export async function lastWindowEnd(product: string): Promise<string | undefined> {
  await init();
  const r = await db().execute({
    sql: "SELECT window_end FROM runs WHERE product = ? AND state != 'failed' ORDER BY started_at DESC LIMIT 1",
    args: [product],
  });
  return r.rows[0]?.window_end as string | undefined;
}

export async function recentRuns(limit = 20) {
  await init();
  const r = await db().execute({
    sql: "SELECT run_id, product, window_start, window_end, started_at, state, error FROM runs ORDER BY started_at DESC LIMIT ?",
    args: [limit],
  });
  return r.rows.map((row) => ({ ...row }));
}

// ── Events ────────────────────────────────────────────────────────────────

export async function recentEvents(days = 14): Promise<MonitoredEvent[]> {
  await init();
  const since = new Date(Date.now() - days * 86_400_000).toISOString();
  const r = await db().execute({
    sql: "SELECT json, alerted_at FROM events WHERE last_seen_at >= ? ORDER BY last_seen_at DESC",
    args: [since],
  });
  return r.rows.map((row) => ({
    ...(JSON.parse(row.json as string) as MonitoredEvent),
    alertedAt: (row.alerted_at as string | null) ?? undefined,
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

export async function markAlerted(eventKey: string): Promise<void> {
  await init();
  await db().execute({ sql: "UPDATE events SET alerted_at = ? WHERE event_key = ?", args: [now(), eventKey] });
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
