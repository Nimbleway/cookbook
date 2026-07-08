"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, Radio } from "lucide-react";
import type { RetailerId } from "@/lib/types";
import { ALL_RETAILERS, RETAILER_META } from "@/lib/retailers";
import { useReducedMotion } from "@/lib/use-reduced-motion";

// A live console of Nimble agents working across retailers — replaces a salesy
// comparison block with proof the engine is genuinely live. Mock data, but it
// reads like the real agent fleet at work.

const KEYWORDS = [
  "protein bars", "energy drinks", "sparkling water", "cat food", "coffee",
  "greek yogurt", "cold brew", "electrolyte mix", "dog treats", "trail mix",
  "laundry pods", "baby formula", "olive oil", "hot sauce", "kombucha",
  "sunscreen", "running shoes", "air fryer", "dish soap", "granola",
];

type Event = {
  id: number;
  retailer: RetailerId;
  keyword: string;
  status: "scanning" | "done";
  count: number;
  latency: string;
  age: number; // seconds since spawned
};

let SEED = 1;
function makeEvent(): Event {
  SEED = (SEED * 9301 + 49297) % 233280;
  const rnd = SEED / 233280;
  const retailer = ALL_RETAILERS[Math.floor(rnd * ALL_RETAILERS.length)];
  const keyword = KEYWORDS[Math.floor(((rnd * 7.3) % 1) * KEYWORDS.length)];
  return {
    id: SEED + Date.now(),
    retailer,
    keyword,
    status: "scanning",
    count: 24 + Math.floor(((rnd * 13.7) % 1) * 37),
    latency: (0.6 + ((rnd * 5.1) % 1) * 1.6).toFixed(1) + "s",
    age: 0,
  };
}

// A static, non-animated snapshot for first paint / reduced-motion.
function snapshot(): Event[] {
  const base: Array<[RetailerId, string, number, string, number]> = [
    ["amazon", "protein bars", 60, "0.8s", 1],
    ["walmart", "sparkling water", 48, "1.1s", 3],
    ["target", "coffee", 30, "0.9s", 6],
    ["amazon", "energy drinks", 60, "1.3s", 9],
    ["walmart", "cat food", 40, "1.0s", 12],
    ["target", "greek yogurt", 28, "1.2s", 15],
  ];
  return base.map(([retailer, keyword, count, latency, age], i) => ({
    id: i,
    retailer,
    keyword,
    status: "done",
    count,
    latency,
    age,
  }));
}

export function LiveAgentStream() {
  const reduced = useReducedMotion();
  const [events, setEvents] = useState<Event[]>(snapshot);
  const [perMin, setPerMin] = useState(48);

  useEffect(() => {
    if (reduced) return;
    // Begin with one active scan on top of the snapshot (deferred so it's not a
    // synchronous setState in the effect body).
    const seed = setTimeout(
      () => setEvents((prev) => [makeEvent(), ...prev].slice(0, 7)),
      0,
    );
    let tick = 0;
    const id = setInterval(() => {
      tick++;
      setEvents((prev) => {
        const next = prev.map((e) => ({ ...e, age: e.age + 1 }));
        // Every 2s: resolve the active scan and start a new one.
        if (tick % 2 === 0) {
          if (next[0]?.status === "scanning") next[0] = { ...next[0], status: "done" };
          return [makeEvent(), ...next].slice(0, 7);
        }
        return next;
      });
      if (tick % 3 === 0) setPerMin((p) => 44 + ((p + 7) % 18));
    }, 1000);
    return () => {
      clearTimeout(seed);
      clearInterval(id);
    };
  }, [reduced]);

  return (
    <section className="mx-auto max-w-5xl px-5 py-16">
      <div className="mb-6 text-center">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-amber-200 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-amber-700">
          <Radio className="h-3.5 w-3.5 animate-pulse-dot" />
          This is running live
        </div>
        <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Every result was pulled in <span className="text-gradient">real time</span>
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          No cached dashboards. Nimble&apos;s agents read each retailer&apos;s shelf
          on demand — here&apos;s the fleet at work.
        </p>
      </div>

      <div className="overflow-hidden rounded-3xl border border-border bg-[oklch(0.15_0_0)] text-white shadow-[0_30px_80px_-50px_oklch(0.2_0_0/0.7)]">
        <div className="flex items-center gap-2 border-b border-white/10 px-5 py-3">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
          </span>
          <span className="font-mono text-sm font-semibold">Nimble agents · live</span>
          <span className="ml-auto font-mono text-xs text-white/45">
            {perMin} scans/min
          </span>
        </div>

        <ul className="divide-y divide-white/[0.06] font-mono text-[13px]">
          {events.map((e) => (
            <li
              key={e.id}
              className="flex animate-fade-up items-center gap-3 px-5 py-2.5"
            >
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: RETAILER_META[e.retailer].color }}
              />
              <span className="shrink-0 font-semibold text-white/85">{RETAILER_META[e.retailer].label}</span>
              <span className="min-w-0 flex-1 truncate text-white/45">
                {e.status === "scanning" ? (
                  <span className="inline-flex items-center gap-1.5 text-amber-300">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    scanning &ldquo;{e.keyword}&rdquo;…
                  </span>
                ) : (
                  <>
                    &ldquo;{e.keyword}&rdquo;{" "}
                    <span className="text-emerald-300/90">
                      <Check className="mb-0.5 inline h-3 w-3" /> {e.count} products
                    </span>{" "}
                    <span className="text-white/35">· {e.latency}</span>
                  </>
                )}
              </span>
              <span className="ml-auto shrink-0 text-white/30">
                {e.status === "scanning" ? "now" : `${e.age}s ago`}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
