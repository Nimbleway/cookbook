import nimble from "@nimble-way/eve";

// Nimble Search finds each competitor's official pricing page; Extract reads it
// as markdown. The API key comes from NIMBLE_API_KEY.
export default nimble({ search: { maxResults: 5 } });
