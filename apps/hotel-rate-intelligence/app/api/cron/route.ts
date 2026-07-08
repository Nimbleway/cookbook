// Cron job handler - runs on a schedule defined in vercel.json
// This re-uses the exact same core agent function as the on-demand UI flow.
// Required env: KV_REST_API_URL, KV_REST_API_TOKEN, NIMBLE_API_KEY, ANTHROPIC_API_KEY
// Optional: SLACK_WEBHOOK_URL (can also be per-config)

import { NextRequest, NextResponse } from "next/server";
import { runRateIntelAgent } from "@/lib/agent";
import { getMonitorConfigs, saveRunResult, appendRunIndex } from "@/lib/kv";
import { sendSlackAlert } from "@/lib/slack";
import { nextSaturday } from "@/lib/dates";

export const maxDuration = 300;

// Vercel Cron authenticates requests with the CRON_SECRET environment variable.
// Fail-closed: if CRON_SECRET is not set, all requests are rejected.
// Set CRON_SECRET in Vercel project settings before deploying.
function isAuthorized(req: NextRequest): boolean {
  const secret = process.env.CRON_SECRET;
  if (!secret) return false; // fail-closed: no secret = no access
  const authHeader = req.headers.get("authorization");
  return authHeader === `Bearer ${secret}`;
}

export async function GET(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const configs = await getMonitorConfigs();
  if (configs.length === 0) {
    return NextResponse.json({ message: "No monitor configs found", ran: 0 });
  }

  const results = [];

  for (const config of configs) {
    try {
      const startDate = nextSaturday();
      const result = await runRateIntelAgent({
        userHotel: config.userHotel,
        competitors: config.competitors,
        windowDays: config.windowDays,
        startDate: startDate.toISOString().slice(0, 10),
      });

      const runAt = new Date().toISOString();
      const runKey = `run:${config.id}:${runAt}`;

      // Check if any flags exceed the threshold
      const thresholdBreached = result.flags.some(
        (f) =>
          f.type === "undercutting" &&
          f.percentDiff !== null &&
          f.percentDiff !== undefined &&
          Math.abs(f.percentDiff) >= config.threshold
      );

      let alertSent = false;
      if (thresholdBreached && config.slackWebhookUrl) {
        try {
          await sendSlackAlert(config.slackWebhookUrl, config, result.flags, result.summary);
          alertSent = true;
        } catch (err) {
          console.error(`Slack alert failed for config ${config.id}:`, err);
        }
      }

      await saveRunResult({ configId: config.id, runAt, result, alertSent });
      await appendRunIndex(config.id, runKey);

      results.push({
        configId: config.id,
        hotel: config.userHotel.name,
        flagCount: result.flags.length,
        thresholdBreached,
        alertSent,
        errorCount: result.errors.length,
      });
    } catch (err) {
      results.push({
        configId: config.id,
        hotel: config.userHotel.name,
        error: String(err),
      });
    }
  }

  return NextResponse.json({ ran: configs.length, results });
}
