// Conference/event mode configuration — all public (NEXT_PUBLIC_*) so it's available
// client-side and safe to expose. Drives the event banner and the single
// "talk to Nimble" CTA target. Every contact CTA points to the book-a-demo /
// category-review flow.
// Who the "talk to us" CTAs reach — configurable via NEXT_PUBLIC_CONTACT_EMAIL.
const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "salinas@nimbleway.com";
const contactSubject = "Nimble Retail Intelligence — let's talk";
const contactBody =
  "Hi Menachem,\n\nI just tried the Nimble live retail-shelf demo — I'd love to see it for my brand / category.\n\nThanks!";

export const conferenceConfig = {
  eventName: process.env.NEXT_PUBLIC_EVENT_NAME || "",
  contactEmail,
  // Every "let's talk / see your brand" CTA opens a pre-filled email to the CRO.
  // Override with NEXT_PUBLIC_BOOKING_URL (e.g. a booking page) for variations.
  contactUrl:
    process.env.NEXT_PUBLIC_BOOKING_URL ||
    `mailto:${contactEmail}?subject=${encodeURIComponent(contactSubject)}&body=${encodeURIComponent(contactBody)}`,
};

export const isConferenceMode = Boolean(conferenceConfig.eventName);

// Default: land on the HERO (home page). Set NEXT_PUBLIC_LANDING_CATEGORY to a
// category to instead auto-load a live result on first paint — only worth doing
// on a PREWARMED booth machine (cold serverless would show a ~20s scan on load).
export const landingCategory = (process.env.NEXT_PUBLIC_LANDING_CATEGORY ?? "").trim();
