import { connectSlackCredentials } from "@vercel/connect/eve";
import { slackChannel } from "eve/channels/slack";

// Slack through Vercel Connect: no bot token or signing secret in the project.
export default slackChannel({
  credentials: connectSlackCredentials(process.env.SLACK_CONNECTOR ?? "slack/pricing-brief"),
});
