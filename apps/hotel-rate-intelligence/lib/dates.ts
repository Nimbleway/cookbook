// Date utility functions for the rate sweep

// Returns the next Saturday from today (or today if today is Saturday)
export function nextSaturday(from: Date = new Date()): Date {
  const d = new Date(from);
  const day = d.getDay(); // 0=Sun, 6=Sat
  const daysUntilSat = day === 6 ? 0 : (6 - day);
  d.setDate(d.getDate() + daysUntilSat);
  return d;
}

// Returns an array of YYYY-MM-DD strings for `count` days starting at `start`
export function dateRange(start: Date, count: number): string[] {
  const dates: string[] = [];
  for (let i = 0; i < count; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    dates.push(toISODate(d));
  }
  return dates;
}

export function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

// Format a date as "Sat Jun 21" for display
export function formatDateLabel(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

// OTA date parameters: Booking.com and Expedia encode checkin/checkout as query params
// These helpers produce the URL param string to append to a listing URL
export function bookingDateParams(checkin: string, checkout: string): string {
  // checkin/checkout: YYYY-MM-DD
  return `checkin=${checkin}&checkout=${checkout}&group_adults=2&no_rooms=1`;
}

export function expediaDateParams(checkin: string, checkout: string): string {
  // Expedia uses startDate/endDate in ISO format on property pages
  return `startDate=${checkin}&endDate=${checkout}`;
}
