import { z } from "zod";

/**
 * One pricing plan as the model reads it from a page. Every field the page
 * might not show is nullable: `null` means "not visible on this read", never
 * "removed", so a bad read can't produce a false alert.
 */
export const planSchema = z.object({
  name: z
    .string()
    .nullable()
    .describe("Plan name as shown on the page, or null if the page doesn't show one."),
  price: z
    .object({
      amount: z.number().nonnegative().describe("Price as a number, e.g. 19.95"),
      currency: z.string().default("USD"),
      period: z.enum(["month", "year"]),
    })
    .nullable()
    .describe("List price, or null if no price is shown (e.g. 'Contact sales')."),
  starting_at: z
    .boolean()
    .default(false)
    .describe("True when the page says 'starting at' or 'from'."),
  limits: z
    .array(
      z.object({
        metric: z.string().describe("What is limited, e.g. 'emails'."),
        amount: z.number().nonnegative(),
        per: z.enum(["day", "month"]),
      })
    )
    .default([])
    .describe("Usage limits shown for the plan. Empty if the page doesn't show them."),
});

export type Plan = z.infer<typeof planSchema>;

export type Change =
  | { kind: "plan_added"; plan: string }
  | { kind: "plan_removed"; plan: string }
  | { kind: "price"; plan: string; from: string; to: string }
  | { kind: "billing_period"; plan: string; from: string; to: string }
  | { kind: "limit"; plan: string; metric: string; from: string; to: string };
