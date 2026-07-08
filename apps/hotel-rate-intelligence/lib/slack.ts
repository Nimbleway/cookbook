import { RateFlag, MonitorConfig } from "./types";

export async function sendSlackAlert(
  webhookUrl: string,
  config: MonitorConfig,
  flags: RateFlag[],
  summary: string
): Promise<void> {
  const hotelName = config.userHotel.name;
  const criticalFlags = flags.filter(
    (f) =>
      f.type === "undercutting" &&
      f.percentDiff !== null &&
      f.percentDiff !== undefined &&
      Math.abs(f.percentDiff) >= config.threshold
  );

  const message = {
    text: `Rate alert for ${hotelName}`,
    blocks: [
      {
        type: "header",
        text: {
          type: "plain_text",
          text: `Rate Alert: ${hotelName}`,
        },
      },
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `*${criticalFlags.length} competitive undercutting flags* exceeded your ${config.threshold}% threshold.`,
        },
      },
      ...criticalFlags.slice(0, 5).map((f) => ({
        type: "section",
        text: {
          type: "mrkdwn",
          text: `*${f.date}* - ${f.competitorName} on ${f.ota}: $${f.competitorRate} vs your $${f.userRate} (${f.percentDiff?.toFixed(1)}% below)\n${f.reviewContext ?? ""}\n_${f.note}_`,
        },
      })),
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `*Summary:*\n${summary}`,
        },
      },
    ],
  };

  const res = await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(message),
  });

  if (!res.ok) {
    throw new Error(`Slack webhook failed: ${res.status} ${await res.text()}`);
  }
}
