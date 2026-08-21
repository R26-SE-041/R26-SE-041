"""
Modal Serverless Endpoints: BGE-M3 Embedding + BGE Reranker

Deploy:
    modal deploy backend/modal_endpoints/bge_retrieval.py

Endpoints:

  BGEEmbedder  POST /embed
    { "texts": list[str], "normalize": bool }
    -> { "embeddings": list[list[float]], "dimension": int }

  BGEReranker  POST /rerank
    { "query": str, "candidates": list[dict], "top_k": int }
    -> { "ranked": list[dict], "scores": list[float] }

Models:
  BAAI/bge-m3              (~2.2 GB, 1024-D multilingual embedding)
  BAAI/bge-reranker-v2-m3  (~1.1 GB, multilingual cross-encoder)

GPU: T4 (16 GB VRAM) — both models fit with room to spare.
     Keeps cost minimal vs A10G while giving 5-10x speedup over local CPU.

Cold-start strategy:
  - Model weights are cached in the Modal volume "voicelearn-bge-models".
  - @modal.enter() loads the model ONCE per container lifetime.
  - scaledown_window=1200 keeps the container warm for 20 minutes after the
    last request, eliminating cold starts within a conversation session.
  - Weights are never downloaded during a live request.
"""

from typing import List, Optional
from pydantic import BaseModel
import modal

# ── Shared image ─────────────────────────────────────────────────────────────
# sentence-transformers is the only heavy dependency needed for both models.
# We pin versions to match the local requirements.txt exactly so embedding
# behaviour is identical (same normalization, same tokenizer, same pooling).
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "sentence-transformers==3.1.1",
        "torch>=2.2.0",
        "transformers>=4.41.0",
        "accelerate>=0.28.0",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.0.0",
    )
    .env({
        "HF_HOME": "/bge_models",
        "TRANSFORMERS_CACHE": "/bge_models",
    })
)

app = modal.App("voicelearn-bge-retrieval", image=image)

# Separate volume from the Gemma volume — these are much smaller models.
bge_volume = modal.Volume.from_name("voicelearn-bge-models", create_if_missing=True)

EMBEDDING_MODEL = "BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
EMBEDDING_DIMENSION = 1024
MODELS_DIR = "/bge_models"


# ── Request / Response schemas ───────────────────────────────────────────────

class EmbedRequest(BaseModel):
    texts: List[str]
    normalize: bool = True   # MUST stay True — existing Chroma vectors use normalize=True


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    dimension: int


class RerankRequest(BaseModel):
    query: str
    candidates: List[dict]   # each dict has at least a "text" key; other fields passed through
    top_k: int = 5


class RerankResponse(BaseModel):
    ranked: List[dict]       # candidates sorted by reranker_score descending
    scores: List[float]      # sigmoid-transformed scores in the same order


# ── BGE-M3 Embedder ──────────────────────────────────────────────────────────

@app.cls(
    gpu="T4",
    volumes={MODELS_DIR: bge_volume},
    scaledown_window=1200,
    memory=8192,
)
class BGEEmbedder:
    """
    Hosts BAAI/bge-m3 on a T4 GPU.

    The model is loaded exactly ONCE per container via @modal.enter().
    All subsequent requests reuse the in-memory model — no re-downloading.

    Embedding settings match the local ingestion pipeline:
      normalize_embeddings=True → unit-norm vectors → cosine similarity in Chroma.
    This guarantees that query embeddings produced here are compatible with the
    document embeddings already stored in Chroma (which were created locally
    with the same model and normalize=True).
    """

    @modal.enter()
    def load_model(self):
        from sentence_transformers import SentenceTransformer
        import torch

        print(f"[BGEEmbedder] Loading {EMBEDDING_MODEL} …")
        self.model = SentenceTransformer(
            EMBEDDING_MODEL,
            cache_folder=MODELS_DIR,
        )
        bge_volume.commit()
        # Move to GPU explicitly (sentence-transformers usually does this
        # automatically, but we make it explicit for clarity and diagnostics).
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = self.model.to(device)
        self.device = device
        print(f"[BGEEmbedder] {EMBEDDING_MODEL} loaded on {device} ✓")

    @modal.fastapi_endpoint(method="POST")
    def embed(self, payload: EmbedRequest) -> EmbedResponse:
        """
        Embed a list of texts using BAAI/bge-m3.

        normalize=True is required for cosine-similarity search in Chroma.
        The endpoint validates that every returned vector is exactly 1024-D.
        """
        if not payload.texts:
            return EmbedResponse(embeddings=[], dimension=EMBEDDING_DIMENSION)

        embeddings = self.model.encode(
            payload.texts,
            show_progress_bar=False,
            normalize_embeddings=payload.normalize,
            batch_size=32,         # safe for T4 with 1024-D outputs
            convert_to_numpy=True,
        ).tolist()

        # Validate dimension — guard against accidental model swap
        for vec in embeddings:
            if len(vec) != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"BGE-M3 returned {len(vec)}-D vector; expected {EMBEDDING_DIMENSION}. "
                    "Do not change the embedding model — existing Chroma vectors will break."
                )

        return EmbedResponse(embeddings=embeddings, dimension=EMBEDDING_DIMENSION)


# ── BGE Reranker ──────────────────────────────────────────────────────────────

@app.cls(
    gpu="T4",
    volumes={MODELS_DIR: bge_volume},
    scaledown_window=1200,
    memory=8192,
)
class BGEReranker:
    """
    Hosts BAAI/bge-reranker-v2-m3 (multilingual cross-encoder) on a T4 GPU.

    Accepts a query + candidate chunks, returns them sorted by relevance score.
    Handles cross-language pairs (Tamil query / English document) natively.
    """

    @modal.enter()
    def load_model(self):
        from sentence_transformers import CrossEncoder
        import torch

        print(f"[BGEReranker] Loading {RERANKER_MODEL} …")
        self.model = CrossEncoder(
            RERANKER_MODEL,
            max_length=512,
            # CrossEncoder automatically uses the GPU when torch.cuda is available.
        )
        bge_volume.commit()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        print(f"[BGEReranker] {RERANKER_MODEL} loaded on {device} ✓")

    @modal.fastapi_endpoint(method="POST")
    def rerank(self, payload: RerankRequest) -> RerankResponse:
        """
        Rerank candidates by cross-encoder relevance score.

        Input:  query + list of candidate dicts (each with at least "text").
        Output: candidates sorted by reranker_score descending, with scores.

        Scores are sigmoid-normalized logits so they lie in (0, 1) and are
        compatible with the existing reranker_score field on chunk dicts.
        """
        import math

        if not payload.candidates or len(payload.candidates) < 2:
            # Nothing to rerank — return as-is
            return RerankResponse(
                ranked=payload.candidates,
                scores=[1.0] * len(payload.candidates),
            )

        pairs = [(payload.query, c.get("text", "")) for c in payload.candidates]
        raw_scores = self.model.predict(pairs).tolist()

        # Sigmoid transform: logit → (0, 1)
        def sigmoid(x: float) -> float:
            return 1.0 / (1.0 + math.exp(-x))

        sig_scores = [sigmoid(s) for s in raw_scores]

        # Sort candidates by score descending
        sorted_pairs = sorted(
            zip(sig_scores, payload.candidates),
            key=lambda x: x[0],
            reverse=True,
        )

        top_k = payload.top_k
        ranked = []
        scores = []
        for score, candidate in sorted_pairs[:top_k]:
            c = dict(candidate)
            c["reranker_score"] = round(score, 6)
            ranked.append(c)
            scores.append(round(score, 6))

        return RerankResponse(ranked=ranked, scores=scores)
