import type { Plan } from "./plans";

/** Case- and whitespace-insensitive key for plan names and limit metrics. */
export const key = (text: string): string => text.toLowerCase().replace(/\s+/g, " ").trim();

const round2 = (n: number): number => Math.round(n * 100) / 100;

/**
 * Puts one read into a stable shape before it is stored or compared:
 * trimmed names, rounded prices, upper-case currency and deduplicated
 * limits. Plans keep the order the page lists them in: nameless plans are
 * matched by that position, and sorting by price would reorder them whenever
 * a price changes.
 */
export function normalizePlans(plans: Plan[]): Plan[] {
  const normalized = plans.map((plan) => {
    const name = plan.name?.trim() ? plan.name.trim() : null;
    const price = plan.price
      ? {
          amount: round2(plan.price.amount),
          currency: (plan.price.currency || "USD").toUpperCase(),
          period: plan.price.period,
        }
      : null;

    const limits = new Map<string, Plan["limits"][number]>();
    for (const limit of plan.limits) {
      const metric = key(limit.metric);
      limits.set(`${metric}/${limit.per}`, { amount: Math.round(limit.amount), metric, per: limit.per });
    }

    return {
      limits: [...limits.values()].sort((a, b) => `${a.metric}/${a.per}`.localeCompare(`${b.metric}/${b.per}`)),
      name,
      price,
      starting_at: plan.starting_at,
    };
  });

  return normalized;
}

export const formatPrice = (price: NonNullable<Plan["price"]>, startingAt = false): string =>
  `${startingAt ? "from " : ""}${price.currency === "USD" ? "$" : `${price.currency} `}${price.amount}/${price.period === "month" ? "mo" : "yr"}`;

/** How a plan is named in alerts: its name, or its price tier when the page shows no name. */
export const planLabel = (plan: Plan, tier: number): string =>
  plan.name ?? (plan.price ? `${formatPrice(plan.price)} plan` : `tier ${tier + 1} plan`);
