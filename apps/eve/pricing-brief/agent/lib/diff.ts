import { formatPrice, key, limitKey, planLabel } from "./normalize";
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
    const seen = new Set(now.limits.map(limitKey));
    const limits = [...now.limits, ...old.limits.filter((l) => !seen.has(limitKey(l)))];
    return {
      ...now,
      limits,
      price: keepPrice ? old.price : now.price,
      starting_at: keepPrice ? old.starting_at : now.starting_at,
    };
  });
  return [...updated, ...missing];
}

type Limit = Plan["limits"][number];

const limitText = (l: Limit) => `${l.amount.toLocaleString("en-US")} ${l.metric}/${l.per}`;

/** Price and billing-period changes for one matched plan. */
function diffPrice(plan: string, old: Plan, now: Plan, result: DiffResult): void {
  if (!(old.price && now.price)) {
    if (old.price || now.price) {
      result.unknown.push(`${plan}: price`);
    }
    return;
  }
  const from = formatPrice(old.price, old.starting_at);
  const to = formatPrice(now.price, now.starting_at);
  if (old.price.period !== now.price.period) {
    result.changes.push({ from, kind: "billing_period", plan, to });
    return;
  }
  // "starting at" alone isn't compared: a read can miss the word, and a
  // missed qualifier shouldn't alert. It still shows in the from/to text.
  if (old.price.amount !== now.price.amount || old.price.currency !== now.price.currency) {
    result.changes.push({ from, kind: "price", plan, to });
  }
}

/** Usage-limit changes for one matched plan. A limit missing from either read is unseen, not removed. */
function diffLimits(plan: string, old: Plan, now: Plan, result: DiffResult): void {
  if (!(old.limits.length && now.limits.length)) {
    if (old.limits.length || now.limits.length) {
      result.unknown.push(`${plan}: limits`);
    }
    return;
  }
  const oldLimits = new Map(old.limits.map((l): [string, Limit] => [limitKey(l), l]));
  const newKeys = new Set(now.limits.map(limitKey));
  for (const limit of now.limits) {
    const prev = oldLimits.get(limitKey(limit));
    if (prev?.amount === limit.amount) {
      continue;
    }
    const from = prev ? limitText(prev) : "none";
    result.changes.push({ from, kind: "limit", metric: limit.metric, plan, to: limitText(limit) });
  }
  for (const prev of old.limits.filter((l) => !newKeys.has(limitKey(l)))) {
    result.unknown.push(`${plan}: ${limitKey(prev)} limit`);
  }
}

/**
 * Compares two normalized reads of the same pricing page. A field that is
 * null or empty on either side is "unknown", not a change. A plan missing from
 * one read is unseen; missing from two in a row, it is removed.
 */
export function diffPlans(before: StoredPlan[], after: Plan[]): DiffResult {
  const result: DiffResult = { changes: [], unknown: [] };

  for (const [old, now, tier] of pairPlans(before, after)) {
    if (old && now) {
      // Label by the previous read, so an alert reads "the $15/mo plan is now $18/mo".
      const plan = old.name ?? now.name ?? planLabel(old, tier);
      diffPrice(plan, old, now, result);
      diffLimits(plan, old, now, result);
    } else if (now) {
      result.changes.push({ kind: "plan_added", plan: planLabel(now, tier) });
    } else if (old?.unseen) {
      result.changes.push({ kind: "plan_removed", plan: planLabel(old, tier) });
    } else if (old) {
      result.unknown.push(`${planLabel(old, tier)}: plan`);
    }
  }

  return result;
}
