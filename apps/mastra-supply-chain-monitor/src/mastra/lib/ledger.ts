// The monitor's memory between ticks. The server can sleep between a sweep and a collect,
// so everything a later tick needs lives here: every run ID the sweep started and the raw
// result once collected. Events, leads and start failures are in ledger-events.ts.
import { db, init, now } from "./db";

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

// Gives a claim back when planning failed before any run started, so the next trigger can sweep.
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
