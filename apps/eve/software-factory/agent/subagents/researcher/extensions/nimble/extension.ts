import nimble from "@nimble-way/eve";

/**
 * Nimble web data for the factory.
 *
 * @remarks
 * The extension is mounted once, here. Every agent in the factory (the root
 * and each station) promotes Nimble Search and Extract into its built-in
 * `web_search` and `web_fetch` slots through its own `tools/web_search.ts` and
 * `tools/web_fetch.ts`, so all web access goes through Nimble. eve's build
 * rejects those shared tool modules when the extension is mounted more than
 * once. The namespaced duplicates and Web Search Agent tools are disabled. The
 * API key comes from `NIMBLE_API_KEY`.
 */
export default nimble({});
