// What the monitor does with a triaged event: a Slack alert for the ones that matter now,
// and a daily digest for all of them. Sources are rendered from Nimble's trust data, never
// from model-written text.
import { config } from "../config";
import { productBySlug } from "../watchlist";
import type { Citation, MonitoredEvent } from "./events";

const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;
const ICON: Record<string, string> = { critical: "🔴", high: "🟠", medium: "🟡", low: "⚪" };

// Alert only on events that are both serious and well sourced. A serious event the run
// could not confirm still goes to the digest, flagged for a deep dive.
export function shouldAlert(e: MonitoredEvent): boolean {
  const serious = e.triage?.severity === "critical" || e.triage?.severity === "high";
  return serious && e.confidence !== "low";
}

const productNames = (slugs: string[]) => slugs.map((s) => productBySlug(s)?.name ?? s).join(", ");

function sourceLine(c: Citation): string {
  const label = c.title ?? new URL(c.url).hostname.replace(/^www\./, "");
  const kind = [c.sourceType, c.sourceCategory].filter(Boolean).join(", ");
  return `<${c.url}|${label}>${kind ? ` (${kind})` : ""}`;
}

export function slackMessage(e: MonitoredEvent): string {
  const t = e.triage!;
  const status = e.previousStatus ? `${e.status} (was ${e.previousStatus})` : e.status;
  const lines = [
    `${ICON[t.severity]} *${t.severity.toUpperCase()}${e.previousStatus ? " · UPDATE" : ""} · ${e.headline}*`,
    `*Products:* ${productNames(e.products)}  ·  *Where:* ${e.location}  ·  *When:* ${e.eventDate}  ·  *Status:* ${status}`,
    `*How it reaches us:* ${e.impactMechanism}`,
    `*Why this severity:* ${t.rationale}`,
    `*Suggested action:* ${t.recommendedAction}`,
    `*Sources* (confidence: ${e.confidence}): ${e.citations.map(sourceLine).join("  ·  ") || e.sourceUrl}`,
  ];
  const excerpt = e.citations.flatMap((c) => c.excerpts)[0];
  if (excerpt) lines.push(`> ${excerpt}`);
  return lines.join("\n");
}

export async function postToSlack(text: string): Promise<"sent" | "printed"> {
  if (!config.slackWebhookUrl) {
    console.log(`\n── Slack (SLACK_WEBHOOK_URL not set, printing instead) ──\n${text}\n`);
    return "printed";
  }
  const res = await fetch(config.slackWebhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(`Slack webhook returned ${res.status}`);
  return "sent";
}

export function digestMarkdown(input: {
  date: string;
  events: MonitoredEvent[];
  leads: Array<{ product: string; text: string }>;
  startFailures: Array<Record<string, unknown>>;
}): string {
  const out = [`# Supply chain events · ${input.date}`, ""];
  if (!input.events.length) out.push("No new events today.", "");

  const confirmed = input.events.filter((e) => e.confidence !== "low");
  const unconfirmed = input.events.filter((e) => e.confidence === "low");

  for (const sev of SEVERITY_ORDER) {
    const group = confirmed.filter((e) => e.triage?.severity === sev);
    if (!group.length) continue;
    out.push(`## ${ICON[sev]} ${sev[0].toUpperCase()}${sev.slice(1)}`, "");
    for (const e of group) out.push(...eventBlock(e));
  }
  const untriaged = confirmed.filter((e) => !e.triage);
  if (untriaged.length) {
    out.push("## Not yet triaged", "");
    for (const e of untriaged) out.push(...eventBlock(e));
  }
  if (unconfirmed.length) {
    out.push("## Unconfirmed (low confidence — candidates for a deep dive)", "");
    for (const e of unconfirmed) out.push(...eventBlock(e));
  }
  if (input.leads.length) {
    out.push("## Leads the sweep saw but could not confirm", "");
    for (const l of input.leads) out.push(`- **${productBySlug(l.product)?.name ?? l.product}:** ${l.text}`);
    out.push("");
  }
  if (input.startFailures.length) {
    out.push("## Runs that failed to start", "");
    for (const f of input.startFailures) {
      const unknown = f.create_outcome === "unknown";
      out.push(
        `- ${f.product}: ${f.message}${unknown ? " — **may have been created; check the Nimble dashboard before re-running**" : ""}`,
      );
    }
    out.push("");
  }
  return out.join("\n");
}

function eventBlock(e: MonitoredEvent): string[] {
  const status = e.previousStatus ? `${e.status} (was ${e.previousStatus})` : e.status;
  return [
    `### ${e.headline}`,
    `${productNames(e.products)} · ${e.location} · ${e.eventDate} · ${status} · confidence ${e.confidence}`,
    "",
    e.summary,
    "",
    `- **How it reaches us:** ${e.impactMechanism}`,
    ...(e.triage ? [`- **Why:** ${e.triage.rationale}`, `- **Action:** ${e.triage.recommendedAction}`] : []),
    `- **Sources:** ${e.citations.map((c) => `[${c.title ?? new URL(c.url).hostname}](${c.url})`).join(", ") || e.sourceUrl}`,
    "",
  ];
}
