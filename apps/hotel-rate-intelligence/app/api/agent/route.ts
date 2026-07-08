import { NextRequest } from "next/server";
import { streamRateIntelAgent } from "@/lib/agent";
import { HotelInput } from "@/lib/types";

export const maxDuration = 300; // 5 minutes for long extraction runs

export async function POST(req: NextRequest) {
  let body: {
    userHotel: HotelInput;
    competitors: HotelInput[];
    windowDays: 7 | 14;
    startDate?: string;
  };

  try {
    body = await req.json();
  } catch {
    return new Response("Invalid JSON body", { status: 400 });
  }

  const { userHotel, competitors, windowDays, startDate } = body;

  if (!userHotel?.name || !userHotel?.city) {
    return new Response("userHotel.name and userHotel.city are required", { status: 400 });
  }
  if (!competitors || competitors.length === 0) {
    return new Response("At least one competitor is required", { status: 400 });
  }

  const stream = streamRateIntelAgent({ userHotel, competitors, windowDays: windowDays ?? 7, startDate });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
