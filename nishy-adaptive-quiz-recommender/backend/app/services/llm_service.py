"""
LLM Service — Qwen2.5-7B via Modal.com (primary) + sentence-transformers (embeddings).
Gemini dependency removed for quiz generation.
"""
import os
import json
import re
import time
import logging
import httpx
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MODAL_ENDPOINT_URL = os.getenv(
    "MODAL_ENDPOINT_URL",
    "https://your-workspace--qwen-adaptive-quiz-web-endpoint.modal.run"
)
MODAL_API_KEY = os.getenv("MODAL_API_KEY", "")  # optional if endpoint is public


class QwenModalService:
    """
    HTTP client for the Qwen2.5-7B Modal.com serverless endpoint.
    Handles retries, JSON extraction, and cold-start timeouts gracefully.
    """

    def __init__(self):
        self.endpoint = MODAL_ENDPOINT_URL.rstrip("/")
        headers = {"Content-Type": "application/json"}
        # Only add auth if key is set and not the placeholder value
        if MODAL_API_KEY and MODAL_API_KEY != "your-api-key":
            headers["Authorization"] = f"Bearer {MODAL_API_KEY}"
        # 90s timeout — covers cold start (~40s) + large prompt inference (~30s)
        self.client = httpx.Client(headers=headers, timeout=90.0)
        logger.info(f"QwenModalService initialized | endpoint={self.endpoint}")

    def check_health(self) -> bool:
        """Check if the Modal endpoint is reachable. Returns True if healthy."""
        try:
            resp = self.client.get(f"{self.endpoint}/health", timeout=10.0)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Modal health check failed: {e}")
            return False

    def call(self, prompt: str, temperature: float = 0.4, max_tokens: int = 1024) -> str:
        """Call the Modal Qwen endpoint. Returns raw text."""
        for attempt in range(2):  # 2 retries — fail faster if endpoint is down
            try:
                start = time.time()
                resp = self.client.post(
                    f"{self.endpoint}/generate",
                    json={"prompt": prompt, "temperature": temperature, "max_tokens": max_tokens},
                )
                resp.raise_for_status()
                elapsed = time.time() - start
                text = resp.json()["text"]
                logger.debug(f"Qwen response in {elapsed:.1f}s | len={len(text)}")
                return text
            except httpx.TimeoutException:
                logger.warning(f"Qwen timeout attempt {attempt + 1}/2 — retrying...")
                if attempt < 1:
                    time.sleep(2)
            except httpx.HTTPStatusError as e:
                logger.error(f"Qwen HTTP error: {e.response.status_code} — {e.response.text[:200]}")
                raise
            except httpx.ConnectError as e:
                logger.error(f"Qwen connection failed (is Modal deployed?): {e}")
                raise RuntimeError(
                    f"Cannot connect to Modal endpoint: {self.endpoint}. "
                    "Run: modal deploy modal_inference/qwen_endpoint.py"
                ) from e
        raise RuntimeError("Qwen endpoint failed after 2 retries")

    def call_json(self, prompt: str, temperature: float = 0.2) -> dict:
        """Call Qwen and parse JSON response. Strips markdown fences."""
        full_prompt = (
            prompt
            + "\n\nCRITICAL: Return ONLY valid JSON. No markdown, no code fences, no explanation."
        )
        raw = self.call(full_prompt, temperature=temperature, max_tokens=1200)
        return self._extract_json(raw)

    def _extract_json(self, text: str) -> dict:
        """Robustly extract JSON even from messy LLM output."""
        # Strategy 1: direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Strategy 2: strip markdown fences
        clean = re.sub(r"```(?:json)?\n?", "", text).strip().rstrip("`")
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Strategy 3: first { ... } block
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract JSON from Qwen output: {text[:300]}")


class EmbeddingService:
    """
    Local sentence-transformers embeddings — no API key, no cost, runs offline.
    Model: all-MiniLM-L6-v2 (384-dim, fast, good quality for RAG).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Lazy load — expensive import only when first used
        self._model = None
        self._model_name = model_name
        logger.info(f"EmbeddingService initialized (lazy) | model={model_name}")

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            logger.info(f"sentence-transformers model loaded: {self._model_name}")

    def get_embedding(self, text: str) -> list[float]:
        """Embed a single document chunk."""
        self._load()
        vec = self._model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def get_query_embedding(self, text: str) -> list[float]:
        """Embed a query (same model — MiniLM handles both well)."""
        return self.get_embedding(text)

    def get_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Batch encode for efficiency during ingestion."""
        self._load()
        vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        return [v.tolist() for v in vecs]


# ── Convenience aliases used by agents ────────────────────────────────────
# Agents import LlmService — we make it point to Qwen now
LlmService = QwenModalService
