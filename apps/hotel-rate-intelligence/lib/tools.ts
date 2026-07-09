import { tool } from "ai";
import { z } from "zod";
import { nimbleSearch, nimbleExtract, chunk } from "./nimble";
import { OtaListing, RateEntry, RoomCategory } from "./types";
import { bookingDateParams, expediaDateParams } from "./dates";

// --- Core logic functions (called directly by the agent runner) ---

export async function searchOtaListingsImpl(
  hotelName: string,
  city: string
): Promise<{ listings: OtaListing[]; errors: string[] }> {
  const otas = ["booking.com", "expedia"] as const;
  const results: OtaListing[] = [];
  const errors: string[] = [];

  for (const ota of otas) {
    const query = `"${hotelName}" ${city} site:${ota === "booking.com" ? "booking.com" : "expedia.com"} hotel`;
    try {
      const { results: searchResults } = await nimbleSearch(query, 5);

      // Filter to direct hotel property pages (not search/list pages)
      const propertyPages = searchResults.filter((r) => {
        const url = r.url.toLowerCase();
        if (ota === "booking.com") {
          return url.includes("booking.com/hotel/") || url.includes("booking.com/en-us/hotel/");
        } else {
          return (
            url.includes("expedia.com/") &&
            (url.includes("h") || url.includes("/Hotels") || url.includes("-hotel-"))
          );
        }
      });

      if (propertyPages.length > 0) {
        results.push({
          hotelName,
          ota: ota === "booking.com" ? "booking" : "expedia",
          url: propertyPages[0].url,
        });
      } else if (searchResults.length > 0) {
        results.push({
          hotelName,
          ota: ota === "booking.com" ? "booking" : "expedia",
          url: searchResults[0].url,
        });
      } else {
        errors.push(`No results found for ${hotelName} on ${ota}`);
      }
    } catch (err) {
      errors.push(`Search failed for ${hotelName} on ${ota}: ${String(err)}`);
    }
  }

  return { listings: results, errors };
}

export async function extractRatePageImpl(
  hotelName: string,
  ota: "booking" | "expedia",
  url: string,
  dates: string[]
): Promise<{ hotelName: string; entries: RateEntry[]; errors: Array<{ date: string; reason: string }> }> {
  const entries: RateEntry[] = [];
  const errors: Array<{ date: string; reason: string }> = [];

  const dateBatches = chunk(dates, 5);

  for (const batch of dateBatches) {
    await Promise.all(
      batch.map(async (date) => {
        const checkinDate = new Date(date + "T00:00:00");
        const checkoutDate = new Date(checkinDate);
        checkoutDate.setDate(checkoutDate.getDate() + 1);
        const checkout = checkoutDate.toISOString().slice(0, 10);

        const separator = url.includes("?") ? "&" : "?";
        const dateUrl =
          ota === "booking"
            ? `${url}${separator}${bookingDateParams(date, checkout)}`
            : `${url}${separator}${expediaDateParams(date, checkout)}`;

        try {
          const { markdown } = await nimbleExtract(dateUrl);
          if (!markdown || markdown.trim().length < 100) {
            errors.push({ date, reason: "Empty or near-empty page response" });
            return;
          }

          const parsed = parseRatesFromMarkdown(markdown, hotelName, ota, url, date);
          entries.push(...parsed);
        } catch (err) {
          errors.push({ date, reason: String(err) });
        }
      })
    );
  }

  return { hotelName, entries, errors };
}

// --- AI SDK tool wrappers (for agentic use via generateText/streamText) ---
// These wrap the same logic so the LLM can call them directly if used in a tool-calling loop.

export const searchOtaListings = tool({
  description:
    "Search Booking.com and Expedia for the listing page URL of a specific hotel. " +
    "Returns up to 5 candidate URLs per OTA.",
  inputSchema: z.object({
    hotelName: z.string().describe("Name of the hotel to search for"),
    city: z.string().describe("City where the hotel is located"),
  }),
  execute: async (input) => searchOtaListingsImpl(input.hotelName, input.city),
});

export const extractRatePage = tool({
  description:
    "Extract nightly rates, room types, review rating, and review count from an OTA hotel listing page " +
    "for a specific set of dates (each is a 1-night stay).",
  inputSchema: z.object({
    hotelName: z.string().describe("Name of the hotel (for labeling results)"),
    ota: z.enum(["booking", "expedia"]).describe("Which OTA this URL is from"),
    url: z.string().describe("The OTA listing page URL"),
    dates: z
      .array(z.string())
      .describe("Array of YYYY-MM-DD checkin dates to fetch rates for."),
  }),
  execute: async (input) =>
    extractRatePageImpl(input.hotelName, input.ota, input.url, input.dates),
});

// --- Heuristic parser ---

function parseRatesFromMarkdown(
  markdown: string,
  hotelName: string,
  ota: "booking" | "expedia",
  url: string,
  date: string
): RateEntry[] {
  // Extract price patterns: $123, USD 123, 123 USD, £123, €123
  const pricePattern = /[\$£€]?\s*(\d{2,4})(?:\.\d{2})?\s*(?:USD|GBP|EUR|per night|\/night)?/gi;
  const prices: number[] = [];
  let match: RegExpExecArray | null;
  while ((match = pricePattern.exec(markdown)) !== null) {
    const val = parseInt(match[1]);
    if (val >= 50 && val <= 5000) {
      prices.push(val);
    }
  }

  // Extract room type lines
  const roomTypePattern =
    /(?:^|\n)([A-Z][a-zA-Z\s]{3,50}(?:Room|Suite|King|Queen|Twin|Double|Single|Bed|Studio))/gm;
  const roomTypes: string[] = [];
  while ((match = roomTypePattern.exec(markdown)) !== null) {
    roomTypes.push(match[1].trim());
  }

  // Extract star rating (normalize to /10)
  let reviewRating: number | null = null;
  const ratingMatch = markdown.match(
    /(\d+(?:\.\d)?)\s*\/\s*10|(\d+(?:\.\d)?)\s*\/\s*5|score[:\s]+(\d+(?:\.\d)?)/i
  );
  if (ratingMatch) {
    const raw = parseFloat(ratingMatch[1] ?? ratingMatch[2] ?? ratingMatch[3] ?? "0");
    reviewRating = ratingMatch[1] ? raw : ratingMatch[2] ? raw * 2 : raw;
  }

  // Extract review count
  let reviewCount: number | null = null;
  const reviewCountMatch = markdown.match(/(\d[\d,]+)\s+(?:reviews?|ratings?|guests?)/i);
  if (reviewCountMatch) {
    reviewCount = parseInt(reviewCountMatch[1].replace(/,/g, ""));
  }

  // Extract discount messaging
  let discountMessaging: string | null = null;
  const discountMatch = markdown.match(
    /(?:sale|deal|discount|off|save|limited|reduced|special)[^\n]{0,80}/i
  );
  if (discountMatch) {
    discountMessaging = discountMatch[0].trim();
  }

  const lowestRate = prices.length > 0 ? Math.min(...prices) : null;
  const roomType = roomTypes[0] ?? "Room (type not parsed)";

  return [
    {
      hotelName,
      ota,
      url,
      date,
      rate: lowestRate,
      currency: "USD",
      roomType,
      roomCategory: categorizeRoom(roomType),
      reviewRating,
      reviewCount,
      discountMessaging,
      categoryConfidence: roomTypes.length > 0 ? "high" : "low",
    },
  ];
}

function categorizeRoom(roomType: string): RoomCategory {
  const lower = roomType.toLowerCase();
  if (/suite/.test(lower)) return "Suite";
  if (/deluxe|superior|premium|executive/.test(lower)) return "Deluxe";
  if (/standard|classic|basic|economy|regular|cozy|comfortable/.test(lower)) return "Standard";
  if (/king|queen|twin|double|single/.test(lower)) return "Standard";
  return "Unknown";
}
