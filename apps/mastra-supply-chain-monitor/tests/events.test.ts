// Pure logic: turning a real sweep result into events, merging, diffing, alert rules.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { diffAgainst, eventsFromResult, mergeAcrossProducts, type MonitoredEvent } from "../src/mastra/lib/events";
import { digestMarkdown, shouldAlert, slackMessage } from "../src/mastra/lib/notify";

// A real result from a live smoke run (laptop, 2026-10-05 to 2026-10-12, medium effort).
const real = JSON.parse(readFileSync("tests/fixtures/sweep_laptop_smoke.json", "utf8"));

test("a real result becomes events with their own citations and confidence", () => {
  const { events, leads } = eventsFromResult(real, "laptop");
  assert.equal(events.length, 1);
  const [e] = events;
  assert.match(e.headline, /blank sailings/i);
  assert.deepEqual(e.exposures, ["ocean freight Kaohsiung to Los Angeles/Long Beach"]);
  assert.deepEqual(e.products, ["laptop"]);
  // Echoed top-level fields grade low with no citations; they must not drag the event down.
  assert.equal(e.confidence, "high");
  assert.ok(e.citations.length >= 1);
  assert.ok(e.citations.every((c) => c.url.startsWith("https://")));
  // Leads stay leads.
  assert.equal(leads.length, 4);
});

function ev(over: Partial<MonitoredEvent>): MonitoredEvent {
  return {
    eventKey: "k",
    headline: "h",
    eventType: "export_control",
    summary: "",
    location: "China",
    eventDate: "2026-10-09",
    status: "announced",
    expectedDuration: null,
    impactMechanism: "",
    sourceUrl: "https://example.com/a",
    publishedAt: "2026-10-09",
    exposures: [],
    products: ["laptop"],
    confidence: "high",
    citations: [],
    runIds: ["r1"],
    ...over,
  };
}

test("an exposure shared by two products maps the event to both", () => {
  const result = {
    ready: true as const,
    runId: "r",
    output: {
      type: "json" as const,
      json: {
        events: [
          {
            headline: "Licensing tightened for magnet exports",
            event_type: "export_control",
            location: "China",
            affected_exposures: ["NdFeB rare-earth magnets (China)"],
            event_date: "2026-10-09",
            source_url: "https://example.com/m",
          },
        ],
      },
      trust: { claims: [] },
    },
  };
  const [e] = eventsFromResult(result, "earbuds").events;
  assert.deepEqual(e.products.sort(), ["earbuds", "laptop"]);
  assert.equal(e.confidence, "low"); // no claims at all: never alert on it
});

test("the same event found by two products' runs merges into one", () => {
  const merged = mergeAcrossProducts([
    ev({ eventKey: "a", products: ["laptop"], runIds: ["r1"] }),
    ev({ eventKey: "b", products: ["earbuds"], runIds: ["r2"], sourceUrl: "https://www.example.com/a/" }),
  ]);
  assert.equal(merged.length, 1);
  assert.deepEqual(merged[0].products.sort(), ["earbuds", "laptop"]);
  assert.deepEqual(merged[0].runIds.sort(), ["r1", "r2"]);
});

test("diff: new, repeat, and status change", () => {
  const known = [ev({ eventKey: "known", status: "announced" })];
  const diff = diffAgainst(known, [
    ev({ eventKey: "x", status: "announced" }), // same event, same status
    ev({ eventKey: "y", sourceUrl: "https://example.com/other", eventType: "port_disruption", location: "Port of Long Beach" }),
  ]);
  assert.equal(diff.repeats.length, 1);
  assert.equal(diff.repeats[0].eventKey, "known");
  assert.equal(diff.fresh.length, 1);

  const escalated = diffAgainst(known, [ev({ eventKey: "z", status: "escalating" })]);
  assert.equal(escalated.updates.length, 1);
  assert.equal(escalated.updates[0].previousStatus, "announced");
  assert.equal(escalated.updates[0].eventKey, "known");
});

test("alert only on serious, sourced events", () => {
  const triage = { rationale: "r", recommendedAction: "a" };
  assert.equal(shouldAlert(ev({ triage: { severity: "critical", ...triage } })), true);
  assert.equal(shouldAlert(ev({ triage: { severity: "high", ...triage }, confidence: "low" })), false);
  assert.equal(shouldAlert(ev({ triage: { severity: "medium", ...triage } })), false);
  assert.equal(shouldAlert(ev({})), false); // untriaged
});

test("slack message renders sources from trust, digest groups by severity", () => {
  const e = ev({
    headline: "Magnet licensing",
    triage: { severity: "high", rationale: "single source", recommendedAction: "check cover" },
    citations: [{ url: "https://www.reuters.com/x", sourceType: "primary", sourceCategory: "news", excerpts: [] }],
  });
  const msg = slackMessage(e);
  assert.match(msg, /HIGH · Magnet licensing/);
  assert.match(msg, /<https:\/\/www\.reuters\.com\/x\|reuters\.com> \(primary, news\)/);

  const md = digestMarkdown({
    date: "2026-10-12",
    events: [e, ev({ headline: "Untriaged one" }), ev({ headline: "Weak one", confidence: "low" })],
    leads: [{ product: "laptop", text: "a lead" }],
    startFailures: [{ product: "earbuds", create_outcome: "unknown", message: "HTTP 500" }],
  });
  assert.match(md, /## 🟠 High/);
  assert.match(md, /## Not yet triaged[\s\S]*Untriaged one/);
  assert.match(md, /## Unconfirmed[\s\S]*Weak one/);
  assert.match(md, /check the Nimble dashboard/);
});
