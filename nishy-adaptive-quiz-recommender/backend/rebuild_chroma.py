"""
ChromaDB Recovery Script
========================
The existing ChromaDB database is corrupt (seq_id decode error from version mismatch).
This script:
1. Backs up and wipes the corrupt ChromaDB data
2. Re-extracts and re-embeds every uploaded PDF/DOCX from data/uploads/
3. Updates chunk_count in sessions.db
"""
import os
import sys
import sqlite3
import shutil
import json
import glob
from pathlib import Path

# ── Setup paths ────────────────────────────────────────────────────
CHROMA_DIR = "./db/chroma"
DB_PATH    = "./db/sessions.db"
UPLOAD_DIR = "./data/uploads"

def main():
    print("=" * 60)
    print("ChromaDB Recovery Script")
    print("=" * 60)

    # 1. Backup and wipe corrupt chroma data
    backup_dir = "./db/chroma_backup"
    if os.path.exists(CHROMA_DIR):
        print(f"\n[1/4] Backing up corrupt ChromaDB to {backup_dir} ...")
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        shutil.copytree(CHROMA_DIR, backup_dir)
        print(f"      Backup done. Wiping {CHROMA_DIR} ...")
        shutil.rmtree(CHROMA_DIR)
    os.makedirs(CHROMA_DIR, exist_ok=True)
    print("      ChromaDB directory reset. ✓")

    # 2. Load document records from SQLite
    print(f"\n[2/4] Loading document records from {DB_PATH} ...")
    if not os.path.exists(DB_PATH):
        print("ERROR: sessions.db not found! Nothing to recover.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    docs = conn.execute(
        "SELECT document_id, filename, topics, chunk_count FROM documents ORDER BY created_at"
    ).fetchall()
    print(f"      Found {len(docs)} document record(s).")
    for d in docs:
        print(f"      - {d['filename']} (doc_{d['document_id']})")

    # 3. Re-embed each document
    print(f"\n[3/4] Re-embedding documents from {UPLOAD_DIR} ...")

    # Import services after chroma reset
    from app.services.rag_service import RagService
    rag = RagService()

    recovered = 0
    failed = []

    for doc in docs:
        doc_id   = doc["document_id"]
        filename = doc["filename"]
        coll_id  = f"doc_{doc_id}"

        # Find the file under data/uploads/{doc_id}/
        search_patterns = [
            os.path.join(UPLOAD_DIR, doc_id, filename),
            os.path.join(UPLOAD_DIR, doc_id, "*.pdf"),
            os.path.join(UPLOAD_DIR, doc_id, "*.docx"),
            os.path.join(UPLOAD_DIR, doc_id, "*.pptx"),
            os.path.join(UPLOAD_DIR, doc_id, "*.txt"),
        ]
        file_path = None
        for pattern in search_patterns:
            matches = glob.glob(pattern)
            if matches:
                file_path = matches[0]
                break

        if not file_path or not os.path.exists(file_path):
            print(f"  [SKIP] {filename} — upload file not found under uploads/{doc_id}/")
            failed.append(filename)
            continue

        ext = Path(file_path).suffix.lstrip(".").lower()
        print(f"  [RE-EMBED] {filename} ({ext}) → {coll_id} ...")
        try:
            if ext == "pdf":
                chunks = rag.extract_pdf(file_path)
            elif ext == "docx":
                chunks = rag.extract_docx(file_path)
            elif ext == "pptx":
                chunks = rag.extract_pptx(file_path)
            elif ext in ("txt",):
                chunks = rag.extract_txt(file_path)
            else:
                print(f"         Unsupported format: {ext} — skipping")
                failed.append(filename)
                continue

            if not chunks:
                print(f"         No chunks extracted — skipping")
                failed.append(filename)
                continue

            rag.embed_and_store(coll_id, chunks)
            # Update chunk_count in DB
            conn.execute(
                "UPDATE documents SET chunk_count = ? WHERE document_id = ?",
                (len(chunks), doc_id)
            )
            conn.commit()
            print(f"         ✓ {len(chunks)} chunks embedded.")
            recovered += 1
        except Exception as e:
            print(f"         ERROR: {e}")
            failed.append(filename)

    # 4. Summary
    print(f"\n[4/4] Recovery complete.")
    print(f"      Recovered : {recovered}/{len(docs)} documents")
    if failed:
        print(f"      Failed     : {', '.join(failed)}")
        print("      Re-upload the failed files manually via the upload page.")
    else:
        print("      All documents recovered successfully! ✓")

    conn.close()
    print("\nYou can now start a new quiz session.")

if __name__ == "__main__":
    main()
