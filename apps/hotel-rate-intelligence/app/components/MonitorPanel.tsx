"use client";

import { useState, useEffect } from "react";
import { MonitorConfig, HotelInput } from "@/lib/types";

const inputCls =
  "w-full bg-[#1E2535] border border-[#2A3348] rounded-lg px-3 py-2 text-sm text-[#F0EFFB] placeholder-[#6B7694] focus:outline-none focus:border-[#6665EC] focus:ring-1 focus:ring-[#6665EC]/30 transition-colors";

const labelCls = "block text-xs font-medium text-[#6B7694] mb-1.5";

export function MonitorPanel() {
  const [configs, setConfigs] = useState<MonitorConfig[]>([]);
  const [form, setForm] = useState({
    userHotelName: "",
    userHotelCity: "",
    competitorNames: "",
    competitorCity: "",
    threshold: 10,
    windowDays: 7 as 7 | 14,
    slackWebhookUrl: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/monitor")
      .then((r) => r.json())
      .then(setConfigs)
      .catch(() => {});
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const competitors: HotelInput[] = form.competitorNames
        .split(",")
        .map((n) => ({ name: n.trim(), city: form.competitorCity.trim() }))
        .filter((c) => c.name);

      const res = await fetch("/api/monitor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userHotel: { name: form.userHotelName, city: form.userHotelCity },
          competitors,
          threshold: form.threshold,
          windowDays: form.windowDays,
          slackWebhookUrl: form.slackWebhookUrl,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const config = await res.json();
      setConfigs((prev) => [...prev, config]);
      setForm({ userHotelName: "", userHotelCity: "", competitorNames: "", competitorCity: "", threshold: 10, windowDays: 7, slackWebhookUrl: "" });
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    await fetch(`/api/monitor?id=${id}`, { method: "DELETE" });
    setConfigs((prev) => prev.filter((c) => c.id !== id));
  };

  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs text-[#6B7694] mb-4 leading-relaxed">
          Save a monitoring config and the Vercel cron job (daily, 08:00 UTC) will re-run the full
          Search + Extract + reasoning flow headlessly. If a competitor undercuts your rate by more
          than the threshold, a Slack alert is sent.
        </p>

        {configs.length === 0 ? (
          <div className="bg-[#161B26] border border-dashed border-[#2A3348] rounded-lg p-6 text-center text-sm text-[#6B7694]">
            No monitors configured yet.
          </div>
        ) : (
          <div className="space-y-2">
            {configs.map((c) => (
              <div
                key={c.id}
                className="bg-[#161B26] border border-[#2A3348] rounded-lg p-4 flex items-start justify-between gap-3"
              >
                <div>
                  <div className="text-sm font-semibold text-[#F0EFFB]">{c.userHotel.name}</div>
                  <div className="text-xs text-[#6B7694] mt-0.5">
                    vs {c.competitors.map((x) => x.name).join(", ")}
                  </div>
                  <div className="flex gap-3 mt-1.5 text-[10px] text-[#6B7694]">
                    <span className="bg-[#1E2535] px-1.5 py-0.5 rounded">Alert at {c.threshold}% below</span>
                    <span className="bg-[#1E2535] px-1.5 py-0.5 rounded">{c.windowDays}-day window</span>
                    {c.slackWebhookUrl && <span className="bg-[#6665EC]/20 text-[#6665EC] px-1.5 py-0.5 rounded">Slack on</span>}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(c.id)}
                  className="text-xs text-[#6B7694] hover:text-[#E05C5C] transition-colors"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="text-xs font-semibold text-[#6B7694] uppercase tracking-wider mb-4">New monitor</h2>
        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelCls}>Your hotel name</label>
              <input type="text" placeholder="Hotel name" value={form.userHotelName}
                onChange={(e) => setForm({ ...form, userHotelName: e.target.value })} required className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>City</label>
              <input type="text" placeholder="City" value={form.userHotelCity}
                onChange={(e) => setForm({ ...form, userHotelCity: e.target.value })} required className={inputCls} />
            </div>
          </div>

          <div>
            <label className={labelCls}>Competitor names (comma-separated)</label>
            <input type="text" placeholder="The Grand Hotel, Park Inn..." value={form.competitorNames}
              onChange={(e) => setForm({ ...form, competitorNames: e.target.value })} required className={inputCls} />
          </div>

          <div>
            <label className={labelCls}>Competitors city</label>
            <input type="text" placeholder="City" value={form.competitorCity}
              onChange={(e) => setForm({ ...form, competitorCity: e.target.value })} required className={inputCls} />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelCls}>Alert threshold (%)</label>
              <input type="number" min={1} max={50} value={form.threshold}
                onChange={(e) => setForm({ ...form, threshold: Number(e.target.value) })} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Window</label>
              <select value={form.windowDays}
                onChange={(e) => setForm({ ...form, windowDays: Number(e.target.value) as 7 | 14 })} className={inputCls}>
                <option value={7}>7 days</option>
                <option value={14}>14 days</option>
              </select>
            </div>
          </div>

          <div>
            <label className={labelCls}>Slack webhook URL (optional)</label>
            <input type="url" placeholder="https://hooks.slack.com/..." value={form.slackWebhookUrl}
              onChange={(e) => setForm({ ...form, slackWebhookUrl: e.target.value })} className={inputCls} />
          </div>

          {error && <p className="text-xs text-[#E05C5C]">{error}</p>}

          <button type="submit" disabled={saving}
            className="w-full bg-[#1E2535] hover:bg-[#2A3348] border border-[#2A3348] hover:border-[#6665EC] disabled:opacity-50 text-[#B8BDD6] rounded-lg px-4 py-2.5 text-sm font-medium transition-colors">
            {saving ? "Saving..." : "Save monitor"}
          </button>
        </form>
      </div>
    </div>
  );
}
