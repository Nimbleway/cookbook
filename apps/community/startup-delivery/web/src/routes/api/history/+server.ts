import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";

/** Server-side history from Tower is not wired yet; the UI uses localStorage. */
export const GET: RequestHandler = async () => {
  return json({
    entries: [],
    source: "client",
    note: "Persisted deliveries are stored in the browser until a Tower list API exists.",
  });
};
