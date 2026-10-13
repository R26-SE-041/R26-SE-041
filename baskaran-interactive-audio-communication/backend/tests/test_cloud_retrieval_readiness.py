from types import SimpleNamespace
from app.api.v1.routes import documents

def test_modal_retrieval_does_not_require_a_local_model_cache(monkeypatch):
    monkeypatch.setattr(documents, 'get_settings', lambda: SimpleNamespace(
        use_modal_retrieval_models=True, modal_bge_embed_url='https://embed.modal.run',
        modal_bge_rerank_url='https://rerank.modal.run'))
    def no_local_cache():
        raise AssertionError('Cloud uploads must not inspect local model weights')
    monkeypatch.setattr(documents, 'bge_m3_cache_status', no_local_cache)
    assert documents._retrieval_status()[0] is True

def test_modal_retrieval_rejects_missing_endpoint_configuration(monkeypatch):
    monkeypatch.setattr(documents, 'get_settings', lambda: SimpleNamespace(
        use_modal_retrieval_models=True, modal_bge_embed_url='', modal_bge_rerank_url=''))
    assert documents._retrieval_status()[0] is False

def test_local_retrieval_still_requires_complete_model_weights(monkeypatch):
    monkeypatch.setattr(documents, 'get_settings', lambda: SimpleNamespace(use_modal_retrieval_models=False))
    monkeypatch.setattr(documents, 'bge_m3_cache_status', lambda: (False, 'incomplete'))
    assert documents._retrieval_status() == (False, 'incomplete')
