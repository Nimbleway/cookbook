import { AGENTS } from '../lib/agents';

/** Prints .env lines for the agents named gallery-<template> in your Nimble account. */
async function main() {
  const res = await fetch('https://sdk.nimbleway.com/v2/agents?limit=100', {
    headers: { Authorization: `Bearer ${process.env.NIMBLE_API_KEY}` },
  });
  if (!res.ok) throw new Error(`list agents ${res.status}`);
  const { items } = (await res.json()) as { items: { id: string; agent_name: string | null }[] };
  for (const agent of AGENTS) {
    const match = items.find((a) => a.agent_name === `gallery-${agent.template}`);
    console.log(`${agent.envVar}=${match?.id ?? ''}${match ? '' : `   # not found: gallery-${agent.template}`}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
