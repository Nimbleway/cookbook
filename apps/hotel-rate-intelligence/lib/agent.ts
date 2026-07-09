import { createAnthropic } from "@ai-sdk/anthropic";
import { generateText } from "ai";
import { searchOtaListingsImpl, extractRatePageImpl } from "./tools";
import { HotelInput, AgentResult, RateEntry, RateFlag, OtaListing } from "./types";
import { nextSaturday, dateRange } from "./dates";

const anthropic = createAnthropic({
  apiKey: process.env.ANTHROPIC_API_KEY!,
});

export interface AgentRunOptions {
  userHotel: HotelInput;
  competitors: HotelInput[];
  windowDays: 7 | 14;
  startDate?: string; // YYYY-MM-DD, defaults to next Saturday
}

// Core agent function - shared between the UI (streaming) and cron (non-streaming) flows.
// lib/tools.ts:searchOtaListingsImpl - Nimble Search (listing discovery)
// lib/tools.ts:extractRatePageImpl  - Nimble Extract (rate data)
export async function runRateIntelAgent(
  options: AgentRunOptions,
  onProgress?: (msg: string) => void
): Promise<AgentResult> {
  const { userHotel, competitors, windowDays } = options;

  const startDate = options.startDate
    ? new Date(options.startDate + "T00:00:00")
    : nextSaturday();

  const dates = dateRange(startDate, windowDays);
  const allHotels = [userHotel, ...competitors];

  const listings: OtaListing[] = [];
  const allRates: RateEntry[] = [];
  const errors: Array<{ hotel: string; ota: string; reason: string }> = [];

  // Step 1: Discover OTA listing pages for each hotel via Nimble Search
  // lib/tools.ts:searchOtaListingsImpl -> lib/nimble.ts:nimbleSearch -> POST /v1/search
  onProgress?.(`Searching OTA listings for ${allHotels.length} hotels...`);

  for (const hotel of allHotels) {
    try {
      const result = await searchOtaListingsImpl(hotel.name, hotel.city);
      listings.push(...result.listings);
      for (const err of result.errors) {
        errors.push({ hotel: hotel.name, ota: "search", reason: err });
      }
      onProgress?.(`Found ${result.listings.length} listings for ${hotel.name}`);
    } catch (err) {
      errors.push({ hotel: hotel.name, ota: "search", reason: String(err) });
    }
  }

  // Step 2: Extract rates for each listing across all dates via Nimble Extract
  // lib/tools.ts:extractRatePageImpl -> lib/nimble.ts:nimbleExtract -> POST /v1/extract
  // Run in parallel batches of 5 to avoid overwhelming the API.
  onProgress?.(`Extracting rates for ${listings.length} listings across ${dates.length} dates...`);

  const BATCH_SIZE = 5;

  const extractionTasks = listings.map(
    (listing) => () => extractRatePageImpl(listing.hotelName, listing.ota, listing.url, dates)
  );

  for (let i = 0; i < extractionTasks.length; i += BATCH_SIZE) {
    const batch = extractionTasks.slice(i, i + BATCH_SIZE);
    const results = await Promise.all(batch.map((t) => t()));
    for (const result of results) {
      allRates.push(...result.entries);
      for (const err of result.errors) {
        const listing = listings.find((l) => l.hotelName === result.hotelName);
        errors.push({
          hotel: result.hotelName,
          ota: listing?.ota ?? "unknown",
          reason: err.reason,
        });
      }
      onProgress?.(`Extracted ${result.entries.length} rate entries for ${result.hotelName}`);
    }
  }

  // Step 3: Reasoning step - LLM analyzes all extracted data
  onProgress?.("Analyzing rates and generating summary...");

  const rateDataJson = JSON.stringify(
    {
      userHotel: userHotel.name,
      competitors: competitors.map((c) => c.name),
      dates,
      rates: allRates,
    },
    null,
    2
  );

  const reasoningPrompt = `You are a hotel revenue management analyst. Analyze the following rate data and produce:

1. Rate parity flags: cases where the same hotel has meaningfully different rates (>5%) across Booking.com and Expedia on the same date.
2. Competitive undercutting flags: cases where a competitor's rate for a comparable room category is noticeably lower (>5%) than the user's hotel on the same date. Only flag when room categories match (Standard vs Standard, Deluxe vs Deluxe, Suite vs Suite). If the category is "Unknown" or confidence is "low", mark it as "verify manually" instead of flagging.
3. Review-informed context: when flagging undercutting, note the review rating gap. "Priced below you with a comparable or better rating" is more concerning than "priced below you but rated meaningfully lower."
4. Date-specific patterns: call out if undercutting or parity issues are concentrated on specific days of the week (e.g. Fri/Sat only).
5. A short written summary (3-5 sentences) a revenue manager could act on.

Rate data:
${rateDataJson}

Respond in JSON with this exact structure:
{
  "flags": [
    {
      "type": "parity or undercutting",
      "date": "YYYY-MM-DD",
      "hotelName": "string",
      "ota": "booking or expedia or null",
      "competitorName": "string or null",
      "userRate": number,
      "competitorRate": number or null,
      "percentDiff": number or null,
      "roomCategory": "Standard or Deluxe or Suite or Unknown",
      "reviewContext": "string or null",
      "note": "plain text explanation"
    }
  ],
  "summary": "string"
}

Only include flags you can directly support from the extracted data. Do not guess at rates that were not extracted.`;

  const { text } = await generateText({
    model: anthropic("claude-sonnet-4-6"),
    prompt: reasoningPrompt,
    maxOutputTokens: 4096,
  });

  let flags: RateFlag[] = [];
  let summary = "";

  try {
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]) as { flags?: RateFlag[]; summary?: string };
      flags = parsed.flags ?? [];
      summary = parsed.summary ?? "";
    }
  } catch {
    summary = text;
  }

  onProgress?.("Analysis complete.");

  return { listings, rates: allRates, flags, summary, errors };
}

// Streaming version for the UI - wraps runRateIntelAgent with SSE progress events.
// The SSE stream sends { type: "progress", message } events during the run,
// then a final { type: "result", data: AgentResult } event.
export function streamRateIntelAgent(options: AgentRunOptions): ReadableStream {
  const encoder = new TextEncoder();

  return new ReadableStream({
    async start(controller) {
      const send = (event: object) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      };

      try {
        const result = await runRateIntelAgent(options, (msg) => {
          send({ type: "progress", message: msg });
        });
        send({ type: "result", data: result });
      } catch (err) {
        send({ type: "error", message: String(err) });
      } finally {
        controller.close();
      }
    },
  });
}
