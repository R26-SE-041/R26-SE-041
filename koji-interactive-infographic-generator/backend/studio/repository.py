"""Durable jobs with ownership checks, idempotency and fenced worker leases."""
from __future__ import annotations
import os
from contextlib import contextmanager
from uuid import uuid4
import psycopg2
from psycopg2.extras import Json, RealDictCursor

@contextmanager
def connection():
    conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=10)
    try:
        with conn:
            yield conn
    finally:
        conn.close()

class Repository:
    def save_feedback(self,user_id,data):
        with connection() as conn,conn.cursor() as cur:
            cur.execute("""insert into agent_feedback
                (session_id,auth_user_id,agent_name,output_id,rating,reason_codes,comment,input_context,output_snapshot,parent_output_id)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(agent_name,output_id) do update set rating=excluded.rating,
                    reason_codes=excluded.reason_codes,comment=excluded.comment,
                    input_context=excluded.input_context,output_snapshot=excluded.output_snapshot
                where agent_feedback.auth_user_id=excluded.auth_user_id returning id::text""",
                (data["session_id"],user_id,data["agent_name"],data["output_id"],data["rating"],data.get("reason_codes",[]),
                 data.get("comment"),Json(data.get("input_context",{})),Json(data.get("output_snapshot",{})),data.get("parent_output_id")))
            row=cur.fetchone()
            if not row:
                raise LookupError("Output belongs to another account")
            feedback_id=row[0]; pair_id=None
            if data.get("parent_feedback_id"):
                if data["rating"] != 1:
                    raise ValueError("Only a liked retry can complete a preference pair")
                cur.execute("""insert into preference_pairs
                    (agent_name,negative_feedback_id,positive_feedback_id,negative_output_id,positive_output_id,negative_reasons,positive_reasons)
                    select n.agent_name,n.id,p.id,n.output_id,p.output_id,n.reason_codes,p.reason_codes
                    from agent_feedback n join agent_feedback p on p.id=%s::uuid
                    where n.id=%s::uuid and n.rating=-1 and n.auth_user_id=%s
                        and n.agent_name=p.agent_name and n.session_id=p.session_id and n.output_id<>p.output_id
                    on conflict(negative_feedback_id) do update set positive_feedback_id=excluded.positive_feedback_id,
                        positive_output_id=excluded.positive_output_id,positive_reasons=excluded.positive_reasons
                    returning id::text""",(feedback_id,data["parent_feedback_id"],user_id))
                pair=cur.fetchone()
                if not pair:
                    raise ValueError("Choose a disliked output from the same account, agent and session")
                pair_id=pair[0]
            return {"feedback_id":feedback_id,"preference_pair_id":pair_id,"status":"recorded"}

    def get_job(self, user_id, job_id):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select * from koji_jobs where id=%s and user_id=%s", (job_id,user_id))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_jobs(self, user_id):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select * from koji_jobs where user_id=%s order by created_at desc limit 30", (user_id,))
            return [dict(row) for row in cur.fetchall()]

    def create_job(self, user_id, payload, endpoints):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Serialise the per-user active-job limit and idempotency lookup.
            cur.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (user_id,))
            cur.execute("select * from koji_jobs where user_id=%s and request_id=%s", (user_id,payload["request_id"]))
            existing = cur.fetchone()
            if existing:
                original = existing["payload"]
                if original != payload:
                    raise ValueError("Request ID already belongs to a different request")
                return dict(existing)
            source = self.get_history(user_id,payload["generation_id"]) if payload.get("generation_id") else None
            if payload.get("generation_id") and not source:
                raise LookupError("Source generation not found")
            chat_id = payload.get("chat_id")
            if not chat_id and source:
                chat_id = source["metadata"].get("chatId") or str(source["id"])
            if chat_id:
                cur.execute("select 1 from koji_chats where user_id=%s and id=%s and deleted_at is not null",(user_id,chat_id))
                if cur.fetchone():
                    raise ValueError("Restore this creation from the Recycle Bin before continuing")
            if payload.get("generation_id") and payload["kind"] in {"labels", "threed"}:
                cur.execute("select * from koji_jobs where user_id=%s and generation_id=%s and kind=%s and status in ('queued','running') order by created_at limit 1",(user_id,payload["generation_id"],payload["kind"]))
                active = cur.fetchone()
                if active:
                    return dict(active)
            cur.execute("select count(*) from koji_jobs where user_id=%s and status in ('queued','running')",(user_id,))
            if cur.fetchone()["count"] >= int(os.getenv("STUDIO_MAX_ACTIVE_JOBS","3")):
                raise OverflowError("Finish an active job before starting another")
            job_id = str(uuid4())
            cur.execute("""insert into koji_jobs(id,user_id,request_id,kind,generation_id,payload,endpoints)
                values(%s,%s,%s,%s,%s,%s,%s) returning *""",(job_id,user_id,payload["request_id"],payload["kind"],payload.get("generation_id"),Json(payload),Json(endpoints)))
            job = dict(cur.fetchone())
            if payload["kind"] in {"generate","sketch","enhance"}:
                chat_id = payload.get("chat_id") or job_id
                self._chat_event(cur,user_id,chat_id,payload.get("prompt_event_id") or job_id+":prompt","prompt",
                    {"prompt":payload.get("raw_prompt") or payload.get("prompt") or "", "mode":payload.get("mode"),
                     "sketch":payload.get("sketch"),"status":"queued","jobId":job_id})
                if payload.get("enhanced_payload"):
                    self._chat_event(cur,user_id,chat_id,job_id+":enhancement","enhancement",
                        {"prompt":payload["prompt"],"payload":payload["enhanced_payload"],"jobId":job_id})
            elif payload["kind"] == "analysis":
                a = payload["analysis"]
                chat_id = source["metadata"].get("chatId") or str(source["id"])
                # Validate under the same per-user lock used by PDF removal.
                if a.get("document_ids"):
                    cur.execute("""select id,status from koji_documents where user_id=%s
                        and id=any(%s::uuid[])""",(user_id,a["document_ids"]))
                    selected = cur.fetchall()
                    if len(selected) != len(set(a["document_ids"])):
                        raise LookupError("Selected PDF not found")
                    if any(row["status"] != "ready" for row in selected):
                        raise ValueError("Wait until selected PDFs are ready")
                self._chat_event(cur,user_id,chat_id,a["id"],"interaction",
                    {"id":a["id"],"mode":a["mode"],"question":a.get("question") or
                        ("Identify selected object" if a["mode"]=="identify" else "Explain selected region"),
                     "answer":"","selection":a["interaction"],"structureId":a.get("structure_id"),
                     "status":"queued","jobId":job_id,"documentIds":a.get("document_ids",[])},str(source["id"]))
            return job

    def claim(self):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select * from koji_jobs where status='queued' or
                (status='running' and lease_until<now()) order by created_at
                for update skip locked limit 1""")
            row = cur.fetchone()
            if not row:
                return None
            token = str(uuid4())
            cur.execute("""update koji_jobs set status='running', lease_token=%s,
                lease_until=now()+interval '2 minutes',updated_at=now() where id=%s returning *""",(token,row["id"]))
            return dict(cur.fetchone())

    def update_job(self, job, **values):
        allowed = {"state","stage","result","error","status","generation_id"}
        if not values or not values.keys() <= allowed:
            raise ValueError("Invalid job update")
        assignments = ",".join(key+"=%s" for key in values)
        args = [Json(value) if key in {"state","result"} and value is not None else value for key,value in values.items()]
        with connection() as conn, conn.cursor() as cur:
            cur.execute("update koji_jobs set "+assignments+",updated_at=now() where id=%s and lease_token=%s and status='running'",(*args,job["id"],job["lease_token"]))
            if cur.rowcount != 1:
                raise RuntimeError("Worker lease lost")
        job.update(values)

    def heartbeat(self, job):
        with connection() as conn, conn.cursor() as cur:
            cur.execute("""update koji_jobs set lease_until=now()+interval '2 minutes'
                where id=%s and lease_token=%s and status='running'""",(job["id"],job["lease_token"]))
            return cur.rowcount == 1

    def get_history(self, user_id, generation_id):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select * from koji_generations where id=%s and user_id=%s",(generation_id,user_id))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_history(self, user_id, before=None):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select * from koji_generations g where user_id=%s
                and not exists(select 1 from koji_chats c where c.user_id=g.user_id
                    and c.id=coalesce(g.metadata->>'chatId',g.id::text) and c.deleted_at is not null)
                and (%s::timestamptz is null or created_at<%s::timestamptz)
                order by created_at desc limit 50""",(user_id,before,before))
            return [dict(row) for row in cur.fetchall()]

    def save_history(self, user_id, generation_id, metadata, image_path, created_at=None, thumbnail_path=None):
        with connection() as conn, conn.cursor() as cur:
            cur.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (user_id,))
            cur.execute("select count(*) from koji_generations where user_id=%s and metadata->>'chatId'=%s",(user_id,metadata.get("chatId")))
            metadata = {**metadata,"version":cur.fetchone()[0]+1}
            cur.execute("""insert into koji_generations(id,user_id,metadata,image_path,created_at,thumbnail_path)
                values(%s,%s,%s,%s,coalesce(%s::timestamptz,now()),%s) on conflict(id) do nothing""",(generation_id,user_id,Json(metadata),image_path,created_at,thumbnail_path))

    def patch_history(self, user_id, generation_id, patch, glb_path=None):
        with connection() as conn, conn.cursor() as cur:
            cur.execute("""update koji_generations set metadata=metadata || %s,
                glb_path=coalesce(%s,glb_path),updated_at=now() where id=%s and user_id=%s""",(Json(patch),glb_path,generation_id,user_id))
            if cur.rowcount != 1:
                raise LookupError("Generation not found")
            if "anatomyAnnotations" in patch:
                cur.execute("select metadata from koji_generations where id=%s and user_id=%s",(generation_id,user_id))
                metadata=cur.fetchone()[0]
                self._chat_event(cur,user_id,metadata.get("chatId") or generation_id,str(uuid4()),"labels",
                    {"annotations":patch["anatomyAnnotations"],"source":"manual"},generation_id)

    def append_interaction(self,user_id,generation_id,interaction):
        source=self.get_history(user_id,generation_id)
        if not source:
            raise LookupError("Generation not found")
        self.append_chat_event(user_id,source["metadata"].get("chatId") or str(source["id"]),
            interaction["id"],"interaction",interaction,generation_id,interaction.get("createdAt"))

    def delete_history(self,user_id,generation_id,before_delete=None):
        with connection() as conn, conn.cursor() as cur:
            cur.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (user_id,))
            cur.execute("select status from koji_jobs where generation_id=%s and user_id=%s and status in ('queued','running') for update",(generation_id,user_id))
            if cur.fetchone():
                raise ValueError("Wait for this image's active jobs before deleting it")
            # Keep the row recoverable if object deletion fails. The owner lock
            # also prevents a source job starting during this operation.
            if before_delete:
                before_delete()
            cur.execute("delete from koji_generations where id=%s and user_id=%s",(generation_id,user_id))

    def save_auto_labels(self,user_id,generation_id,labels):
        with connection() as conn, conn.cursor() as cur:
            cur.execute("""update koji_generations set metadata=metadata || %s,updated_at=now()
                where id=%s and user_id=%s and (metadata->>'annotationsEdited') is distinct from 'true'""",
                (Json({"anatomyAnnotations":labels,"labelingError":None}),generation_id,user_id))
            if cur.rowcount:
                cur.execute("select metadata from koji_generations where id=%s and user_id=%s",(generation_id,user_id))
                metadata=cur.fetchone()[0]
                self._chat_event(cur,user_id,metadata.get("chatId") or generation_id,str(uuid4()),"labels",
                    {"annotations":labels,"source":"automatic"},generation_id)

    def _chat_event(self, cur, user_id, chat_id, event_id, kind, data, generation_id=None, created_at=None):
        title = str(data.get("prompt") or data.get("question") or "New conversation").strip()[:80] or "New conversation"
        cur.execute("""insert into koji_chats(user_id,id,title) values(%s,%s,%s)
            on conflict(user_id,id) do update set updated_at=now()
            where koji_chats.deleted_at is null""", (user_id,chat_id,title))
        if cur.rowcount != 1:
            raise ValueError("Restore this creation from the Recycle Bin before continuing")
        cur.execute("""insert into koji_chat_events(user_id,id,chat_id,kind,generation_id,data,created_at)
            values(%s,%s,%s,%s,%s,%s,coalesce(%s::timestamptz,now()))
            on conflict(user_id,id) do update set data=koji_chat_events.data || excluded.data
            where koji_chat_events.chat_id=excluded.chat_id and koji_chat_events.kind=excluded.kind
                and koji_chat_events.generation_id is not distinct from excluded.generation_id""",
            (user_id,event_id,chat_id,kind,generation_id,Json(data),created_at))
        if cur.rowcount != 1:
            raise ValueError("Event ID belongs to another conversation or event kind")

    def append_chat_event(self,user_id,chat_id,event_id,kind,data,generation_id=None,created_at=None):
        with connection() as conn,conn.cursor() as cur:
            self._chat_event(cur,user_id,chat_id,event_id,kind,data,generation_id,created_at)

    def list_chats(self,user_id,before=None,before_id="",query="",mode="",since=None,trashed=False):
        pattern="%"+query+"%"
        with connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select c.*, latest.id as latest_generation_id,
                coalesce(latest.thumbnail_path,latest.image_path) as preview_path,
                coalesce(latest.metadata->>'mode',
                    (select e.data->>'mode' from koji_chat_events e where e.user_id=c.user_id
                     and e.chat_id=c.id and e.kind='prompt' order by e.created_at desc,e.id desc limit 1),'general') as mode,
                latest.glb_path is not null as has_three_d,
                (select count(*) from koji_generations g where g.user_id=c.user_id
                 and coalesce(g.metadata->>'chatId',g.id::text)=c.id) as version_count,
                (select count(*) from koji_chat_events e where e.user_id=c.user_id and e.chat_id=c.id) as event_count
                from koji_chats c left join lateral (
                    select g.* from koji_generations g where g.user_id=c.user_id
                    and coalesce(g.metadata->>'chatId',g.id::text)=c.id
                    order by g.created_at desc,g.id desc limit 1
                ) latest on true where c.user_id=%s and (c.deleted_at is not null)=%s
                and (%s::timestamptz is null or (c.updated_at,c.id)<(%s::timestamptz,%s))
                and (%s::timestamptz is null or c.updated_at >= %s::timestamptz)
                and (%s='' or coalesce(latest.metadata->>'mode',
                    (select e.data->>'mode' from koji_chat_events e where e.user_id=c.user_id
                     and e.chat_id=c.id and e.kind='prompt' order by e.created_at desc,e.id desc limit 1),'general')=%s)
                and (%s='' or c.title ilike %s or exists(select 1 from koji_chat_events e
                    where e.user_id=c.user_id and e.chat_id=c.id and
                    (e.data->>'prompt' ilike %s or e.data->>'question' ilike %s or e.data->>'answer' ilike %s)))
                order by c.updated_at desc,c.id desc limit 50""",(user_id,trashed,before,before,before_id,since,since,mode,mode,query,pattern,pattern,pattern,pattern))
            return [dict(row) for row in cur.fetchall()]

    def get_chat(self,user_id,chat_id):
        with connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select * from koji_chats where user_id=%s and id=%s",(user_id,chat_id))
            row=cur.fetchone()
            return dict(row) if row else None

    def list_chat_events(self,user_id,chat_id,before=None,before_id=""):
        with connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select e.*,g.image_path,g.thumbnail_path,g.glb_path from koji_chat_events e
                left join koji_generations g on g.id=e.generation_id and g.user_id=e.user_id
                where e.user_id=%s and e.chat_id=%s
                and (%s::timestamptz is null or (e.created_at,e.id)<(%s::timestamptz,%s))
                order by e.created_at desc,e.id desc limit 50""",(user_id,chat_id,before,before,before_id))
            return [dict(row) for row in cur.fetchall()]

    def rename_chat(self,user_id,chat_id,title):
        with connection() as conn,conn.cursor() as cur:
            cur.execute("update koji_chats set title=%s,updated_at=now() where user_id=%s and id=%s",(title,user_id,chat_id))
            if cur.rowcount!=1:
                raise LookupError("Conversation not found")

    def get_interactions(self,user_id,generation_id):
        with connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select data,created_at from koji_chat_events
                where user_id=%s and generation_id=%s and kind='interaction'
                order by created_at,id""",(user_id,generation_id))
            return [{**row["data"],"createdAt":row["created_at"].isoformat()} for row in cur.fetchall()]

    def set_chat_trashed(self,user_id,chat_id,trashed):
        with connection() as conn,conn.cursor() as cur:
            cur.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))",(user_id,))
            if trashed:
                self._check_chat_idle(cur,user_id,chat_id)
            cur.execute("""update koji_chats set deleted_at=case when %s then coalesce(deleted_at,now()) else null end
                where user_id=%s and id=%s""",(trashed,user_id,chat_id))
            if cur.rowcount != 1:
                raise LookupError("Conversation not found")

    def _check_chat_idle(self,cur,user_id,chat_id):
        cur.execute("""select id from koji_jobs where user_id=%s and status in ('queued','running') and
            (coalesce(payload->>'chat_id',id::text)=%s or generation_id in
                (select id from koji_generations where user_id=%s and coalesce(metadata->>'chatId',id::text)=%s))
            limit 1""",(user_id,chat_id,user_id,chat_id))
        if cur.fetchone():
            raise ValueError("Wait for this conversation's active jobs before deleting it")

    def delete_chat(self,user_id,chat_id,remove_assets):
        with connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))",(user_id,))
            self._check_chat_idle(cur,user_id,chat_id)
            cur.execute("select deleted_at from koji_chats where user_id=%s and id=%s for update",(user_id,chat_id))
            chat = cur.fetchone()
            if not chat:
                raise LookupError("Conversation not found")
            if chat["deleted_at"] is None:
                raise ValueError("Move this creation to the Recycle Bin before deleting permanently")
            cur.execute("""select image_path,thumbnail_path,glb_path from koji_generations
                where user_id=%s and coalesce(metadata->>'chatId',id::text)=%s""",(user_id,chat_id))
            paths=[path for row in cur.fetchall() for path in (row["image_path"],row["thumbnail_path"],row["glb_path"]) if path]
            cur.execute("select data->>'glbPath' as path from koji_chat_events where user_id=%s and chat_id=%s and kind='threed'",(user_id,chat_id))
            paths.extend(row["path"] for row in cur.fetchall() if row["path"] and row["path"].startswith(user_id+"/"))
            remove_assets(list(set(paths)))
            cur.execute("delete from koji_generations where user_id=%s and coalesce(metadata->>'chatId',id::text)=%s",(user_id,chat_id))
            cur.execute("delete from koji_chats where user_id=%s and id=%s",(user_id,chat_id))

    def model_path(self,user_id,generation_id,event_id):
        with connection() as conn,conn.cursor() as cur:
            cur.execute("""select data->>'glbPath' from koji_chat_events
                where user_id=%s and generation_id=%s and id=%s and kind='threed'""",(user_id,generation_id,event_id))
            row=cur.fetchone()
            return row[0] if row and row[0] and row[0].startswith(user_id+"/") else None

    def asset_paths(self,user_id,generation_id):
        with connection() as conn,conn.cursor() as cur:
            cur.execute("""select image_path from koji_generations where user_id=%s and id=%s
                union select thumbnail_path from koji_generations where user_id=%s and id=%s
                union select glb_path from koji_generations where user_id=%s and id=%s
                union select data->>'glbPath' from koji_chat_events
                    where user_id=%s and generation_id=%s and kind='threed'""",
                (user_id,generation_id,user_id,generation_id,user_id,generation_id,user_id,generation_id))
            return [row[0] for row in cur.fetchall() if row[0] and row[0].startswith(user_id+"/")]
