"""Private, workspace-scoped PDF indexing and question-aware retrieval on the CPU worker."""
from __future__ import annotations

import base64
import math
import os
import re
from io import BytesIO
from functools import lru_cache
from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor, execute_values
from studio.repository import connection

MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_DOCUMENTS = 10
MAX_PAGES = 300
MAX_CHUNKS = 2000
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def filename_for_upload(value: str) -> str:
    name = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    if not name.lower().endswith(".pdf") or len(name) > 180:
        raise ValueError("Choose a PDF file with a name of at most 180 characters")
    return name


def extract_chunks(data: bytes):
    from pypdf import PdfReader
    from shared.rag import chunk_text
    if not data.startswith(b"%PDF-"):
        raise ValueError("This file is not a valid PDF")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported. Upload an unlocked copy.")
        if not 0 < len(reader.pages) <= MAX_PAGES:
            raise ValueError(f"Upload a PDF with 1 to {MAX_PAGES} pages")
        chunks, skipped = [], 0
        for number, page in enumerate(reader.pages, 1):
            # Bound extracted text as well as compressed upload size.
            text = page.extract_text() or ""
            if len(text) > 200_000:
                raise ValueError("A PDF page contains too much text. Split this PDF and retry.")
            if not text.strip():
                skipped += 1
                continue
            # Short overlapping passages fit MiniLM's 256-token input more reliably.
            chunks.extend({"page": number, "content": part} for part in chunk_text(text, 900, 120))
            if len(chunks) > MAX_CHUNKS:
                raise ValueError("This PDF is too large to index. Split it into smaller files.")
        if not chunks:
            raise ValueError("No readable text found. Upload a text PDF or use OCR on the scanned pages first.")
        return chunks, len(reader.pages), skipped
    except ValueError:
        raise
    except Exception:
        raise ValueError("This PDF could not be read. Export a fresh PDF and upload it again.") from None


def embed_texts(texts: list[str]):
    # Fixed model/dimension for this index; changing the shared model cannot corrupt it.
    return _model().encode(texts, batch_size=32, normalize_embeddings=True).tolist()


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL, device="cpu")


def vector_literal(vector):
    if len(vector) != 384 or any(not math.isfinite(float(value)) for value in vector):
        raise ValueError("Invalid PDF embedding")
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def public_document(row):
    return {key: row.get(key) for key in (
        "id", "filename", "size_bytes", "status", "error", "page_count", "skipped_pages", "job_id", "created_at")}


class Documents:
    def list(self, user_id):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select * from koji_documents where user_id=%s order by created_at,id",
                        (user_id,))
            return [dict(row) for row in cur.fetchall()]

    def get(self, user_id, document_id):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select * from koji_documents where user_id=%s and id=%s", (user_id, document_id))
            row = cur.fetchone()
            return dict(row) if row else None

    def selected(self, user_id, document_ids):
        if not document_ids:
            return []
        unique = list(dict.fromkeys(str(value) for value in document_ids))
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select * from koji_documents where user_id=%s and id=any(%s::uuid[])",
                        (user_id, unique))
            rows = [dict(row) for row in cur.fetchall()]
        if len(rows) != len(unique):
            raise LookupError("A selected PDF is no longer available in your workspace")
        if any(row["status"] != "ready" for row in rows):
            raise ValueError("Wait until all selected PDFs are ready, or deselect them")
        return rows

    def register(self, user_id, document_id, filename, path, size):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (user_id,))
            cur.execute("select count(*) from koji_documents where user_id=%s", (user_id,))
            if cur.fetchone()["count"] >= MAX_DOCUMENTS:
                raise ValueError(f"You can store up to {MAX_DOCUMENTS} PDFs in your workspace")
            self._capacity(cur, user_id)
            job_id = self._queue(cur, user_id, document_id)
            cur.execute("""insert into koji_documents(id,user_id,filename,storage_path,size_bytes,job_id)
                values(%s,%s,%s,%s,%s,%s) returning *""",
                        (document_id, user_id, filename, path, size, job_id))
            return dict(cur.fetchone())

    def _capacity(self, cur, user_id):
        cur.execute("select count(*) from koji_jobs where user_id=%s and status in ('queued','running')", (user_id,))
        if cur.fetchone()["count"] >= int(os.getenv("STUDIO_MAX_ACTIVE_JOBS", "3")):
            raise OverflowError("Finish an active job before uploading or retrying another PDF")

    def _queue(self, cur, user_id, document_id):
        job_id = str(uuid4())
        payload = {"kind": "document_index", "document_id": str(document_id)}
        cur.execute("""insert into koji_jobs(id,user_id,request_id,kind,payload,endpoints)
            values(%s,%s,%s,'document_index',%s,'{}')""", (job_id, user_id, str(uuid4()), Json(payload)))
        return job_id

    def retry(self, user_id, document_id):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (user_id,))
            cur.execute("select * from koji_documents where user_id=%s and id=%s for update", (user_id, document_id))
            row = cur.fetchone()
            if not row:
                raise LookupError("PDF not found")
            if row["status"] != "failed":
                raise ValueError("Only failed PDFs can be retried")
            self._capacity(cur, user_id)
            job_id = self._queue(cur, user_id, document_id)
            cur.execute("update koji_documents set status='processing',error=null,job_id=%s where user_id=%s and id=%s returning *",
                        (job_id, user_id, document_id))
            return dict(cur.fetchone())

    def finish(self, job, chunks, page_count, skipped):
        with connection() as conn, conn.cursor() as cur:
            cur.execute("""select 1 from koji_jobs where id=%s and user_id=%s and lease_token=%s
                and status='running' and lease_until>now() for update""", (job["id"], job["user_id"], job["lease_token"]))
            if not cur.fetchone():
                raise RuntimeError("Worker lease lost")
            document_id = job["payload"]["document_id"]
            cur.execute("select status from koji_documents where id=%s and user_id=%s and job_id=%s for update",
                        (document_id, job["user_id"], job["id"]))
            row = cur.fetchone()
            if not row:
                raise RuntimeError("PDF was removed or requeued")
            if row[0] == "ready":
                return
            cur.execute("delete from koji_document_chunks where user_id=%s and document_id=%s", (job["user_id"], document_id))
            cur.execute("set local search_path=public,extensions")
            execute_values(cur, """insert into koji_document_chunks(user_id,document_id,page,content,embedding) values %s""",
                           [(job["user_id"], document_id, c["page"], c["content"], vector_literal(c["embedding"])) for c in chunks],
                           template="(%s,%s,%s,%s,%s::vector)")
            cur.execute("""update koji_documents set status='ready',error=null,page_count=%s,skipped_pages=%s
                where user_id=%s and id=%s and job_id=%s""", (page_count, skipped, job["user_id"], document_id, job["id"]))

    def fail(self, job, message):
        with connection() as conn, conn.cursor() as cur:
            cur.execute("""update koji_documents set status='failed',error=%s where user_id=%s and id=%s
                and job_id=%s and status='processing'""",
                        (message, job["user_id"], job["payload"]["document_id"], job["id"]))

    def delete(self, user_id, document_id, remove_assets):
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (user_id,))
            cur.execute("select * from koji_documents where user_id=%s and id=%s for update", (user_id, document_id))
            row = cur.fetchone()
            if not row:
                raise LookupError("PDF not found")
            cur.execute("""select 1 from koji_jobs where user_id=%s and status in ('queued','running') and
                (payload->>'document_id'=%s or payload->'analysis'->'document_ids' ? %s) limit 1""",
                        (user_id, document_id, document_id))
            if cur.fetchone():
                raise ValueError("Wait for questions and PDF processing to finish before removing this file")
            remove_assets([row["storage_path"]])
            cur.execute("delete from koji_documents where user_id=%s and id=%s", (user_id, document_id))

    def retrieve(self, user_id, document_ids, query, limit=4):
        self.selected(user_id, document_ids)
        if not document_ids:
            return []
        vector = vector_literal(embed_texts([query])[0])
        # Both lexical and semantic candidates come from the same authorized scope.
        with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("set local search_path=public,extensions")
            cur.execute("""with scoped as materialized (
                select c.id,c.document_id,c.page,c.content,d.filename,
                    1-(c.embedding <=> %s::vector) as similarity,
                    ts_rank(c.fts,websearch_to_tsquery('english',%s)) as lexical,
                    c.fts @@ websearch_to_tsquery('english',%s) as lexical_match
                from koji_document_chunks c join koji_documents d on d.id=c.document_id and d.user_id=c.user_id
                where c.user_id=%s and d.status='ready' and c.document_id=any(%s::uuid[])
            ), semantic as (
                select id,row_number() over(order by similarity desc,id) as rank from scoped
                where similarity>=%s order by similarity desc,id limit 20
            ), lexical as (
                select id,row_number() over(order by lexical desc,id) as rank from scoped
                where lexical_match order by lexical desc,id limit 20
            ), fused as (
                select coalesce(s.id,l.id) as id,coalesce(1.0/(60+s.rank),0)+coalesce(1.0/(60+l.rank),0) as score
                from semantic s full join lexical l on s.id=l.id
            ) select c.*,f.score from scoped c join fused f on f.id=c.id order by f.score desc,c.id limit %s""",
                        (vector, query, query, user_id, list(document_ids),
                         float(os.getenv("STUDIO_PDF_MIN_SIMILARITY", "0.30")), limit))
            return [dict(row) for row in cur.fetchall()]


def index_document(job, storage):
    documents = Documents()
    row = documents.get(str(job["user_id"]), job["payload"]["document_id"])
    if not row or str(row["job_id"]) != str(job["id"]):
        raise RuntimeError("PDF was removed or requeued")
    if row["status"] == "ready":
        return {"document_id": str(row["id"])}
    chunks, pages, skipped = extract_chunks(base64.b64decode(storage.download(row["storage_path"]), validate=True))
    embeddings = embed_texts([chunk["content"] for chunk in chunks])
    for chunk, vector in zip(chunks, embeddings, strict=True):
        chunk["embedding"] = vector
    documents.finish(job, chunks, pages, skipped)
    return {"document_id": str(row["id"])}


def evidence_context(chunks):
    # Keep citation metadata tied to exactly the text passed into the model.
    sources = [{"number": i, "documentId": str(c["document_id"]), "filename": c["filename"],
                "page": c["page"], "excerpt": c["content"]} for i, c in enumerate(chunks, 1)]
    context = "\n\n".join(f"[{s['number']}] {s['filename']} | PDF page {s['page']}\n{s['excerpt']}" for s in sources)
    return context, sources


def checked_pdf_answer(answer, sources):
    """Do not present an answer as sourced if references are missing or invented."""
    cited = {int(value) for value in re.findall(r"\[(\d+)\]", answer or "")}
    available = {source["number"] for source in sources}
    if not cited or not cited <= available:
        return ("I could not produce an answer with valid references to the selected PDFs. "
                "Review the retrieved passages below, try a more specific question, or choose another PDF.")
    return answer
