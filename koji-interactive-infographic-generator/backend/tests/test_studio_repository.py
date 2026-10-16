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
            cur.execute("delete from agent_feedback where auth_user_id in (%s,%s)",(self.owner,self.other))
            cur.execute("delete from auth.users where id in (%s,%s)",(self.owner,self.other))

    def payload(self,**changes):
        return {"request_id":str(uuid4()),"kind":"generate","prompt":"heart","mode":"general",**changes}

    def test_output_ratings_save_change_and_remain_private_for_every_agent(self):
        from shared.db import _FEEDBACK_AGENTS
        for agent in _FEEDBACK_AGENTS:
            output=str(uuid4())
            data={"session_id":"test","agent_name":agent,"output_id":output,"rating":1}
            first=self.repo.save_feedback(self.owner,data)
            with self.assertRaises(LookupError):
                self.repo.save_feedback(self.other,{**data,"rating":-1})
            second=self.repo.save_feedback(self.owner,{**data,"rating":-1,"comment":"User marked this output as not useful."})
            self.assertEqual(first["feedback_id"],second["feedback_id"])
            with connection() as conn,conn.cursor() as cur:
                cur.execute("select rating,auth_user_id::text from agent_feedback where output_id=%s",(output,))
                self.assertEqual(cur.fetchone(),(-1,self.owner))
                cur.execute("set local role authenticated")
                cur.execute("select set_config('request.jwt.claim.sub',%s,true)",(self.other,))
                cur.execute("select id from agent_feedback where output_id=%s",(output,))
                self.assertEqual(cur.fetchall(),[])

    def test_feedback_pairs_require_owned_disliked_output_in_same_session(self):
        data={"session_id":"test","agent_name":"image-agent","output_id":str(uuid4()),"rating":-1}
        negative=self.repo.save_feedback(self.owner,data)
        retry={**data,"output_id":str(uuid4()),"rating":1,"parent_feedback_id":negative["feedback_id"]}
        with self.assertRaises(ValueError):
            self.repo.save_feedback(self.other,retry)
        pair=self.repo.save_feedback(self.owner,retry)
        self.assertIsNotNone(pair["preference_pair_id"])

    def test_request_id_is_idempotent_but_not_reusable_for_changed_payload(self):
        payload=self.payload()
        first=self.repo.create_job(self.owner,payload,{"image":"https://a.example"})
        again=self.repo.create_job(self.owner,payload,{"image":"https://b.example"})
        self.assertEqual(first["id"],again["id"])
        self.assertEqual(again["endpoints"]["image"],"https://a.example")
        with self.assertRaises(ValueError):
            self.repo.create_job(self.owner,{**payload,"prompt":"fish"},{})

    def test_archive_groups_versions_and_filters_without_crossing_owners(self):
        from datetime import datetime, timezone, timedelta
        first, latest, foreign = (str(uuid4()) for _ in range(3))
        self.repo.save_history(self.owner,first,{"chatId":"heart-study","prompt":"Heart study","mode":"anatomy"},self.owner+"/first.png")
        self.repo.save_history(self.owner,latest,{"chatId":"heart-study","prompt":"Heart study","mode":"anatomy"},self.owner+"/latest.png")
        self.repo.save_history(self.other,foreign,{"chatId":"heart-study","mode":"sketch"},self.other+"/private.png")
        self.repo.append_chat_event(self.owner,"heart-study","prompt.test","prompt",{"prompt":"Heart study","mode":"anatomy"})
        self.repo.append_chat_event(self.other,"heart-study","prompt.test","prompt",{"prompt":"Private drawing","mode":"sketch"})
        with connection() as conn,conn.cursor() as cur:
            cur.execute("update koji_generations set created_at=now()-interval '1 day' where id=%s",(first,))
        rows=self.repo.list_chats(self.owner,query="heart",mode="anatomy",since=datetime.now(timezone.utc)-timedelta(days=7))
        self.assertEqual(len(rows),1)
        self.assertEqual(str(rows[0]["latest_generation_id"]),latest)
        self.assertEqual(rows[0]["version_count"],2)
        self.assertEqual(rows[0]["preview_path"],self.owner+"/latest.png")
        self.assertEqual(self.repo.list_chats(self.owner,mode="sketch"),[])
        self.assertEqual(self.repo.list_chats(self.owner,since=datetime.now(timezone.utc)+timedelta(days=1)),[])

    def test_owner_cannot_read_another_users_job_or_source_generation(self):
        job=self.repo.create_job(self.owner,self.payload(),{})
        self.assertIsNone(self.repo.get_job(self.other,str(job["id"])))
        generation=str(uuid4())
        self.repo.save_history(self.owner,generation,{"chatId":"chat"},self.owner+"/image.png")
        with self.assertRaises(LookupError):
            self.repo.create_job(self.other,self.payload(kind="threed",generation_id=generation),{})

    def test_gallery_includes_older_model_versions_and_filters_owner_and_recycle_bin(self):
        generation, latest, sketch, foreign = (str(uuid4()) for _ in range(4))
        self.repo.save_history(self.owner,generation,{"chatId":"models","prompt":"Skull","mode":"anatomy"},self.owner+"/skull.png")
        self.repo.save_history(self.owner,latest,{"chatId":"models","mode":"anatomy"},self.owner+"/latest.png")
        self.repo.save_history(self.owner,sketch,{"chatId":"drawing","mode":"sketch"},self.owner+"/drawing.png")
        self.repo.append_chat_event(self.owner,"drawing","drawing.image","image",{"mode":"sketch"},sketch)
        self.repo.save_history(self.other,foreign,{"chatId":"private","mode":"anatomy"},self.other+"/image.png")
        self.repo.patch_history(self.owner,generation,{},glb_path=self.owner+"/new.glb")
        self.repo.patch_history(self.other,foreign,{},glb_path=self.other+"/private.glb")
        self.repo.append_chat_event(self.owner,"models","model.old","threed",{"glbPath":self.owner+"/old.glb"},generation)
        self.repo.append_chat_event(self.owner,"models","model.new","threed",{"glbPath":self.owner+"/new.glb"},generation)
        models = self.repo.list_models(self.owner)
        self.assertEqual({row["glb_path"] for row in models},{self.owner+"/old.glb",self.owner+"/new.glb"})
        self.assertEqual(len(models),2)
        self.assertEqual(len(self.repo.list_chats(self.owner,category="sketch")),1)
        self.assertEqual(len(self.repo.list_chats(self.owner,category="images")),1)
        self.repo.set_chat_trashed(self.owner,"models",True)
        self.assertEqual(self.repo.list_models(self.owner),[])
        self.assertEqual(len(self.repo.list_models(self.owner,trashed=True)),2)

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

    def test_active_jobs_remain_visible_when_newer_completed_jobs_fill_recent_activity(self):
        active = self.repo.create_job(self.owner, self.payload(), {})
        with connection() as conn, conn.cursor() as cur:
            cur.execute("""insert into koji_jobs(id,user_id,request_id,kind,status,payload,endpoints)
                select gen_random_uuid(),%s,gen_random_uuid(),'generate','completed','{}','{}'
                from generate_series(1,35)""", (self.owner,))
        jobs = self.repo.list_jobs(self.owner)
        self.assertEqual(len(jobs), 30)
        self.assertEqual(jobs[0]["id"], active["id"])

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
        self.repo.set_chat_trashed(self.owner,"chat",True)
        self.repo.delete_chat(self.owner,"chat",remove)
        self.assertEqual(set(remove.call_args.args[0]),{self.owner+"/image.png",self.owner+"/thumbnail.png",
            self.owner+"/old.glb",self.owner+"/new.glb"})
        self.assertIsNone(self.repo.get_chat(self.owner,"chat"))
        self.assertIsNone(self.repo.get_history(self.owner,generation))

    def test_workspace_pdf_retrieval_is_scoped_to_owner_and_selected_files(self):
        from studio.documents import Documents
        documents = Documents()
        selected, unselected, foreign = (str(uuid4()) for _ in range(3))
        for owner in (self.owner,self.other):
            self.repo.append_chat_event(owner,"course","prompt","prompt",{"prompt":"Heart study"})
        first=documents.register(self.owner,selected,"Textbook.pdf",self.owner+"/selected.pdf",100)
        second=documents.register(self.owner,unselected,"Other.pdf",self.owner+"/other.pdf",100)
        third=documents.register(self.other,foreign,"Private.pdf",self.other+"/private.pdf",100)
        vector=[1.0]+[0.0]*383
        for row in (first,second,third):
            with connection() as conn,conn.cursor() as cur:
                cur.execute("""update koji_jobs set status='running',lease_token=%s,lease_until=now()+interval '2 minutes'
                    where id=%s returning *""",(str(uuid4()),row["job_id"]))
            job=self.repo.get_job(str(row["user_id"]),str(row["job_id"]))
            documents.finish(job,[{"page":3,"content":"Left ventricle has thick walls for high pressure.","embedding":vector}],4,0)
            self.repo.update_job(job,status="completed")
        with patch("studio.documents.embed_texts",return_value=[vector]):
            results=documents.retrieve(self.owner,[selected],"left ventricle thick walls")
        self.assertEqual({str(row["document_id"]) for row in results},{selected})
        self.assertEqual(results[0]["page"],3)
        self.assertEqual(results[0]["filename"],"Textbook.pdf")
        with patch("studio.documents.embed_texts",return_value=[[0.0,1.0]+[0.0]*382]),patch.dict(os.environ,{"STUDIO_PDF_MIN_SIMILARITY":"0.30"}):
            self.assertEqual(documents.retrieve(self.owner,[selected],"chloroplast photosynthesis"),[])
        with self.assertRaises(LookupError):
            documents.selected(self.owner,[foreign])
        self.assertEqual(str(documents.selected(self.owner,[selected])[0]["id"]),selected)
        with connection() as conn,conn.cursor() as cur:
            cur.execute("set local role authenticated")
            cur.execute("select set_config('request.jwt.claim.sub',%s,true)",(self.other,))
            cur.execute("select id from koji_documents where user_id=%s",(self.owner,))
            self.assertEqual(cur.fetchall(),[])
            cur.execute("select id from koji_document_chunks where user_id=%s",(self.owner,))
            self.assertEqual(cur.fetchall(),[])

    def test_deleting_original_chat_preserves_workspace_pdf_and_indexing_job(self):
        from studio.documents import Documents
        from unittest.mock import Mock
        documents=Documents()
        self.repo.append_chat_event(self.owner,"original","prompt","prompt",{"prompt":"Study"})
        identifier=str(uuid4())
        row=documents.register(self.owner,identifier,"Notes.pdf",self.owner+"/notes.pdf",100)
        # A retained origin column must never restore chat ownership or cascading deletion.
        with connection() as conn,conn.cursor() as cur:
            cur.execute("update koji_documents set chat_id='original' where id=%s",(identifier,))
        remove=Mock()
        self.repo.set_chat_trashed(self.owner,"original",True)
        self.repo.delete_chat(self.owner,"original",remove)
        remove.assert_called_once_with([])
        self.assertIsNotNone(documents.get(self.owner,identifier))
        self.assertEqual(len(documents.list(self.owner)),1)
        job=self.repo.get_job(self.owner,str(row["job_id"]))
        self.assertEqual(job["status"],"queued")
        self.assertNotIn("chat_id",job["payload"])
        job=self.repo.claim()
        vector=[1.0]+[0.0]*383
        documents.finish(job,[{"page":1,"content":"Heart walls", "embedding":vector}],1,0)
        self.repo.update_job(job,status="completed")
        with patch("studio.documents.embed_texts",return_value=[vector]):
            self.assertEqual(str(documents.retrieve(self.owner,[identifier],"Heart walls")[0]["document_id"]),identifier)

    def test_recycle_bin_preserves_versions_assets_and_conversation_until_restored(self):
        generation = str(uuid4())
        self.repo.save_history(self.owner,generation,{"chatId":"recycle","prompt":"Heart"},self.owner+"/image.png")
        self.repo.append_chat_event(self.owner,"recycle","image","image",{"prompt":"Heart"},generation)
        self.repo.append_chat_event(self.owner,"recycle","question","interaction",{"answer":"A saved answer"},generation)
        original = self.repo.get_chat(self.owner,"recycle")
        self.repo.set_chat_trashed(self.owner,"recycle",True)
        self.assertEqual(self.repo.list_chats(self.owner),[])
        self.assertEqual(self.repo.list_history(self.owner),[])
        self.assertEqual(self.repo.list_chats(self.owner,trashed=True)[0]["id"],"recycle")
        self.assertEqual(self.repo.list_chats(self.other,trashed=True),[])
        self.assertEqual(self.repo.get_history(self.owner,generation)["image_path"],self.owner+"/image.png")
        self.assertEqual(len(self.repo.list_chat_events(self.owner,"recycle")),2)
        with self.assertRaises(LookupError):
            self.repo.set_chat_trashed(self.other,"recycle",False)
        with self.assertRaisesRegex(ValueError,"Restore"):
            self.repo.create_job(self.owner,self.payload(kind="threed",generation_id=generation),{})
        self.repo.set_chat_trashed(self.owner,"recycle",False)
        self.assertEqual(self.repo.list_chats(self.owner,trashed=True),[])
        self.assertEqual(len(self.repo.list_history(self.owner)),1)
        self.assertEqual(self.repo.get_chat(self.owner,"recycle")["updated_at"],original["updated_at"])

    def test_permanent_delete_requires_recycle_bin_and_preserves_active_history(self):
        from unittest.mock import Mock
        self.repo.append_chat_event(self.owner,"keep","prompt","prompt",{"prompt":"Keep me"})
        remove = Mock()
        with self.assertRaisesRegex(ValueError,"Recycle Bin"):
            self.repo.delete_chat(self.owner,"keep",remove)
        remove.assert_not_called()
        self.assertIsNotNone(self.repo.get_chat(self.owner,"keep"))

    def test_pdf_completion_is_fenced_and_removal_waits_for_active_questions(self):
        from studio.documents import Documents
        from unittest.mock import Mock
        documents=Documents()
        self.repo.append_chat_event(self.owner,"course","prompt","prompt",{"prompt":"Study"})
        document=str(uuid4())
        row=documents.register(self.owner,document,"Notes.pdf",self.owner+"/notes.pdf",100)
        job=self.repo.claim()
        stale={**job,"lease_token":str(uuid4())}
        with self.assertRaisesRegex(RuntimeError,"lease lost"):
            documents.finish(stale,[],1,0)
        documents.finish(job,[{"page":1,"content":"Heart wall", "embedding":[1.0]+[0.0]*383}],1,0)
        self.repo.update_job(job,status="completed")
        generation=str(uuid4())
        self.repo.save_history(self.owner,generation,{"chatId":"another-image"},self.owner+"/image.png")
        question=self.repo.create_job(self.owner,self.payload(kind="analysis",generation_id=generation,
            analysis={"id":"q","mode":"ask","question":"Why?","interaction":{"type":"point","coords":[.4,.5]},"document_ids":[document]}),{})
        remove=Mock()
        with self.assertRaisesRegex(ValueError,"finish"):
            documents.delete(self.owner,document,remove)
        remove.assert_not_called()
        with connection() as conn,conn.cursor() as cur:
            cur.execute("update koji_jobs set status='failed' where id=%s",(question["id"],))
        documents.delete(self.owner,document,remove)
        remove.assert_called_once_with([self.owner+"/notes.pdf"])
        with connection() as conn,conn.cursor() as cur:
            cur.execute("select count(*) from koji_document_chunks where document_id=%s",(document,))
            self.assertEqual(cur.fetchone()[0],0)

if __name__=="__main__":
    unittest.main()
