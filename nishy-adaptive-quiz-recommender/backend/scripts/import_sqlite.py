"""Copy existing assessment records to Supabase without replacing cloud rows.

Run migrate.py first. Source SQLite is opened read-only; the entire import is
one PostgreSQL transaction. This does not copy Chroma or graph checkpoints.
"""
import argparse
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

TABLES = ("documents", "sessions", "questions", "answers", "analytics", "research_logs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", required=True, type=Path)
    args = parser.parse_args()
    load_dotenv()
    if not os.getenv("DATABASE_URL", "").strip():
        raise SystemExit("DATABASE_URL is required.")
    source_path = args.sqlite.resolve(strict=True)
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import execute_values

    source = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)
    destination = psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require", connect_timeout=10)
    counts = []
    try:
        with destination:
            with destination.cursor() as cursor:
                cursor.execute("SET LOCAL search_path TO nishy_quiz, pg_catalog")
                for table in TABLES:
                    if not source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                        continue
                    rows = source.execute(f'SELECT * FROM "{table}"')
                    columns = [item[0] for item in rows.description]
                    query = sql.SQL("INSERT INTO {} ({}) VALUES %s ON CONFLICT DO NOTHING").format(
                        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
                    )
                    inserted = total = 0
                    while batch := rows.fetchmany(500):
                        # One page makes rowcount cover the entire batch.
                        execute_values(cursor, query, batch, page_size=500)
                        inserted += cursor.rowcount
                        total += len(batch)
                    counts.append((table, inserted, total))
    finally:
        source.close()
        destination.close()
    for table, inserted, total in counts:
        print(f"{table}: imported {inserted}, existing {total - inserted}")


if __name__ == "__main__":
    main()
