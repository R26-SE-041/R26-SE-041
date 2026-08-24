from app.services import bge_m3_cache


def test_cache_status_accepts_a_complete_pytorch_checkpoint(tmp_path, monkeypatch):
    """BGE-M3 may be cached as pytorch_model.bin instead of safetensors."""
    snapshot = tmp_path / "models--BAAI--bge-m3" / "snapshots" / "test-snapshot"
    snapshot.mkdir(parents=True)
    for name in bge_m3_cache._REQUIRED_FILES:
        (snapshot / name).write_text("{}")
    (snapshot / "pytorch_model.bin").write_bytes(b"checkpoint")

    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    monkeypatch.setattr(bge_m3_cache, "_MINIMUM_WEIGHT_BYTES", 1)

    assert bge_m3_cache.bge_m3_cache_status() == (True, "ready")
