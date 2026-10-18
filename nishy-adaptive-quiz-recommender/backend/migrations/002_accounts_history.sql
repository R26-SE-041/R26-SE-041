SET LOCAL search_path TO nishy_quiz, pg_catalog;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS deleted_at TEXT;
CREATE INDEX IF NOT EXISTS documents_owner_idx ON documents(user_id, created_at);
CREATE INDEX IF NOT EXISTS sessions_history_idx ON sessions(student_id, deleted_at, created_at);
