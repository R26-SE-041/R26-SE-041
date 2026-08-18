"""Embedding, hybrid PostgreSQL retrieval, PDF indexing, and web fallback."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any
from urllib.parse import quote


@lru_cache(maxsize=1)
def _embedding_model() -> Any:
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))


def embed(text: str) -> list[float]:
    clean = text.strip()
    if not clean:
        raise ValueError("Cannot embed empty text")
    vector = _embedding_model().encode(clean, normalize_embeddings=True)
    return [float(value) for value in vector]


def hybrid_retrieve(query: str, table: str = "knowledge_chunks", n: int = 5) -> list[dict[str, Any]]:
    from shared.db import hybrid_retrieve as db_hybrid_retrieve
    return db_hybrid_retrieve(query=query, query_embedding=embed(query), table=table, n=n)


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    if chunk_size <= overlap or overlap < 0:
        raise ValueError("chunk_size must be greater than overlap")
    normalized = re.sub(r"\s+", " ", text).strip()
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = end - overlap
    return [chunk for chunk in chunks if chunk]


def index_pdf(path: str, subject: str | None = None) -> int:
    from pypdf import PdfReader
    from shared.db import insert_knowledge_chunk
    reader = PdfReader(path)
    inserted = 0
    for page_number, page in enumerate(reader.pages, start=1):
        for content in chunk_text(page.extract_text() or ""):
            insert_knowledge_chunk(content, path, page_number, subject, embed(content))
            inserted += 1
    return inserted


def jina_scrape(topic: str, timeout: int = 15) -> str:
    """Fetch a readable Wikipedia page through Jina Reader; disabled without opt-in."""
    if os.getenv("ENABLE_WEB_FALLBACK", "false").lower() not in {"1", "true", "yes"}:
        return ""
    import requests
    target = f"https://en.wikipedia.org/wiki/{quote(topic.replace(' ', '_'))}"
    response = requests.get(f"https://r.jina.ai/{target}", timeout=timeout)
    response.raise_for_status()
    return response.text

