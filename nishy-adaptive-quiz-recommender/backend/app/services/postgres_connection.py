"""Small DB-API bridge for the assessment service's parameterized queries.

Each statement owns a pooled connection and transaction. Results are buffered
before returning the connection, so API threads never share transactions.
"""
import os
import re
from functools import lru_cache


@lru_cache(maxsize=1)
def _pool():
    from psycopg2.pool import ThreadedConnectionPool

    return ThreadedConnectionPool(
        1, int(os.getenv("DB_POOL_MAX", "10")),
        dsn=os.environ["DATABASE_URL"],
        connect_timeout=10,
        sslmode="require",
    )


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
        connection = pool.getconn()
        try:
            with connection:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Set these inside the transaction rather than relying on
                    # startup options being forwarded by the Supabase pooler.
                    cursor.execute("SET LOCAL search_path TO nishy_quiz, pg_catalog; SET LOCAL statement_timeout = '30s'")
                    cursor.execute(query, params)
                    rows = cursor.fetchall() if cursor.description else []
            return Rows(rows)
        finally:
            pool.putconn(connection)

    def commit(self):
        # execute() commits each successful statement, rolls back failures.
        pass
