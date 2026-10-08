"""Real Postgres tests. CI provides an isolated database, never a user project."""
from __future__ import annotations
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4
import psycopg2
from studio.repository import Repository, connection

TEST_URL=os.getenv("STUDIO_TEST_DATABASE_URL")

@unittest.skipUnless(TEST_URL,"Set STUDIO_TEST_DATABASE_URL to an isolated Postgres test database")
class RepositoryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment=patch.dict(os.environ,{"DATABASE_URL":TEST_URL})
        cls.environment.start()
        with connection() as conn,conn.cursor() as cur:
            cur.execute("""
                do $$ begin create role anon; exception when duplicate_object then null; end $$;
                do $$ begin create role authenticated; exception when duplicate_object then null; end $$;
                create schema if not exists auth; create schema if not exists storage;
                create table if not exists auth.users(id uuid primary key);
                create or replace function auth.uid() returns uuid language sql stable as
                    $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
                create table if not exists storage.buckets(id text primary key,name text,public bool,file_size_limit bigint,allowed_mime_types text[]);
                create table if not exists storage.objects(id uuid primary key,bucket_id text,name text);
                alter table storage.objects enable row level security;
                create or replace function storage.foldername(name text) returns text[] language sql immutable as
                    $$ select (string_to_array(name,'/'))[1:array_length(string_to_array(name,'/'),1)-1] $$;
            """)
            for migration in sorted((Path(__file__).parents[1]/"studio/migrations").glob("*.sql")):
                cur.execute(migration.read_text())
        cls.repo=Repository()

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()

    def setUp(self):
        self.owner=str(uuid4()); self.other=str(uuid4())
        with connection() as conn,conn.cursor() as cur:
            cur.execute("insert into auth.users(id) values(%s),(%s)",(self.owner,self.other))

    def tearDown(self):
        with connection() as conn,conn.cursor() as cur:
            cur.execute("delete from auth.users where id in (%s,%s)",(self.owner,self.other))

    def payload(self,**changes):
        return {"request_id":str(uuid4()),"kind":"generate","prompt":"heart","mode":"general",**changes}

    def test_request_id_is_idempotent_but_not_reusable_for_changed_payload(self):
        payload=self.payload()
        first=self.repo.create_job(self.owner,payload,{"image":"https://a.example"})
        again=self.repo.create_job(self.owner,payload,{"image":"https://b.example"})
        self.assertEqual(first["id"],again["id"])
        self.assertEqual(again["endpoints"]["image"],"https://a.example")
        with self.assertRaises(ValueError):
            self.repo.create_job(self.owner,{**payload,"prompt":"fish"},{})

    def test_owner_cannot_read_another_users_job_or_source_generation(self):
        job=self.repo.create_job(self.owner,self.payload(),{})
        self.assertIsNone(self.repo.get_job(self.other,str(job["id"])))
        generation=str(uuid4())
        self.repo.save_history(self.owner,generation,{"chatId":"chat"},self.owner+"/image.png")
        with self.assertRaises(LookupError):
            self.repo.create_job(self.other,self.payload(kind="threed",generation_id=generation),{})

    def test_running_source_job_is_deduplicated(self):
        generation=str(uuid4())
        self.repo.save_history(self.owner,generation,{"chatId":"chat"},self.owner+"/image.png")
        a=self.repo.create_job(self.owner,self.payload(kind="threed",generation_id=generation),{})
        b=self.repo.create_job(self.owner,self.payload(kind="threed",generation_id=generation),{})
        self.assertEqual(a["id"],b["id"])

    def test_expired_lease_is_reclaimed_and_old_worker_is_fenced(self):
        original=self.repo.create_job(self.owner,self.payload(),{})
        first=self.repo.claim()
        self.assertEqual(original["id"],first["id"])
        with connection() as conn,conn.cursor() as cur:
            cur.execute("update koji_jobs set lease_until=now()-interval '1 second' where id=%s",(first["id"],))
        second=self.repo.claim()
        self.assertNotEqual(first["lease_token"],second["lease_token"])
        self.assertFalse(self.repo.heartbeat(first))
        with self.assertRaisesRegex(RuntimeError,"lease lost"):
            self.repo.update_job(first,status="completed")

    def test_late_automatic_labels_do_not_overwrite_manual_edits(self):
        generation=str(uuid4())
        self.repo.save_history(self.owner,generation,{"chatId":"chat"},self.owner+"/image.png")
        self.repo.patch_history(self.owner,generation,{"annotationsEdited":True,"anatomyAnnotations":[{"label":"My correction"}]})
        self.repo.save_auto_labels(self.owner,generation,[{"label":"Automatic"}])
        self.assertEqual(self.repo.get_history(self.owner,generation)["metadata"]["anatomyAnnotations"],[{"label":"My correction"}])

    def test_rls_restricts_direct_authenticated_reads(self):
        self.repo.create_job(self.owner,self.payload(),{})
        with connection() as conn,conn.cursor() as cur:
            cur.execute("grant usage on schema public,auth to authenticated")
            cur.execute("set local role authenticated")
            cur.execute("select set_config('request.jwt.claim.sub',%s,true)",(self.other,))
            cur.execute("select id from koji_jobs")
            self.assertEqual(cur.fetchall(),[])


    def test_question_is_archived_atomically_and_duplicate_completion_merges(self):
        generation=str(uuid4())
        self.repo.save_history(self.owner,generation,{"chatId":"chat"},self.owner+"/image.png")
        payload=self.payload(kind="analysis",generation_id=generation,
            analysis={"id":"question.a","mode":"ask","question":"What is this?",
                      "interaction":{"type":"point","coords":[.3,.7]}})
        job=self.repo.create_job(self.owner,payload,{})
        before=self.repo.get_interactions(self.owner,generation)
        self.assertEqual(before[0]["status"],"queued")
        self.repo.append_interaction(self.owner,generation,{"id":"question.a","answer":"A leaf.","status":"completed"})
        after=self.repo.get_interactions(self.owner,generation)
        self.assertEqual(len(after),1)
        self.assertEqual(after[0]["selection"]["coords"],[.3,.7])
        self.assertEqual(after[0]["jobId"],str(job["id"]))
        self.assertEqual(after[0]["answer"],"A leaf.")

    def test_event_cursor_handles_equal_timestamps_without_losing_old_messages(self):
        timestamp="2026-10-08T00:00:00Z"
        for index in range(65):
            self.repo.append_chat_event(self.owner,"chat",f"event.{index:03}","prompt",
                {"prompt":str(index)},created_at=timestamp)
        first=self.repo.list_chat_events(self.owner,"chat")
        last=first[-1]
        second=self.repo.list_chat_events(self.owner,"chat",last["created_at"],last["id"])
        self.assertEqual(len(first),50)
        self.assertEqual(len(second),15)
        self.assertEqual(len({row["id"] for row in first+second}),65)
        self.assertEqual(self.repo.list_chat_events(self.other,"chat"),[])

    def test_delete_chat_preserves_active_jobs_then_removes_all_model_versions(self):
        generation=str(uuid4())
        self.repo.save_history(self.owner,generation,{"chatId":"chat"},self.owner+"/image.png",
            thumbnail_path=self.owner+"/thumbnail.png")
        self.repo.append_chat_event(self.owner,"chat","version.1","threed",
            {"glbPath":self.owner+"/old.glb"},generation)
        self.repo.append_chat_event(self.owner,"chat","version.2","threed",
            {"glbPath":self.owner+"/new.glb"},generation)
        self.repo.patch_history(self.owner,generation,{},glb_path=self.owner+"/new.glb")
        job=self.repo.create_job(self.owner,self.payload(kind="threed",generation_id=generation),{})
        from unittest.mock import Mock
        remove=Mock()
        with self.assertRaisesRegex(ValueError,"active jobs"):
            self.repo.delete_chat(self.owner,"chat",remove)
        remove.assert_not_called()
        with connection() as conn,conn.cursor() as cur:
            cur.execute("update koji_jobs set status='failed' where id=%s",(job["id"],))
        self.repo.delete_chat(self.owner,"chat",remove)
        self.assertEqual(set(remove.call_args.args[0]),{self.owner+"/image.png",self.owner+"/thumbnail.png",
            self.owner+"/old.glb",self.owner+"/new.glb"})
        self.assertIsNone(self.repo.get_chat(self.owner,"chat"))
        self.assertIsNone(self.repo.get_history(self.owner,generation))

if __name__=="__main__":
    unittest.main()
