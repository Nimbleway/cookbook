import { neon } from "@neondatabase/serverless";
import type { Plan } from "./plans";

/**
 * Postgres access. Snapshots must outlive sessions, so they live here rather
 * than in session state. `DATABASE_URL` comes from the Neon integration.
 */
const sql = () => {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("DATABASE_URL is not set. Add a Postgres database (e.g. Neon) to the Vercel project.");
  }
  return neon(url);
};

let schemaReady: Promise<void> | undefined;

/** Creates the two tables on first use, so there is no separate migration step. */
export function ensureSchema(): Promise<void> {
  schemaReady ??= (async () => {
    const q = sql();
    await q`CREATE TABLE IF NOT EXISTS competitors (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      pricing_url TEXT NOT NULL,
      added_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )`;
    await q`CREATE TABLE IF NOT EXISTS snapshots (
      id SERIAL PRIMARY KEY,
      competitor_id INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
      read_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      source_url TEXT NOT NULL,
      plans JSONB NOT NULL
    )`;
    await q`CREATE INDEX IF NOT EXISTS snapshots_latest ON snapshots (competitor_id, read_at DESC)`;
  })().catch((error) => {
    schemaReady = undefined; // retry on the next call instead of caching the failure
    throw error;
  });
  return schemaReady;
}

export interface Competitor {
  id: number;
  name: string;
  pricing_url: string;
}

/**
 * Adds a competitor, or updates its pricing URL if the name is already tracked.
 * Names match case-insensitively, like every other lookup here.
 */
export async function upsertCompetitor(name: string, pricingUrl: string): Promise<Competitor> {
  await ensureSchema();
  const updated = await sql()`UPDATE competitors SET pricing_url = ${pricingUrl}
    WHERE lower(name) = lower(${name}) RETURNING id, name, pricing_url`;
  if (updated[0]) {
    return updated[0] as Competitor;
  }
  const rows = await sql()`INSERT INTO competitors (name, pricing_url) VALUES (${name}, ${pricingUrl})
    ON CONFLICT (name) DO UPDATE SET pricing_url = EXCLUDED.pricing_url
    RETURNING id, name, pricing_url`;
  return rows[0] as Competitor;
}

export async function listCompetitors(): Promise<Competitor[]> {
  await ensureSchema();
  return (await sql()`SELECT id, name, pricing_url FROM competitors ORDER BY name`) as Competitor[];
}

export async function findCompetitor(name: string): Promise<Competitor | undefined> {
  await ensureSchema();
  const rows = await sql()`SELECT id, name, pricing_url FROM competitors WHERE lower(name) = lower(${name})`;
  return rows[0] as Competitor | undefined;
}

export async function removeCompetitor(name: string): Promise<boolean> {
  await ensureSchema();
  const rows = await sql()`DELETE FROM competitors WHERE lower(name) = lower(${name}) RETURNING id`;
  return rows.length > 0;
}

export interface Snapshot {
  id: number;
  plans: Plan[];
  read_at: string;
  source_url: string;
}

export async function latestSnapshot(competitorId: number): Promise<Snapshot | undefined> {
  await ensureSchema();
  const rows = await sql()`SELECT id, plans, read_at, source_url FROM snapshots
    WHERE competitor_id = ${competitorId} ORDER BY id DESC LIMIT 1`;
  return rows[0] as Snapshot | undefined;
}

/**
 * Inserts a snapshot only if no newer one was saved since `previousId` was
 * read. A per-competitor lock serializes overlapping checks, so the second
 * one sees the first's row, gets null back and compares again. Returns the
 * read time, or null when it lost the race.
 */
export async function insertSnapshotIfLatest(
  competitorId: number,
  sourceUrl: string,
  plans: Plan[],
  previousId: number | null
): Promise<string | null> {
  await ensureSchema();
  const q = sql();
  const [, rows] = await q.transaction([
    q`SELECT pg_advisory_xact_lock(${competitorId})`,
    q`INSERT INTO snapshots (competitor_id, source_url, plans)
      SELECT ${competitorId}, ${sourceUrl}, ${JSON.stringify(plans)}::jsonb
      WHERE NOT EXISTS (SELECT 1 FROM snapshots WHERE competitor_id = ${competitorId} AND id > ${previousId ?? 0})
      RETURNING read_at`,
  ]);
  const row = rows[0] as { read_at: string } | undefined;
  return row ? new Date(row.read_at).toISOString() : null;
}
