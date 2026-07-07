"use client";

import type { SearchState } from "@/lib/use-search";
import { ALL_RETAILERS } from "@/lib/retailers";

// A slim fixed gold bar at the very top of the viewport — the global "working"
// signal during a live pull. Determinate by retailers-arrived; fills to 100%
// and fades out when the search settles. Pure (no effects): width + opacity are
// derived from status, and CSS transitions animate the change.
export function TopProgress({ state }: { state: SearchState }) {
  const active = state.status === "loading" || state.status === "partial";
  const done = state.status === "done";
  // During the live pull, progress = live retailers that have landed.
  const arrived = ALL_RETAILERS.length - state.pending.length;

  const width = active
    ? Math.max(10, Math.round((arrived / ALL_RETAILERS.length) * 100))
    : done
      ? 100
      : 0;
  const opacity = active ? 1 : 0; // done → full width, fading out

  return (
    <div
      className="pointer-events-none fixed inset-x-0 top-0 z-[70] h-[3px]"
      aria-hidden
    >
      <div
        className="bg-gold h-full rounded-r-full transition-[width,opacity] duration-300 ease-out"
        style={{
          width: `${width}%`,
          opacity,
          boxShadow: "0 0 10px oklch(0.84 0.17 100 / 0.7)",
        }}
      />
    </div>
  );
}
