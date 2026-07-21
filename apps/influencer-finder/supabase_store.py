"""Supabase store for the influencer dataset. Falls back to no-op (local cache) when
creds are absent or the client can't connect, so the app runs without Supabase."""
import config as C

_TABLE = C.TABLE


def client():
    if not (C.SUPABASE_URL and C.SUPABASE_KEY):
        return None
    try:
        from supabase import create_client
        return create_client(C.SUPABASE_URL, C.SUPABASE_KEY)
    except Exception as e:  # noqa: BLE001
        print(f"  supabase unavailable ({e}); using local cache only")
        return None


def upsert(rows: list) -> int:
    """Upsert influencer rows, deduped on (platform, handle). Returns count written, 0 if no client."""
    sb = client()
    if not sb or not rows:
        return 0
    try:
        sb.table(_TABLE).upsert(rows, on_conflict="platform,handle").execute()
        return len(rows)
    except Exception as e:  # noqa: BLE001
        print(f"  supabase upsert failed ({e}); rows kept in local cache")
        return 0


def fetch_all():
    """Return all rows from Supabase, or None if unavailable (caller falls back to cache)."""
    sb = client()
    if not sb:
        return None
    try:
        return sb.table(_TABLE).select("*").execute().data
    except Exception as e:  # noqa: BLE001
        print(f"  supabase fetch failed ({e})")
        return None
