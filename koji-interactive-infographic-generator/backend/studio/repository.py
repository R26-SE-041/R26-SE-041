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
                self._chat_event(cur,user_id,chat_id,a["id"],"interaction",
                    {"id":a["id"],"mode":a["mode"],"question":a.get("question") or
                        ("Identify selected object" if a["mode"]=="identify" else "Explain selected region"),
                     "answer":"","selection":a["interaction"],"structureId":a.get("structure_id"),
                     "status":"queued","jobId":job_id},str(source["id"]))
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
            cur.execute("""select * from koji_generations where user_id=%s and (%s::timestamptz is null or created_at<%s::timestamptz)
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
            on conflict(user_id,id) do update set updated_at=now()""", (user_id,chat_id,title))
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

    def list_chats(self,user_id,before=None,before_id="",query=""):
        pattern="%"+query+"%"
        with connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select c.*,
                (select count(*) from koji_chat_events e where e.user_id=c.user_id and e.chat_id=c.id) as event_count
                from koji_chats c where c.user_id=%s
                and (%s::timestamptz is null or (c.updated_at,c.id)<(%s::timestamptz,%s))
                and (%s='' or c.title ilike %s or exists(select 1 from koji_chat_events e
                    where e.user_id=c.user_id and e.chat_id=c.id and
                    (e.data->>'prompt' ilike %s or e.data->>'question' ilike %s or e.data->>'answer' ilike %s)))
                order by c.updated_at desc,c.id desc limit 50""",(user_id,before,before,before_id,query,pattern,pattern,pattern,pattern))
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

    def delete_chat(self,user_id,chat_id,remove_assets):
        with connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))",(user_id,))
            cur.execute("""select id from koji_jobs where user_id=%s and status in ('queued','running') and
                (coalesce(payload->>'chat_id',id::text)=%s or generation_id in
                    (select id from koji_generations where user_id=%s and coalesce(metadata->>'chatId',id::text)=%s))
                limit 1""",(user_id,chat_id,user_id,chat_id))
            if cur.fetchone():
                raise ValueError("Wait for this conversation's active jobs before deleting it")
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
