"""Local-only cache benchmark: python -m scripts.benchmark_embeddings.

Requires an already downloaded MiniLM model. Never calls Modal or downloads a model.
This measures embedding reuse, not end-to-end quiz or GPU latency.
"""
import os
import time

os.environ["HF_HUB_OFFLINE"] = "1"

from app.services.llm_service import EmbeddingService


def main():
    service = EmbeddingService()
    started = time.perf_counter()
    service._load()
    load_seconds = time.perf_counter() - started
    texts = [
        "Mitochondria produce ATP through aerobic cellular respiration.",
        "Chloroplasts capture light energy for photosynthesis in plant cells.",
        "Ribosomes translate messenger RNA into polypeptide chains.",
        "Which organelle produces ATP through aerobic respiration?",
    ]
    EmbeddingService._vectors.clear()
    started = time.perf_counter()
    original = service.get_batch_embeddings(texts)
    uncached_seconds = time.perf_counter() - started
    started = time.perf_counter()
    for _ in range(100):
        cached = EmbeddingService().get_batch_embeddings(texts)
    cached_seconds = (time.perf_counter() - started) / 100
    assert cached == original, "Cached embeddings changed"
    print(f"Model load: {load_seconds:.3f}s")
    print(f"Uncached batch (4 texts): {uncached_seconds:.6f}s")
    print(f"Cached batch mean (100 runs): {cached_seconds:.6f}s")
    print("Identical cached vectors: yes; Modal requests: 0")


if __name__ == "__main__":
    main()
