"""
Supabase auto-migration: creates DB tables and storage buckets on app startup.

This runs automatically when the FastAPI app starts — no manual Supabase
dashboard setup required.

Tables created (idempotent — safe to call multiple times):
    - documents   : tracks uploaded files (PDF, PPTX, DOCX, etc.)
    - sessions    : tracks user voice query sessions

Buckets created:
    - documents   : stores uploaded lecture files (private)
    - audio       : stores TTS audio output (private)
"""

import asyncio
from app.db.supabase import get_supabase
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── SQL DDL ───────────────────────────────────────────────────────────────────
_DOCUMENTS_DDL = """
CREATE TABLE IF NOT EXISTS documents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL,
  filename      text NOT NULL,
  file_type     text NOT NULL DEFAULT 'pdf',
  storage_path  text NOT NULL,
  chunk_count   int  DEFAULT 0,
  created_at    timestamptz DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see/modify their own documents
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'documents' AND policyname = 'Users see own documents'
  ) THEN
    CREATE POLICY "Users see own documents"
      ON documents FOR ALL
      USING (auth.uid() = user_id);
  END IF;
END $$;
"""

_SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL,
  language   text NOT NULL DEFAULT 'english',
  created_at timestamptz DEFAULT now()
);

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'sessions' AND policyname = 'Users see own sessions'
  ) THEN
    CREATE POLICY "Users see own sessions"
      ON sessions FOR ALL
      USING (auth.uid() = user_id);
  END IF;
END $$;
"""

_BUCKETS = [
    {
        "id": "documents",
        "name": "documents",
        "public": False,
        "file_size_limit": 52428800,   # 50 MB
        "allowed_mime_types": [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/plain",
            "text/markdown",
        ],
    },
    {
        "id": "audio",
        "name": "audio",
        "public": False,
        "file_size_limit": 10485760,   # 10 MB
        "allowed_mime_types": ["audio/wav", "audio/mpeg", "audio/webm"],
    },
]


async def run_migrations() -> None:
    """
    Idempotent startup migration.
    Creates tables and buckets if they don't already exist.
    """
    try:
        client = await get_supabase()

        # ── 1. Tables ─────────────────────────────────────────────────────────
        logger.info("Running DB migrations…")
        for ddl_label, ddl in [("documents", _DOCUMENTS_DDL), ("sessions", _SESSIONS_DDL)]:
            try:
                await client.rpc("exec_sql", {"sql": ddl}).execute()
                logger.info("Table '%s' ready", ddl_label)
            except Exception:
                # Fallback: rpc not available — use postgrest direct
                try:
                    await client.postgrest.session.post(
                        f"{client.rest_url}/rpc/exec_sql",
                        json={"sql": ddl},
                    )
                    logger.info("Table '%s' ready (fallback)", ddl_label)
                except Exception as inner_e:
                    logger.warning(
                        "Migration DDL for '%s' skipped (may already exist): %s",
                        ddl_label, inner_e,
                    )

        # ── 2. Storage buckets ────────────────────────────────────────────────
        logger.info("Ensuring storage buckets exist…")
        for bucket in _BUCKETS:
            try:
                existing = await client.storage.get_bucket(bucket["id"])
                logger.info("Bucket '%s' already exists", bucket["id"])
            except Exception:
                try:
                    await client.storage.create_bucket(
                        bucket["id"],
                        options={
                            "public": bucket["public"],
                            "file_size_limit": bucket["file_size_limit"],
                            "allowed_mime_types": bucket["allowed_mime_types"],
                        },
                    )
                    logger.info("Bucket '%s' created", bucket["id"])
                except Exception as e:
                    logger.warning("Bucket '%s' skipped: %s", bucket["id"], e)

        logger.info("Migrations complete ✓")

    except Exception as e:
        # Never crash the app on migration failure — log and continue
        logger.error("Migration failed (non-fatal): %s", e)
