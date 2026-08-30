"""Rebuild the derived Chroma index from persisted uploaded documents.

The source uploads and previous vector directory are left untouched. Run from
the backend directory after setting CHROMA_PERSIST_DIR to a clean directory.
"""

import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from app.services.rag_service import RagService  # noqa: E402


UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"
DATABASE_PATH = BACKEND_DIR / "db" / "sessions.db"


def rebuild() -> None:
    rag = RagService()
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    documents = connection.execute(
        "SELECT document_id, filename FROM documents ORDER BY created_at"
    ).fetchall()

    for document in documents:
        document_id = document["document_id"]
        document_dir = UPLOAD_DIR / document_id
        candidates = list(document_dir.glob("*")) if document_dir.exists() else []
        if not candidates:
            print(f"SKIP {document_id}: upload file not found")
            continue

        source_path = candidates[0]
        suffix = source_path.suffix.casefold()
        if suffix == ".pdf":
            chunks = rag.extract_pdf(str(source_path))
        elif suffix == ".docx":
            chunks = rag.extract_docx(str(source_path))
        elif suffix == ".pptx":
            chunks = rag.extract_pptx(str(source_path))
        elif suffix == ".txt":
            chunks = rag.extract_txt(str(source_path))
        else:
            print(f"SKIP {document_id}: unsupported source type {suffix}")
            continue

        collection_id = f"doc_{document_id}"
        rag.embed_and_store(collection_id, chunks)
        print(f"INDEXED {document_id}: {len(chunks)} chunks from {source_path.name}")


if __name__ == "__main__":
    rebuild()
