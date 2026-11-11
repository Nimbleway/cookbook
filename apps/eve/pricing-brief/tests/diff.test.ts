import { describe, expect, it } from "vitest";
import { carryForward, diffPlans } from "../agent/lib/diff";
import { normalizePlans } from "../agent/lib/normalize";
import type { Plan } from "../agent/lib/plans";

const plan = (over: Partial<Plan>): Plan => ({
  limits: [],
  name: null,
  price: null,
  starting_at: false,
  ...over,
});
const usd = (amount: number, period: "month" | "year" = "month") => ({ amount, currency: "USD", period });
const diff = (a: Plan[], b: Plan[]) => diffPlans(normalizePlans(a), normalizePlans(b));

describe("named plans (Resend-style)", () => {
  const before = [
    plan({ name: "Pro", price: usd(20) }),
    plan({ name: "Free", price: usd(0) }),
  ];

  it("reports nothing when only name case, spacing or plan order differ", () => {
    const after = [
      plan({ name: "free", price: usd(0) }),
      plan({ name: " Pro ", price: usd(20) }),
    ];
    expect(diff(before, after)).toEqual({ changes: [], unknown: [] });
  });

  it("reports a price change by plan name", () => {
    const after = [plan({ name: "Pro", price: usd(25) }), before[1]];
    expect(diff(before, after).changes).toEqual([{ from: "$20/mo", kind: "price", plan: "Pro", to: "$25/mo" }]);
  });

  it("reports a billing-period change instead of a price change", () => {
    const after = [plan({ name: "Pro", price: usd(240, "year") }), before[1]];
    expect(diff(before, after).changes).toEqual([
      { from: "$20/mo", kind: "billing_period", plan: "Pro", to: "$240/yr" },
    ]);
  });

  it("reports plans added and removed", () => {
    const after = [before[0], plan({ name: "Scale", price: usd(90) })];
    expect(diff(before, after).changes).toEqual([
      { kind: "plan_added", plan: "Scale" },
      { kind: "plan_removed", plan: "Free" },
    ]);
  });
});

describe("nameless plans (Postmark-style)", () => {
  const before = [plan({ price: usd(15) }), plan({ price: usd(16.5) }), plan({ price: usd(18) })];

  it("matches plans by page position and labels them by price", () => {
    const after = [plan({ price: usd(18) }), plan({ price: usd(16.5) }), plan({ price: usd(18) })];
    expect(diff(before, after).changes).toEqual([
      { from: "$15/mo", kind: "price", plan: "$15/mo plan", to: "$18/mo" },
    ]);
  });
});

describe("gaps in a read never alert", () => {
  it("treats a missing price or limits as unknown", () => {
    const before = [plan({ limits: [{ amount: 50_000, metric: "Emails", per: "month" }], name: "Essentials", price: usd(19.95) })];
    const after = [plan({ name: "Essentials" })];
    expect(diff(before, after)).toEqual({
      changes: [],
      unknown: ["Essentials: price", "Essentials: limits"],
    });
  });

  it("compares limits only when both reads show them (SendGrid-style slider)", () => {
    const before = [plan({ name: "Essentials", price: usd(19.95), starting_at: true })];
    const after = [plan({ limits: [{ amount: 50_000, metric: "emails", per: "month" }], name: "Essentials", price: usd(19.95), starting_at: true })];
    expect(diff(before, after).changes).toEqual([]);
  });

  it("reports a limit change when both reads show it", () => {
    const before = [plan({ limits: [{ amount: 10_000, metric: "emails", per: "month" }], name: "Basic", price: usd(15) })];
    const after = [plan({ limits: [{ amount: 15_000, metric: "Emails", per: "month" }], name: "Basic", price: usd(15) })];
    expect(diff(before, after).changes).toEqual([
      { from: "10,000 emails/month", kind: "limit", metric: "emails", plan: "Basic", to: "15,000 emails/month" },
    ]);
  });
});

describe("normalizePlans", () => {
  it("rounds prices and upper-cases currency", () => {
    const [p] = normalizePlans([plan({ price: { amount: 19.954, currency: "usd", period: "month" } })]);
    expect(p.price).toEqual({ amount: 19.95, currency: "USD", period: "month" });
  });

  it("keeps the page's plan order", () => {
    const out = normalizePlans([plan({ name: "Enterprise" }), plan({ name: "Pro", price: usd(20) }), plan({ name: "Free", price: usd(0) })]);
    expect(out.map((p) => p.name)).toEqual(["Enterprise", "Pro", "Free"]);
  });
});

describe("review fixes", () => {
  it("reports a switch to 'starting at' as a price change", () => {
    const before = [plan({ name: "Pro", price: usd(20) })];
    const after = [plan({ name: "Pro", price: usd(20), starting_at: true })];
    expect(diff(before, after).changes).toEqual([{ from: "$20/mo", kind: "price", plan: "Pro", to: "from $20/mo" }]);
  });

  it("reports limits added and removed", () => {
    const before = [plan({ name: "Pro", limits: [{ amount: 100, metric: "emails", per: "day" }] })];
    const after = [
      plan({
        name: "Pro",
        limits: [
          { amount: 100, metric: "emails", per: "day" },
          { amount: 5, metric: "domains", per: "month" },
        ],
      }),
    ];
    expect(diff(before, after).changes).toEqual([
      { from: "none", kind: "limit", metric: "domains", plan: "Pro", to: "5 domains/month" },
    ]);
    expect(diff(after, before).changes).toEqual([
      { from: "5 domains/month", kind: "limit", metric: "domains", plan: "Pro", to: "none" },
    ]);
  });

  it("keeps the last known price through a partial read, so the next change still alerts", () => {
    const day1 = normalizePlans([plan({ name: "Growth", price: usd(29) })]);
    const day2Read = normalizePlans([plan({ name: "Growth", price: null })]);
    expect(diffPlans(day1, day2Read)).toEqual({ changes: [], unknown: ["Growth: price"] });
    const day2Stored = carryForward(day1, day2Read);
    const day3 = normalizePlans([plan({ name: "Growth", price: usd(25) })]);
    expect(diffPlans(day2Stored, day3).changes).toEqual([
      { from: "$29/mo", kind: "price", plan: "Growth", to: "$25/mo" },
    ]);
  });
});
