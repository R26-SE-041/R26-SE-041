"""
Database service for Supabase PostgreSQL and local SQLite development.
"""
import os
import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DB_PATH = os.getenv("SQLITE_DB_PATH", "./db/sessions.db")


class DbService:
    """Assessment persistence; DATABASE_URL selects Supabase PostgreSQL."""

    def __init__(self):
        self.is_postgres = bool(os.getenv("DATABASE_URL", "").strip())
        if self.is_postgres:
            from app.services.postgres_connection import PostgresConnection
            self.conn = PostgresConnection()
            # Schema changes are applied explicitly by scripts/migrate.py.
            return
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate()
        logger.info(f"DbService initialized | db={DB_PATH}")

    def _migrate(self):
        """Add new columns to existing tables if they don't exist (safe migration)."""
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "topics_detected" not in existing:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN topics_detected TEXT DEFAULT '[]'")
            logger.info("Migration: added topics_detected column")
        if "chunk_count" not in existing:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN chunk_count INTEGER DEFAULT 0")
            logger.info("Migration: added chunk_count column")
        if "rating" not in existing:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN rating INTEGER DEFAULT NULL")
            logger.info("Migration: added rating column")
        if "feedback_comment" not in existing:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN feedback_comment TEXT DEFAULT NULL")
            logger.info("Migration: added feedback_comment column")
        if "is_topic_session" not in existing:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN is_topic_session INTEGER DEFAULT 0")
            logger.info("Migration: added is_topic_session column")
        for column in ("title", "deleted_at"):
            if column not in existing:
                self.conn.execute(f"ALTER TABLE sessions ADD COLUMN {column} TEXT")
        document_columns = {row[1] for row in self.conn.execute("PRAGMA table_info(documents)").fetchall()}
        if "user_id" not in document_columns:
            self.conn.execute("ALTER TABLE documents ADD COLUMN user_id TEXT")
        question_columns = {
            row[1] for row in self.conn.execute("PRAGMA table_info(questions)").fetchall()
        }
        question_migrations = {
            "source_file": "TEXT DEFAULT ''",
            "page_number": "INTEGER DEFAULT 0",
            "retrieved_text": "TEXT DEFAULT ''",
            "grounding_status": "TEXT DEFAULT 'rejected'",
        }
        for column, definition in question_migrations.items():
            if column not in question_columns:
                self.conn.execute(f"ALTER TABLE questions ADD COLUMN {column} {definition}")
                logger.info("Migration: added questions.%s", column)
        self.conn.commit()

    def _create_tables(self):
        """Create all tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id     TEXT PRIMARY KEY,
                filename        TEXT NOT NULL,
                topics          TEXT DEFAULT '[]',
                chunk_count     INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id      TEXT PRIMARY KEY,
                student_id      TEXT NOT NULL,
                created_at      TEXT DEFAULT (datetime('now')),
                completed_at    TEXT,
                exam_type       TEXT,
                num_questions   INTEGER,
                difficulty_mode TEXT,
                time_limit_min  INTEGER,
                status          TEXT DEFAULT 'processing',
                chroma_collection_id TEXT,
                topics_detected TEXT DEFAULT '[]',
                chunk_count     INTEGER DEFAULT 0,
                is_topic_session INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS questions (
                q_id            TEXT PRIMARY KEY,
                session_id      TEXT REFERENCES sessions(session_id),
                q_index         INTEGER,
                topic           TEXT,
                bloom_level     TEXT,
                difficulty      REAL,
                q_type          TEXT,
                question_text   TEXT,
                options_json    TEXT,
                correct_answer  TEXT,
                model_answer    TEXT,
                grounding_score REAL,
                is_flagged      INTEGER DEFAULT 0,
                source_file     TEXT DEFAULT '',
                page_number     INTEGER DEFAULT 0,
                retrieved_text  TEXT DEFAULT '',
                grounding_status TEXT DEFAULT 'rejected',
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS answers (
                answer_id       TEXT PRIMARY KEY,
                session_id      TEXT REFERENCES sessions(session_id),
                q_id            TEXT REFERENCES questions(q_id),
                student_answer  TEXT,
                is_correct      INTEGER,
                score           REAL,
                attempt_number  INTEGER,
                hints_used      INTEGER DEFAULT 0,
                time_taken_sec  INTEGER,
                feedback        TEXT,
                misconception   TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS analytics (
                session_id           TEXT PRIMARY KEY REFERENCES sessions(session_id),
                final_score          REAL,
                topic_scores         TEXT,
                bloom_scores         TEXT,
                difficulty_progression TEXT,
                weak_topics          TEXT,
                strong_topics        TEXT,
                recommendations      TEXT,
                avg_grounding_score  REAL,
                flagged_count        INTEGER,
                avg_attempts         REAL,
                avg_hints_used       REAL,
                total_time_sec       INTEGER,
                created_at           TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS research_logs (
                log_id      TEXT PRIMARY KEY,
                session_id  TEXT,
                agent_name  TEXT,
                event_type  TEXT,
                latency_ms  INTEGER,
                extra_data  TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        self.conn.commit()

    # ── Documents ──────────────────────────────────
    def save_document(self, doc: dict) -> None:
        self.conn.execute("""
            INSERT INTO documents (document_id, filename, topics, chunk_count, user_id)
            VALUES (:document_id, :filename, :topics, :chunk_count, :user_id)
            ON CONFLICT(document_id) DO UPDATE SET filename=excluded.filename,
                topics=excluded.topics, chunk_count=excluded.chunk_count
        """, {"user_id": None, **doc})
        self.conn.commit()

    def get_all_documents(self, user_id: str) -> List[dict]:
        rows = self.conn.execute("SELECT * FROM documents WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_documents(self, doc_ids: List[str]) -> List[dict]:
        if not doc_ids:
            return []
        placeholders = ",".join("?" * len(doc_ids))
        rows = self.conn.execute(f"SELECT * FROM documents WHERE document_id IN ({placeholders})", doc_ids).fetchall()
        return [dict(row) for row in rows]

    # ── Session ────────────────────────────────────
    def create_session(self, session: dict) -> None:
        self.conn.execute("""
            INSERT INTO sessions (session_id, student_id, exam_type, num_questions,
                difficulty_mode, time_limit_min, status, chroma_collection_id, is_topic_session, title)
            VALUES (:session_id, :student_id, :exam_type, :num_questions,
                :difficulty_mode, :time_limit_min, :status, :chroma_collection_id, :is_topic_session, :title)
        """, {"title": None, **session})
        self.conn.commit()

    def update_session_status(self, session_id: str, status: str) -> None:
        self.conn.execute(
            "UPDATE sessions SET status=? WHERE session_id=?",
            (status, session_id)
        )
        self.conn.commit()

    def update_session_progress(self, session_id: str, topics: list, chunk_count: int) -> None:
        """Persist topics and chunk_count to DB for status polling."""
        import json
        self.conn.execute(
            "UPDATE sessions SET topics_detected=?, chunk_count=? WHERE session_id=?",
            (json.dumps(topics), chunk_count, session_id)
        )
        self.conn.commit()

    def get_session(self, session_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def save_feedback(self, session_id: str, rating: int, comment: Optional[str]) -> None:
        """Persist post-quiz star rating and optional comment."""
        self.conn.execute(
            "UPDATE sessions SET rating=?, feedback_comment=? WHERE session_id=?",
            (rating, comment, session_id)
        )
        self.conn.commit()
        logger.info(f"Feedback saved | session={session_id} rating={rating}")

    # ── Questions ──────────────────────────────────
    def save_question(self, q: dict) -> None:
        self.conn.execute("""
            INSERT INTO questions
            (q_id, session_id, q_index, topic, bloom_level, difficulty, q_type,
             question_text, options_json, correct_answer, model_answer,
             grounding_score, is_flagged, source_file, page_number,
             retrieved_text, grounding_status)
            VALUES (:q_id, :session_id, :q_index, :topic, :bloom_level, :difficulty,
             :q_type, :question_text, :options_json, :correct_answer, :model_answer,
             :grounding_score, :is_flagged, :source_file, :page_number,
             :retrieved_text, :grounding_status)
            ON CONFLICT(q_id) DO UPDATE SET session_id=excluded.session_id,
                q_index=excluded.q_index, topic=excluded.topic,
                bloom_level=excluded.bloom_level, difficulty=excluded.difficulty,
                q_type=excluded.q_type, question_text=excluded.question_text,
                options_json=excluded.options_json, correct_answer=excluded.correct_answer,
                model_answer=excluded.model_answer, grounding_score=excluded.grounding_score,
                is_flagged=excluded.is_flagged, source_file=excluded.source_file,
                page_number=excluded.page_number, retrieved_text=excluded.retrieved_text,
                grounding_status=excluded.grounding_status
        """, q)
        self.conn.commit()

    def get_previous_questions(
        self,
        student_id: str,
        *,
        exclude_session_id: str = "",
        q_type: Optional[str] = None,
        limit: Optional[int] = 120,
    ) -> List[dict]:
        """Return a learner's recent questions for cross-session deduplication.

        Question generation used to compare candidates only with the current
        in-memory quiz. Starting another quiz could consequently produce the
        same fact and wording again even though it was already persisted.
        """
        clauses = ["s.student_id = ?", "q.session_id <> ?"]
        params: list = [student_id, exclude_session_id]
        if q_type:
            clauses.append("q.q_type = ?")
            params.append(q_type)
        limit_clause = ""
        if limit is not None:
            params.append(max(1, min(int(limit), 500)))
            limit_clause = "LIMIT ?"
        rows = self.conn.execute(
            f"""
            SELECT q.question_text, q.options_json, q.correct_answer,
                   q.model_answer, q.topic, q.q_type
            FROM questions q
            JOIN sessions s ON s.session_id = q.session_id
            WHERE {' AND '.join(clauses)}
            ORDER BY q.created_at DESC, q.q_id DESC
            {limit_clause}
            """,
            params,
        ).fetchall()
        questions = []
        for row in rows:
            item = dict(row)
            try:
                options = json.loads(item.pop("options_json") or "null")
            except (TypeError, json.JSONDecodeError):
                options = None
            questions.append({
                "question": item.pop("question_text", ""),
                "options": options,
                **item,
            })
        return questions

    # ── Answers ────────────────────────────────────
    def save_answer(self, a: dict) -> None:
        self.conn.execute("""
            INSERT INTO answers
            (answer_id, session_id, q_id, student_answer, is_correct, score,
             attempt_number, hints_used, time_taken_sec, feedback, misconception)
            VALUES (:answer_id, :session_id, :q_id, :student_answer, :is_correct,
             :score, :attempt_number, :hints_used, :time_taken_sec, :feedback, :misconception)
            ON CONFLICT(answer_id) DO UPDATE SET student_answer=excluded.student_answer,
                is_correct=excluded.is_correct, score=excluded.score,
                feedback=excluded.feedback, misconception=excluded.misconception
        """, a)
        self.conn.commit()

    # ── Analytics ──────────────────────────────────
    def save_analytics(self, a: dict) -> None:
        self.conn.execute("""
            INSERT INTO analytics
            (session_id, final_score, topic_scores, bloom_scores,
             difficulty_progression, weak_topics, strong_topics, recommendations,
             avg_grounding_score, flagged_count, avg_attempts, avg_hints_used, total_time_sec)
            VALUES (:session_id, :final_score, :topic_scores, :bloom_scores,
             :difficulty_progression, :weak_topics, :strong_topics, :recommendations,
             :avg_grounding_score, :flagged_count, :avg_attempts, :avg_hints_used, :total_time_sec)
            ON CONFLICT(session_id) DO UPDATE SET final_score=excluded.final_score,
                topic_scores=excluded.topic_scores, bloom_scores=excluded.bloom_scores,
                difficulty_progression=excluded.difficulty_progression,
                weak_topics=excluded.weak_topics, strong_topics=excluded.strong_topics,
                recommendations=excluded.recommendations,
                avg_grounding_score=excluded.avg_grounding_score,
                flagged_count=excluded.flagged_count, avg_attempts=excluded.avg_attempts,
                avg_hints_used=excluded.avg_hints_used, total_time_sec=excluded.total_time_sec
        """, a)
        self.conn.commit()

    def get_analytics(self, session_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM analytics WHERE session_id=?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def record_attempt(self, session_id: str, answer: dict):
        import uuid
        attempt = int(answer.get("attempts", 1))
        self.save_answer({
            "answer_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{answer['q_id']}:{attempt}")),
            "session_id": session_id, "q_id": answer["q_id"],
            "student_answer": answer.get("student_answer", ""),
            "is_correct": int(bool(answer.get("is_correct"))), "score": answer.get("score", 0),
            "attempt_number": attempt, "hints_used": answer.get("hints_used", 0),
            "time_taken_sec": answer.get("time_taken_sec", 0),
            "feedback": answer.get("feedback", ""), "misconception": answer.get("misconception"),
        })

    def record_report(self, session_id: str, report: dict):
        from datetime import timezone
        fields = ("topic_scores", "bloom_scores", "difficulty_progression", "weak_topics", "strong_topics", "recommendations")
        payload = {key: json.dumps(report.get(key, {} if key.endswith("scores") else [])) for key in fields}
        for key in ("final_score", "avg_grounding_score", "avg_attempts", "avg_hints_used", "total_time_sec"):
            payload[key] = report.get(key, 0)
        self.save_analytics({**payload, "session_id": session_id, "flagged_count": report.get("flagged_questions_count", 0)})
        self.conn.execute("UPDATE sessions SET status='completed', completed_at=COALESCE(completed_at, ?) WHERE session_id=?",
                          (datetime.now(timezone.utc).isoformat(), session_id))
        self.conn.commit()

    # ── Research Logs ─────────────────────────────
    def log_event(self, session_id: str, agent: str, event: str,
                  latency_ms: int = 0, extra: dict = None) -> None:
        import uuid
        self.conn.execute("""
            INSERT INTO research_logs (log_id, session_id, agent_name, event_type, latency_ms, extra_data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), session_id, agent, event, latency_ms,
               json.dumps(extra or {})))
        self.conn.commit()

    def get_history(self, user_id: str, *, deleted=False, limit=100) -> List[dict]:
        condition = "IS NOT NULL" if deleted else "IS NULL"
        rows = self.conn.execute(f"""
            SELECT s.session_id, s.title, s.created_at, s.completed_at, s.exam_type,
                   s.num_questions, s.difficulty_mode, s.status, s.topics_detected,
                   s.deleted_at, a.final_score,
                   (SELECT COUNT(DISTINCT q_id) FROM answers WHERE session_id=s.session_id) AS answered
            FROM sessions s LEFT JOIN analytics a ON a.session_id=s.session_id
            WHERE s.student_id=? AND s.deleted_at {condition}
            ORDER BY s.created_at DESC, s.session_id DESC LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def move_history(self, session_id: str, user_id: str, deleted: bool):
        from datetime import timezone
        self.conn.execute("UPDATE sessions SET deleted_at=? WHERE session_id=? AND student_id=?",
                          (datetime.now(timezone.utc).isoformat() if deleted else None, session_id, user_id))
        self.conn.commit()
