import { formatPrice, key, planLabel } from "./normalize";
import type { Change, Plan, StoredPlan } from "./plans";

export interface DiffResult {
  changes: Change[];
  /** Fields one side couldn't see. Logged, never alerted on. */
  unknown: string[];
}

type Pair = [StoredPlan | undefined, Plan | undefined, number];

/**
 * Pairs the plans of two reads. Plans are matched by name when every plan on
 * both sides has one, and by their position on the page otherwise.
 */
function pairPlans(before: StoredPlan[], after: Plan[]): Pair[] {
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
 * Fills what today's read couldn't see with the last known values, so a read
 * that misses a price, a limit or a whole plan doesn't become the baseline
 * that hides the next real change. A plan missing from one read is kept and
 * marked unseen; missing from a second read in a row, it is dropped.
 */
export function carryForward(before: StoredPlan[], after: Plan[]): StoredPlan[] {
  const known = new Map<Plan, Plan>();
  const missing: StoredPlan[] = [];
  for (const [old, now] of pairPlans(before, after)) {
    if (old && now) {
      known.set(now, old);
    } else if (old && !old.unseen) {
      missing.push({ ...old, unseen: 1 });
    }
  }
  const updated = after.map((now): StoredPlan => {
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
  return [...updated, ...missing];
}

const limitText = (l: Plan["limits"][number]) => `${l.amount.toLocaleString("en-US")} ${l.metric}/${l.per}`;

/**
 * Compares two normalized reads of the same pricing page. A field that is
 * null or empty on either side is "unknown", not a change.
 */
export function diffPlans(before: StoredPlan[], after: Plan[]): DiffResult {
  const changes: Change[] = [];
  const unknown: string[] = [];

  for (const [old, now, tier] of pairPlans(before, after)) {
    if (!old && now) {
      changes.push({ kind: "plan_added", plan: planLabel(now, tier) });
      continue;
    }
    if (old && !now) {
      // Missing from one read is unseen; missing from two in a row is removed.
      if (old.unseen) {
        changes.push({ kind: "plan_removed", plan: planLabel(old, tier) });
      } else {
        unknown.push(`${planLabel(old, tier)}: plan`);
      }
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
