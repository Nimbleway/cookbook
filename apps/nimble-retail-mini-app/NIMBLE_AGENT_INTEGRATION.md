# NIMBLE AGENT INTEGRATION

## Retailers

Phase 1 supports:

* Amazon
* Walmart
* Target

All retailer intelligence should come from Nimble agents.

Claude should never generate retailer search data.

Claude should only:

* Summarize
* Explain
* Recommend
* Answer questions

based on returned Nimble data.

---

# Retailer Agent Configuration

Create a centralized retailer configuration:

```ts
export const NIMBLE_AGENTS = {
  amazon: {
    name: "Amazon SERP Agent",
    endpoint: process.env.NIMBLE_AMAZON_SERP_AGENT_ENDPOINT,
  },

  walmart: {
    name: "Walmart SERP Agent",
    endpoint: process.env.NIMBLE_WALMART_SERP_AGENT_ENDPOINT,
  },

  target: {
    name: "Target SERP Agent",
    endpoint: process.env.NIMBLE_TARGET_SERP_AGENT_ENDPOINT,
  },
};
```

Environment Variables:

```env
NIMBLE_API_KEY=

NIMBLE_AMAZON_SERP_AGENT_ENDPOINT=

NIMBLE_WALMART_SERP_AGENT_ENDPOINT=

NIMBLE_TARGET_SERP_AGENT_ENDPOINT=

ANTHROPIC_API_KEY=
```

---

# Search Flow

User enters:

* Category
* Keyword
* Brand

Example:

"protein bars"

The application should simultaneously call:

Amazon SERP Agent

Walmart SERP Agent

Target SERP Agent

in parallel.

Never run sequentially.

---

# Expected Data Collection

Collect:

* Product rank
* Product title
* Brand
* Sponsored flag
* Price
* Rating
* Review count
* Product URL
* Image URL
* Availability

for page-one results.

---

# Normalized Schema

```ts
type RetailerSerpResult = {
  retailer: "amazon" | "walmart" | "target";
  keyword: string;
  rank: number;
  productTitle: string;
  brand: string;
  price?: number;
  rating?: number;
  reviewCount?: number;
  sponsored: boolean;
  productUrl?: string;
  imageUrl?: string;
  availability?: string;
  collectedAt: string;
};
```

---

# Cross-Retailer Insights

The most valuable insights should compare retailers.

Examples:

* Which retailer is most competitive?
* Which retailer has the highest sponsored penetration?
* Which brands dominate across all retailers?
* Which brands win organically on Amazon but not Walmart?
* Which brands over-index on Target?
* Which retailer has the most fragmented shelf?

These insights should be surfaced automatically.

---

# Fault Tolerance

If Amazon fails:

Show Walmart and Target.

If Walmart fails:

Show Amazon and Target.

If Target fails:

Show Amazon and Walmart.

Never fail the entire experience because one retailer fails.

---

# Latency Requirements

Run all retailer calls in parallel.

Generate insight cards as soon as the first retailer returns.

Do not wait for all retailers.

Do not wait for Claude.

Claude summaries should be asynchronous.

The user should see value within seconds.
