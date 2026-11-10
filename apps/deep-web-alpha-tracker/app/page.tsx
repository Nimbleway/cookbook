import { Dashboard } from '@/components/Dashboard';
import { loadSnapshot } from '@/lib/db';
import { sampleSnapshot } from '@/lib/sample';

export const dynamic = 'force-dynamic';

export default async function Page() {
  if (!process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_ROLE_KEY) {
    return <Dashboard snapshot={sampleSnapshot()} liveShare={0} note="Supabase is not configured, so this is the bundled sample. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, then run npm run seed." />;
  }
  try {
    const snap = await loadSnapshot();
    if (!snap.records.length) {
      return <Dashboard snapshot={sampleSnapshot()} liveShare={0} note="Supabase has no companies yet. Run npm run seed to load the watchlist." />;
    }
    return <Dashboard snapshot={snap} liveShare={snap.liveShare} />;
  } catch (err) {
    return <Dashboard snapshot={sampleSnapshot()} liveShare={0} note={`Could not read Supabase (${(err as Error).message}). Showing the bundled sample.`} />;
  }
}
