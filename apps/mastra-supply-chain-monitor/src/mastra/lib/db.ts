// The ledger's connection and schema. Every ledger function awaits init() first, so the
// tables exist (and older ledgers are migrated) before the first query.
import { createClient, type Client } from "@libsql/client";
import { config } from "../config";

let client: Client | undefined;
let ready: Promise<void> | undefined;

export function db(): Client {
  client ??= createClient({ url: config.databaseUrl, authToken: config.databaseAuthToken });
  return client;
}

export async function init(): Promise<void> {
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
          alerted_at TEXT,
          alerted_status TEXT
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
    .then(() => db().execute("ALTER TABLE events ADD COLUMN alerted_status TEXT").catch(() => undefined))
    // Events alerted before alerted_status existed were alerted at their stored status.
    .then(() =>
      db().execute(
        "UPDATE events SET alerted_status = json_extract(json, '$.status') WHERE alerted_at IS NOT NULL AND alerted_status IS NULL",
      ),
    )
    // A retried collect tick must not list the same lead twice. Older ledgers may already
    // hold duplicates, which would block the index, so drop them first.
    .then(() => db().execute("DELETE FROM leads WHERE id NOT IN (SELECT MIN(id) FROM leads GROUP BY run_id, text)"))
    .then(() => db().execute("CREATE UNIQUE INDEX IF NOT EXISTS leads_run_text ON leads (run_id, text)"))
    .then(() => undefined)
    // Don't cache a failed setup: the next call tries again.
    .catch((err) => {
      ready = undefined;
      throw err;
    });
  return ready;
}

export const now = () => new Date().toISOString();
