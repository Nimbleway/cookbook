# AI setup guide: Deep Web Alpha Tracker

Open this file in Claude Code (or another AI coding assistant) and ask it to set the app up.

1. Run `npm install` in this folder.
2. Ask the user for a Supabase project. Run `supabase/schema.sql` against it (SQL editor, or `supabase db query --linked -f supabase/schema.sql`). Put `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env.local`. Never commit keys.
3. Put `NIMBLE_API_KEY` in `.env.local`. Run `npm run agents:find`; for each agent it cannot find, create one from the matching gallery template (`POST https://sdk.nimbleway.com/v2/agents` with `"template": "hf-…"` and `"agent_name": "gallery-hf-…"`), then run it again and copy the lines into `.env.local`.
4. Optional: `SLACK_WEBHOOK_URL`, `APP_URL`, `REFRESH_KEY`.
5. Run `npm run seed`, then `npm run dev`, and open http://localhost:3000.
6. Verify: the header shows "Sample data"; switching off Low and Medium in the confidence filter lowers the datapoint count; clicking a row opens the drawer with citations.
7. To load live data, use Refresh with a few agents first (for example Catalysts and Forensic at `high`), check the results, then run the rest. A full refresh is 450 runs; mind the account's daily run limit.
8. Deploy with `vercel deploy --prod` after adding every variable from `.env.example` with `vercel env add`.
