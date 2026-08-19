from datetime import datetime, timezone

from app.services import local_document_store


def test_local_document_store_persists_lists_and_deletes_one_document(tmp_path, monkeypatch):
    """The fallback registry survives a fresh read and isolates document deletion."""
    monkeypatch.setattr(local_document_store, "_root", lambda: tmp_path)
    now = datetime.now(timezone.utc)

    first_path = local_document_store.save_document(
        document_id="11111111-1111-1111-1111-111111111111",
        user_id="guest",
        filename="first.pdf",
        file_type="pdf",
        chunk_count=3,
        uploaded_at=now,
        content=b"first pdf",
    )
    local_document_store.save_document(
        document_id="22222222-2222-2222-2222-222222222222",
        user_id="guest",
        filename="second.pdf",
        file_type="pdf",
        chunk_count=5,
        uploaded_at=now,
        content=b"second pdf",
    )

    assert first_path == "local/11111111-1111-1111-1111-111111111111/first.pdf"
    assert [record["filename"] for record in local_document_store.list_documents("guest")] == [
        "first.pdf", "second.pdf"
    ]
    assert local_document_store.delete_document("11111111-1111-1111-1111-111111111111", "guest")
    assert not (tmp_path / "files" / "11111111-1111-1111-1111-111111111111.pdf").exists()
    assert [record["filename"] for record in local_document_store.list_documents("guest")] == ["second.pdf"]
