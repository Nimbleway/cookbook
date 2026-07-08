"use client";

import type { RetailerId, RetailerResult } from "@/lib/types";
import { RETAILER_META } from "@/lib/retailers";
import { AlertTriangle } from "lucide-react";

export type RetailerSelection = RetailerId | "all";

// Click a retailer → the whole experience recomputes for that shelf.
// "See how the shelf changes" is a core discovery moment.
export function RetailerTabs({
  results,
  selected,
  onSelect,
}: {
  results: RetailerResult[];
  selected: RetailerSelection;
  onSelect: (sel: RetailerSelection) => void;
}) {
  const ok = results.filter((r) => r.status === "ok");
  const failed = results.filter((r) => r.status === "error");

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Tab active={selected === "all"} onClick={() => onSelect("all")}>
          <span className="font-semibold">All retailers</span>
        </Tab>
        {ok.map((r) => (
          <Tab
            key={r.retailer}
            active={selected === r.retailer}
            color={RETAILER_META[r.retailer].color}
            onClick={() => onSelect(r.retailer)}
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: RETAILER_META[r.retailer].color }}
            />
            <span
              className="font-semibold"
              style={
                selected === r.retailer
                  ? undefined
                  : { color: RETAILER_META[r.retailer].color }
              }
            >
              {RETAILER_META[r.retailer].label}
            </span>
          </Tab>
        ))}
      </div>

      {failed.length > 0 && (
        <div className="flex items-center gap-1.5 text-xs text-brand">
          <AlertTriangle className="h-3.5 w-3.5" />
          {failed.map((f) => RETAILER_META[f.retailer].label).join(", ")}{" "}
          unavailable — showing the rest.
        </div>
      )}
    </div>
  );
}

function Tab({
  active,
  color,
  onClick,
  children,
}: {
  active: boolean;
  color?: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm transition ${
        active
          ? "border-transparent bg-foreground text-background shadow-sm"
          : "border-border bg-card text-foreground hover:border-brand/40"
      }`}
      style={active && color ? { background: color, color: "white" } : undefined}
    >
      {children}
    </button>
  );
}
