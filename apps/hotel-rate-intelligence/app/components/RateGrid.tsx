"use client";

import { RateEntry, RateFlag, OtaListing } from "@/lib/types";
import { formatDateLabel } from "@/lib/dates";

interface Props {
  rates: RateEntry[];
  flags: RateFlag[];
  listings: OtaListing[];
  dates: string[];
  userHotelName: string;
}

export function RateGrid({ rates, flags, listings, dates, userHotelName }: Props) {
  const hotels = Array.from(new Set(rates.map((r) => r.hotelName)));
  const otas = ["booking", "expedia"] as const;

  const rateIndex = new Map<string, RateEntry>();
  for (const r of rates) rateIndex.set(`${r.hotelName}|${r.ota}|${r.date}`, r);

  const undercutKeys = new Set<string>();
  const parityKeys = new Set<string>();
  for (const f of flags) {
    if (f.type === "undercutting" && f.competitorName)
      undercutKeys.add(`${f.competitorName}|${f.ota ?? ""}|${f.date}`);
    if (f.type === "parity")
      otas.forEach((ota) => parityKeys.add(`${f.hotelName}|${ota}|${f.date}`));
  }

  const getCellStyle = (hotel: string, ota: string, date: string, entry: RateEntry | undefined) => {
    if (!entry || entry.rate === null) return "bg-[#161B26] text-[#2A3348]";
    const key = `${hotel}|${ota}|${date}`;
    const isUser = hotel === userHotelName;
    if (undercutKeys.has(key)) return "bg-[#D97757]/10 text-[#D97757] border-[#D97757]/20";
    if (parityKeys.has(key)) return "bg-yellow-900/20 text-yellow-400 border-yellow-700/20";
    if (isUser) return "bg-[#6665EC]/10 text-[#A09DB2] border-[#6665EC]/20";
    return "bg-[#1E2535] text-[#B8BDD6] border-[#2A3348]";
  };

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-[#2A3348]">
        <table className="min-w-full text-xs border-collapse">
          <thead>
            <tr className="border-b border-[#2A3348]">
              <th className="text-left text-[#6B7694] font-medium px-4 py-3 sticky left-0 bg-[#161B26] z-10 min-w-[160px] border-r border-[#2A3348]">
                Hotel / OTA
              </th>
              {dates.map((date) => (
                <th key={date} className="text-center text-[#6B7694] font-medium px-2 py-3 min-w-[80px] whitespace-nowrap">
                  {formatDateLabel(date)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {hotels.map((hotel, hi) =>
              otas.map((ota, oi) => {
                const listing = listings.find((l) => l.hotelName === hotel && l.ota === ota);
                const isUser = hotel === userHotelName;
                const isLastOta = oi === otas.length - 1;
                const isLastHotel = hi === hotels.length - 1;

                return (
                  <tr
                    key={`${hotel}|${ota}`}
                    className={`${!isLastOta || !isLastHotel ? "border-b border-[#2A3348]/50" : ""} ${isUser ? "bg-[#6665EC]/5" : ""}`}
                  >
                    <td className="sticky left-0 z-10 px-4 py-2.5 border-r border-[#2A3348] bg-inherit">
                      <div className={`text-xs font-semibold truncate max-w-[140px] ${isUser ? "text-[#6665EC]" : "text-[#B8BDD6]"}`}>
                        {hotel}
                      </div>
                      <div className="text-[10px] text-[#6B7694] capitalize mt-0.5 flex items-center gap-1">
                        {ota === "booking" ? "Booking.com" : "Expedia"}
                      </div>
                    </td>
                    {dates.map((date) => {
                      const entry = rateIndex.get(`${hotel}|${ota}|${date}`);
                      const cellStyle = getCellStyle(hotel, ota, date, entry);

                      return (
                        <td key={date} className="px-1.5 py-1.5 text-center">
                          {entry?.rate != null ? (
                            <a
                              href={listing?.url ?? "#"}
                              target="_blank"
                              rel="noopener noreferrer"
                              title={`${entry.roomType} (${entry.roomCategory})${entry.reviewRating ? ` | ${entry.reviewRating}/10` : ""}${entry.discountMessaging ? " | " + entry.discountMessaging : ""}`}
                              className={`block rounded px-1 py-1 border text-xs font-mono font-semibold hover:opacity-80 transition-opacity ${cellStyle}`}
                            >
                              ${entry.rate}
                              <div className="text-[9px] font-normal opacity-60 font-sans">{entry.roomCategory}</div>
                            </a>
                          ) : (
                            <span className="block rounded px-1 py-1.5 text-[#2A3348] text-xs">--</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap gap-4 text-[11px] text-[#6B7694]">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded bg-[#6665EC]/20 border border-[#6665EC]/30 inline-block" />
          Your hotel
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded bg-[#D97757]/20 border border-[#D97757]/30 inline-block" />
          Undercutting flag
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded bg-yellow-900/20 border border-yellow-700/30 inline-block" />
          Parity issue
        </span>
        <span className="text-[#6B7694]/60">Hover a cell for room type + review details. Click to open OTA listing.</span>
      </div>
    </div>
  );
}
