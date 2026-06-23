import { createApp, server, analytics } from '@databricks/appkit';
import type { Request, Response } from 'express';

const SCOUT_SQL = `
INSERT INTO users.toms_nimbleway_com.local_biz_scout
SELECT /*+ REPARTITION(10) */
  '__SEARCH_ID__'                                                            AS search_id,
  current_timestamp()                                                        AS searched_at,
  '__BUSINESS_TYPE__'                                                        AS business_type,
  '__LOCATION__'                                                             AS location,
  s.title                                                                    AS search_title,
  s.url                                                                      AS search_url,
  CAST(v.value:SearchResult[0]:title        AS STRING)                      AS name,
  try_cast(regexp_replace(
    CAST(v.value:SearchResult[0]:rating AS STRING), '[^0-9.]', '') AS DOUBLE) AS rating,
  try_cast(regexp_replace(
    CAST(v.value:SearchResult[0]:number_of_reviews AS STRING), '[^0-9]', '') AS INT) AS review_count,
  CAST(v.value:SearchResult[0]:price_level  AS STRING)                      AS price_level,
  CAST(v.value:SearchResult[0]:address      AS STRING)                      AS address,
  CAST(v.value:SearchResult[0]:phone_number AS STRING)                      AS phone_number,
  CAST(v.value:SearchResult[0]:place_url    AS STRING)                      AS place_url,
  CAST(v.value:SearchResult[0]:business_category[0] AS STRING)              AS category,
  v.value:SearchResult[0]                                                    AS raw,
  current_timestamp()                                                        AS ingested_at
FROM nimble_integration.tools.nimble_search(
  '__SEARCH_QUERY__', __MAX_RESULTS__, 'location', 'lite', 'US', 'en', NULL, NULL, NULL
) s,
LATERAL nimble_integration.tools.nimble_agent_run(
  'google_maps_search',
  to_json(named_struct('query', CONCAT(s.title, ' ', '__LOCATION__'))),
  false
) r,
LATERAL variant_explode(r.parsing) v
WHERE r.status = 'success'
  AND v.pos = 0
  AND v.value:SearchResult[0] IS NOT NULL
`;

function buildSql(
  searchId: string,
  businessType: string,
  location: string,
  searchQuery: string,
  maxResults: number,
): string {
  const esc = (s: string) => s.replace(/'/g, "''");
  return SCOUT_SQL
    .replace(/__SEARCH_ID__/g,      esc(searchId))
    .replace(/__BUSINESS_TYPE__/g,  esc(businessType))
    .replace(/__LOCATION__/g,       esc(location))
    .replace(/__SEARCH_QUERY__/g,   esc(searchQuery))
    .replace(/__MAX_RESULTS__/g,    String(Math.min(Math.max(1, maxResults), 100)));
}

// In-memory job registry (per-process; resets on restart)
type JobState = 'running' | 'succeeded' | 'failed';
const jobs = new Map<string, { state: JobState; error: string | null }>();

await createApp({
  plugins: [server(), analytics({})],

  onPluginsReady(appkit) {
    appkit.server.extend((app) => {
      app.post('/api/scout', async (req: Request, res: Response) => {
        try {
          const { businessType, location, maxResults = 10 } = req.body as {
            businessType: string;
            location: string;
            maxResults?: number;
          };

          if (!businessType?.trim() || !location?.trim()) {
            res.status(400).json({ error: 'businessType and location are required' });
            return;
          }

          const searchId = crypto.randomUUID();
          const searchQuery = `${businessType.trim()} in ${location.trim()}`;
          const statement = buildSql(
            searchId,
            businessType.trim(),
            location.trim(),
            searchQuery,
            maxResults,
          );

          // Register job as running before responding
          jobs.set(searchId, { state: 'running', error: null });
          res.json({ statementId: searchId, searchId });

          // Run INSERT in background using analytics plugin (has proper auth)
          appkit.analytics.query(statement).then(() => {
            jobs.set(searchId, { state: 'succeeded', error: null });
          }).catch((err: unknown) => {
            const message = err instanceof Error ? err.message : String(err);
            console.error('[scout] INSERT failed:', message);
            jobs.set(searchId, { state: 'failed', error: message });
          });
        } catch (err) {
          console.error('[scout]', err);
          res.status(500).json({ error: 'Failed to start search' });
        }
      });

      app.get('/api/scout/status/:statementId', (req: Request, res: Response) => {
        const id = Array.isArray(req.params.statementId)
          ? req.params.statementId[0]
          : req.params.statementId;
        const job = jobs.get(id);
        if (!job) {
          res.status(404).json({ state: 'UNKNOWN', error: 'Job not found' });
          return;
        }
        // Map internal state to the state names the frontend expects
        const stateMap: Record<JobState, string> = {
          running:   'RUNNING',
          succeeded: 'SUCCEEDED',
          failed:    'FAILED',
        };
        res.json({ state: stateMap[job.state], error: job.error });
      });
    });
  },
});
