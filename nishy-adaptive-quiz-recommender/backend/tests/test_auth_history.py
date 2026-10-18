import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import Depends, FastAPI
from app.auth import authorize_request
from app.routers.history import router
from app.services.db_service import DbService

RealClient = httpx.AsyncClient


class AccountHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {"DATABASE_URL": "", "SUPABASE_URL": "https://auth.example", "SUPABASE_ANON_KEY": "public-test-key"})
        self.env.start()
        self.path = patch("app.services.db_service.DB_PATH", ":memory:")
        self.path.start()
        self.db = DbService()
        self.db.is_postgres = True  # Keep the shared in-memory fixture open between requests.
        for user in ("alice", "bob"):
            self.db.create_session(dict(session_id=user + "-quiz", student_id=user, exam_type="mcq", num_questions=5,
                                        difficulty_mode="easy", time_limit_min=None, status="ready",
                                        chroma_collection_id=user, is_topic_session=1, title="Lipids"))
            self.db.save_document(dict(document_id=user + "-doc", filename="notes.txt", topics="[]", chunk_count=1, user_id=user))
        self.db_patch = patch("app.services.db_service.DbService", return_value=self.db)
        self.db_patch.start()
        self.history_patch = patch("app.routers.history.DbService", return_value=self.db)
        self.history_patch.start()
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/history", dependencies=[Depends(authorize_request)])
        @app.get("/api/v1/session/{session_id}/status", dependencies=[Depends(authorize_request)])
        def status(session_id: str):
            return {"status": "ready"}
        self.client = RealClient(transport=httpx.ASGITransport(app=app), base_url="https://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.history_patch.stop(); self.db_patch.stop()
        self.db.conn.close(); self.path.stop(); self.env.stop()

    async def request(self, method, path, user="alice", status=200):
        remote = AsyncMock()
        remote.__aenter__.return_value.get.return_value = httpx.Response(status, json={"id": user})
        with patch("app.auth.httpx.AsyncClient", return_value=remote):
            return await self.client.request(method, path, headers={"Authorization": "Bearer test-access-token"})

    async def test_authentication_required_and_invalid_tokens_rejected(self):
        self.assertEqual((await self.client.get("/api/v1/history")).status_code, 401)
        self.assertEqual((await self.request("GET", "/api/v1/history", status=401)).status_code, 401)

    async def test_private_history_and_cross_account_access(self):
        result = await self.request("GET", "/api/v1/history")
        self.assertEqual([x["session_id"] for x in result.json()], ["alice-quiz"])
        for suffix in ("trash", "restore"):
            self.assertEqual((await self.request("POST", "/api/v1/history/bob-quiz/" + suffix)).status_code, 404)
        self.assertEqual((await self.request("GET", "/api/v1/session/bob-quiz/status")).status_code, 404)
        self.assertEqual([d["document_id"] for d in self.db.get_all_documents("alice")], ["alice-doc"])

    async def test_recycle_bin_restore_preserves_progress(self):
        self.db.conn.execute("INSERT INTO questions(q_id, session_id) VALUES ('q1', 'alice-quiz')")
        self.db.record_attempt("alice-quiz", dict(q_id="q1", student_answer="2", score=100, is_correct=True))
        self.db.record_report("alice-quiz", {"final_score": 100})
        before = (await self.request("GET", "/api/v1/history")).json()[0]
        self.assertEqual(before["answered"], 1)
        self.assertEqual(before["status"], "completed")
        for _ in range(2):
            self.assertEqual((await self.request("POST", "/api/v1/history/alice-quiz/trash")).status_code, 200)
        self.assertEqual((await self.request("GET", "/api/v1/history")).json(), [])
        self.assertEqual(len((await self.request("GET", "/api/v1/history?deleted=true")).json()), 1)
        self.assertEqual((await self.request("GET", "/api/v1/session/alice-quiz/status")).status_code, 404)
        self.assertEqual((await self.request("POST", "/api/v1/history/alice-quiz/restore")).status_code, 200)
        after = (await self.request("GET", "/api/v1/history")).json()[0]
        self.assertEqual(before, after)
        self.assertEqual((await self.request("GET", "/api/v1/history?deleted=true")).json(), [])

    async def test_auth_outage_fails_closed(self):
        self.assertEqual((await self.request("GET", "/api/v1/history", status=503)).status_code, 503)


if __name__ == "__main__":
    unittest.main()
