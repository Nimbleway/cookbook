import { AGENT_BY_KEY } from './agents';
import type { ChangeEvent } from './types';

const ARROW = { bullish: '▲', bearish: '▼', neutral: '•' } as const;

/** Slack Block Kit message: one section per company, strongest changes first. */
export function slackMessage(changes: ChangeEvent[], appUrl?: string) {
  const byTicker = new Map<string, ChangeEvent[]>();
  for (const c of [...changes].sort((a, b) => b.magnitude - a.magnitude)) {
    byTicker.set(c.ticker, [...(byTicker.get(c.ticker) ?? []), c]);
  }
  const tickers = [...byTicker.keys()].slice(0, 20);
  const blocks: object[] = [
    { type: 'header', text: { type: 'plain_text', text: `Deep web alpha: ${changes.length} meaningful changes across ${byTicker.size} names` } },
  ];
  for (const t of tickers) {
    const lines = byTicker
      .get(t)!
      .slice(0, 5)
      .map((c) => {
        const src = c.citations[0] ? ` <${c.citations[0].url}|source>` : '';
        return `${ARROW[c.direction]} ${c.headline} · _${AGENT_BY_KEY[c.agent].short}, ${c.confidence} confidence_${src}`;
      });
    blocks.push({ type: 'section', text: { type: 'mrkdwn', text: `*${t}*\n${lines.join('\n')}` } });
  }
  if (appUrl) blocks.push({ type: 'actions', elements: [{ type: 'button', text: { type: 'plain_text', text: 'Open tracker' }, url: appUrl }] });
  return { text: `Deep web alpha: ${changes.length} meaningful changes`, blocks };
}

export async function postToSlack(changes: ChangeEvent[]): Promise<boolean> {
  const url = process.env.SLACK_WEBHOOK_URL;
  if (!url || !changes.length) return false;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(slackMessage(changes, process.env.APP_URL)),
  });
  return res.ok;
}
