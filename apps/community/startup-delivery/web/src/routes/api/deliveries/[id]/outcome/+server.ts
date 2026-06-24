import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { agentUrl, bridgeHeaders, useMock } from "$lib/server/agent";
import type { OutcomeDecision } from "$lib/types";

// The outcome-capture loop's write path. A founder tells us what actually happened
// — a thumbs on the verdict, a decision (built / passed / still deciding…), and/or
// a free-text note — and we proxy it to the bridge, which records it keyed by
// tracking_id and folds it back onto the delivery. CAPTURE-ONLY: the bridge stores
// the outcome but does NOT feed it into the score (weight-fitting is a later step).
//
// Mirrors the GET proxy next door: same id shape + bridgeHeaders() secret + MOCK
// short-circuit. Degrades gracefully — every failure path returns a JSON error
// object, never a thrown 500, so the quiet capture UI can fail silently and the
// page is never broken by a flaky bridge.
const VALID_ID = /^DEL-\d{8}-(?:[A-Z0-9]{4}|[A-Z0-9]{8})$/i;

const DECISIONS: readonly OutcomeDecision[] = [
  "built",
  "building",
  "passed",
  "considering",
  "dead",
];

const NOTE_MAX = 500;

export const POST: RequestHandler = async ({ params, request }) => {
  const id = params.id.trim().toUpperCase();
  if (!VALID_ID.test(id)) return json({ error: "not found" }, { status: 404 });

  // Parse defensively — a malformed body is a 400, never a 500.
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid body" }, { status: 400 });
  }
  if (typeof body !== "object" || body === null) {
    return json({ error: "invalid body" }, { status: 400 });
  }

  const raw = body as Record<string, unknown>;

  // Build a clean, minimal payload from only the recognized fields. Anything else
  // is dropped so the client can't smuggle extra keys to the bridge.
  const payload: { verdictHelpful?: boolean; decision?: OutcomeDecision; note?: string; source?: string } = {};

  if (typeof raw.verdictHelpful === "boolean") {
    payload.verdictHelpful = raw.verdictHelpful;
  }
  if (typeof raw.decision === "string" && (DECISIONS as readonly string[]).includes(raw.decision)) {
    payload.decision = raw.decision as OutcomeDecision;
  }
  if (typeof raw.note === "string") {
    const note = raw.note.trim();
    if (note.length > NOTE_MAX) return json({ error: "note too long" }, { status: 400 });
    if (note) payload.note = note;
  }

  // At least one meaningful field is required (matches the shared contract + bridge).
  if (
    payload.verdictHelpful === undefined &&
    payload.decision === undefined &&
    payload.note === undefined
  ) {
    return json({ error: "empty outcome" }, { status: 400 });
  }

  // Where the label was captured (weak unbox thumbs vs the stronger permalink
  // return-path) — useful provenance for future outcome calibration. Whitelisted.
  if (raw.source === "unbox" || raw.source === "permalink") {
    payload.source = raw.source;
  }

  if (useMock()) {
    // Canned ok — mirror what the bridge stamps so the UI can reflect it.
    return json({
      ok: true,
      outcome: {
        ...payload,
        capturedAt: new Date().toISOString(),
        source: "web-mock",
      },
    });
  }

  try {
    const res = await fetch(`${agentUrl()}/deliveries/${encodeURIComponent(id)}/outcome`, {
      method: "POST",
      headers: { ...bridgeHeaders(), "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.status === 404) return json({ error: "not found" }, { status: 404 });
    if (res.status === 400) return json({ error: "invalid outcome" }, { status: 400 });
    if (!res.ok) return json({ error: "unavailable" }, { status: 502 });
    return json(await res.json());
  } catch (err) {
    console.error(`[api/deliveries/${id}/outcome] agent unreachable: ${String(err)}`);
    return json({ error: "unavailable" }, { status: 502 });
  }
};
