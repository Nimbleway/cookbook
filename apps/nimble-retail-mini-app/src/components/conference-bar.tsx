import { conferenceConfig, isConferenceMode } from "@/lib/config";

// Thin event banner shown only when NEXT_PUBLIC_EVENT_NAME is set.
export function ConferenceBar() {
  if (!isConferenceMode) return null;
  const { eventName } = conferenceConfig;
  return (
    <div className="bg-brand-gradient text-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-2 gap-y-0.5 px-4 py-1.5 text-center text-xs font-medium sm:text-sm">
        <span className="inline-block h-1.5 w-1.5 shrink-0 animate-pulse-dot rounded-full bg-brand" />
        <span className="text-balance">
          Built for <strong>{eventName}</strong> on real-time Nimble retail data
        </span>
      </div>
    </div>
  );
}
