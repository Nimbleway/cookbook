import { formatPrice, key, planLabel } from "./normalize";
import type { Change, Plan } from "./plans";

export interface DiffResult {
  changes: Change[];
  /** Fields one side couldn't see. Logged, never alerted on. */
  unknown: string[];
}

/**
 * Compares two normalized reads of the same pricing page.
 *
 * Plans are matched by name when every plan on both sides has one, and by
 * their position on the page otherwise. A field that is null
 * or empty on either side is "unknown", not a change.
 */
export function diffPlans(before: Plan[], after: Plan[]): DiffResult {
  const changes: Change[] = [];
  const unknown: string[] = [];

  const byName = [...before, ...after].every((plan) => plan.name);
  const pairs: Array<[Plan | undefined, Plan | undefined, number]> = [];

  if (byName) {
    const old = new Map(before.map((plan) => [key(plan.name as string), plan]));
    const now = new Map(after.map((plan) => [key(plan.name as string), plan]));
    after.forEach((plan, i) => {
      pairs.push([old.get(key(plan.name as string)), plan, i]);
    });
    before.forEach((plan, i) => {
      if (!now.has(key(plan.name as string))) {
        pairs.push([plan, undefined, i]);
      }
    });
  } else {
    for (let i = 0; i < Math.max(before.length, after.length); i++) {
      pairs.push([before[i], after[i], i]);
    }
  }

  for (const [old, now, tier] of pairs) {
    if (!old && now) {
      changes.push({ kind: "plan_added", plan: planLabel(now, tier) });
      continue;
    }
    if (old && !now) {
      changes.push({ kind: "plan_removed", plan: planLabel(old, tier) });
      continue;
    }
    if (!(old && now)) {
      continue;
    }
    // Label by the previous read, so an alert reads "the $15/mo plan is now $18/mo".
    const plan = old.name ?? now.name ?? planLabel(old, tier);

    if (old.price && now.price) {
      if (old.price.period !== now.price.period) {
        changes.push({
          from: formatPrice(old.price, old.starting_at),
          kind: "billing_period",
          plan,
          to: formatPrice(now.price, now.starting_at),
        });
      } else if (old.price.amount !== now.price.amount || old.price.currency !== now.price.currency) {
        changes.push({
          from: formatPrice(old.price, old.starting_at),
          kind: "price",
          plan,
          to: formatPrice(now.price, now.starting_at),
        });
      }
    } else if (old.price || now.price) {
      unknown.push(`${plan}: price`);
    }

    if (old.limits.length && now.limits.length) {
      const oldLimits = new Map(old.limits.map((l) => [`${l.metric}/${l.per}`, l]));
      for (const limit of now.limits) {
        const prev = oldLimits.get(`${limit.metric}/${limit.per}`);
        if (prev && prev.amount !== limit.amount) {
          changes.push({
            from: `${prev.amount.toLocaleString("en-US")} ${prev.metric}/${prev.per}`,
            kind: "limit",
            metric: limit.metric,
            plan,
            to: `${limit.amount.toLocaleString("en-US")} ${limit.metric}/${limit.per}`,
          });
        }
      }
    } else if (old.limits.length || now.limits.length) {
      unknown.push(`${plan}: limits`);
    }

  }

  return { changes, unknown };
}
