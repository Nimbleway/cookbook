export interface HotelInput {
  name: string;
  city: string;
}

export interface MonitorConfig {
  id: string;
  userHotel: HotelInput;
  competitors: HotelInput[];
  threshold: number; // percent below user's rate to trigger alert
  windowDays: 7 | 14;
  startDate: string; // ISO date string
  slackWebhookUrl: string;
  createdAt: string;
}

export interface OtaListing {
  hotelName: string;
  ota: "booking" | "expedia";
  url: string;
}

export type RoomCategory = "Standard" | "Deluxe" | "Suite" | "Unknown";

export interface RateEntry {
  hotelName: string;
  ota: "booking" | "expedia";
  url: string;
  date: string; // YYYY-MM-DD
  rate: number | null; // nightly rate in USD
  currency: string;
  roomType: string; // raw room type from OTA
  roomCategory: RoomCategory;
  reviewRating: number | null;
  reviewCount: number | null;
  discountMessaging: string | null;
  categoryConfidence: "high" | "low" | "unmatched";
}

export interface RateFlag {
  type: "parity" | "undercutting";
  date: string;
  hotelName: string;
  ota?: string;
  competitorName?: string;
  userRate: number;
  competitorRate?: number;
  percentDiff?: number;
  roomCategory: RoomCategory;
  reviewContext?: string;
  note: string;
}

export interface AgentResult {
  listings: OtaListing[];
  rates: RateEntry[];
  flags: RateFlag[];
  summary: string;
  errors: Array<{ hotel: string; ota: string; reason: string }>;
}
