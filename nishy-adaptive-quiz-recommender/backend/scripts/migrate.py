"""Apply the assessment schema once before starting the production API."""
import os
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv()
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL is required for Supabase migration.")
    import psycopg2

    connection = psycopg2.connect(url, sslmode="require", connect_timeout=10)
    try:
        with connection:
            with connection.cursor() as cursor:
                # Serialize simultaneous deploys without a public exec_sql RPC.
                cursor.execute("SELECT pg_advisory_xact_lock(26041001)")
                for migration in sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")):
                    cursor.execute(migration.read_text(encoding="utf-8"))
    finally:
        connection.close()
    print("Supabase assessment schema is ready.")


if __name__ == "__main__":
    main()
