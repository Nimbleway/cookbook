import { formatPrice, key, planLabel } from "./normalize";
import type { Change, Plan } from "./plans";

export interface DiffResult {
  changes: Change[];
  /** Fields one side couldn't see. Logged, never alerted on. */
  unknown: string[];
}

type Pair = [Plan | undefined, Plan | undefined, number];

/**
 * Pairs the plans of two reads. Plans are matched by name when every plan on
 * both sides has one, and by their position on the page otherwise.
 */
function pairPlans(before: Plan[], after: Plan[]): Pair[] {
  const pairs: Pair[] = [];
  const byName = [...before, ...after].every((plan) => plan.name);

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
  return pairs;
}

/**
 * Fills fields today's read couldn't see with the last known values, so a
 * read that misses a price doesn't become the baseline that hides the next
 * real change. Plans the read didn't return are not carried forward.
 */
export function carryForward(before: Plan[], after: Plan[]): Plan[] {
  const known = new Map<Plan, Plan>();
  for (const [old, now] of pairPlans(before, after)) {
    if (old && now) {
      known.set(now, old);
    }
  }
  return after.map((now) => {
    const old = known.get(now);
    if (!old) {
      return now;
    }
    const keepPrice = !now.price && old.price;
    // A limit missing from today's read is unseen, not removed: keep it.
    const seen = new Set(now.limits.map((l) => `${l.metric}/${l.per}`));
    const limits = [...now.limits, ...old.limits.filter((l) => !seen.has(`${l.metric}/${l.per}`))];
    return {
      ...now,
      limits,
      price: keepPrice ? old.price : now.price,
      starting_at: keepPrice ? old.starting_at : now.starting_at,
    };
  });
}

const limitText = (l: Plan["limits"][number]) => `${l.amount.toLocaleString("en-US")} ${l.metric}/${l.per}`;

/**
 * Compares two normalized reads of the same pricing page. A field that is
 * null or empty on either side is "unknown", not a change.
 */
export function diffPlans(before: Plan[], after: Plan[]): DiffResult {
  const changes: Change[] = [];
  const unknown: string[] = [];

  for (const [old, now, tier] of pairPlans(before, after)) {
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
      const from = formatPrice(old.price, old.starting_at);
      const to = formatPrice(now.price, now.starting_at);
      if (old.price.period !== now.price.period) {
        changes.push({ from, kind: "billing_period", plan, to });
      } else if (old.price.amount !== now.price.amount || old.price.currency !== now.price.currency) {
        // "starting at" alone isn't compared: a read can miss the word, and a
        // missed qualifier shouldn't alert. It still shows in the from/to text.
        changes.push({ from, kind: "price", plan, to });
      }
    } else if (old.price || now.price) {
      unknown.push(`${plan}: price`);
    }

    if (old.limits.length && now.limits.length) {
      const oldLimits = new Map(old.limits.map((l) => [`${l.metric}/${l.per}`, l]));
      const newLimits = new Map(now.limits.map((l) => [`${l.metric}/${l.per}`, l]));
      for (const [id, limit] of newLimits) {
        const prev = oldLimits.get(id);
        if (!prev || prev.amount !== limit.amount) {
          changes.push({
            from: prev ? limitText(prev) : "none",
            kind: "limit",
            metric: limit.metric,
            plan,
            to: limitText(limit),
          });
        }
      }
      for (const [id, prev] of oldLimits) {
        if (!newLimits.has(id)) {
          unknown.push(`${plan}: ${prev.metric}/${prev.per} limit`); // unseen, not removed
        }
      }
    } else if (old.limits.length || now.limits.length) {
      unknown.push(`${plan}: limits`);
    }
  }

  return { changes, unknown };
}
