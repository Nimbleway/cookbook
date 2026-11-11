import { defineChannel, GET } from "eve/channels";
import { readAcmeGrowthPrice, renderAcmePage } from "../lib/acme";

// Public demo pricing page for the cookbook walkthrough (Acme Mail is not a real company).
export default defineChannel({
  routes: [
    GET("/demo/acme-mail/pricing", async () => {
      const html = renderAcmePage(await readAcmeGrowthPrice());
      return new Response(html, {
        headers: { "cache-control": "no-store", "content-type": "text/html; charset=utf-8" },
      });
    }),
  ],
});
