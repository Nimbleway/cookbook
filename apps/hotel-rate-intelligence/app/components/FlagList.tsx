"use client";

import { RateFlag } from "@/lib/types";
import { formatDateLabel } from "@/lib/dates";

interface Props {
  flags: RateFlag[];
}

export function FlagList({ flags }: Props) {
  if (flags.length === 0) {
    return (
      <div className="flex items-center gap-3 py-4 text-[#6B7694] text-sm">
        <span className="text-[#34C48B] text-lg">&#10003;</span>
        No rate parity or undercutting issues found in this date window.
      </div>
    );
  }

  const undercutting = flags.filter((f) => f.type === "undercutting");
  const parity = flags.filter((f) => f.type === "parity");

  return (
    <div className="space-y-6">
      {undercutting.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-[#D97757] inline-block" />
            <h3 className="text-xs font-semibold text-[#D97757] uppercase tracking-wider">
              Competitive undercutting — {undercutting.length} {undercutting.length === 1 ? "flag" : "flags"}
            </h3>
          </div>
          <div className="space-y-2">
            {undercutting.map((f, i) => (
              <div
                key={i}
                className="bg-[#D97757]/5 border border-[#D97757]/20 rounded-lg p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-[#F0EFFB]">{f.competitorName}</span>
                      <span className="text-[#6B7694] text-xs">on</span>
                      <span className="text-[#A09DB2] text-xs capitalize">{f.ota === "booking" ? "Booking.com" : "Expedia"}</span>
                      <span className="text-[#6B7694] text-xs">|</span>
                      <span className="text-[#A09DB2] text-xs">{formatDateLabel(f.date)}</span>
                    </div>
                    {f.note && <p className="text-xs text-[#6B7694] mt-1.5 leading-relaxed">{f.note}</p>}
                    {f.reviewContext && (
                      <p className="text-xs text-[#A09DB2] mt-1 italic">{f.reviewContext}</p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-[#D97757] font-mono font-bold text-base">${f.competitorRate}</div>
                    <div className="text-[#6B7694] text-xs">vs your ${f.userRate}</div>
                    {f.percentDiff != null && (
                      <div className="mt-1 bg-[#D97757]/20 text-[#D97757] text-[10px] font-semibold px-1.5 py-0.5 rounded inline-block">
                        {Math.abs(f.percentDiff).toFixed(1)}% below
                      </div>
                    )}
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2 text-[10px] text-[#6B7694]">
                  <span className="bg-[#1E2535] px-1.5 py-0.5 rounded">{f.roomCategory}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {parity.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 inline-block" />
            <h3 className="text-xs font-semibold text-yellow-400 uppercase tracking-wider">
              Rate parity issues — {parity.length} {parity.length === 1 ? "flag" : "flags"}
            </h3>
          </div>
          <div className="space-y-2">
            {parity.map((f, i) => (
              <div
                key={i}
                className="bg-yellow-900/10 border border-yellow-700/20 rounded-lg p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-[#F0EFFB]">{f.hotelName}</span>
                      <span className="text-[#6B7694] text-xs">|</span>
                      <span className="text-[#A09DB2] text-xs">{formatDateLabel(f.date)}</span>
                    </div>
                    {f.note && <p className="text-xs text-[#6B7694] mt-1.5 leading-relaxed">{f.note}</p>}
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-yellow-400 font-mono font-bold text-base">${f.userRate}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
