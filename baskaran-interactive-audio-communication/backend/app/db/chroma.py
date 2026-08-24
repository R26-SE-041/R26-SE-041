"""
ChromaDB client and collection helpers.

In Docker mode  : connects to chromadb container via AsyncHttpClient.
In local dev mode: uses a local PersistentClient (file-based, no server needed).

Local mode is triggered when CHROMA_HOST is "localhost" or "127.0.0.1"
(set CHROMA_HOST=localhost in .env for local dev).
"""

import asyncio
from functools import lru_cache
from pathlib import Path

import chromadb
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Local ChromaDB data directory (relative to backend/)
_LOCAL_DB_PATH = Path(__file__).parent.parent.parent / "chroma_data"


def _is_local_mode() -> bool:
    """Return True when running locally (not inside Docker)."""
    settings = get_settings()
    return settings.chroma_host in ("localhost", "127.0.0.1", "local")


def _collection_name() -> str:
    """Return the BGE-M3-only collection, never the legacy MiniLM collection."""
    configured = get_settings().chroma_collection
    return configured if configured.endswith("_bge_m3") else f"{configured}_bge_m3"


@lru_cache
def _get_persistent_client() -> chromadb.ClientAPI:
    """Return a local persistent ChromaDB client (no server needed)."""
    _LOCAL_DB_PATH.mkdir(parents=True, exist_ok=True)
    logger.info("ChromaDB: using local persistent store at %s", _LOCAL_DB_PATH)
    return chromadb.PersistentClient(path=str(_LOCAL_DB_PATH))


async def _get_async_http_client():
    """Return a remote AsyncHttpClient (Docker/prod mode)."""
    settings = get_settings()
    logger.info("ChromaDB: connecting to remote %s:%s", settings.chroma_host, settings.chroma_port)
    return chromadb.AsyncHttpClient(host=settings.chroma_host, port=settings.chroma_port)


async def get_or_create_collection(client=None):
    """
    Return (or create) the main documents collection.
    Automatically chooses local vs remote ChromaDB based on CHROMA_HOST.
    """
    settings = get_settings()

    if _is_local_mode():
        # Synchronous PersistentClient — wrap blocking calls in thread executor
        sync_client = _get_persistent_client()
        loop = asyncio.get_event_loop()
        collection = await loop.run_in_executor(
            None,
            lambda: sync_client.get_or_create_collection(
                name=_collection_name(),
                metadata={"hnsw:space": "cosine"},
            ),
        )
        return _AsyncCollectionWrapper(collection, loop)
    else:
        # Async HTTP client for Docker/prod
        c = client or await _get_async_http_client()
        return await c.get_or_create_collection(
            name=_collection_name(),
            metadata={"hnsw:space": "cosine"},
        )


class _AsyncCollectionWrapper:
    """
    Wraps a synchronous chromadb.Collection to expose async upsert/query
    methods — so ingestion.py can await them regardless of local vs remote mode.
    """

    def __init__(self, collection, loop: asyncio.AbstractEventLoop):
        self._col = collection
        self._loop = loop

    async def upsert(self, **kwargs):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._col.upsert(**kwargs))

    async def query(self, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._col.query(**kwargs))

    async def count(self) -> int:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._col.count)

    async def delete(self, **kwargs):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._col.delete(**kwargs))

    async def get(self, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._col.get(**kwargs))
