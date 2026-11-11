import { head } from "@vercel/blob";

/**
 * Acme Mail is a demo pricing page, clearly labeled as not a real company, so
 * the cookbook can show a guaranteed price change. The Growth price lives in
 * Blob as JSON (written by `npm run demo:price`); the page itself is rendered
 * by `acme-page.ts` on the app's own route, because Blob serves HTML as a download.
 */
export const ACME_PRICE_KEY = "acme-mail/price.json";
export const ACME_DEFAULT_GROWTH = 25;

export async function readAcmeGrowthPrice(): Promise<number> {
  try {
    const meta = await head(ACME_PRICE_KEY);
    const res = await fetch(meta.url, { cache: "no-store" });
    const { growth } = (await res.json()) as { growth?: number };
    return typeof growth === "number" && growth > 0 ? growth : ACME_DEFAULT_GROWTH;
  } catch {
    return ACME_DEFAULT_GROWTH;
  }
}
