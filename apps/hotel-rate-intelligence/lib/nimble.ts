// Nimble API client - Search and Extract
// Verify current schema at https://docs.nimbleway.com before deploying.
// This file reflects the Nimble Web API as of mid-2025.

const NIMBLE_API_KEY = process.env.NIMBLE_API_KEY!;

// All Nimble SDK endpoints share this base URL.
// Docs: https://docs.nimbleway.com
const BASE = "https://sdk.nimbleway.com/v1";

// Search API: text query -> list of URLs + snippets
// POST /v1/search
const SEARCH_ENDPOINT = `${BASE}/search`;

// Extract API: URL -> rendered page content
// POST /v1/extract
const EXTRACT_ENDPOINT = `${BASE}/extract`;

function authHeaders(): Record<string, string> {
  return {
    Authorization: `Bearer ${NIMBLE_API_KEY}`,
    "Content-Type": "application/json",
  };
}

export interface SearchResult {
  title: string;
  url: string;
  description: string;
}

export interface SearchResponse {
  results: SearchResult[];
  error?: string;
}

// nimbleSearch: POST /v1/search
// Uses search_depth "lite" (titles + URLs + snippets, 1 credit each) because
// we only need URLs at this stage, not full page content.
// focus "shopping" tells Nimble to weight commercial/product pages.
export async function nimbleSearch(
  query: string,
  numResults: number = 5
): Promise<SearchResponse> {
  const body = {
    query,
    max_results: numResults,
    search_depth: "lite", // fast + cheap; we just need URLs
    focus: "shopping", // hotel booking pages are shopping-category queries
    include_domains: ["booking.com", "expedia.com"],
  };

  const res = await fetch(SEARCH_ENDPOINT, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Nimble Search failed (${res.status}): ${text}`);
  }

  const data = await res.json();

  // Nimble Search response shape (verify against current docs):
  // { results: [{ title, url, description, ... }] }
  const raw: Array<{ title?: string; url?: string; description?: string; snippet?: string }> =
    data?.results ?? data?.data?.results ?? [];

  return {
    results: raw.slice(0, numResults).map((r) => ({
      title: r.title ?? "",
      url: r.url ?? "",
      description: r.description ?? r.snippet ?? "",
    })),
  };
}

export interface ExtractResponse {
  markdown: string;
  error?: string;
}

// nimbleExtract: POST /v1/extract
// Uses driver "vx10" (stealth headless) with JS rendering on because OTA
// hotel pages are dynamic React/Vue apps that won't render without JS.
// formats: ["markdown"] gives us clean text the LLM can parse directly.
export async function nimbleExtract(url: string): Promise<ExtractResponse> {
  const body = {
    url,
    render: true,
    driver: "vx10", // stealth headless browser; OTA pages often have bot detection
    formats: ["markdown"],
    country: "US",
  };

  const res = await fetch(EXTRACT_ENDPOINT, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Nimble Extract failed (${res.status}): ${text}`);
  }

  const data = await res.json();

  // Nimble Extract response shape (verify against current docs):
  // { data: { markdown: "...", html: "..." }, metadata: { ... } }
  const markdown =
    data?.data?.markdown ??
    data?.markdown ??
    data?.data?.html ?? // fallback to HTML if markdown not in this response
    "";

  return { markdown };
}

// Chunk an array into groups of size n for batched parallel requests
export function chunk<T>(arr: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}
