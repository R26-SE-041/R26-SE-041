"""Small DB-API bridge for the assessment service's parameterized queries.

Each statement owns a pooled connection and transaction. Results are buffered
before returning the connection, so API threads never share transactions.
"""
import os
import re
from functools import lru_cache
from threading import BoundedSemaphore, Lock

_pool_size = max(1, int(os.getenv("DB_POOL_MAX", "10")))
_pool_slots = BoundedSemaphore(_pool_size)
_pool_lock = Lock()


@lru_cache(maxsize=1)
def _create_pool():
    from psycopg2.pool import ThreadedConnectionPool

    return ThreadedConnectionPool(
        1, _pool_size,
        dsn=os.environ["DATABASE_URL"],
        connect_timeout=10,
        sslmode="require",
    )


def _pool():
    # lru_cache alone can invoke its factory concurrently on a cache miss.
    with _pool_lock:
        return _create_pool()


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class PostgresConnection:
    def execute(self, query, params=()):
        from psycopg2.extras import RealDictCursor

        # These are internal SQL templates, never user-supplied SQL.
        if isinstance(params, dict):
            query = re.sub(r"(?<!:):([a-zA-Z_]\w*)", r"%(\1)s", query)
        else:
            query = query.replace("?", "%s")
        pool = _pool()
        # psycopg2's pool raises immediately when busy. Polling and background
        # generation must wait for a slot instead of randomly returning 500s.
        if not _pool_slots.acquire(timeout=35):
            raise TimeoutError("Database is busy; connection wait timed out")
        connection = None
        try:
            connection = pool.getconn()
            with connection:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Set these inside the transaction rather than relying on
                    # startup options being forwarded by the Supabase pooler.
                    cursor.execute("SET LOCAL search_path TO nishy_quiz, pg_catalog; SET LOCAL statement_timeout = '30s'")
                    cursor.execute(query, params)
                    rows = cursor.fetchall() if cursor.description else []
            return Rows(rows)
        finally:
            try:
                if connection is not None:
                    pool.putconn(connection)
            finally:
                _pool_slots.release()

    def commit(self):
        # execute() commits each successful statement, rolls back failures.
        pass
