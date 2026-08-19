"""
Supabase client factory.
Uses the service-role key for server-side operations (bypasses RLS).
Compatible with supabase-py v2.7+ and v2.31+.
"""

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_supabase_client = None


async def get_supabase():
    """Return a cached async Supabase client. Works with supabase v2.7–v2.31+."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    settings = get_settings()
    url = settings.supabase_url
    key = settings.supabase_service_role_key

    # Try async client first (supabase >= 2.7)
    try:
        from supabase import acreate_client
        _supabase_client = await acreate_client(url, key)
        logger.info("Supabase: connected via acreate_client")
        return _supabase_client
    except (ImportError, AttributeError):
        pass

    # Fallback: create_async_client (supabase >= 2.31)
    try:
        from supabase import create_async_client
        _supabase_client = await create_async_client(url, key)
        logger.info("Supabase: connected via create_async_client")
        return _supabase_client
    except (ImportError, AttributeError):
        pass

    # Last resort: sync client wrapped (shouldn't be needed but safe)
    from supabase import create_client
    _supabase_client = create_client(url, key)
    logger.warning("Supabase: using sync create_client fallback")
    return _supabase_client
