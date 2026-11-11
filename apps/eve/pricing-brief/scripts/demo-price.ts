/**
 * Sets the Growth plan price on the Acme Mail demo pricing page.
 * Acme Mail is not a real company: the page exists so the demo can show a
 * guaranteed price change. The deployed app serves the page at
 * /demo/acme-mail/pricing.
 *
 *   npm run demo:price            # Growth plan at $25/mo (the baseline)
 *   npm run demo:price -- 29      # Growth plan at $29/mo (the change)
 */
import { put } from "@vercel/blob";
import { ACME_DEFAULT_GROWTH, ACME_PRICE_KEY } from "../agent/lib/acme.ts";

const growth = Number(process.argv[2] ?? ACME_DEFAULT_GROWTH);
if (!Number.isFinite(growth) || growth <= 0) {
  console.error("Usage: npm run demo:price -- <growth price in USD>");
  process.exit(1);
}

await put(ACME_PRICE_KEY, JSON.stringify({ growth }), {
  access: "public",
  addRandomSuffix: false,
  allowOverwrite: true,
  cacheControlMaxAge: 60,
  contentType: "application/json",
});

console.log(`Acme Mail Growth plan is now $${growth}/month.`);
console.log("Page: <your deployment>/demo/acme-mail/pricing (can take up to a minute to update).");
