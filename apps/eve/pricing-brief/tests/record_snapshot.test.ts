import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Snapshot } from "../agent/lib/db";
import type { Plan } from "../agent/lib/plans";

// The db layer is stubbed: these tests cover the tool's save-and-compare flow.
const db = vi.hoisted(() => ({
  findCompetitor: vi.fn(),
  insertSnapshotIfLatest: vi.fn(),
  latestSnapshot: vi.fn(),
}));
vi.mock("../agent/lib/db", () => db);

const { default: recordSnapshot } = await import("../agent/tools/record_snapshot");

const growth = (amount: number): Plan => ({
  limits: [],
  name: "Growth",
  price: { amount, currency: "USD", period: "month" },
  starting_at: false,
});
const input = (plans: Plan[]) => ({ competitor: "Acme Mail", plans, source_url: "https://acme.test/pricing" });
// The tool doesn't use its session context.
const run = (plans: Plan[]) => recordSnapshot.execute(input(plans), {} as never);
const snapshot = (plans: Plan[]): Snapshot => ({
  id: 1,
  plans,
  read_at: "2026-11-10T13:00:00Z",
  source_url: "https://acme.test/pricing",
});

describe("record_snapshot", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    db.findCompetitor.mockResolvedValue({ id: 7, name: "Acme Mail", pricing_url: "https://acme.test/pricing" });
    db.insertSnapshotIfLatest.mockResolvedValue("2026-11-11T13:00:00.000Z");
  });

  it("stores the first read as a baseline with no changes", async () => {
    db.latestSnapshot.mockResolvedValue(undefined);
    const result = await run([growth(29)]);
    expect(result).toMatchObject({ baseline: true, changes: [] });
    expect(db.insertSnapshotIfLatest).toHaveBeenCalledWith(7, "https://acme.test/pricing", [growth(29)], null);
  });

  it("returns a price change against the previous read", async () => {
    db.latestSnapshot.mockResolvedValue(snapshot([growth(29)]));
    const result = await run([growth(25)]);
    expect(result).toMatchObject({
      baseline: false,
      changes: [{ from: "$29/mo", kind: "price", plan: "Growth", to: "$25/mo" }],
    });
  });

  it("gives up with an error when overlapping checks keep saving first", async () => {
    db.latestSnapshot.mockResolvedValue(snapshot([growth(29)]));
    db.insertSnapshotIfLatest.mockResolvedValue(null);
    const result = await run([growth(25)]);
    expect(result).toEqual({ error: "Another check of Acme Mail is saving at the same time. Try again shortly." });
    expect(db.insertSnapshotIfLatest).toHaveBeenCalledTimes(3);
  });
});
