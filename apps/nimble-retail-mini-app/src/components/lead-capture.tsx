"use client";

import { ChevronUp } from "lucide-react";
import { useLeadModal } from "./lead-modal";

// Floating launcher for the lead form. Collapsed by default so it never covers
// the report; clicking opens the shared in-app lead modal (no mail-app handoff).
// Desktop = a small gold pill bottom-right; mobile = a slim bottom bar.
export function LeadCapture({
  visible,
  keyword,
  brand,
}: {
  visible: boolean;
  keyword?: string;
  brand?: string | null;
}) {
  const { open } = useLeadModal();
  if (!visible) return null;

  return (
    <>
      {/* Desktop: bottom-right gold pill */}
      <div className="fixed bottom-5 right-5 z-40 hidden lg:block">
        <button
          onClick={() => open({ keyword, brand })}
          className="inline-flex items-center gap-1.5 rounded-full bg-gold px-4 py-2.5 text-sm font-bold text-background shadow-[0_10px_30px_-10px_oklch(0.78_0.16_85/0.6)] transition active:scale-[0.98]"
        >
          Want to know more?
          <ChevronUp className="h-4 w-4" />
        </button>
      </div>

      {/* Mobile: full-width bottom bar */}
      <button
        onClick={() => open({ keyword, brand })}
        className="fixed inset-x-0 bottom-0 z-40 flex w-full items-center justify-center gap-1.5 border-t border-border bg-gold px-4 py-3.5 text-sm font-bold text-background lg:hidden"
      >
        See what Nimble can do for your brand
        <ChevronUp className="h-4 w-4" />
      </button>
    </>
  );
}
