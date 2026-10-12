// Scores new events against the watchlist. It reads Nimble's cited event fields and
// decides how much they matter to these products. It has no tools: it never researches,
// and it never restates sources (those are rendered from Nimble's trust data).
import { Agent } from "@mastra/core/agent";
import { z } from "zod";
import { config } from "../config";

export const triageSchema = z.object({
  assessments: z.array(
    z.object({
      eventKey: z.string().describe("The eventKey of the candidate being assessed, verbatim."),
      duplicateOf: z
        .string()
        .nullable()
        .describe("eventKey of a KNOWN event this candidate repeats with nothing new, else null."),
      severity: z.enum(["critical", "high", "medium", "low"]),
      affectedProducts: z.array(z.string()).describe("Product slugs from the watchlist."),
      rationale: z.string().describe("One or two sentences, using only facts in the event fields."),
      recommendedAction: z.string().describe("One concrete next step for the sourcing team."),
    }),
  ),
});

export const triageAgent = new Agent({
  id: "triage",
  name: "Supply chain triage",
  description: "Scores newly detected supply chain events against the product watchlist.",
  model: config.model,
  instructions: `You triage supply chain events for a consumer electronics sourcing team.

You receive the WATCHLIST (products, their exposures, and which exposures are single-source),
CANDIDATE events found by today's research runs, and KNOWN events already reported in the last
14 days. Assess every candidate.

Severity rubric:
- critical: stops, or is likely to stop, supply of a single-source exposure for two weeks or more,
  or a legal restriction (export ban, licensing, sanctions) on a single-source exposure takes effect.
- high: material delay or cost increase on a single-source exposure; a stoppage of a multi-source
  exposure; or an ongoing event that is escalating.
- medium: disruption to a multi-source exposure with alternatives available, or an announced
  change taking effect more than 30 days out.
- low: minor, indirect, resolved, or easing.

Rules:
- Use only the facts in the event fields. Never add figures, dates, or facts from memory.
- affectedProducts: the products whose exposures are named in the event's affected exposures.
  Add another product only when the event concerns the same part category it buys (the same
  material, site, or lane), not merely the same supplier for a different part: a PC CPU price rise
  at TSMC does not reach a product that buys a Bluetooth SoC from TSMC. The research runs check
  each product separately; do not overrule them with general reasoning.
- duplicateOf: set it only when a candidate is the same real-world event as a KNOWN event and
  adds nothing new. A status change (for example announced -> escalating) is new: leave it null.
- recommendedAction: one concrete step (check inventory cover, request allocation, pre-book
  capacity, qualify an alternate, watch for a named follow-up). Not "monitor the situation".`,
});
