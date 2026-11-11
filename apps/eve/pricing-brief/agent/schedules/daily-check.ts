import { defineSchedule } from "eve/schedules";
import slack from "../channels/slack";

// 13:00 UTC = 9:00 in New York. The run posts only when something changed.
export default defineSchedule({
  cron: "0 13 * * *",
  async run({ to, waitUntil, appAuth }) {
    const channelId = process.env.SLACK_CHANNEL_ID;
    if (!channelId) {
      console.warn("[daily-check] SLACK_CHANNEL_ID is not set; skipping.");
      return;
    }
    waitUntil(to(slack, { channelId }).send("Run the daily pricing check.", { auth: appAuth }));
  },
});
