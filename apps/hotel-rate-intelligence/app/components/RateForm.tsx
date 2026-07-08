"use client";

import { useState } from "react";
import { HotelInput } from "@/lib/types";
import { toISODate } from "@/lib/dates";

interface Props {
  onSubmit: (data: {
    userHotel: HotelInput;
    competitors: HotelInput[];
    windowDays: 7 | 14;
    startDate: string;
  }) => void;
  loading: boolean;
}

const defaultStartDate = () => {
  const d = new Date();
  const day = d.getDay();
  const daysUntilSat = day === 6 ? 7 : 6 - day;
  d.setDate(d.getDate() + daysUntilSat);
  return toISODate(d);
};

const inputCls =
  "w-full bg-[#1E2535] border border-[#2A3348] rounded-lg px-3 py-2 text-sm text-[#F0EFFB] placeholder-[#6B7694] focus:outline-none focus:border-[#6665EC] focus:ring-1 focus:ring-[#6665EC]/30 transition-colors";

const labelCls = "block text-xs font-medium text-[#6B7694] uppercase tracking-wider mb-1.5";

export function RateForm({ onSubmit, loading }: Props) {
  const [userHotel, setUserHotel] = useState<HotelInput>({ name: "", city: "" });
  const [competitors, setCompetitors] = useState<HotelInput[]>([
    { name: "", city: "" },
    { name: "", city: "" },
  ]);
  const [windowDays, setWindowDays] = useState<7 | 14>(7);
  const [startDate, setStartDate] = useState(defaultStartDate());

  const addCompetitor = () => {
    if (competitors.length < 4) setCompetitors([...competitors, { name: "", city: "" }]);
  };

  const removeCompetitor = (i: number) => {
    setCompetitors(competitors.filter((_, idx) => idx !== i));
  };

  const updateCompetitor = (i: number, field: keyof HotelInput, value: string) => {
    const updated = [...competitors];
    updated[i] = { ...updated[i], [field]: value };
    setCompetitors(updated);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const validCompetitors = competitors.filter((c) => c.name.trim() && c.city.trim());
    if (!userHotel.name.trim() || !userHotel.city.trim() || validCompetitors.length === 0) return;
    onSubmit({ userHotel, competitors: validCompetitors, windowDays, startDate });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Your hotel */}
      <div>
        <p className={labelCls}>Your hotel</p>
        <div className="space-y-2">
          <input
            type="text"
            placeholder="Hotel name"
            value={userHotel.name}
            onChange={(e) => setUserHotel({ ...userHotel, name: e.target.value })}
            className={inputCls}
            required
          />
          <input
            type="text"
            placeholder="City"
            value={userHotel.city}
            onChange={(e) => setUserHotel({ ...userHotel, city: e.target.value })}
            className={inputCls}
            required
          />
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-[#2A3348]" />

      {/* Competitors */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className={labelCls + " mb-0"}>Competitors</p>
          <span className="text-xs text-[#6B7694]">{competitors.length} / 4</span>
        </div>
        <div className="space-y-3">
          {competitors.map((c, i) => (
            <div key={i} className="bg-[#161B26] border border-[#2A3348] rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#6B7694]">Competitor {i + 1}</span>
                <button
                  type="button"
                  onClick={() => removeCompetitor(i)}
                  disabled={competitors.length <= 1}
                  className="text-[#6B7694] hover:text-[#E05C5C] text-xs transition-colors disabled:opacity-30"
                >
                  Remove
                </button>
              </div>
              <input
                type="text"
                placeholder="Hotel name"
                value={c.name}
                onChange={(e) => updateCompetitor(i, "name", e.target.value)}
                className={inputCls}
              />
              <input
                type="text"
                placeholder="City"
                value={c.city}
                onChange={(e) => updateCompetitor(i, "city", e.target.value)}
                className={inputCls}
              />
            </div>
          ))}
        </div>
        {competitors.length < 4 && (
          <button
            type="button"
            onClick={addCompetitor}
            className="mt-3 w-full border border-dashed border-[#2A3348] rounded-lg py-2 text-xs text-[#6B7694] hover:border-[#6665EC] hover:text-[#6665EC] transition-colors"
          >
            + Add competitor
          </button>
        )}
      </div>

      {/* Divider */}
      <div className="border-t border-[#2A3348]" />

      {/* Date range */}
      <div>
        <p className={labelCls}>Date range</p>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-[#6B7694] mb-1 block">Start date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className={inputCls}
            />
          </div>
          <div>
            <label className="text-xs text-[#6B7694] mb-1 block">Window</label>
            <select
              value={windowDays}
              onChange={(e) => setWindowDays(Number(e.target.value) as 7 | 14)}
              className={inputCls}
            >
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
            </select>
          </div>
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={loading}
        className="w-full bg-[#6665EC] hover:bg-[#5554D4] disabled:bg-[#2A3348] disabled:text-[#6B7694] text-white rounded-lg px-4 py-3 text-sm font-semibold transition-colors shadow-lg shadow-[#6665EC]/20"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Running analysis...
          </span>
        ) : (
          "Check rates"
        )}
      </button>
    </form>
  );
}
