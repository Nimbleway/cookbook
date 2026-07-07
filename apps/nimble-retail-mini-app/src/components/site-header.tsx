"use client";
/* eslint-disable @next/next/no-img-element */
import { useLeadModal } from "./lead-modal";

// Floating white pill header: Nimble wordmark on the left (clicking it returns
// home), and a gold "Meet us at [Shoptalk]" CTA on the right using the real
// Shoptalk Europe wordmark — the Nimble × Shoptalk tie-in. Opens the in-app
// lead form. Shown on every page.
export function SiteHeader({ onHome }: { onHome?: () => void }) {
  const { open } = useLeadModal();
  const Logo = (
    <img
      src="/nimble-logo.svg"
      alt="Nimble"
      className="h-[22px] w-auto"
      width={157}
      height={22}
    />
  );
  return (
    <header className="sticky top-0 z-30 bg-gradient-to-b from-background via-background/85 to-transparent px-4 pb-3 pt-3 sm:px-6">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 rounded-full border border-black/5 bg-white/95 px-4 shadow-[0_10px_30px_-14px_oklch(0_0_0/0.7)] backdrop-blur sm:px-5">
        {/* Left: Nimble — click to go home */}
        <div className="flex shrink-0 items-center gap-3">
          {onHome ? (
            <button onClick={onHome} aria-label="Back to home" className="transition active:scale-95">
              {Logo}
            </button>
          ) : (
            Logo
          )}
          <span className="hidden h-4 w-px bg-black/10 lg:block" />
          <span className="hidden text-sm font-medium text-neutral-500 lg:block">
            Retail Intelligence
          </span>
        </div>

        {/* Right: Contact CTA — opens the in-app lead form */}
        <button
          onClick={() => open()}
          className="inline-flex shrink-0 items-center gap-2 rounded-full bg-gold py-2 pl-4 pr-3.5 text-sm font-bold text-[oklch(0.16_0_0)] transition hover:brightness-105 active:scale-[0.98]"
        >
          <span className="whitespace-nowrap">Contact us for more data</span>
        </button>
      </div>
    </header>
  );
}
