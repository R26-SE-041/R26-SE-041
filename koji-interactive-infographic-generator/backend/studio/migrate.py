"""Apply only this component's versioned migrations to its configured project."""
from pathlib import Path
import os
import psycopg2
from dotenv import load_dotenv


def main():
    load_dotenv()
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("Configure DATABASE_URL in backend/.env before applying migrations")
    conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=10)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("select pg_advisory_lock(hashtext('koji-studio-migrations'))")
            cur.execute("""create table if not exists public.koji_schema_migrations
                (name text primary key, applied_at timestamptz not null default now());
                alter table public.koji_schema_migrations enable row level security;
                revoke all on public.koji_schema_migrations from anon, authenticated;""")
            for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                cur.execute("select 1 from public.koji_schema_migrations where name=%s", (path.name,))
                if cur.fetchone():
                    print("Already applied:", path.name)
                    continue
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute("insert into public.koji_schema_migrations(name) values(%s)", (path.name,))
                print("Applied:", path.name)
    finally:
        conn.close()  # Also releases the session advisory lock.


if __name__ == "__main__":
    main()
